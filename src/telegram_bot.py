import logging
import re
import os
import asyncio
from datetime import datetime
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardRemove
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

from src.config import TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, TEMP_DIR
from src.database import (
    AVAILABLE_TOPICS,
    AVAILABLE_VOICES,
    get_user,
    create_or_update_user,
    get_user_topics,
    set_user_topics,
    init_db
)
from src.collector import collect_news_by_topics
from src.generator import init_gemini, generate_podcast_content, text_to_speech

# Thiết lập Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Các trạng thái cho cuộc hội thoại Onboarding (Thiết lập ban đầu)
(
    ONBOARDING_TOPICS,
    ONBOARDING_VOICE,
    ONBOARDING_TIME,
    ONBOARDING_CUSTOM_TIME
) = range(4)

# ----------------- Helper Functions -----------------

def get_topics_keyboard(user_id: int, is_settings: bool = False) -> InlineKeyboardMarkup:
    """Tạo bàn phím inline hiển thị các chủ đề có tích chọn ✅."""
    selected_topics = get_user_topics(user_id)
    keyboard = []
    
    for code, name in AVAILABLE_TOPICS.items():
        checkmark = "✅ " if code in selected_topics else "❌ "
        button_text = f"{checkmark}{name}"
        callback_data = f"settings_toggle_{code}" if is_settings else f"onboarding_toggle_{code}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
    # Thêm nút xác nhận/tiếp theo ở cuối
    if is_settings:
        keyboard.append([InlineKeyboardButton("🔙 Quay lại cài đặt", callback_data="settings_main")])
    else:
        keyboard.append([InlineKeyboardButton("Tiếp theo ➡️", callback_data="onboarding_next_topics")])
        
    return InlineKeyboardMarkup(keyboard)

def get_voices_keyboard(user_id: int, is_settings: bool = False) -> InlineKeyboardMarkup:
    """Tạo bàn phím inline chọn giọng nói."""
    user = get_user(user_id)
    current_voice = user.get("voice") if user else None
    keyboard = []
    
    for code, name in AVAILABLE_VOICES.items():
        checkmark = "⭐ " if code == current_voice else ""
        button_text = f"{checkmark}{name}"
        callback_data = f"settings_setvoice_{code}" if is_settings else f"onboarding_setvoice_{code}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
    if is_settings:
        keyboard.append([InlineKeyboardButton("🔙 Quay lại cài đặt", callback_data="settings_main")])
        
    return InlineKeyboardMarkup(keyboard)

