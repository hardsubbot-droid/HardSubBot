import asyncio
import logging
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from config import DOWNLOAD_DIR, OUTPUT_DIR, TEMP_DIR
from core.downloader import download_group_message
from core.subtitle import normalize_srt
from core.encoder import hardcode
from core.progress import progress_bar

log = logging.getLogger(__name__)

@dataclass
class Job:
    task_id: str
    chat_id: int
    user_id: int
    video_message_id: int
    subtitle_message_id: int
    video_name: str
    status: str = "Waiting"
    percent: float = 0.0
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    progress_message_id: int = 0

class TaskManager:
    def __init__(self, application):
        self.application = application
        self.jobs = {}
        self.queue = asyncio.Queue()
        self.workers = []
        self.active = set()

    async def start(self):
        from config import MAX_CONCURRENT_JOBS
        self.workers = [
            asyncio.create_task(self.worker(), name=f"job-worker-{i}")
            for i in range(MAX_CONCURRENT_JOBS)
        ]

    async def stop(self):
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)

    async def create_task(self, **kwargs):
        task_id = secrets.token_hex(4)
        job = Job(task_id=task_id, **kwargs)
        self.jobs[task_id] = job
        return job

    async def enqueue(self, task_id, user_id):
        job = self.jobs.get(task_id)
        if not job:
            return "المهمة غير موجودة."
        if job.user_id != user_id:
            return "غير مصرح لك ببدء هذه المهمة."
        if job.status != "Waiting":
            return "هذه المهمة بدأت بالفعل أو انتهت."
        job.status = "Queued"
        await self.queue.put(task_id)
        return "تمت إضافة المهمة إلى قائمة الانتظار."

    async def cancel(self, task_id, user_id, is_owner=False):
        job = self.jobs.get(task_id)
        if not job:
            return "المهمة غير موجودة."
        if job.user_id != user_id and not is_owner:
            return "غير مصرح لك بإلغاء هذه المهمة."
        if job.status in ("Completed", "Failed", "Cancelled"):
            return "المهمة منتهية بالفعل."
        job.cancel_event.set()
        if job.status in ("Waiting", "Queued"):
            job.status = "Cancelled"
        return "تم إرسال طلب إلغاء المهمة."

    async def list_for_user(self, user_id):
        rows = [
            f"{j.task_id}: {j.status} ({j.percent:.1f}%)"
            for j in self.jobs.values() if j.user_id == user_id
        ]
        return "\n".join(rows[-15:]) or "لا توجد مهام."

    async def notify(self, job, text, markup=None):
        try:
            if job.progress_message_id:
                await self.application.bot.edit_message_text(
                    chat_id=job.chat_id, message_id=job.progress_message_id,
                    text=text, reply_markup=markup
                )
            else:
                msg = await self.application.bot.send_message(
                    chat_id=job.chat_id, text=text, reply_markup=markup
                )
                job.progress_message_id = msg.message_id
        except Exception:
            log.exception("Could not update task message")

    async def worker(self):
        while True:
            task_id = await self.queue.get()
            job = self.jobs.get(task_id)
            if not job or job.status == "Cancelled":
                self.queue.task_done()
                continue
            try:
                await self.process(job)
            except asyncio.CancelledError:
                job.status = "Cancelled"
                await self.notify(job, f"⛔ تم إلغاء المهمة {task_id}")
                # Keep the worker alive when a user cancels a job.
                # Only propagate cancellation when the worker itself is shutting down.
                if asyncio.current_task() and asyncio.current_task().cancelling():
                    raise
            except Exception as exc:
                job.status = "Failed"
                log.exception("Task %s failed", task_id)
                await self.notify(job, f"❌ فشلت المهمة {task_id}\n{type(exc).__name__}: {str(exc)[:500]}")
            finally:
                self.active.discard(task_id)
                self.queue.task_done()

    async def process(self, job):
        from config import TEMP_DIR, DOWNLOAD_DIR, OUTPUT_DIR
        assistant = self.application.bot_data["assistant"]
        client = await assistant.require_client()
        safe_id = job.task_id
        video = Path(DOWNLOAD_DIR) / f"{safe_id}_video"
        srt_raw = Path(DOWNLOAD_DIR) / f"{safe_id}_subtitle.srt"
        srt_clean = Path(TEMP_DIR) / f"{safe_id}_subtitle.srt"
        output = Path(OUTPUT_DIR) / f"{safe_id}_hardsub.mp4"
        paths = [video, srt_raw, srt_clean, output]

        try:
            job.status = "Downloading"
            await self.notify(job, f"⬇️ جاري تنزيل ملفات المهمة {safe_id}...")
            await download_group_message(client, job.chat_id, job.video_message_id, video)
            await download_group_message(client, job.chat_id, job.subtitle_message_id, srt_raw)

            job.status = "Validating"
            normalize_srt(srt_raw, srt_clean)

            async def update_progress(percent):
                job.percent = percent
                job.status = "Encoding"
                await self.notify(
                    job,
                    f"🎬 جاري دمج الترجمة\nالمهمة: {safe_id}\n{progress_bar(percent)}"
                )

            job.status = "Encoding"
            await hardcode(video, srt_clean, output, update_progress, job.cancel_event)
            if job.cancel_event.is_set():
                raise asyncio.CancelledError()

            job.status = "Uploading"
            await self.notify(job, f"⬆️ اكتمل الدمج، جاري رفع الناتج للمهمة {safe_id}...")
            await client.send_file(
                job.chat_id, str(output),
                caption=f"✅ اكتملت الترجمة الصلبة\nالمهمة: {safe_id}",
                force_document=False
            )
            job.status = "Completed"
            await self.notify(job, f"✅ اكتملت المهمة {safe_id}")
        except asyncio.CancelledError:
            job.status = "Cancelled"
            await self.notify(job, f"⛔ تم إلغاء المهمة {safe_id}")
            raise
        finally:
            for path in paths:
                try:
                    if path.exists():
                        path.unlink()
                except OSError:
                    log.warning("Could not remove temporary file %s", path)
