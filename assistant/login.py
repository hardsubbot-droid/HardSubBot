from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from config import API_ID, API_HASH, SESSION_PATH

class LoginFlow:
    def __init__(self):
        if not API_ID or not API_HASH:
            raise RuntimeError("API_ID/API_HASH are not configured")
        self.client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
        self.state = "phone"
        self.phone = None
        self.phone_code_hash = None

    async def begin(self, phone):
        if not phone.startswith("+") or not phone[1:].isdigit():
            raise ValueError("Phone must be in international format")
        self.phone = phone
        await self.client.connect()
        sent = await self.client.send_code_request(phone)
        self.phone_code_hash = sent.phone_code_hash
        self.state = "code"

    async def submit_code(self, code):
        try:
            await self.client.sign_in(
                phone=self.phone,
                code=code,
                phone_code_hash=self.phone_code_hash
            )
            self.state = "done"
            return "done"
        except SessionPasswordNeededError:
            self.state = "password"
            return "password"

    async def submit_password(self, password):
        await self.client.sign_in(password=password)
        self.state = "done"

    async def cancel(self):
        try:
            if self.client.is_connected():
                await self.client.disconnect()
        except Exception:
            pass