def get_time_keyboard(is_settings: bool = False) -> InlineKeyboardMarkup:
    """Tạo bàn phím inline chọn giờ gửi tin."""
    prefix = "settings_settime_" if is_settings else "onboarding_settime_"
    keyboard = [
        [
            InlineKeyboardButton("06:00", callback_data=f"{prefix}06:00"),
            InlineKeyboardButton("06:30", callback_data=f"{prefix}06:30"),
        ],
        [
            InlineKeyboardButton("07:00", callback_data=f"{prefix}07:00"),
            InlineKeyboardButton("07:30", callback_data=f"{prefix}07:30"),
        ],
        [
            InlineKeyboardButton("08:00", callback_data=f"{prefix}08:00"),
            InlineKeyboardButton("08:30", callback_data=f"{prefix}08:30"),
        ],
        [
            InlineKeyboardButton("⌨️ Tự nhập giờ", callback_data=f"settings_custom_time" if is_settings else "onboarding_custom_time")
        ]
    ]
    if is_settings:
        keyboard.append([InlineKeyboardButton("🔙 Quay lại cài đặt", callback_data="settings_main")])
        
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Bàn phím chính của menu cài đặt /settings."""
    keyboard = [
        [InlineKeyboardButton("📁 Thay đổi chủ đề quan tâm", callback_data="settings_menu_topics")],
        [InlineKeyboardButton("🗣️ Thay đổi giọng đọc podcast", callback_data="settings_menu_voice")],
        [InlineKeyboardButton("⏰ Thay đổi giờ nhận tin hàng ngày", callback_data="settings_menu_time")],
        [InlineKeyboardButton("❌ Đóng cài đặt", callback_data="settings_close")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def generate_and_send_podcast(
    user_id: int, 
    context: ContextTypes.DEFAULT_TYPE, 
    username: str
) -> bool:
    """
    Quy trình cốt lõi: Thu thập tin tức -> Gọi Gemini tạo kịch bản -> TTS -> Gửi qua Telegram.
    Hàm này được dùng cho cả lệnh chạy ngay (/podcast) lẫn Scheduler gửi tự động.
    """
    bot = context.bot if hasattr(context, "bot") else context
    user = get_user(user_id)
    if not user:
        return False
        
    topics = get_user_topics(user_id)
    if not topics:
        await bot.send_message(
            chat_id=user_id,
            text="Bạn chưa chọn chủ đề quan tâm nào. Hãy dùng lệnh /settings để cấu hình chủ đề nhé!"
        )
        return False

    status_msg = await bot.send_message(
        chat_id=user_id,
        text="🔄 <b>Đang chuẩn bị...</b>\n1. 🔎 Thu thập tin tức theo chủ đề..."
    )
    
    try:
        # 1. Thu thập tin tức
        news_data = collect_news_by_topics(topics, hours_limit=24)
        
        # Cập nhật trạng thái
        await status_msg.edit_text(
            "🔄 <b>Đang biên tập...</b>\n1. ✅ Thu thập tin tức xong.\n2. 🤖 Gemini đang soạn kịch bản podcast..."
        )
        
        # 2. Tạo kịch bản và tóm tắt HTML qua Gemini
        script, summary_text = await generate_podcast_content(news_data, username)
        
        # Cập nhật trạng thái
        await status_msg.edit_text(
            "🔄 <b>Đang tạo âm thanh...</b>\n1. ✅ Thu thập tin tức xong.\n2. ✅ Soạn kịch bản xong.\n3. 🗣️ Đang chuyển đổi giọng đọc nói..."
        )
        
        # 3. Tạo file âm thanh MP3
        output_file = os.path.join(TEMP_DIR, f"podcast_{user_id}_{int(datetime.now().timestamp())}.mp3")
        voice = user.get("voice", "vi-VN-HoaiMyNeural")
        
        success_tts = await text_to_speech(script, voice, output_file)
        if not success_tts:
            await status_msg.edit_text("❌ Lỗi xảy ra trong quá trình tạo giọng đọc. Vui lòng thử lại sau.")
            return False
            
        # Cập nhật trạng thái
        await status_msg.edit_text(
            "🔄 <b>Đang gửi...</b>\n1. ✅ Thu thập tin tức xong.\n2. ✅ Soạn kịch bản xong.\n3. ✅ Tạo file âm thanh xong.\n4. 🚀 Đang gửi podcast qua Telegram..."
        )
        
        # 4. Gửi file audio kèm tóm tắt nội dung
        voice_name_display = AVAILABLE_VOICES.get(voice, voice)
        date_str = datetime.now().strftime("%d/%m/%Y")
        
        caption_intro = f"🎙️ <b>Bản tin Podcast cá nhân hóa ngày {date_str}</b>\n🗣️ Giọng đọc: {voice_name_display}\n\n"
        full_caption = caption_intro + summary_text
        
        # Nếu caption quá dài (Telegram giới hạn caption audio 1024 ký tự),
        # ta sẽ gửi caption ngắn hơn và gửi tóm tắt đầy đủ ở tin nhắn riêng.
        if len(full_caption) > 1020:
            await bot.send_audio(
                chat_id=user_id,
                audio=open(output_file, 'rb'),
                caption=caption_intro + "<i>Chi tiết tóm tắt tin tức được gửi trong tin nhắn tiếp theo!</i>",
                parse_mode="HTML"
            )
            await bot.send_message(
                chat_id=user_id,
                text=summary_text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        else:
            await bot.send_audio(
                chat_id=user_id,
                audio=open(output_file, 'rb'),
                caption=full_caption,
                parse_mode="HTML"
            )
            
        # Xóa tin nhắn trạng thái
        await status_msg.delete()
        
        # Cập nhật ngày gửi cuối cùng để tránh Scheduler gửi lặp
        today_str = datetime.now().strftime("%Y-%m-%d")
        create_or_update_user(user_id, last_sent_date=today_str)
        
        # Xóa file audio tạm thời
        if os.path.exists(output_file):
            os.remove(output_file)
            
        return True
        
    except Exception as e:
        logger.error(f"Lỗi quy trình tạo/gửi podcast cho user {user_id}: {e}", exc_info=True)
        try:
            await status_msg.edit_text("❌ Có lỗi xảy ra trong quá trình xử lý bản tin. Vui lòng thử lại sau.")
        except Exception:
            await bot.send_message(chat_id=user_id, text="❌ Có lỗi xảy ra trong quá trình xử lý bản tin.")
        return False

# ----------------- Telegram Commands & Onboarding Flow -----------------

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Khởi động bot và bắt đầu luồng Onboarding cài đặt."""
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "bạn"
    
    user = get_user(user_id)
    # Nếu người dùng đã cài đặt xong xuôi rồi, không chạy lại onboarding
    if user and user.get("is_onboarding_completed") == 1:
        await update.message.reply_text(
            f"Chào mừng trở lại, {username}! Bạn đã hoàn thành thiết lập nhận tin trước đó rồi.\n\n"
            f"• Lệnh /podcast để nghe bản tin tổng hợp ngay bây giờ.\n"
            f"• Lệnh /settings để tùy chỉnh lại chủ đề, giọng nói, giờ hẹn nhận tin."
        )
        return ConversationHandler.END

    # Tạo mới hoặc reset user
    create_or_update_user(user_id, username=username, is_onboarding_completed=0)
    # Đặt mặc định chọn 3 chủ đề đầu tiên để người dùng dễ tiếp cận
    set_user_topics(user_id, ["ai", "tech", "world"])
    
    await update.message.reply_text(
        f"Chào mừng {username} đến với <b>AI Daily Podcast Agent</b>! 🎙️🤖\n\n"
        f"Tôi là trợ lý ảo sẽ thu thập tin nóng hàng ngày và đọc dạng Podcast riêng cho bạn.\n\n"
        f"Hãy hoàn thành <b>3 bước thiết lập nhanh</b> sau để bắt đầu nhé!\n\n"
        f"👉 <b>Bước 1:</b> Chọn các chủ đề bạn quan tâm dưới đây (nhấn để Tích chọn ✅ hoặc Bỏ chọn ❌, sau đó nhấn nút <b>Tiếp theo ➡️</b>):",
        reply_markup=get_topics_keyboard(user_id, is_settings=False),
        parse_mode="HTML"
    )
    return ONBOARDING_TOPICS

