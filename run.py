import os
import shutil
import sys

def setup_env():
    """Tự động kiểm tra và khởi tạo file .env từ file .env.example nếu chưa có và không có sẵn biến môi trường hệ thống."""
    # Nếu các biến môi trường hệ thống đã được cài đặt sẵn (chạy trên Cloud), không cần tạo file .env
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("GEMINI_API_KEY"):
        return

    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            print("Không tìm thấy file .env. Đang tự động sao chép từ .env.example...")
            shutil.copy(".env.example", ".env")
            print("⚠️ Đã tạo file .env thành công.")
            print("👉 Vui lòng mở file .env ở thư mục dự án và điền: TELEGRAM_BOT_TOKEN và GEMINI_API_KEY trước khi khởi chạy lại.")
            sys.exit(0)
        else:
            print("❌ Lỗi: Không tìm thấy file .env hay .env.example trong thư mục dự án.")
            sys.exit(1)

if __name__ == "__main__":
    # Đảm bảo thiết lập môi trường
    setup_env()
    
    # Import các thành phần dự án sau khi nạp cấu hình
    from src.config import validate_config
    from src.telegram_bot import build_bot_app
    
    try:
        # Validate cấu hình môi trường
        validate_config()
        
        # Nếu chạy trên Cloud (Render, Railway, v.v.), cổng PORT sẽ được cấp tự động
        port = os.getenv("PORT")
        if port:
            from src.web_server import start_health_server
            print(f"-> Phát hiện cổng {port} từ Cloud. Đang khởi chạy Health Server...")
            start_health_server(int(port))
            
        print("=========================================")
        print("🎙️  AI DAILY PODCAST TELEGRAM BOT IS RUNNING")
        print("=========================================")
        print("• Bot Telegram đang chạy ở chế độ Polling...")
        print("• Scheduler quét giờ gửi tin tự động đã kích hoạt.")
        print("=========================================")
        
        # Khởi chạy bot (scheduler sẽ tự động chạy trong post_init)
        application = build_bot_app()
        application.run_polling()
        
    except ValueError as ve:
        print(f"\n⚠️ Cấu hình chưa hoàn tất:\n{ve}")
        print("\n👉 Vui lòng kiểm tra lại file .env hoặc cấu hình Environment Variables trên Cloud.")
    except Exception as e:
        print(f"\n❌ Lỗi khởi chạy ứng dụng: {e}")
