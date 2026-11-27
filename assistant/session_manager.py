import logging
from telethon import TelegramClient
from config import API_ID, API_HASH, SESSION_PATH

log = logging.getLogger(__name__)

class AssistantSession:
    def __init__(self):
        self.client = None

    async def connect_if_authorized(self):
        if not API_ID or not API_HASH:
            return False
        client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
        try:
            await client.connect()
            if await client.is_user_authorized():
                self.client = client
                log.info("Assistant account session connected")
                return True
            await client.disconnect()
            return False
        except Exception:
            log.exception("Assistant session connection failed")
            try:
                await client.disconnect()
            except Exception:
                pass
            return False

    async def adopt_client(self, client):
        if self.client and self.client is not client:
            await self.disconnect()
        self.client = client

    async def status(self):
        if not self.client:
            return "الحساب المساعد غير متصل. أضفه من الخاص باستخدام زر إضافة الحساب."
        try:
            me = await self.client.get_me()
            return f"الحساب المساعد متصل: @{me.username or 'بدون اسم مستخدم'}"
        except Exception:
            return "جلسة الحساب المساعد غير صالحة أو غير متصلة."

    async def disconnect(self):
        if self.client:
            try:
                await self.client.disconnect()
            finally:
                self.client = None

    async def require_client(self):
        if not self.client or not self.client.is_connected():
            raise RuntimeError("Assistant account is not connected")
        if not await self.client.is_user_authorized():
            raise RuntimeError("Assistant account session is not authorized")
        return self.client