async def onboarding_toggle_topic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xử lý bật/tắt chủ đề trong quá trình Onboarding."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    topic_code = query.data.split("_")[-1]
    
    # Toggle chủ đề
    current_topics = get_user_topics(user_id)
    if topic_code in current_topics:
        current_topics.remove(topic_code)
    else:
        current_topics.append(topic_code)
        
    set_user_topics(user_id, current_topics)
    
    # Cập nhật lại giao diện nút bấm
    await query.edit_message_reply_markup(
        reply_markup=get_topics_keyboard(user_id, is_settings=False)
    )
    return ONBOARDING_TOPICS

async def onboarding_next_topics_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xác nhận chủ đề đã chọn và chuyển sang Bước 2: Chọn giọng đọc."""
    query = update.callback_query
    user_id = query.from_user.id
    
    selected_topics = get_user_topics(user_id)
    if not selected_topics:
        await query.answer("Vui lòng chọn ít nhất 1 chủ đề quan tâm!", show_alert=True)
        return ONBOARDING_TOPICS
        
    await query.answer()
    await query.edit_message_text(
        text="👉 <b>Bước 2:</b> Hãy chọn giọng đọc podcast mà bạn thích nhất dưới đây:",
        reply_markup=get_voices_keyboard(user_id, is_settings=False),
        parse_mode="HTML"
    )
    return ONBOARDING_VOICE

async def onboarding_setvoice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lưu giọng nói và chuyển sang Bước 3: Chọn giờ gửi tin."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    voice_code = query.data.replace("onboarding_setvoice_", "")
    
    create_or_update_user(user_id, voice=voice_code)
    
    await query.edit_message_text(
        text="👉 <b>Bước 3:</b> Chọn giờ bạn muốn nhận tin podcast tự động mỗi sáng:",
        reply_markup=get_time_keyboard(is_settings=False),
        parse_mode="HTML"
    )
    return ONBOARDING_TIME

async def onboarding_settime_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lưu giờ gửi tin (preset) và hoàn thành Onboarding."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    username = query.from_user.first_name or "bạn"
    time_str = query.data.replace("onboarding_settime_", "")
    
    # Lưu giờ hẹn và đánh dấu hoàn thành thiết lập
    create_or_update_user(user_id, schedule_time=time_str, is_onboarding_completed=1)
    
    user_data = get_user(user_id)
    voice_name = AVAILABLE_VOICES.get(user_data['voice'])
    topics_list = ", ".join([AVAILABLE_TOPICS[t] for t in get_user_topics(user_id)])
    
    await query.edit_message_text(
        text=f"🎉 <b>Thiết lập thành công!</b>\n\n"
             f"• ⏰ Giờ nhận tin: <b>{time_str}</b> hàng ngày\n"
             f"• 🗣️ Giọng đọc: <b>{voice_name}</b>\n"
             f"• 📁 Chủ đề quan tâm: <i>{topics_list}</i>\n\n"
             f"Bây giờ bot sẽ tiến hành tổng hợp bản tin podcast nghe thử đầu tiên cho bạn. Vui lòng đợi trong giây lát... 🎙️",
        parse_mode="HTML"
    )
    
    # Chạy quy trình tạo podcast nghe thử ngay lập tức
    asyncio.create_task(generate_and_send_podcast(user_id, context, username))
    
    return ConversationHandler.END

async def onboarding_custom_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Yêu cầu nhập giờ tùy chỉnh bằng bàn phím text."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text="Vui lòng nhập giờ gửi bạn muốn nhận bằng cách nhắn tin văn bản theo định dạng <b>HH:MM</b> (24 giờ, ví dụ: <code>07:15</code> hoặc <code>08:45</code>):",
        parse_mode="HTML"
    )
    return ONBOARDING_CUSTOM_TIME

async def onboarding_custom_time_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xử lý và validate chuỗi giờ tự nhập trong Onboarding."""
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "bạn"
    time_text = update.message.text.strip()
    
    # Kiểm tra định dạng HH:MM
    if not re.match(r"^(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$", time_text):
        await update.message.reply_text(
            "⚠️ Giờ nhập không hợp lệ. Vui lòng nhắn tin lại theo định dạng đúng là <b>HH:MM</b> (Ví dụ: <code>07:45</code>):",
            parse_mode="HTML"
        )
        return ONBOARDING_CUSTOM_TIME
        
    # Lưu giờ hẹn và kết thúc
    create_or_update_user(user_id, schedule_time=time_text, is_onboarding_completed=1)
    
    user_data = get_user(user_id)
    voice_name = AVAILABLE_VOICES.get(user_data['voice'])
    topics_list = ", ".join([AVAILABLE_TOPICS[t] for t in get_user_topics(user_id)])
    
    await update.message.reply_text(
        text=f"🎉 <b>Thiết lập thành công!</b>\n\n"
             f"• ⏰ Giờ nhận tin: <b>{time_text}</b> hàng ngày\n"
             f"• 🗣️ Giọng đọc: <b>{voice_name}</b>\n"
             f"• 📁 Chủ đề quan tâm: <i>{topics_list}</i>\n\n"
             f"Bây giờ bot sẽ tiến hành tổng hợp bản tin podcast nghe thử đầu tiên cho bạn. Vui lòng đợi trong giây lát... 🎙️",
        parse_mode="HTML"
    )
    
    # Chạy quy trình tạo podcast nghe thử
    asyncio.create_task(generate_and_send_podcast(user_id, context, username))
    
    return ConversationHandler.END

