from pathlib import Path
from config import MAX_VIDEO_SIZE

async def download_group_message(client, chat_id: int, message_id: int, destination: Path):
    message = await client.get_messages(chat_id, ids=message_id)
    if not message or not message.media:
        raise ValueError(f"Media message {message_id} was not found")
    size = getattr(message.file, "size", None)
    if size and size > MAX_VIDEO_SIZE:
        raise ValueError("File exceeds configured maximum size")
    result = await client.download_media(message, file=str(destination))
    if not result or not destination.exists():
        raise RuntimeError("Telegram media download failed")
    return destination
