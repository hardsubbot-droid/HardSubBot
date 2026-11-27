import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from config import OWNER_ID, GROUP_ID, MAX_VIDEO_SIZE
from bot.keyboards import main_menu, task_keyboard, cancel_login_keyboard
from assistant.login import LoginFlow
from core.subtitle import validate_srt_file

log = logging.getLogger(__name__)
login_flows = {}
pending_media = {}

def authorized_group(chat_id):
    return GROUP_ID == 0 or chat_id == GROUP_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.effective_message.reply_text("هذا البوت خاص.")
        return
    await update.effective_message.reply_text(
        "مرحبًا بك في HardSubBot.\nأرسل الفيديو ثم ملف SRT داخل مجموعة العمل.",
        reply_markup=main_menu()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "طريقة الاستخدام:\n1) أرسل الفيديو إلى مجموعة العمل.\n2) أرسل ملف SRT.\n3) اضغط بدء الدمج.\n\n"
        "يجب أن يكون الحساب المساعد عضوًا في المجموعة، وأن يكون البوت قادرًا على قراءة الرسائل."
    )

async def on_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not authorized_group(message.chat_id):
        return
    user_id = update.effective_user.id if update.effective_user else 0
    if message.video or (message.document and (message.document.mime_type or "").startswith("video/")):
        media = message.video or message.document
        if media.file_size and media.file_size > MAX_VIDEO_SIZE:
            await message.reply_text("حجم الفيديو يتجاوز الحد المحدد في إعدادات البوت.")
            return
        pending_media[(message.chat_id, user_id)] = {
            "video_message_id": message.message_id,
            "video_name": getattr(media, "file_name", None) or "video",
            "video_size": media.file_size or 0
        }
        await message.reply_text("تم استلام الفيديو. أرسل ملف الترجمة SRT الآن.")
        return

    if message.document and (message.document.file_name or "").lower().endswith(".srt"):
        key = (message.chat_id, user_id)
        pending = pending_media.get(key)
        if not pending:
            await message.reply_text("أرسل الفيديو أولًا، ثم ملف SRT.")
            return
        task_manager = context.application.bot_data["task_manager"]
        task = await task_manager.create_task(
            chat_id=message.chat_id,
            user_id=user_id,
            video_message_id=pending["video_message_id"],
            subtitle_message_id=message.message_id,
            video_name=pending["video_name"]
        )
        pending_media.pop(key, None)
        await message.reply_text(
            f"تم تجهيز المهمة `{task.task_id}`.\nاضغط لبدء الدمج.",
            reply_markup=task_keyboard(task.task_id),
            parse_mode="Markdown"
        )

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data or ""

    if data == "help":
        await query.message.reply_text("أرسل الفيديو ثم SRT في مجموعة العمل.")
        return
    if data == "assistant_login":
        if user_id != OWNER_ID:
            await query.message.reply_text("غير مصرح.")
            return
        login_flows[user_id] = LoginFlow()
        await query.message.reply_text(
            "أرسل رقم الهاتف مع مفتاح الدولة، مثال: +967XXXXXXXXX",
            reply_markup=cancel_login_keyboard()
        )
        return
    if data == "login_cancel":
        flow = login_flows.pop(user_id, None)
        if flow:
            await flow.cancel()
        await query.message.reply_text("تم إلغاء عملية تسجيل الدخول.")
        return
    if data == "assistant_status":
        assistant = context.application.bot_data["assistant"]
        status = await assistant.status()
        await query.message.reply_text(status)
        return
    if data == "tasks":
        manager = context.application.bot_data["task_manager"]
        await query.message.reply_text(await manager.list_for_user(user_id))
        return
    if data.startswith("merge:"):
        task_id = data.split(":", 1)[1]
        manager = context.application.bot_data["task_manager"]
        result = await manager.enqueue(task_id, user_id)
        await query.message.reply_text(result)
        return
    if data.startswith("cancel:"):
        task_id = data.split(":", 1)[1]
        manager = context.application.bot_data["task_manager"]
        result = await manager.cancel(task_id, user_id, is_owner=(user_id == OWNER_ID))
        await query.message.reply_text(result)
        return

async def private_login_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or user.id != OWNER_ID:
        return
    flow = login_flows.get(user.id)
    if not flow:
        return
    text = (update.effective_message.text or "").strip()
    assistant = context.application.bot_data["assistant"]
    try:
        if flow.state == "phone":
            await flow.begin(text)
            await update.effective_message.reply_text("أرسل رمز تسجيل الدخول الذي وصلك من Telegram.")
        elif flow.state == "code":
            result = await flow.submit_code(text)
            if result == "password":
                await update.effective_message.reply_text("الحساب محمي بالتحقق بخطوتين. أرسل كلمة المرور.")
            else:
                await assistant.adopt_client(flow.client)
                login_flows.pop(user.id, None)
                await update.effective_message.reply_text("✅ تم تسجيل الحساب المساعد بنجاح.")
        elif flow.state == "password":
            await flow.submit_password(text)
            await assistant.adopt_client(flow.client)
            login_flows.pop(user.id, None)
            await update.effective_message.reply_text("✅ تم تسجيل الحساب المساعد بنجاح.")
    except Exception as exc:
        log.warning("Assistant login failed: %s", type(exc).__name__)
        await update.effective_message.reply_text("تعذر إكمال تسجيل الدخول. تحقق من الرمز أو أعد المحاولة.")

def register_handlers(application: Application):
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(callbacks))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, private_login_text))
    media_filter = filters.VIDEO | filters.Document.ALL
    application.add_handler(MessageHandler(media_filter, on_media))
