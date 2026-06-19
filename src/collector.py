import feedparser
import re
import html
from datetime import datetime, timedelta
import time
from bs4 import BeautifulSoup
from typing import List, Dict, Any

# Định nghĩa các nguồn RSS tương ứng với từng chủ đề
TOPIC_RSS_FEEDS = {
    "ai": [
        "https://vnexpress.net/rss/so-hoa.rss",
        "https://genk.vn/ict.rss"
    ],
    "tech": [
        "https://vnexpress.net/rss/so-hoa.rss",
        "https://genk.vn/ict.rss"
    ],
    "finance": [
        "https://vnexpress.net/rss/kinh-doanh.rss",
        "https://cafef.vn/thi-truong-chung-khoan.rss",
        "https://cafef.vn/tai-chinh-quoc-te.rss"
    ],
    "startup": [
        "https://vnexpress.net/rss/startup.rss"
    ],
    "world": [
        "https://vnexpress.net/rss/the-gioi.rss",
        "https://tuoitre.vn/rss/the-gioi.rss"
    ],
    "life": [
        "https://vnexpress.net/rss/suc-khoe.rss",
        "https://vnexpress.net/rss/gia-dinh.rss"
    ]
}

# Các từ khóa lọc cho chủ đề AI từ nguồn Số hóa/ICT tổng hợp
AI_KEYWORDS = [
    "ai", "trí tuệ nhân tạo", "chatgpt", "gemini", "openai", "copilot", 
    "llm", "claud", "anthropic", "midjourney", "sora", "deepmind", 
    "luma", "nvidia", "stable diffusion", "machine learning", "robot"
]

def clean_html(raw_html: str) -> str:
    """Loại bỏ các thẻ HTML, làm sạch khoảng trắng thừa và giải mã HTML entities."""
    if not raw_html:
        return ""
    # Dùng BeautifulSoup để bóc tách text
    soup = BeautifulSoup(raw_html, "html.parser")
    # Thay thế thẻ br hoặc p bằng khoảng trắng
    text = soup.get_text(separator=" ")
    # Giải mã các ký tự html như &nbsp; &amp; ...
    text = html.unescape(text)
    # Xóa khoảng trắng thừa
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_rss_datetime(entry: Dict[str, Any]) -> datetime:
    """Chuyển đổi thời gian của entry RSS thành đối tượng datetime."""
    for date_key in ['published_parsed', 'updated_parsed']:
        if date_key in entry and entry[date_key]:
            try:
                struct_time = entry[date_key]
                return datetime.fromtimestamp(time.mktime(struct_time))
            except Exception:
                pass
    return datetime.now()

def fetch_feed_articles(url: str, max_articles: int = 15) -> List[Dict[str, Any]]:
    """Tải và phân tích cú pháp từ 1 URL RSS feed."""
    try:
        # Cấu hình User-Agent để tránh bị các trang web chặn
        feed = feedparser.parse(url, agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        articles = []
        for entry in feed.entries[:max_articles]:
            title = clean_html(entry.get('title', ''))
            summary = clean_html(entry.get('summary', entry.get('description', '')))
            link = entry.get('link', '')
            pub_date = parse_rss_datetime(entry)
            
            if title:
                articles.append({
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "pub_date": pub_date
                })
        return articles
    except Exception as e:
        print(f"Lỗi khi đọc feed từ {url}: {e}")
        return []

def collect_news_by_topics(topic_codes: List[str], hours_limit: int = 24) -> Dict[str, List[Dict[str, Any]]]:
    """
    Thu thập tin tức theo danh sách chủ đề yêu cầu.
    Giới hạn tin tức trong vòng `hours_limit` giờ qua (mặc định 24h).
    """
    results = {}
    now = datetime.now()
    time_threshold = now - timedelta(hours=hours_limit)
    
    for code in topic_codes:
        if code not in TOPIC_RSS_FEEDS:
            continue
            
        feeds = TOPIC_RSS_FEEDS[code]
        all_articles = []
        
        for feed_url in feeds:
            articles = fetch_feed_articles(feed_url)
            all_articles.extend(articles)
            
        # Lọc tin theo thời gian (24 giờ qua)
        recent_articles = [art for art in all_articles if art['pub_date'] >= time_threshold]
        
        # Nếu không có tin mới trong 24h qua, lấy 5 tin mới nhất của chủ đề đó làm fallback
        if not recent_articles:
            # Sắp xếp theo ngày giảm dần
            all_articles.sort(key=lambda x: x['pub_date'], reverse=True)
            recent_articles = all_articles[:5]
            
        # Xử lý lọc đặc biệt cho chủ đề AI
        if code == "ai":
            filtered_ai_articles = []
            for art in recent_articles:
                # Kiểm tra xem tiêu đề hoặc tóm tắt có chứa từ khóa AI không
                text_to_search = (art['title'] + " " + art['summary']).lower()
                is_ai = any(kw in text_to_search for kw in AI_KEYWORDS)
                if is_ai:
                    filtered_ai_articles.append(art)
            
            # Nếu lọc xong bị ít tin quá, lấy 3 tin AI gần nhất từ toàn bộ articles (không giới hạn 24h)
            if len(filtered_ai_articles) < 3:
                fallback_ai = []
                for art in all_articles:
                    text_to_search = (art['title'] + " " + art['summary']).lower()
                    if any(kw in text_to_search for kw in AI_KEYWORDS):
                        fallback_ai.append(art)
                # Loại bỏ trùng lặp nếu có
                for f_art in fallback_ai[:5]:
                    if f_art not in filtered_ai_articles:
                        filtered_ai_articles.append(f_art)
            
            recent_articles = filtered_ai_articles
            
        # Bỏ trùng lặp theo tiêu đề
        seen_titles = set()
        unique_articles = []
        for art in recent_articles:
            clean_title = art['title'].lower().strip()
            if clean_title not in seen_titles:
                seen_titles.add(clean_title)
                # Định dạng lại đối tượng trả về (chuyển datetime sang string cho tiện gửi API)
                unique_articles.append({
                    "title": art["title"],
                    "summary": art["summary"],
                    "link": art["link"],
                    "pub_date": art["pub_date"].strftime("%Y-%m-%d %H:%M:%S")
                })
                
        # Giới hạn tối đa 5 tin mỗi chủ đề để tránh quá tải kịch bản
        results[code] = unique_articles[:5]
        
    return results

if __name__ == "__main__":
    # Test nhanh chức năng thu thập tin tức
    print("Đang chạy thử thu thập tin tức...")
    news = collect_news_by_topics(["ai", "tech"])
    for topic, articles in news.items():
        print(f"\n--- CHỦ ĐỀ: {topic} (Có {len(articles)} tin) ---")
        for i, art in enumerate(articles, 1):
            print(f"{i}. {art['title']} ({art['pub_date']})")
            print(f"   Link: {art['link']}")
