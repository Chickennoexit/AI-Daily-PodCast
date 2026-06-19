import os
import json
import asyncio
import logging
import re
import edge_tts
import google.generativeai as genai
from typing import Dict, List, Any, Tuple
from src.database import AVAILABLE_TOPICS, AVAILABLE_VOICES

logger = logging.getLogger(__name__)

# Cấu hình Gemini
def init_gemini(api_key: str):
    """Khởi tạo Gemini API với API Key cung cấp."""
    if not api_key:
        raise ValueError("Thiếu GEMINI_API_KEY trong cấu hình.")
    genai.configure(api_key=api_key)

async def generate_podcast_content(
    news_data: Dict[str, List[Dict[str, Any]]], 
    username: str = "bạn"
) -> Tuple[str, str]:
    """
    Sử dụng Gemini để tổng hợp tin tức và viết kịch bản podcast.
    Trả về một tuple gồm: (kịch bản giọng nói, văn bản tóm tắt dạng HTML gửi kèm Telegram)
    """
    model = genai.GenerativeModel("models/gemini-1.5-flash")
    
    # Định dạng dữ liệu tin tức đầu vào thành chuỗi văn bản cho Gemini đọc
    news_context = ""
    for topic_code, articles in news_data.items():
        topic_name = AVAILABLE_TOPICS.get(topic_code, topic_code)
        if not articles:
            continue
        news_context += f"\n=== CHỦ ĐỀ: {topic_name} ===\n"
        for i, art in enumerate(articles, 1):
            news_context += f"Tin {i}: {art['title']}\n"
            news_context += f"Tóm tắt: {art['summary']}\n"
            news_context += f"Nguồn: {art['link']}\n\n"
            
    if not news_context.strip():
        # Trường hợp không thu thập được tin nào
        script = f"Chào buổi sáng {username}. Hôm nay tôi đã kiểm tra các nguồn tin tức nhưng không thấy có tin tức mới nào nổi bật thuộc các chủ đề bạn quan tâm. Chúc bạn một ngày mới làm việc hiệu quả và tràn đầy năng lượng nhé!"
        summary = f"<b>Chào buổi sáng {username}!</b>\n\nHôm nay không có tin tức mới nào nổi bật thuộc các chủ đề bạn đã đăng ký.\nChúc bạn một ngày mới tốt lành! ☀️"
        return script, summary

    prompt = f"""
Bạn là một trợ lý AI thông minh kiêm MC Podcast chuyên nghiệp. Hãy đọc danh sách tin tức thu thập được dưới đây và thực hiện hai nhiệm vụ:

1. Viết một kịch bản nói (script) podcast buổi sáng dành cho người nghe tên là "{username}".
   - Kịch bản phải được viết bằng giọng văn nói tiếng Việt tự nhiên, ấm áp, lôi cuốn, trôi chảy như một MC Radio thực thụ.
   - Bắt đầu bằng lời chào buổi sáng thân thiện, giới thiệu các chủ đề tin tức hôm nay.
   - Tóm tắt và kết nối các tin tức quan trọng một cách logic, chuyển ý mượt mà giữa các chủ đề. Không chỉ đọc danh sách đầu dòng khô khan.
   - Kết thúc bằng lời chúc ngày mới năng động và nhiều niềm vui.
   - QUAN TRỌNG: Kịch bản này sẽ được chuyển thành giọng đọc bằng công nghệ Text-to-Speech (TTS). Do đó, kịch bản tuyệt đối KHÔNG chứa bất kỳ ký tự đặc biệt nào như dấu sao (*), dấu thăng (#), dấu ngoặc vuông [], dấu ngoặc nhọn, hoặc các thẻ định dạng. Chỉ sử dụng các dấu câu cơ bản (. , ? !). Tránh chèn các đường link URL vào kịch bản nói. Độ dài nói khoảng 2-3 phút (khoảng 350-500 từ).

2. Tạo một bản tóm tắt (summary_text) để gửi kèm qua tin nhắn Telegram.
   - Định dạng bằng thẻ HTML được Telegram hỗ trợ (như <b>, <i>, <a>, <code>).
   - Liệt kê các chủ đề nổi bật kèm tiêu đề tin chính và tạo link liên kết nhấp vào tiêu đề đó dẫn tới link gốc (ví dụ: <a href="link_goc">Tiêu đề tin</a>).
   - Bản tóm tắt ngắn gọn, trực quan để người dùng có thể đọc lướt nhanh nội dung của podcast.

Dữ liệu tin tức thu thập được:
{news_context}

Hãy trả về kết quả dưới định dạng JSON với cấu trúc sau:
{{
  "script": "nội dung kịch bản nói hoàn toàn bằng chữ không chứa ký tự markdown",
  "summary_text": "nội dung tóm tắt HTML để hiển thị trên Telegram"
}}
"""

    try:
        # Gọi Gemini với cấu hình trả về JSON
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        # Làm sạch chuỗi JSON nếu Gemini trả về markdown JSON block (ví dụ ```json ...)
        response_text = response.text.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r"^```(?:json)?\n", "", response_text)
            response_text = re.sub(r"\n```$", "", response_text)
            
        result_json = json.loads(response_text)
        script = result_json.get("script", "")
        summary_text = result_json.get("summary_text", "")
        
        return script, summary_text
    except Exception as e:
        logger.error(f"Lỗi khi tạo kịch bản với Gemini: {e}", exc_info=True)
        # Phương án dự phòng (fallback) nếu Gemini lỗi hoặc trả về sai định dạng
        script = f"Chào buổi sáng {username}. Đã có lỗi xảy ra trong quá trình tổng hợp tin tức hôm nay. Mong bạn thông cảm. Chúc bạn một ngày mới tốt lành!"
        summary_text = f"<b>Chào buổi sáng {username}!</b>\n\n⚠️ Đã xảy ra lỗi khi tổng hợp kịch bản podcast. Vui lòng thử lại sau."
        return script, summary_text

