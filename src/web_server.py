from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import logging

logger = logging.getLogger(__name__)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Trả về 200 OK cho các yêu cầu HTTP GET để vượt qua Health Check."""
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"AI Daily Podcast Telegram Bot is running!")
        
    def log_message(self, format, *args):
        # Ghi đè để tắt log truy cập HTTP mặc định nhằm tránh làm rác log hệ thống
        pass

def start_health_server(port: int):
    """Khởi động HTTP server trên một luồng phụ (background thread)."""
    def run_server():
        try:
            server_address = ("", port)
            httpd = HTTPServer(server_address, HealthCheckHandler)
            logger.info(f"Web Server Health Check đã khởi động thành công trên cổng {port}.")
            httpd.serve_forever()
        except Exception as e:
            logger.error(f"Lỗi khi chạy Web Server Health Check: {e}", exc_info=True)
            
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
