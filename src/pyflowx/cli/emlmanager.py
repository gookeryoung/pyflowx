"""EML 邮件管理工具 Web 版本.

提供基于 Web 的 EML 邮件文件管理功能,
支持邮件读取、数据库存储、搜索和聚合显示.
"""

from __future__ import annotations

import argparse
import email
import hashlib
import json
import sqlite3
import threading
from datetime import datetime
from email.header import decode_header
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

# ============================================================================
# 配置
# ============================================================================

DB_NAME = "eml_manager.db"
TABLE_NAME = "emails"
DEFAULT_PORT = 8080


# ============================================================================
# 数据库管理
# ============================================================================


class EmailDatabase:
    """邮件数据库管理类."""

    def __init__(self, db_path: Path):
        """初始化数据库连接."""
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表结构."""
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        cursor = self.conn.cursor()

        # 创建邮件表
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_hash TEXT NOT NULL,
                subject TEXT,
                sender TEXT,
                recipients TEXT,
                date TEXT,
                date_parsed TEXT,
                body_text TEXT,
                body_html TEXT,
                has_attachments INTEGER DEFAULT 0,
                file_size INTEGER,
                created_at TEXT,
                updated_at TEXT
            )
        """
        )

        # 创建索引
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_subject ON {TABLE_NAME}(subject)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_sender ON {TABLE_NAME}(sender)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_date ON {TABLE_NAME}(date_parsed)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_file_hash ON {TABLE_NAME}(file_hash)")

        self.conn.commit()

    def insert_email(self, email_data: dict[str, Any]) -> bool:
        """插入邮件数据."""
        try:
            with self._lock:
                cursor = self.conn.cursor()
                cursor.execute(
                    f"""
                    INSERT OR REPLACE INTO {TABLE_NAME} 
                    (file_path, file_hash, subject, sender, recipients, date, date_parsed,
                     body_text, body_html, has_attachments, file_size, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        email_data["file_path"],
                        email_data["file_hash"],
                        email_data.get("subject", ""),
                        email_data.get("sender", ""),
                        email_data.get("recipients", ""),
                        email_data.get("date", ""),
                        email_data.get("date_parsed", ""),
                        email_data.get("body_text", ""),
                        email_data.get("body_html", ""),
                        email_data.get("has_attachments", 0),
                        email_data.get("file_size", 0),
                        datetime.now().isoformat(),
                        datetime.now().isoformat(),
                    ),
                )
                self.conn.commit()
            return True
        except sqlite3.Error:
            return False

    def search_emails(self, keyword: str = "", field: str = "all") -> list[dict[str, Any]]:
        """搜索邮件."""
        with self._lock:
            cursor = self.conn.cursor()

            if not keyword:
                cursor.execute(f"SELECT * FROM {TABLE_NAME} ORDER BY date_parsed DESC")
            elif field == "subject":
                query = f"SELECT * FROM {TABLE_NAME} WHERE subject LIKE ? ORDER BY date_parsed DESC"
                cursor.execute(query, (f"%{keyword}%",))
            elif field == "sender":
                query = f"SELECT * FROM {TABLE_NAME} WHERE sender LIKE ? ORDER BY date_parsed DESC"
                cursor.execute(query, (f"%{keyword}%",))
            elif field == "recipients":
                query = f"SELECT * FROM {TABLE_NAME} WHERE recipients LIKE ? ORDER BY date_parsed DESC"
                cursor.execute(query, (f"%{keyword}%",))
            else:  # all
                query = f"""
                        SELECT * FROM {TABLE_NAME} 
                        WHERE subject LIKE ? OR sender LIKE ? OR recipients LIKE ? OR body_text LIKE ?
                        ORDER BY date_parsed DESC
                    """
                cursor.execute(query, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"))

            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_grouped_emails(self) -> dict[str, list[dict[str, Any]]]:
        """获取按主题分组的邮件."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(f"SELECT * FROM {TABLE_NAME} ORDER BY subject, date_parsed DESC")

            columns = [description[0] for description in cursor.description]
            emails = [dict(zip(columns, row)) for row in cursor.fetchall()]

        # 按主题分组
        grouped: dict[str, list[dict[str, Any]]] = {}
        for email_data in emails:
            subject = email_data.get("subject", "") or "(无主题)"
            # 标准化主题（去除Re:、Fwd:等前缀）
            normalized_subject = self._normalize_subject(subject)
            if normalized_subject not in grouped:
                grouped[normalized_subject] = []
            grouped[normalized_subject].append(email_data)

        return grouped

    def _normalize_subject(self, subject: str) -> str:
        """标准化邮件主题."""
        import re

        # 移除 Re:, Fwd:, FW: 等前缀
        normalized = re.sub(r"^(Re|Fwd|FW|Fw):\s*", "", subject, flags=re.IGNORECASE)
        return normalized.strip()

    def get_email_count(self) -> int:
        """获取邮件总数."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
            return cursor.fetchone()[0]

    def clear_all(self) -> None:
        """清空所有邮件数据."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(f"DELETE FROM {TABLE_NAME}")
            self.conn.commit()

    def close(self) -> None:
        """关闭数据库连接."""
        if self.conn:
            self.conn.close()


# ============================================================================
# EML 文件解析
# ============================================================================


def decode_mime_words(s: str) -> str:
    """解码 MIME 编码的字符串."""
    if not s:
        return ""

    decoded_list = decode_header(s)
    decoded_string = ""
    for part, encoding in decoded_list:
        if isinstance(part, bytes):
            decoded_string += part.decode(encoding or "utf-8", errors="ignore")
        else:
            decoded_string += str(part)

    return decoded_string


def parse_eml_file(file_path: Path) -> dict[str, Any] | None:
    """解析 EML 文件."""
    try:
        with open(file_path, "rb") as f:
            msg = email.message_from_binary_file(f)

        # 计算文件哈希
        file_hash = hashlib.md5(file_path.read_bytes()).hexdigest()
        file_size = file_path.stat().st_size

        # 提取基本信息
        subject = decode_mime_words(msg.get("Subject", ""))
        sender = decode_mime_words(msg.get("From", ""))
        recipients = decode_mime_words(msg.get("To", ""))
        date_str = msg.get("Date", "")

        # 解析日期
        date_parsed = ""
        if date_str:
            try:
                dt = parsedate_to_datetime(date_str)
                date_parsed = dt.isoformat()
            except Exception:
                date_parsed = date_str

        # 提取正文
        body_text = ""
        body_html = ""
        has_attachments = 0

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # 检查附件
                if "attachment" in content_disposition:
                    has_attachments = 1
                    continue

                # 提取正文
                if content_type == "text/plain" and not body_text:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        body_text = payload.decode(charset, errors="ignore")
                    except Exception:
                        pass
                elif content_type == "text/html" and not body_html:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        body_html = payload.decode(charset, errors="ignore")
                    except Exception:
                        pass
        else:
            content_type = msg.get_content_type()
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or "utf-8"
                if content_type == "text/plain":
                    body_text = payload.decode(charset, errors="ignore")
                elif content_type == "text/html":
                    body_html = payload.decode(charset, errors="ignore")
            except Exception:
                pass

        return {
            "file_path": str(file_path),
            "file_hash": file_hash,
            "subject": subject,
            "sender": sender,
            "recipients": recipients,
            "date": date_str,
            "date_parsed": date_parsed,
            "body_text": body_text[:5000],  # 限制长度
            "body_html": body_html[:5000],
            "has_attachments": has_attachments,
            "file_size": file_size,
        }

    except Exception as e:
        print(f"解析文件失败 {file_path}: {e}")
        return None


# ============================================================================
# Web 服务器
# ============================================================================


class EmlManagerHandler(BaseHTTPRequestHandler):
    """EML 邮件管理器 HTTP 请求处理器."""

    db: EmailDatabase | None = None
    work_dir: Path | None = None

    def do_GET(self) -> None:
        """处理 GET 请求."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)

        if path == "/" or path == "/index.html":
            self._serve_index()
        elif path == "/test":
            self._serve_test_page()
        elif path == "/api/emails":
            self._api_get_emails(query_params)
        elif path == "/api/email":
            self._api_get_email(query_params)
        elif path == "/api/grouped":
            self._api_get_grouped_emails()
        elif path == "/api/count":
            self._api_get_count()
        elif path == "/api/status":
            self._api_get_status()
        else:
            self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        """处理 POST 请求."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path == "/api/import":
            self._api_import_emails()
        elif path == "/api/clear":
            self._api_clear_database()
        else:
            self.send_error(404, "Not Found")

    def _serve_index(self) -> None:
        """返回主页 HTML."""
        html_content = self._get_html_template()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(html_content.encode("utf-8"))

    def _serve_test_page(self) -> None:
        """返回测试页面 HTML."""
        test_html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EML 邮件管理器测试</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
        }
        h1 {
            color: #333;
        }
        .test-result {
            margin: 10px 0;
            padding: 10px;
            border-radius: 4px;
        }
        .success {
            background: #d4edda;
            color: #155724;
        }
        .error {
            background: #f8d7da;
            color: #721c24;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>EML 邮件管理器 API 测试</h1>
        <div id="testResults"></div>
    </div>
    
    <script>
        async function testAPI() {
            const resultsDiv = document.getElementById('testResults');
            
            // 测试状态API
            try {
                const statusResponse = await fetch('/api/status');
                const statusData = await statusResponse.json();
                resultsDiv.innerHTML += '<div class="test-result success">✅ 状态API正常: ' + JSON.stringify(statusData) + '</div>';
            } catch (error) {
                resultsDiv.innerHTML += '<div class="test-result error">❌ 状态API失败: ' + error.message + '</div>';
            }
            
            // 测试邮件列表API
            try {
                const emailsResponse = await fetch('/api/emails');
                const emailsData = await emailsResponse.json();
                resultsDiv.innerHTML += '<div class="test-result success">✅ 邮件列表API正常: ' + emailsData.count + ' 封邮件</div>';
                
                // 显示邮件详情
                if (emailsData.emails && emailsData.emails.length > 0) {
                    const email = emailsData.emails[0];
                    resultsDiv.innerHTML += '<div class="test-result success">✅ 首封邮件: ' + email.subject + ' (' + email.sender + ')</div>';
                }
            } catch (error) {
                resultsDiv.innerHTML += '<div class="test-result error">❌ 邮件列表API失败: ' + error.message + '</div>';
            }
            
            // 测试聚合API
            try {
                const groupedResponse = await fetch('/api/grouped');
                const groupedData = await groupedResponse.json();
                resultsDiv.innerHTML += '<div class="test-result success">✅ 聚合API正常: ' + groupedData.groups + ' 个主题</div>';
            } catch (error) {
                resultsDiv.innerHTML += '<div class="test-result error">❌ 聚合API失败: ' + error.message + '</div>';
            }
        }
        
        // 页面加载后执行测试
        window.onload = testAPI;
    </script>
</body>
</html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(test_html.encode("utf-8"))

    def _api_get_emails(self, query_params: dict[str, list[str]]) -> None:
        """API: 获取邮件列表."""
        if not self.db:
            self._send_json_response({"error": "数据库未初始化"}, 500)
            return

        keyword = query_params.get("keyword", [""])[0]
        field = query_params.get("field", ["all"])[0]

        emails = self.db.search_emails(keyword, field)
        self._send_json_response({"emails": emails, "count": len(emails)})

    def _api_get_email(self, query_params: dict[str, list[str]]) -> None:
        """API: 获取单个邮件详情."""
        if not self.db:
            self._send_json_response({"error": "数据库未初始化"}, 500)
            return

        email_id = query_params.get("id", [""])[0]
        if not email_id:
            self._send_json_response({"error": "缺少邮件ID"}, 400)
            return

        with self.db._lock:
            cursor = self.db.conn.cursor()
            cursor.execute(f"SELECT * FROM {TABLE_NAME} WHERE id = ?", (int(email_id),))
            columns = [description[0] for description in cursor.description]
            row = cursor.fetchone()

        if not row:
            self._send_json_response({"error": "邮件不存在"}, 404)
            return

        email_data = dict(zip(columns, row))
        self._send_json_response({"email": email_data})

    def _api_get_grouped_emails(self) -> None:
        """API: 获取聚合邮件."""
        if not self.db:
            self._send_json_response({"error": "数据库未初始化"}, 500)
            return

        grouped = self.db.get_grouped_emails()
        self._send_json_response({"grouped": grouped, "groups": len(grouped)})

    def _api_get_count(self) -> None:
        """API: 获取邮件总数."""
        if not self.db:
            self._send_json_response({"error": "数据库未初始化"}, 500)
            return

        count = self.db.get_email_count()
        self._send_json_response({"count": count})

    def _api_get_status(self) -> None:
        """API: 获取系统状态."""
        status = {
            "initialized": self.db is not None,
            "work_dir": str(self.work_dir) if self.work_dir else "",
            "db_path": str(self.db.db_path) if self.db else "",
        }
        self._send_json_response(status)

    def _api_import_emails(self) -> None:
        """API: 导入邮件."""
        if not self.work_dir or not self.db:
            self._send_json_response({"error": "工作目录或数据库未初始化"}, 500)
            return

        # 在后台线程中导入
        def import_emails():
            eml_files = list(self.work_dir.rglob("*.eml"))
            if not eml_files:
                return

            # 先批量查询所有已存在的文件
            with self.db._lock:
                cursor = self.db.conn.cursor()
                cursor.execute(f"SELECT file_path, file_hash FROM {TABLE_NAME}")
                existing_files = {row[0]: row[1] for row in cursor.fetchall()}

            new_count = 0
            update_count = 0

            for eml_file in eml_files:
                email_data = parse_eml_file(eml_file)
                if email_data:
                    file_path_str = str(eml_file)

                    if file_path_str in existing_files:
                        if existing_files[file_path_str] != email_data["file_hash"]:
                            self.db.insert_email(email_data)
                            update_count += 1
                    else:
                        self.db.insert_email(email_data)
                        new_count += 1

            print(f"导入完成: 新增 {new_count}, 更新 {update_count}, 总计 {len(eml_files)}")

        thread = threading.Thread(target=import_emails, daemon=True)
        thread.start()

        self._send_json_response({"message": "导入任务已启动", "total_files": len(list(self.work_dir.rglob("*.eml")))})

    def _api_clear_database(self) -> None:
        """API: 清空数据库."""
        if not self.db:
            self._send_json_response({"error": "数据库未初始化"}, 500)
            return

        self.db.clear_all()
        self._send_json_response({"message": "数据库已清空"})

    def _send_json_response(self, data: dict[str, Any], status_code: int = 200) -> None:
        """发送 JSON 响应."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _get_html_template(self) -> str:
        """获取 HTML 模板."""
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EML 邮件</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            color: #667eea;
            font-size: 32px;
            margin-bottom: 20px;
        }
        
        .toolbar {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .btn-primary {
            background: #667eea;
            color: white;
        }
        
        .btn-primary:hover {
            background: #5568d3;
            transform: translateY(-2px);
        }
        
        .btn-danger {
            background: #e74c3c;
            color: white;
        }
        
        .btn-danger:hover {
            background: #c0392b;
        }
        
        .search-box {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        .search-input {
            padding: 12px 20px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
            width: 300px;
        }
        
        .search-input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .search-select {
            padding: 12px 15px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
        }
        
        .view-toggle {
            display: flex;
            gap: 10px;
        }
        
        .radio-btn {
            padding: 8px 16px;
            background: #f8f9fa;
            border: 2px solid #ddd;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .radio-btn.active {
            background: #667eea;
            color: white;
            border-color: #667eea;
        }
        
        .main-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            height: calc(100vh - 200px);
        }
        
        .email-list {
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            overflow-y: auto;
        }
        
        .email-item {
            padding: 15px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .email-item:hover {
            background: #f8f9fa;
        }
        
        .email-item.active {
            background: #e8f4f8;
            border-left: 4px solid #667eea;
        }
        
        .email-subject {
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 5px;
        }
        
        .email-meta {
            display: flex;
            gap: 15px;
            color: #7f8c8d;
            font-size: 12px;
        }
        
        .email-group {
            background: #f8f9fa;
            padding: 10px 15px;
            font-weight: 600;
            color: #667eea;
            border-radius: 8px;
            margin-bottom: 10px;
        }
        
        .email-detail {
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            overflow-y: auto;
        }
        
        .detail-header {
            border-bottom: 2px solid #eee;
            padding-bottom: 20px;
            margin-bottom: 20px;
        }
        
        .detail-title {
            font-size: 24px;
            color: #2c3e50;
            margin-bottom: 15px;
        }
        
        .detail-meta {
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 10px 20px;
            color: #7f8c8d;
        }
        
        .detail-label {
            font-weight: 600;
            color: #2c3e50;
        }
        
        .detail-body {
            white-space: pre-wrap;
            font-size: 14px;
            line-height: 1.6;
            color: #34495e;
        }
        
        .status-bar {
            background: white;
            padding: 15px 30px;
            border-radius: 10px;
            margin-top: 20px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            text-align: center;
            color: #7f8c8d;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 40px;
        }
        
        .loading.active {
            display: block;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #7f8c8d;
        }
        
        .empty-state h3 {
            font-size: 20px;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📧 EML 邮件</h1>
            <div class="toolbar">
                <button class="btn btn-primary" onclick="openDirectory()">📂 打开目录</button>
                <button class="btn btn-primary" onclick="refreshEmails()">🔄 刷新</button>
                <button class="btn btn-danger" onclick="clearDatabase()">🗑️ 清空数据库</button>
                
                <div class="search-box">
                    <input type="text" class="search-input" id="searchKeyword" placeholder="搜索邮件...">
                    <select class="search-select" id="searchField">
                        <option value="all">全部字段</option>
                        <option value="subject">主题</option>
                        <option value="sender">发件人</option>
                        <option value="recipients">收件人</option>
                    </select>
                    <button class="btn btn-primary" onclick="searchEmails()">🔍 搜索</button>
                    <button class="btn btn-primary" onclick="resetSearch()">↩️ 重置</button>
                </div>
                
                <div class="view-toggle">
                    <div class="radio-btn active" onclick="switchView('list')" id="viewList">📋 列表</div>
                    <div class="radio-btn" onclick="switchView('grouped')" id="viewGrouped">📦 聚合</div>
                </div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="email-list" id="emailList">
                <div class="empty-state">
                    <h3>暂无邮件</h3>
                    <p>请先打开目录导入邮件</p>
                </div>
            </div>
            
            <div class="email-detail" id="emailDetail">
                <div class="empty-state">
                    <h3>邮件详情</h3>
                    <p>请选择左侧邮件查看详情</p>
                </div>
            </div>
        </div>
        
        <div class="status-bar" id="statusBar">
            就绪 | 邮件总数: <span id="emailCount">0</span>
        </div>
    </div>
    
    <script>
        let currentView = 'list';
        let selectedEmailId = null;
        
        // API 调用函数
        async function apiCall(url, method = 'GET') {
            try {
                const response = await fetch(url, { method });
                return await response.json();
            } catch (error) {
                console.error('API调用失败:', error);
                return null;
            }
        }
        
        // 打开目录
        async function openDirectory() {
            const dir = prompt('请输入邮件目录路径:');
            if (!dir) return;
            
            updateStatus('正在初始化...');
            
            // 这里简化处理，实际应该通过文件选择器
            // 由于浏览器安全限制，这里使用提示框模拟
            const result = await apiCall('/api/import', 'POST');
            
            if (result) {
                updateStatus('导入任务已启动...');
                setTimeout(() => {
                    refreshEmails();
                }, 2000);
            }
        }
        
        // 刷新邮件列表
        async function refreshEmails() {
            updateStatus('正在加载...');
            
            if (currentView === 'list') {
                const result = await apiCall('/api/emails');
                if (result && result.emails) {
                    renderEmailList(result.emails);
                    document.getElementById('emailCount').textContent = result.count;
                    updateStatus(`共 ${result.count} 封邮件`);
                }
            } else {
                const result = await apiCall('/api/grouped');
                if (result && result.grouped) {
                    renderGroupedEmails(result.grouped);
                    const total = Object.values(result.grouped).reduce((sum, arr) => sum + arr.length, 0);
                    document.getElementById('emailCount').textContent = total;
                    updateStatus(`共 ${total} 封邮件，${result.groups} 个主题`);
                }
            }
        }
        
        // 搜索邮件
        async function searchEmails() {
            const keyword = document.getElementById('searchKeyword').value;
            const field = document.getElementById('searchField').value;
            
            if (!keyword) {
                refreshEmails();
                return;
            }
            
            updateStatus('正在搜索...');
            
            const result = await apiCall(`/api/emails?keyword=${encodeURIComponent(keyword)}&field=${field}`);
            if (result && result.emails) {
                renderEmailList(result.emails);
                document.getElementById('emailCount').textContent = result.count;
                updateStatus(`找到 ${result.count} 封邮件`);
            }
        }
        
        // 重置搜索
        function resetSearch() {
            document.getElementById('searchKeyword').value = '';
            document.getElementById('searchField').value = 'all';
            refreshEmails();
        }
        
        // 切换视图
        function switchView(view) {
            currentView = view;
            
            document.getElementById('viewList').classList.toggle('active', view === 'list');
            document.getElementById('viewGrouped').classList.toggle('active', view === 'grouped');
            
            refreshEmails();
        }
        
        // 渲染邮件列表
        function renderEmailList(emails) {
            const container = document.getElementById('emailList');
            
            if (emails.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <h3>暂无邮件</h3>
                        <p>请先打开目录导入邮件</p>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = emails.map(email => `
                <div class="email-item ${selectedEmailId === email.id ? 'active' : ''}" 
                     onclick="selectEmail(${email.id})">
                    <div class="email-subject">${email.subject || '(无主题)'}</div>
                    <div class="email-meta">
                        <span>👤 ${email.sender || '未知'}</span>
                        <span>📅 ${formatDate(email.date_parsed)}</span>
                        <span>📎 ${email.has_attachments ? '有附件' : '无附件'}</span>
                    </div>
                </div>
            `).join('');
        }
        
        // 渲染聚合邮件
        function renderGroupedEmails(grouped) {
            const container = document.getElementById('emailList');
            
            if (Object.keys(grouped).length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <h3>暂无邮件</h3>
                        <p>请先打开目录导入邮件</p>
                    </div>
                `;
                return;
            }
            
            let html = '';
            for (const [subject, emails] of Object.entries(grouped)) {
                html += `
                    <div class="email-group">${subject} (${emails.length}封)</div>
                    ${emails.map(email => `
                        <div class="email-item ${selectedEmailId === email.id ? 'active' : ''}" 
                             onclick="selectEmail(${email.id})">
                            <div class="email-subject">${email.subject || '(无主题)'}</div>
                            <div class="email-meta">
                                <span>👤 ${email.sender || '未知'}</span>
                                <span>📅 ${formatDate(email.date_parsed)}</span>
                            </div>
                        </div>
                    `).join('')}
                `;
            }
            
            container.innerHTML = html;
        }
        
        // 选择邮件
        async function selectEmail(id) {
            selectedEmailId = id;
            
            // 更新列表选中状态
            document.querySelectorAll('.email-item').forEach(item => {
                item.classList.remove('active');
            });
            event.target.closest('.email-item').classList.add('active');
            
            // 获取邮件详情
            const result = await apiCall(`/api/email?id=${id}`);
            if (result && result.email) {
                renderEmailDetail(result.email);
            }
        }
        
        // 渲染邮件详情
        function renderEmailDetail(email) {
            const container = document.getElementById('emailDetail');
            
            container.innerHTML = `
                <div class="detail-header">
                    <div class="detail-title">${email.subject || '(无主题)'}</div>
                    <div class="detail-meta">
                        <span class="detail-label">发件人:</span>
                        <span>${email.sender || '未知'}</span>
                        <span class="detail-label">收件人:</span>
                        <span>${email.recipients || '未知'}</span>
                        <span class="detail-label">日期:</span>
                        <span>${email.date || '未知'}</span>
                        <span class="detail-label">文件:</span>
                        <span>${email.file_path}</span>
                        <span class="detail-label">大小:</span>
                        <span>${(email.file_size / 1024).toFixed(2)} KB</span>
                        <span class="detail-label">附件:</span>
                        <span>${email.has_attachments ? '有' : '无'}</span>
                    </div>
                </div>
                <div class="detail-body">${email.body_text || email.body_html || '(无正文)'}</div>
            `;
        }
        
        // 清空数据库
        async function clearDatabase() {
            if (!confirm('确定要清空数据库吗？此操作不可恢复！')) return;
            
            const result = await apiCall('/api/clear', 'POST');
            if (result) {
                refreshEmails();
                alert('数据库已清空');
            }
        }
        
        // 格式化日期
        function formatDate(dateStr) {
            if (!dateStr) return '未知';
            try {
                const date = new Date(dateStr);
                return date.toLocaleDateString('zh-CN');
            } catch {
                return dateStr;
            }
        }
        
        // 更新状态栏
        function updateStatus(message) {
            document.getElementById('statusBar').innerHTML = `${message} | 邮件总数: <span id="emailCount">${document.getElementById('emailCount').textContent}</span>`;
        }
        
        // 页面加载完成后初始化
        window.onload = async function() {
            const status = await apiCall('/api/status');
            if (status && status.initialized) {
                refreshEmails();
            } else {
                updateStatus('请先打开目录');
            }
        };
    </script>
</body>
</html>"""


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """EML 邮件管理器 Web 版主函数."""
    parser = argparse.ArgumentParser(description="EML 邮件管理器 Web 版")
    parser.add_argument("--dir", type=str, help="工作目录路径")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="服务器端口")
    args = parser.parse_args()

    # 初始化数据库和工作目录
    if args.dir:
        work_dir = Path(args.dir)
        if work_dir.exists() and work_dir.is_dir():
            EmlManagerHandler.work_dir = work_dir
            db_path = work_dir / DB_NAME
            EmlManagerHandler.db = EmailDatabase(db_path)

            # 自动导入邮件
            eml_files = list(work_dir.rglob("*.eml"))
            if eml_files:
                print(f"发现 {len(eml_files)} 个 EML 文件，开始导入...")

                # 先批量查询所有已存在的文件
                with EmlManagerHandler.db._lock:
                    cursor = EmlManagerHandler.db.conn.cursor()
                    cursor.execute(f"SELECT file_path, file_hash FROM {TABLE_NAME}")
                    existing_files = {row[0]: row[1] for row in cursor.fetchall()}

                new_count = 0
                update_count = 0

                for eml_file in eml_files:
                    email_data = parse_eml_file(eml_file)
                    if email_data:
                        file_path_str = str(eml_file)

                        if file_path_str in existing_files:
                            if existing_files[file_path_str] != email_data["file_hash"]:
                                EmlManagerHandler.db.insert_email(email_data)
                                update_count += 1
                        else:
                            EmlManagerHandler.db.insert_email(email_data)
                            new_count += 1

                print(f"导入完成: 新增 {new_count}, 更新 {update_count}, 总计 {len(eml_files)}")
    else:
        print("警告: 未指定工作目录，请在Web界面中手动导入")

    # 启动服务器
    server_address = ("", args.port)
    httpd = HTTPServer(server_address, EmlManagerHandler)

    print("EML 邮件管理器 Web 版已启动")
    print(f"访问地址: http://localhost:{args.port}")
    print("按 Ctrl+C 停止服务器")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        if EmlManagerHandler.db:
            EmlManagerHandler.db.close()
        httpd.server_close()


if __name__ == "__main__":
    main()