async def text_to_speech(text: str, voice: str, output_path: str) -> bool:
    """
    Chuyển đổi văn bản thành file âm thanh MP3 bằng edge-tts.
    Trả về True nếu thành công, False nếu thất bại.
    """
    try:
        # Kiểm tra xem giọng đọc có được hỗ trợ không
        if voice not in AVAILABLE_VOICES:
            voice = "vi-VN-HoaiMyNeural" # Mặc định
            
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        return True
    except Exception as e:
        logger.error(f"Lỗi khi chuyển đổi Text-to-Speech: {e}", exc_info=True)
        return False

# Chạy thử nghiệm nếu gọi trực tiếp file này
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Vui lòng thiết lập GEMINI_API_KEY trong file .env")
    else:
        init_gemini(api_key)
        
        test_news = {
            "ai": [
                {
                    "title": "Gemini 1.5 Flash ra mắt với tốc độ xử lý vượt trội",
                    "summary": "Google vừa công bố mô hình ngôn ngữ lớn mới mang tên Gemini 1.5 Flash với dung lượng ngữ cảnh lớn và tốc độ phản hồi cực nhanh.",
                    "link": "https://example.com/gemini-flash"
                }
            ],
            "tech": [
                {
                    "title": "Apple công bố iOS 18 tích hợp trí thông minh nhân tạo",
                    "summary": "Trong sự kiện WWDC, Apple giới thiệu iOS 18 tích hợp sâu hệ thống Apple Intelligence vào trợ lý ảo Siri.",
                    "link": "https://example.com/ios-18"
                }
            ]
        }
        
        async def test():
            print("Đang tạo kịch bản thử nghiệm...")
            script, summary = await generate_podcast_content(test_news, "Hùng")
            print("\n--- KỊCH BẢN NÓI ---")
            print(script)
            print("\n--- TÓM TẮT TELEGRAM ---")
            print(summary)
            
            print("\nĐang tạo file âm thanh MP3...")
            success = await text_to_speech(script, "vi-VN-HoaiMyNeural", "test_podcast.mp3")
            if success:
                print("Tạo file test_podcast.mp3 thành công!")
            else:
                print("Tạo file âm thanh thất bại.")
                
        asyncio.run(test())
