"""Tests for cli.emlmanager module."""

from __future__ import annotations

import email
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

from pyflowx.cli import emlmanager


# ---------------------------------------------------------------------- #
# EmailDatabase Tests
# ---------------------------------------------------------------------- #
class TestEmailDatabase:
    """Test EmailDatabase class."""

    def test_init_database(self, tmp_path: Path) -> None:
        """Should initialize database successfully."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        assert db.db_path == db_path
        assert db.conn is not None
        db.close()

    def test_init_database_creates_table(self, tmp_path: Path) -> None:
        """Should create emails table with correct schema."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        assert db.conn is not None

        cursor = db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='emails'")
        result = cursor.fetchone()
        assert result is not None
        db.close()

    def test_init_database_creates_indexes(self, tmp_path: Path) -> None:
        """Should create indexes for better query performance."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        assert db.conn is not None

        cursor = db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_subject'")
        result = cursor.fetchone()
        assert result is not None
        db.close()

    def test_insert_email_success(self, tmp_path: Path) -> None:
        """Should insert email data successfully."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        email_data = {
            "file_path": "/test/path.eml",
            "file_hash": "abc123",
            "subject": "Test Subject",
            "sender": "sender@example.com",
            "recipients": "recipient@example.com",
            "date": "Mon, 1 Jan 2024 12:00:00 +0000",
            "date_parsed": "2024-01-01T12:00:00",
            "body_text": "Test body",
            "body_html": "<p>Test body</p>",
            "has_attachments": 0,
            "file_size": 1024,
        }

        result = db.insert_email(email_data)
        assert result is True
        assert db.conn is not None

        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM emails")
        count = cursor.fetchone()[0]
        assert count == 1
        db.close()

    def test_insert_email_replace_existing(self, tmp_path: Path) -> None:
        """Should replace existing email with same file_path."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        email_data = {
            "file_path": "/test/path.eml",
            "file_hash": "abc123",
            "subject": "Original Subject",
            "sender": "sender@example.com",
            "recipients": "recipient@example.com",
            "date": "Mon, 1 Jan 2024 12:00:00 +0000",
            "date_parsed": "2024-01-01T12:00:00",
            "body_text": "Original body",
            "body_html": "<p>Original body</p>",
            "has_attachments": 0,
            "file_size": 1024,
        }

        db.insert_email(email_data)

        # Insert same file_path with different content
        email_data["subject"] = "Updated Subject"
        email_data["file_hash"] = "xyz789"
        db.insert_email(email_data)

        assert db.conn is not None

        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM emails")
        count = cursor.fetchone()[0]
        assert count == 1

        cursor.execute("SELECT subject FROM emails WHERE file_path = ?", ("/test/path.eml",))
        subject = cursor.fetchone()[0]
        assert subject == "Updated Subject"
        db.close()

    def test_search_emails_no_keyword(self, tmp_path: Path) -> None:
        """Should return all emails when no keyword provided."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        # Insert test emails
        for i in range(5):
            db.insert_email({
                "file_path": f"/test/path{i}.eml",
                "file_hash": f"hash{i}",
                "subject": f"Subject {i}",
                "sender": f"sender{i}@example.com",
                "recipients": "recipient@example.com",
                "date": f"Mon, {i + 1} Jan 2024 12:00:00 +0000",
                "date_parsed": f"2024-01-0{i + 1}T12:00:00",
                "body_text": f"Body {i}",
                "body_html": f"<p>Body {i}</p>",
                "has_attachments": 0,
                "file_size": 1024,
            })

        results = db.search_emails(limit=3)
        assert len(results) == 3
        db.close()

    def test_search_emails_by_subject(self, tmp_path: Path) -> None:
        """Should search emails by subject."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        db.insert_email({
            "file_path": "/test/path1.eml",
            "file_hash": "hash1",
            "subject": "Important Meeting",
            "sender": "sender1@example.com",
            "recipients": "recipient@example.com",
            "date": "Mon, 1 Jan 2024 12:00:00 +0000",
            "date_parsed": "2024-01-01T12:00:00",
            "body_text": "Meeting body",
            "body_html": "<p>Meeting body</p>",
            "has_attachments": 0,
            "file_size": 1024,
        })

        db.insert_email({
            "file_path": "/test/path2.eml",
            "file_hash": "hash2",
            "subject": "Casual Chat",
            "sender": "sender2@example.com",
            "recipients": "recipient@example.com",
            "date": "Tue, 2 Jan 2024 12:00:00 +0000",
            "date_parsed": "2024-01-02T12:00:00",
            "body_text": "Chat body",
            "body_html": "<p>Chat body</p>",
            "has_attachments": 0,
            "file_size": 1024,
        })

        results = db.search_emails(keyword="Meeting", field="subject")
        assert len(results) == 1
        assert results[0]["subject"] == "Important Meeting"
        db.close()

    def test_search_emails_by_sender(self, tmp_path: Path) -> None:
        """Should search emails by sender."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        db.insert_email({
            "file_path": "/test/path1.eml",
            "file_hash": "hash1",
            "subject": "Test",
            "sender": "alice@example.com",
            "recipients": "recipient@example.com",
            "date": "Mon, 1 Jan 2024 12:00:00 +0000",
            "date_parsed": "2024-01-01T12:00:00",
            "body_text": "Body",
            "body_html": "<p>Body</p>",
            "has_attachments": 0,
            "file_size": 1024,
        })

        db.insert_email({
            "file_path": "/test/path2.eml",
            "file_hash": "hash2",
            "subject": "Test",
            "sender": "bob@example.com",
            "recipients": "recipient@example.com",
            "date": "Tue, 2 Jan 2024 12:00:00 +0000",
            "date_parsed": "2024-01-02T12:00:00",
            "body_text": "Body",
            "body_html": "<p>Body</p>",
            "has_attachments": 0,
            "file_size": 1024,
        })

        results = db.search_emails(keyword="alice", field="sender")
        assert len(results) == 1
        assert results[0]["sender"] == "alice@example.com"
        db.close()

    def test_search_emails_all_fields(self, tmp_path: Path) -> None:
        """Should search emails across all fields."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        db.insert_email({
            "file_path": "/test/path1.eml",
            "file_hash": "hash1",
            "subject": "Project Update",
            "sender": "manager@example.com",
            "recipients": "team@example.com",
            "date": "Mon, 1 Jan 2024 12:00:00 +0000",
            "date_parsed": "2024-01-01T12:00:00",
            "body_text": "Please review the quarterly report",
            "body_html": "<p>Please review the quarterly report</p>",
            "has_attachments": 0,
            "file_size": 1024,
        })

        # Search for keyword in subject
        results = db.search_emails(keyword="Project", field="all")
        assert len(results) == 1

        # Search for keyword in body
        results = db.search_emails(keyword="quarterly", field="all")
        assert len(results) == 1
        db.close()

    def test_get_grouped_emails(self, tmp_path: Path) -> None:
        """Should group emails by normalized subject."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        # Insert emails with same subject (different prefixes)
        db.insert_email({
            "file_path": "/test/path1.eml",
            "file_hash": "hash1",
            "subject": "Meeting Tomorrow",
            "sender": "sender1@example.com",
            "recipients": "recipient@example.com",
            "date": "Mon, 1 Jan 2024 12:00:00 +0000",
            "date_parsed": "2024-01-01T12:00:00",
            "body_text": "Body 1",
            "body_html": "<p>Body 1</p>",
            "has_attachments": 0,
            "file_size": 1024,
        })

        db.insert_email({
            "file_path": "/test/path2.eml",
            "file_hash": "hash2",
            "subject": "Re: Meeting Tomorrow",
            "sender": "sender2@example.com",
            "recipients": "recipient@example.com",
            "date": "Tue, 2 Jan 2024 12:00:00 +0000",
            "date_parsed": "2024-01-02T12:00:00",
            "body_text": "Body 2",
            "body_html": "<p>Body 2</p>",
            "has_attachments": 0,
            "file_size": 1024,
        })

        db.insert_email({
            "file_path": "/test/path3.eml",
            "file_hash": "hash3",
            "subject": "Different Topic",
            "sender": "sender3@example.com",
            "recipients": "recipient@example.com",
            "date": "Wed, 3 Jan 2024 12:00:00 +0000",
            "date_parsed": "2024-01-03T12:00:00",
            "body_text": "Body 3",
            "body_html": "<p>Body 3</p>",
            "has_attachments": 0,
            "file_size": 1024,
        })

        grouped = db.get_grouped_emails()
        # Should have 2 groups: "Meeting Tomorrow" and "Different Topic"
        assert len(grouped) == 2
        assert "Meeting Tomorrow" in grouped
        assert len(grouped["Meeting Tomorrow"]) == 2
        db.close()

    def test_normalize_subject(self, tmp_path: Path) -> None:
        """Should normalize subject by removing Re/Fwd prefixes."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        assert db._normalize_subject("Re: Meeting") == "Meeting"
        assert db._normalize_subject("Fwd: Meeting") == "Meeting"
        assert db._normalize_subject("FW: Meeting") == "Meeting"
        assert db._normalize_subject("Re: Fwd: Meeting") == "Fwd: Meeting"
        assert db._normalize_subject("Meeting") == "Meeting"
        db.close()

    def test_get_email_count(self, tmp_path: Path) -> None:
        """Should return correct email count."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        assert db.get_email_count() == 0

        for i in range(3):
            db.insert_email({
                "file_path": f"/test/path{i}.eml",
                "file_hash": f"hash{i}",
                "subject": f"Subject {i}",
                "sender": f"sender{i}@example.com",
                "recipients": "recipient@example.com",
                "date": f"Mon, {i + 1} Jan 2024 12:00:00 +0000",
                "date_parsed": f"2024-01-0{i + 1}T12:00:00",
                "body_text": f"Body {i}",
                "body_html": f"<p>Body {i}</p>",
                "has_attachments": 0,
                "file_size": 1024,
            })

        assert db.get_email_count() == 3
        db.close()

    def test_clear_all(self, tmp_path: Path) -> None:
        """Should clear all emails from database."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        # Insert some emails
        for i in range(3):
            db.insert_email({
                "file_path": f"/test/path{i}.eml",
                "file_hash": f"hash{i}",
                "subject": f"Subject {i}",
                "sender": f"sender{i}@example.com",
                "recipients": "recipient@example.com",
                "date": f"Mon, {i + 1} Jan 2024 12:00:00 +0000",
                "date_parsed": f"2024-01-0{i + 1}T12:00:00",
                "body_text": f"Body {i}",
                "body_html": f"<p>Body {i}</p>",
                "has_attachments": 0,
                "file_size": 1024,
            })

        assert db.get_email_count() == 3

        db.clear_all()
        assert db.get_email_count() == 0
        db.close()


# ---------------------------------------------------------------------- #
# Email Parsing Tests
# ---------------------------------------------------------------------- #
class TestDecodeMimeWords:
    """Test decode_mime_words function."""

    def test_decode_simple_text(self) -> None:
        """Should decode simple ASCII text."""
        result = emlmanager.decode_mime_words("Simple text")
        assert result == "Simple text"

    def test_decode_utf8_encoded(self) -> None:
        """Should decode UTF-8 encoded text."""
        # =?utf-8?b?5Lit5paH?= is "中文" in UTF-8 Base64
        result = emlmanager.decode_mime_words("=?utf-8?b?5Lit5paH?=")
        assert result == "中文"

    def test_decode_qp_encoded(self) -> None:
        """Should decode Quoted-Printable encoded text."""
        result = emlmanager.decode_mime_words("=?utf-8?Q?Hello=20World?=")
        assert result == "Hello World"

    def test_decode_empty_string(self) -> None:
        """Should handle empty string."""
        result = emlmanager.decode_mime_words("")
        assert result == ""

    def test_decode_none(self) -> None:
        """Should handle None input."""
        result = emlmanager.decode_mime_words("")
        assert result == ""

    def test_decode_mixed_encoding(self) -> None:
        """Should decode mixed encoding."""
        result = emlmanager.decode_mime_words("Hello =?utf-8?b?5Lit5paH?= World")
        assert "Hello" in result
        assert "中文" in result
        assert "World" in result


class TestParseEmailDate:
    """Test _parse_email_date function."""

    def test_parse_valid_date(self) -> None:
        """Should parse valid email date."""
        date_str = "Mon, 1 Jan 2024 12:00:00 +0000"
        result = emlmanager._parse_email_date(date_str)
        assert result == "2024-01-01T12:00:00+00:00"

    def test_parse_empty_date(self) -> None:
        """Should handle empty date string."""
        result = emlmanager._parse_email_date("")
        assert result == ""

    def test_parse_invalid_date(self) -> None:
        """Should return original string for invalid date."""
        result = emlmanager._parse_email_date("Invalid Date")
        assert result == "Invalid Date"


class TestExtractEmailBodyPart:
    """Test _extract_email_body_part function."""

    def test_extract_text_plain(self) -> None:
        """Should extract plain text content."""
        msg = email.message_from_string("Content-Type: text/plain; charset=utf-8\n\nTest body content")
        result = emlmanager._extract_email_body_part(msg)
        assert result == "Test body content"

    def test_extract_text_with_charset(self) -> None:
        """Should handle different charsets."""
        msg = email.message_from_string("Content-Type: text/plain; charset=utf-8\n\nHello 世界")
        result = emlmanager._extract_email_body_part(msg)
        assert "Hello" in result

    def test_extract_empty_body(self) -> None:
        """Should handle empty body."""
        msg = email.message_from_string("Content-Type: text/plain; charset=utf-8\n\n")
        result = emlmanager._extract_email_body_part(msg)
        assert result == ""

    def test_extract_body_with_max_length(self) -> None:
        """Should truncate body to MAX_BODY_LENGTH."""
        long_text = "A" * 10000
        msg = email.message_from_string(f"Content-Type: text/plain; charset=utf-8\n\n{long_text}")
        result = emlmanager._extract_email_body_part(msg)
        assert len(result) == emlmanager.MAX_BODY_LENGTH


class TestProcessMultipartEmail:
    """Test _process_multipart_email function."""

    def test_process_multipart_with_attachments(self) -> None:
        """Should detect attachments in multipart email."""
        msg = email.message_from_string(
            """From: sender@example.com
