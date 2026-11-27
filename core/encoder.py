import asyncio
import json
from pathlib import Path
from config import VIDEO_PRESET, VIDEO_CRF, SUBTITLE_FONT, SUBTITLE_SIZE, SUBTITLE_MARGIN

def escape_subtitle_path(path: Path) -> str:
    value = str(path.resolve())
    value = value.replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'")
    value = value.replace(",", r"\,").replace("[", r"\[").replace("]", r"\]")
    return value

async def probe_duration(video: Path) -> float:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(video),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode(errors="replace")[-1500:])
    return float(json.loads(stdout.decode())["format"]["duration"])

async def hardcode(video: Path, subtitle: Path, output: Path, on_progress, cancel_event):
    duration = await probe_duration(video)
    style = (
        f"FontName={SUBTITLE_FONT},FontSize={SUBTITLE_SIZE},"
        f"Outline=2,Shadow=1,MarginV={SUBTITLE_MARGIN},Alignment=2"
    )
    vf = f"subtitles='{escape_subtitle_path(subtitle)}':force_style='{style}'"
    cmd = [
        "ffmpeg", "-y", "-i", str(video),
        "-vf", vf, "-c:v", "libx264", "-preset", VIDEO_PRESET,
        "-crf", str(VIDEO_CRF), "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", "-progress", "pipe:1", "-nostats",
        str(output)
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    async def read_stderr():
        chunks = []
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            chunks.append(line.decode(errors="replace"))
            if len(chunks) > 100:
                chunks.pop(0)
        return "".join(chunks)

    stderr_task = asyncio.create_task(read_stderr())
    try:
        while True:
            if cancel_event.is_set():
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=8)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                raise asyncio.CancelledError()
            line = await proc.stdout.readline()
            if not line:
                break
            decoded = line.decode(errors="replace").strip()
            if decoded.startswith("out_time_ms="):
                try:
                    elapsed = int(decoded.split("=", 1)[1]) / 1_000_000
                    percent = min(99.0, elapsed / duration * 100) if duration else 0
                    await on_progress(percent)
                except (ValueError, ZeroDivisionError):
                    pass
        code = await proc.wait()
        stderr = await stderr_task
        if code != 0:
            raise RuntimeError(stderr[-2500:] or f"FFmpeg exited with code {code}")
        await on_progress(100.0)
        if not output.exists() or output.stat().st_size == 0:
            raise RuntimeError("FFmpeg produced no output")
        return output
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
        if not stderr_task.done():
            stderr_task.cancel()
