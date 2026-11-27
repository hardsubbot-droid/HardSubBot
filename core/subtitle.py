from pathlib import Path
import re

TIMESTAMP = re.compile(
    r"^\s*\d{2}:\d{2}:\d{2}[,.]\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}[,.]\d{3}"
)

def normalize_srt(source: Path, destination: Path):
    raw = source.read_bytes()
    text = None
    for encoding in ("utf-8-sig", "utf-8", "cp1256", "windows-1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("تعذر تحديد ترميز ملف الترجمة")
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if "-->" not in text:
        raise ValueError("ملف SRT لا يحتوي على توقيتات صحيحة")
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    valid = 0
    for block in blocks:
        lines = block.splitlines()
        if any(TIMESTAMP.match(line) for line in lines):
            valid += 1
    if valid == 0:
        raise ValueError("لم يتم العثور على مقاطع ترجمة بتوقيتات SRT")
    destination.write_text(text + "\n", encoding="utf-8-sig")
    return valid