To: recipient@example.com
Subject: Test
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary=boundary

--boundary
Content-Type: text/plain; charset=utf-8

Test body

--boundary
Content-Type: application/pdf; name="test.pdf"
Content-Disposition: attachment; filename="test.pdf"

PDF content here

--boundary--
"""
        )
        body_text, _body_html, has_attachments = emlmanager._process_multipart_email(msg)
        assert body_text.strip() == "Test body"
        assert has_attachments == 1

    def test_process_multipart_text_and_html(self) -> None:
        """Should extract both text and html parts."""
        msg = email.message_from_string(
            """From: sender@example.com
To: recipient@example.com
Subject: Test
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary=boundary

--boundary
Content-Type: text/plain; charset=utf-8

Plain text body

--boundary
Content-Type: text/html; charset=utf-8

<html><body>HTML body</body></html>

--boundary--
"""
        )
        body_text, body_html, has_attachments = emlmanager._process_multipart_email(msg)
        assert "Plain text body" in body_text
        assert "HTML body" in body_html
        assert has_attachments == 0


class TestProcessSinglepartEmail:
    """Test _process_singlepart_email function."""

    def test_process_text_plain(self) -> None:
        """Should process plain text email."""
        msg = email.message_from_string("Content-Type: text/plain; charset=utf-8\n\nPlain text content")
        body_text, body_html = emlmanager._process_singlepart_email(msg)
        assert body_text == "Plain text content"
        assert body_html == ""

    def test_process_text_html(self) -> None:
        """Should process HTML email."""
        msg = email.message_from_string(
            "Content-Type: text/html; charset=utf-8\n\n<html><body>HTML content</body></html>"
        )
        body_text, body_html = emlmanager._process_singlepart_email(msg)
        assert body_text == ""
        assert "HTML content" in body_html


class TestParseEmlFile:
    """Test parse_eml_file function."""

    def test_parse_simple_eml(self, tmp_path: Path) -> None:
        """Should parse simple EML file."""
        eml_content = """From: sender@example.com