async def cancel_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Hủy luồng onboarding khi có lệnh hủy hoặc start lại."""
    await update.message.reply_text(
        "Đã hủy luồng thiết lập ban đầu. Bạn có thể gõ /start để cấu hình lại bất cứ lúc nào.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# ----------------- /podcast (Run Now) Command -----------------

async def run_podcast_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh tạo podcast ngay lập tức."""
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "bạn"
    
    user = get_user(user_id)
    if not user or user.get("is_onboarding_completed") == 0:
        await update.message.reply_text(
            "Bạn chưa hoàn thành các bước thiết lập. Vui lòng gõ lệnh /start để bắt đầu cấu hình."
        )
        return
        
    # Chạy quy trình tạo và gửi podcast
    await generate_and_send_podcast(user_id, context, username)

# ----------------- /settings (Menu) Command -----------------

async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mở menu cài đặt cấu hình."""
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user or user.get("is_onboarding_completed") == 0:
        await update.message.reply_text(
            "Bạn chưa cấu hình bot. Hãy gõ /start để thiết lập ban đầu."
        )
        return
        
    await update.message.reply_text(
        "⚙️ <b>CÀI ĐẶT AI DAILY PODCAST AGENT</b>\n\n"
        "Chọn một trong các mục bên dưới để tùy chỉnh cấu hình của bạn:",
        reply_markup=get_settings_keyboard(),
        parse_mode="HTML"
    )

async def settings_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý các sự kiện click nút bấm trong menu cài đặt (/settings)."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    action = query.data
    
    if action == "settings_main":
        await query.edit_message_text(
            text="⚙️ <b>CÀI ĐẶT AI DAILY PODCAST AGENT</b>\n\n"
                 "Chọn một trong các mục bên dưới để tùy chỉnh cấu hình của bạn:",
            reply_markup=get_settings_keyboard(),
            parse_mode="HTML"
        )
        
    elif action == "settings_menu_topics":
        await query.edit_message_text(
            text="📁 <b>Tùy chỉnh chủ đề quan tâm:</b>\n"
                 "Bấm vào nút để bật/tắt các chủ đề bạn muốn. Sau khi chọn xong bấm 🔙 Quay lại để lưu cấu hình.",
            reply_markup=get_topics_keyboard(user_id, is_settings=True),
            parse_mode="HTML"
        )
        
    elif action.startswith("settings_toggle_"):
        topic_code = action.replace("settings_toggle_", "")
        current_topics = get_user_topics(user_id)
        if topic_code in current_topics:
            current_topics.remove(topic_code)
        else:
            current_topics.append(topic_code)
        set_user_topics(user_id, current_topics)
        # Re-render menu
        await query.edit_message_reply_markup(
            reply_markup=get_topics_keyboard(user_id, is_settings=True)
        )
        
    elif action == "settings_menu_voice":
        await query.edit_message_text(
            text="🗣️ <b>Tùy chỉnh giọng đọc podcast:</b>\n"
                 "Chọn giọng nói bạn ưa thích từ danh sách dưới đây:",
            reply_markup=get_voices_keyboard(user_id, is_settings=True),
            parse_mode="HTML"
        )
        
    elif action.startswith("settings_setvoice_"):
        voice_code = action.replace("settings_setvoice_", "")
        create_or_update_user(user_id, voice=voice_code)
        # Quay về menu chính
        user_data = get_user(user_id)
        await query.edit_message_text(
            text=f"✅ Đã cập nhật giọng đọc thành công!\n👉 Giọng hiện tại: <b>{AVAILABLE_VOICES[voice_code]}</b>",
            reply_markup=get_settings_keyboard(),
            parse_mode="HTML"
        )
        
    elif action == "settings_menu_time":
        await query.edit_message_text(
            text="⏰ <b>Cấu hình giờ nhận podcast hàng ngày:</b>\n"
                 "Chọn một khung giờ sẵn có hoặc bấm nút nhập thủ công:",
            reply_markup=get_time_keyboard(is_settings=True),
            parse_mode="HTML"
        )
        
    elif action.startswith("settings_settime_"):
        time_str = action.replace("settings_settime_", "")
        create_or_update_user(user_id, schedule_time=time_str)
        await query.edit_message_text(
            text=f"✅ Đã hẹn giờ thành công!\n👉 Bạn sẽ nhận bản tin vào lúc <b>{time_str}</b> hàng ngày.",
            reply_markup=get_settings_keyboard(),
            parse_mode="HTML"
        )
        
    elif action == "settings_custom_time":
        # Do Telegram CallbackQueryHandler không thể chuyển hướng sang text handler đơn giản trong /settings
        # chúng ta sẽ hướng dẫn user sử dụng cú pháp gõ lệnh /settime HH:MM
        await query.edit_message_text(
            text="Để tự cấu hình một khung giờ cụ thể nằm ngoài danh sách, vui lòng gõ lệnh theo cú pháp:\n"
                 "<code>/settime HH:MM</code>\nVí dụ: <code>/settime 08:15</code> hoặc <code>/settime 06:45</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Quay lại", callback_data="settings_main")]]),
            parse_mode="HTML"
        )
        
    elif action == "settings_close":
        await query.delete_message()

async def set_time_direct_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh gõ nhanh /settime HH:MM của người dùng."""
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "Cú pháp sử dụng: <code>/settime HH:MM</code>\nVí dụ: <code>/settime 07:15</code>",
            parse_mode="HTML"
        )
        return
        
    time_arg = context.args[0].strip()
    if not re.match(r"^(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$", time_arg):
        await update.message.reply_text(
            "⚠️ Giờ nhập không hợp lệ. Vui lòng nhập định dạng đúng là <b>HH:MM</b> (24h, ví dụ: <code>07:45</code>).",
            parse_mode="HTML"
        )
        return
        
    create_or_update_user(user_id, schedule_time=time_arg)
    await update.message.reply_text(
        f"✅ Đã hẹn giờ thành công!\n👉 Bạn sẽ nhận bản tin vào lúc <b>{time_arg}</b> hàng ngày."
    )

