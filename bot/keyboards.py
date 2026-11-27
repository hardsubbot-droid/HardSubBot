from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة الحساب المساعد", callback_data="assistant_login")],
        [InlineKeyboardButton("👤 حالة الحساب", callback_data="assistant_status")],
        [InlineKeyboardButton("🎬 طريقة الاستخدام", callback_data="help")],
        [InlineKeyboardButton("📋 قائمة المهام", callback_data="tasks")]
    ])

def task_keyboard(task_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ بدء الدمج", callback_data=f"merge:{task_id}")],
        [InlineKeyboardButton("❌ إلغاء المهمة", callback_data=f"cancel:{task_id}")]
    ])

def cancel_login_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("إلغاء تسجيل الدخول", callback_data="login_cancel")]])