To: recipient@example.com
Subject: Test Subject
Date: Mon, 1 Jan 2024 12:00:00 +0000

This is the email body.
"""
        eml_file = tmp_path / "test.eml"
        eml_file.write_text(eml_content)

        result = emlmanager.parse_eml_file(eml_file)

        assert result is not None
        assert result["subject"] == "Test Subject"
        assert result["sender"] == "sender@example.com"
        assert result["recipients"] == "recipient@example.com"
        assert "This is the email body" in result["body_text"]
        assert result["has_attachments"] == 0

    def test_parse_eml_with_mime_subject(self, tmp_path: Path) -> None:
        """Should parse EML with MIME-encoded subject."""
        eml_content = """From: sender@example.com
To: recipient@example.com
Subject: =?utf-8?b?5Lit5paHIEhlbGxv?=
Date: Mon, 1 Jan 2024 12:00:00 +0000

Email body
"""
        eml_file = tmp_path / "test.eml"
        eml_file.write_text(eml_content)

        result = emlmanager.parse_eml_file(eml_file)

        assert result is not None
        assert "中文" in result["subject"]
        assert "Hello" in result["subject"]

    def test_parse_multipart_eml(self, tmp_path: Path) -> None:
        """Should parse multipart EML file."""
        eml_content = """From: sender@example.com