# ----------------- Bot Application Creator -----------------

async def post_init(application: Application):
    """Callback chạy sau khi Bot khởi tạo xong, dùng để khởi chạy Scheduler."""
    from src.scheduler import start_scheduler
    asyncio.create_task(start_scheduler(application))

def build_bot_app() -> Application:
    """Khởi tạo và cấu hình ứng dụng Telegram Bot."""
    # Khởi tạo DB nếu chưa có
    init_db()
    
    # Khởi tạo Gemini AI
    init_gemini(GEMINI_API_KEY)
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    
    # Đăng ký ConversationHandler cho luồng Onboarding
    onboarding_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_cmd)],
        states={
            ONBOARDING_TOPICS: [
                CallbackQueryHandler(onboarding_toggle_topic_callback, pattern="^onboarding_toggle_"),
                CallbackQueryHandler(onboarding_next_topics_callback, pattern="^onboarding_next_topics$")
            ],
            ONBOARDING_VOICE: [
                CallbackQueryHandler(onboarding_setvoice_callback, pattern="^onboarding_setvoice_")
            ],
            ONBOARDING_TIME: [
                CallbackQueryHandler(onboarding_settime_callback, pattern="^onboarding_settime_"),
                CallbackQueryHandler(onboarding_custom_time_callback, pattern="^onboarding_custom_time$")
            ],
            ONBOARDING_CUSTOM_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_custom_time_msg)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_onboarding), CommandHandler("start", start_cmd)],
        allow_reentry=True
    )
    
    app.add_handler(onboarding_handler)
    
    # Đăng ký các lệnh thông thường
    app.add_handler(CommandHandler("podcast", run_podcast_now))
    app.add_handler(CommandHandler("settings", settings_cmd))
    app.add_handler(CommandHandler("settime", set_time_direct_cmd))
    
    # Đăng ký callback cho menu cài đặt /settings
    app.add_handler(CallbackQueryHandler(settings_callback_handler, pattern="^settings_"))
    
    return app

if __name__ == "__main__":
    from src.config import validate_config
    try:
        validate_config()
        print("Đang khởi chạy Telegram Bot...")
        application = build_bot_app()
        application.run_polling()
    except Exception as e:
        print(f"Lỗi: {e}")
