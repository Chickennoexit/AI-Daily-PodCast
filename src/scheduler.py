import asyncio
import logging
from datetime import datetime
from src.database import get_active_users_to_send
from src.telegram_bot import generate_and_send_podcast

logger = logging.getLogger(__name__)

async def start_scheduler(application):
    """
    Bắt đầu vòng lặp Scheduler quét cơ sở dữ liệu mỗi phút.
    Nếu tìm thấy người dùng đến giờ nhận tin (và hôm nay chưa gửi),
    sẽ tiến hành tạo và gửi podcast cho họ.
    """
    logger.info("Scheduler gửi tin tự động đã được khởi động.")
    
    while True:
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            current_date = now.strftime("%Y-%m-%d")
            
            # Truy vấn DB xem có user nào hẹn giờ này và chưa gửi hôm nay không
            users_to_send = get_active_users_to_send(current_time, current_date)
            
            if users_to_send:
                logger.info(f"Phát hiện {len(users_to_send)} user(s) đến giờ nhận tin ({current_time}):")
                
                for user in users_to_send:
                    user_id = user["user_id"]
                    username = user["username"] or "bạn"
                    logger.info(f"-> Đang gửi tin cho {username} (ID: {user_id})")
                    
                    # Chạy tiến trình gửi độc lập cho từng user để tránh nghẽn vòng lặp
                    asyncio.create_task(
                        generate_and_send_podcast(user_id, application.bot)
                    )
            
        except Exception as e:
            logger.error(f"Lỗi trong vòng lặp Scheduler: {e}", exc_info=True)
            
        # Ngủ để đồng bộ hóa với giây 00 của phút tiếp theo
        # Điều này giúp Scheduler chạy chính xác vào đầu mỗi phút
        now = datetime.now()
        seconds_to_sleep = 60 - now.second
        await asyncio.sleep(seconds_to_sleep)