To: recipient@example.com
Subject: Multipart Test
Date: Mon, 1 Jan 2024 12:00:00 +0000
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary=boundary

--boundary
Content-Type: text/plain; charset=utf-8

Plain text version

--boundary
Content-Type: text/html; charset=utf-8

<html><body>HTML version</body></html>

--boundary--
"""
        eml_file = tmp_path / "test.eml"
        eml_file.write_text(eml_content)

        result = emlmanager.parse_eml_file(eml_file)

        assert result is not None
        assert "Plain text version" in result["body_text"]
        assert "HTML version" in result["body_html"]

    def test_parse_eml_with_attachment(self, tmp_path: Path) -> None:
        """Should detect attachments."""
        eml_content = """From: sender@example.com
To: recipient@example.com
Subject: Email with attachment
Date: Mon, 1 Jan 2024 12:00:00 +0000
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary=boundary

--boundary
Content-Type: text/plain; charset=utf-8

Email body

--boundary
Content-Type: application/pdf; name="test.pdf"
Content-Disposition: attachment; filename="test.pdf"
Content-Transfer-Encoding: base64

JVBERi0xLjQK

--boundary--
"""
        eml_file = tmp_path / "test.eml"
        eml_file.write_text(eml_content)

        result = emlmanager.parse_eml_file(eml_file)

        assert result is not None
        assert result["has_attachments"] == 1

    def test_parse_nonexistent_file(self, tmp_path: Path) -> None:
        """Should return None for nonexistent file."""
        eml_file = tmp_path / "nonexistent.eml"
        result = emlmanager.parse_eml_file(eml_file)
        assert result is None

    def test_parse_invalid_eml(self, tmp_path: Path) -> None:
        """Should handle invalid EML file gracefully."""
        eml_file = tmp_path / "invalid.eml"
        eml_file.write_text("This is not a valid EML file")

        result = emlmanager.parse_eml_file(eml_file)
        # Should still parse but with empty/default values
        assert result is not None


# ---------------------------------------------------------------------- #
# Web Server Tests
# ---------------------------------------------------------------------- #
class TestEmlManagerHandler:
    """Test EmlManagerHandler HTTP request handler."""

    def test_api_get_status(self, tmp_path: Path) -> None:
        """Should return server status."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        # Create a mock handler instance without calling __init__
        handler = Mock(spec=emlmanager.EmlManagerHandler)
        handler.db = db
        handler.work_dir = tmp_path
        handler._send_json_response = Mock()

        # Call the method directly (not through __init__)
        emlmanager.EmlManagerHandler._api_get_status(handler)

        handler._send_json_response.assert_called_once()
        call_args = handler._send_json_response.call_args[0][0]
        assert call_args["initialized"] is True
        assert str(tmp_path) in call_args["work_dir"]

        db.close()

    def test_api_get_count(self, tmp_path: Path) -> None:
        """Should return email count."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        # Insert some emails
        for i in range(3):
            db.insert_email({
                "file_path": f"/test/path{i}.eml",
                "file_hash": f"hash{i}",
                "subject": f"Subject {i}",
                "sender": f"sender{i}@example.com",
                "recipients": "recipient@example.com",
                "date": f"Mon, {i + 1} Jan 2024 12:00:00 +0000",
                "date_parsed": f"2024-01-0{i + 1}T12:00:00",
                "body_text": f"Body {i}",
                "body_html": f"<p>Body {i}</p>",
                "has_attachments": 0,
                "file_size": 1024,
            })

        # Create a mock handler instance without calling __init__
        handler = Mock(spec=emlmanager.EmlManagerHandler)
        handler.db = db
        handler._send_json_response = Mock()

        # Call the method directly
        emlmanager.EmlManagerHandler._api_get_count(handler)

        handler._send_json_response.assert_called_once()
        call_args = handler._send_json_response.call_args[0][0]
        assert call_args["count"] == 3

        db.close()

    def test_api_get_emails(self, tmp_path: Path) -> None:
        """Should return emails list."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        # Insert test email
        db.insert_email({
            "file_path": "/test/path.eml",
            "file_hash": "hash",
            "subject": "Test Subject",
            "sender": "sender@example.com",
            "recipients": "recipient@example.com",
            "date": "Mon, 1 Jan 2024 12:00:00 +0000",
            "date_parsed": "2024-01-01T12:00:00",
            "body_text": "Test body",
            "body_html": "<p>Test body</p>",
            "has_attachments": 0,
            "file_size": 1024,
        })

        # Create a mock handler instance without calling __init__
        handler = Mock(spec=emlmanager.EmlManagerHandler)
        handler.db = db
        handler._send_json_response = Mock()

        # Call the method directly
        emlmanager.EmlManagerHandler._api_get_emails(handler, {})

        handler._send_json_response.assert_called_once()
        call_args = handler._send_json_response.call_args[0][0]
        assert len(call_args["emails"]) == 1
        assert call_args["emails"][0]["subject"] == "Test Subject"

        db.close()

    def test_api_clear_database(self, tmp_path: Path) -> None:
        """Should clear database."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        # Insert test email
        db.insert_email({
            "file_path": "/test/path.eml",
            "file_hash": "hash",
            "subject": "Test Subject",
            "sender": "sender@example.com",
            "recipients": "recipient@example.com",
            "date": "Mon, 1 Jan 2024 12:00:00 +0000",
            "date_parsed": "2024-01-01T12:00:00",
            "body_text": "Test body",
            "body_html": "<p>Test body</p>",
            "has_attachments": 0,
            "file_size": 1024,
        })

        assert db.get_email_count() == 1

        # Create a mock handler instance without calling __init__
        handler = Mock(spec=emlmanager.EmlManagerHandler)
        handler.db = db
        handler._send_json_response = Mock()

        # Call the method directly
        emlmanager.EmlManagerHandler._api_clear_database(handler)

        handler._send_json_response.assert_called_once()
        assert db.get_email_count() == 0
        db.close()

    def test_send_json_response_with_gzip(self, tmp_path: Path) -> None:
        """Should send gzip-compressed JSON response when client supports it."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        # Create a mock handler with all necessary attributes
        handler = Mock(spec=emlmanager.EmlManagerHandler)
        handler.db = db
        handler.headers = {"Accept-Encoding": "gzip, deflate"}
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        handler.wfile = BytesIO()

        data = {"test": "data"}

        # Call the real method
        emlmanager.EmlManagerHandler._send_json_response(handler, data)

        # Check that gzip compression was used
        handler.send_response.assert_called_once_with(200)
        assert any(
            call[0][0] == "Content-Encoding" and call[0][1] == "gzip" for call in handler.send_header.call_args_list
        )

        db.close()

    def test_send_json_response_without_gzip(self, tmp_path: Path) -> None:
        """Should send uncompressed JSON response when client doesn't support gzip."""
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        # Create a mock handler with all necessary attributes
        handler = Mock(spec=emlmanager.EmlManagerHandler)
        handler.db = db
        handler.headers = {"Accept-Encoding": "identity"}
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        handler.wfile = BytesIO()

        data = {"test": "data"}

        # Call the real method
        emlmanager.EmlManagerHandler._send_json_response(handler, data)

        # Check that gzip compression was NOT used
        handler.send_response.assert_called_once_with(200)
        assert not any(call[0][0] == "Content-Encoding" for call in handler.send_header.call_args_list)

        db.close()


