# 🎙️ AI Daily Podcast Telegram Bot

Ứng dụng Telegram Bot thông minh giúp tự động thu thập tin tức nóng hổi theo chủ đề bạn quan tâm mỗi ngày, biên soạn kịch bản podcast sinh động qua **Gemini AI**, chuyển đổi thành giọng đọc tự nhiên chất lượng cao qua **Edge-TTS** và gửi file âm thanh kèm tóm tắt nội dung trực tiếp qua Telegram của bạn.

---

## ✨ Tính năng nổi bật
* 🧭 **Luồng cài đặt ban đầu (Onboarding Wizard):** Khi chat `/start` lần đầu, bot sẽ hướng dẫn bạn chọn các chủ đề ưa thích, giọng đọc và hẹn giờ nhận tin thông qua bàn phím nút bấm trực quan.
* 📁 **Lọc tin tức thông minh:** Thu thập tin tức từ các nguồn báo lớn (VnExpress, Tuổi Trẻ, CafeF, GenK...) theo các chủ đề: Trí tuệ nhân tạo (AI), Công nghệ, Tài chính, Khởi nghiệp, Thế giới, Đời sống. Lọc từ khóa AI chuyên sâu để tránh tin rác.
* 🤖 **MC Podcast AI:** Sử dụng **Gemini 1.5 Flash** để đóng vai MC bản tin sáng, xâu chuỗi và biên soạn tin tức thành một kịch bản nói chuyện tự nhiên, gần gũi.
* 🗣️ **Giọng đọc tự nhiên:** Tích hợp **Edge-TTS** (Microsoft Edge) hoàn toàn miễn phí với các giọng đọc tiếng Việt cực kỳ truyền cảm, có tùy chọn giọng Bắc Nam, nam nữ.
* ⏰ **Bộ lập lịch cá nhân (Scheduler):** Tự động gửi bản tin podcast đến từng người dùng đúng khung giờ họ đã đăng ký hàng ngày.
* ⚡ **Chạy tức thì:** Gõ `/podcast` bất kỳ lúc nào để nhận ngay bản tin tổng hợp nóng hổi mới nhất mà không cần đợi đến giờ hẹn.

---

## 🛠️ Hướng dẫn cài đặt

### 1. Chuẩn bị môi trường
Yêu cầu máy tính cài đặt sẵn **Python 3.10+**.

Mở Terminal/PowerShell tại thư mục dự án và cài đặt các thư viện cần thiết:
```bash
pip install -r requirements.txt
```

### 2. Tạo Bot Telegram & Lấy API Keys
1. **Lấy Telegram Bot Token:**
   - Mở Telegram và tìm kiếm bot `@BotFather`.
   - Gửi lệnh `/newbot` và đặt tên cho bot của bạn.
   - `@BotFather` sẽ gửi lại cho bạn một đoạn mã **Token** (Ví dụ: `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).
2. **Lấy Gemini API Key:**
   - Truy cập trang [Google AI Studio](https://aistudio.google.com/).
   - Đăng nhập tài khoản Google của bạn và nhấn **Get API Key**.
   - Tạo một API Key mới (hoàn toàn miễn phí).

### 3. Cấu hình file `.env`
Khởi chạy thử dự án lần đầu tiên bằng lệnh:
```bash
python run.py
```
Dự án sẽ tự động sao chép file cấu hình `.env.example` thành `.env`. 

Hãy mở file `.env` vừa được tạo ra ở thư mục gốc và điền các API key của bạn vào:
```env
TELEGRAM_BOT_TOKEN=điền_bot_token_telegram_ở_đây
GEMINI_API_KEY=điền_gemini_api_key_ở_đây
```

---

## 🚀 Cách chạy ứng dụng

Chạy lệnh khởi động bot:
```bash
python run.py
```

Khi Terminal hiển thị thông báo Bot đang chạy thành công:
1. Mở ứng dụng Telegram, tìm kiếm username bot của bạn.
2. Nhấn nút **Start** hoặc gõ `/start` để bắt đầu cấu hình sở thích của bạn.
3. Làm theo hướng dẫn 3 bước của bot, sau khi hoàn thành bot sẽ gửi cho bạn bản tin podcast nghe thử đầu tiên!

---

## 🎮 Các lệnh hỗ trợ trong Bot

* `/start`: Khởi động luồng thiết lập ban đầu (Onboarding Wizard).
* `/podcast`: Yêu cầu tổng hợp tin tức và gửi podcast ngay lập tức.
* `/settings`: Mở giao diện menu cài đặt để thay đổi nhanh chủ đề quan tâm, giọng đọc, giờ nhận tin.
* `/settime HH:MM`: Hẹn giờ nhận tin trực tiếp (Ví dụ: `/settime 07:15`).
* `/cancel`: Hủy bỏ luồng thiết lập đang dở dang.

## 📦 Hướng dẫn triển khai chạy 24/7 (Không cần treo máy cá nhân)

Để bot luôn hoạt động và gửi tin nhắn đúng giờ mỗi sáng mà không cần bật máy tính của bạn, phương án tốt nhất là đưa mã nguồn lên GitHub và chạy trên dịch vụ đám mây miễn phí **Render.com**. 

Mã nguồn đã được thiết kế tương thích sẵn (tích hợp Web Server Health Check chạy ngầm trên cổng do Cloud cấp để vượt qua bài kiểm tra sức khỏe bắt buộc của Render).

### Các bước triển khai lên Render.com (Miễn phí 100%):

1. **Đưa mã nguồn lên GitHub:**
   - Tạo một kho lưu trữ (Repository) riêng tư (**Private**) trên GitHub để bảo mật code.
   - Đưa toàn bộ các tệp tin trong thư mục này lên GitHub (trừ file `.env` nếu có và file `database.db`).

2. **Đăng ký tài khoản Render:**
   - Truy cập [Render.com](https://render.com/) và đăng nhập (Sign up) bằng tài khoản GitHub của bạn.

3. **Tạo Web Service mới:**
   - Tại trang Dashboard của Render, nhấn **New +** và chọn **Web Service**.
   - Kết nối với kho lưu trữ GitHub chứa mã nguồn bot của bạn.
   - Cấu hình các thông số cơ bản:
     - **Name:** `ai-daily-podcast-bot` (hoặc tên tùy ý bạn).
     - **Runtime:** `Python`.
     - **Build Command:** `pip install -r requirements.txt`.
     - **Start Command:** `python run.py`.
     - **Instance Type:** Chọn gói **Free** (Miễn phí).

4. **Cấu hình biến môi trường (Environment Variables) - Đỡ cài file `.env`:**
   - Trong quá trình thiết lập Web Service (hoặc truy cập mục **Environment** ở thanh menu trái sau khi tạo), nhấn **Add Environment Variable** để thêm 2 biến sau:
     - `TELEGRAM_BOT_TOKEN`: Điền Token lấy từ @BotFather.
     - `GEMINI_API_KEY`: Điền API Key lấy từ Google AI Studio.
   - *Lưu ý: Render sẽ tự động cấp cổng `PORT` và nạp vào ứng dụng của chúng ta.*

5. **Nhấn Deploy Web Service:**
   - Render sẽ tiến hành cài đặt môi trường và khởi chạy.
   - Khi log hiển thị bot khởi chạy thành công và báo trạng thái `Live` màu xanh lá, bot của bạn đã trực tuyến 24/7 và sẵn sàng hoạt động! Bạn chỉ việc vào Telegram chat `/start` để cấu hình.
