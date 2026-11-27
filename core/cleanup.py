import asyncio
import logging
import time
from config import DOWNLOAD_DIR, OUTPUT_DIR, TEMP_DIR

log = logging.getLogger(__name__)

async def cleanup_loop():
    while True:
        try:
            cutoff = time.time() - 24 * 60 * 60
            for directory in (DOWNLOAD_DIR, OUTPUT_DIR, TEMP_DIR):
                for path in directory.iterdir():
                    if path.is_file() and path.stat().st_mtime < cutoff:
                        try:
                            path.unlink()
                        except OSError:
                            log.warning("Could not clean %s", path)
        except Exception:
            log.exception("Cleanup cycle failed")
        await asyncio.sleep(3600)
