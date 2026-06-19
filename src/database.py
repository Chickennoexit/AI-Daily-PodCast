import sqlite3
import os
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = "database.db"

# Các chủ đề mặc định mà bot hỗ trợ
AVAILABLE_TOPICS = {
    "ai": "🤖 Trí tuệ nhân tạo (AI)",
    "tech": "💻 Công nghệ & Thiết bị",
    "finance": "📈 Tài chính & Kinh tế",
    "startup": "🚀 Khởi nghiệp & Doanh nghiệp",
    "world": "🌍 Thời sự & Thế giới",
    "life": "🥗 Đời sống & Sức khỏe"
}

# Giọng đọc mặc định mà edge-tts hỗ trợ
AVAILABLE_VOICES = {
    "vi-VN-HoaiMyNeural": "Giọng Bắc - Nữ (Hoài My)",
    "vi-VN-NamMinhNeural": "Giọng Bắc - Nam (Nam Minh)"
}

def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Tạo kết nối tới SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = DEFAULT_DB_PATH):
    """Khởi tạo cấu trúc các bảng trong Database nếu chưa tồn tại."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    # Tạo bảng users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            voice TEXT DEFAULT 'vi-VN-HoaiMyNeural',
            schedule_time TEXT DEFAULT '07:00',
            is_onboarding_completed INTEGER DEFAULT 0,
            last_sent_date TEXT
        )
    """)
    
    # Tạo bảng user_topics
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_topics (
            user_id INTEGER,
            topic_code TEXT,
            PRIMARY KEY (user_id, topic_code),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)
    
    # Tự động sửa lỗi/di chuyển người dùng đã lỡ chọn giọng Nam (An) sang giọng Hoài My
    cursor.execute("UPDATE users SET voice = 'vi-VN-HoaiMyNeural' WHERE voice = 'vi-VN-AnNeural'")
    
    conn.commit()
    conn.close()

def get_user(user_id: int, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """Lấy thông tin chi tiết của 1 user."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def create_or_update_user(
    user_id: int, 
    username: str = None, 
    voice: str = None, 
    schedule_time: str = None, 
    is_onboarding_completed: int = None,
    last_sent_date: str = None,
    db_path: str = DEFAULT_DB_PATH
) -> Dict[str, Any]:
    """Tạo mới hoặc cập nhật thông tin user."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    # Kiểm tra xem user đã tồn tại chưa
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()
    
    if not exists:
        cursor.execute(
            "INSERT INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        conn.commit()
        
    # Cập nhật các trường nếu có giá trị truyền vào
    updates = []
    params = []
    
    if username is not None:
        updates.append("username = ?")
        params.append(username)
    if voice is not None:
        updates.append("voice = ?")
        params.append(voice)
    if schedule_time is not None:
        updates.append("schedule_time = ?")
        params.append(schedule_time)
    if is_onboarding_completed is not None:
        updates.append("is_onboarding_completed = ?")
        params.append(is_onboarding_completed)
    if last_sent_date is not None:
        updates.append("last_sent_date = ?")
        params.append(last_sent_date)
        
    if updates:
        params.append(user_id)
        cursor.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?",
            tuple(params)
        )
        conn.commit()
        
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user_data = dict(cursor.fetchone())
    conn.close()
    return user_data

def get_user_topics(user_id: int, db_path: str = DEFAULT_DB_PATH) -> List[str]:
    """Lấy danh sách các mã chủ đề mà user đang chọn."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT topic_code FROM user_topics WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row["topic_code"] for row in rows]

def set_user_topics(user_id: int, topic_codes: List[str], db_path: str = DEFAULT_DB_PATH):
    """Thiết lập lại danh sách chủ đề cho user (Xóa cũ thêm mới)."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    # Xóa toàn bộ chủ đề cũ của user
    cursor.execute("DELETE FROM user_topics WHERE user_id = ?", (user_id,))
    
    # Thêm mới các chủ đề hợp lệ
    for code in topic_codes:
        if code in AVAILABLE_TOPICS:
            cursor.execute(
                "INSERT OR IGNORE INTO user_topics (user_id, topic_code) VALUES (?, ?)",
                (user_id, code)
            )
            
    conn.commit()
    conn.close()

def get_active_users_to_send(current_time: str, current_date: str, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Lấy danh sách người dùng đã hoàn thành thiết lập, đến giờ hẹn nhận tin 
    và chưa nhận được podcast trong ngày hôm nay.
    current_time: định dạng 'HH:MM' (ví dụ: '07:00')
    current_date: định dạng 'YYYY-MM-DD' (ví dụ: '2026-06-19')
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM users 
        WHERE is_onboarding_completed = 1 
          AND schedule_time = ? 
          AND (last_sent_date IS NULL OR last_sent_date != ?)
        """,
        (current_time, current_date)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