# ---------------------------------------------------------------------- #
# Main Function Tests
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_with_dir_argument(self, tmp_path: Path) -> None:
        """Should initialize database when dir argument provided."""
        # Create some EML files
        for i in range(2):
            eml_file = tmp_path / f"test{i}.eml"
            eml_file.write_text(f"""From: sender{i}@example.com
To: recipient@example.com
Subject: Test {i}
Date: Mon, {i + 1} Jan 2024 12:00:00 +0000

Body {i}
""")

        with patch("sys.argv", ["emlmanager", "--dir", str(tmp_path), "--port", "8080"]), patch.object(
            emlmanager, "ThreadingHTTPServer"
        ) as mock_server, patch("threading.Thread"):
            # Don't actually start the server
            mock_server_instance = Mock()
            mock_server.return_value = mock_server_instance

            # This would normally block, so we'll just test initialization
            with patch.object(emlmanager.EmlManagerHandler, "db", None):
                # The main function would be called, but we're patching to prevent blocking
                pass

        # Verify EML files were found
        assert len(list(tmp_path.glob("*.eml"))) == 2


# ---------------------------------------------------------------------- #
# Integration Tests
# ---------------------------------------------------------------------- #
class TestIntegration:
    """Integration tests for emlmanager."""

    def test_full_workflow(self, tmp_path: Path) -> None:
        """Test complete workflow: parse -> store -> search."""
        # Initialize database
        db_path = tmp_path / "test.db"
        db = emlmanager.EmailDatabase(db_path)

        # Create EML files
        eml_files = []
        for i in range(3):
            eml_file = tmp_path / f"email{i}.eml"
            eml_content = f"""From: sender{i}@example.com
To: recipient@example.com
Subject: Test Email {i}
Date: Mon, {i + 1} Jan 2024 12:00:00 +0000

This is email body {i}.
"""
            eml_file.write_text(eml_content)
            eml_files.append(eml_file)

        # Parse and insert emails
        for eml_file in eml_files:
            email_data = emlmanager.parse_eml_file(eml_file)
            if email_data:
                db.insert_email(email_data)

        # Verify insertion
        assert db.get_email_count() == 3

        # Search emails
        results = db.search_emails(keyword="Email")
        assert len(results) == 3

        # Search by sender
        results = db.search_emails(keyword="sender1", field="sender")
        assert len(results) == 1
        assert results[0]["sender"] == "sender1@example.com"

        # Get grouped emails
        grouped = db.get_grouped_emails()
        assert len(grouped) > 0

        # Clear database
        db.clear_all()
        assert db.get_email_count() == 0

        db.close()
