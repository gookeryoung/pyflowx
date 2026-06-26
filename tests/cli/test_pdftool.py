"""Tests for cli.pdftool module."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import pyflowx as px
from pyflowx.cli import pdftool


# ---------------------------------------------------------------------- #
# pdf_merge
# ---------------------------------------------------------------------- #
class TestPdfMerge:
    """Test pdf_merge function."""

    def test_pdf_merge_files(self, tmp_path: Path) -> None:
        """Should merge PDF files."""
        pytest.importorskip("pypdf")
        input_files = [tmp_path / "input1.pdf", tmp_path / "input2.pdf"]
        for f in input_files:
            f.write_bytes(b"PDF content")
        output_file = tmp_path / "merged.pdf"

        with patch("pypdf.PdfReader"), patch("pypdf.PdfWriter") as mock_writer:
            mock_writer_instance = MagicMock()
            mock_writer.return_value = mock_writer_instance
            pdftool.pdf_merge(input_files, output_file)
            assert mock_writer_instance.write.called


# ---------------------------------------------------------------------- #
# pdf_split
# ---------------------------------------------------------------------- #
class TestPdfSplit:
    """Test pdf_split function."""

    def test_pdf_split_file(self, tmp_path: Path) -> None:
        """Should split PDF file."""
        pytest.importorskip("pypdf")
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_dir = tmp_path / "split"

        with patch("pypdf.PdfReader") as mock_reader, patch("pypdf.PdfWriter"):
            mock_reader_instance = MagicMock()
            mock_reader.return_value = mock_reader_instance
            mock_reader_instance.pages = [MagicMock()]
            pdftool.pdf_split(input_file, output_dir)
            assert output_dir.exists()


# ---------------------------------------------------------------------- #
# pdf_compress
# ---------------------------------------------------------------------- #
class TestPdfCompress:
    """Test pdf_compress function."""

    def test_pdf_compress_file(self, tmp_path: Path) -> None:
        """Should compress PDF file."""
        pytest.importorskip("fitz")
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "compressed.pdf"

        with patch("fitz.open") as mock_fitz_open:
            mock_doc = MagicMock()
            mock_fitz_open.return_value = mock_doc

            # Mock save to actually create the file
            def mock_save(*args: Any, **kwargs: Any):
                output_file.write_bytes(b"Compressed PDF")

            mock_doc.save = mock_save
            pdftool.pdf_compress(input_file, output_file)
            assert output_file.exists()


# ---------------------------------------------------------------------- #
# pdf_extract_text
# ---------------------------------------------------------------------- #
class TestPdfExtractText:
    """Test pdf_extract_text function."""

    def test_pdf_extract_text_file(self, tmp_path: Path) -> None:
        """Should extract text from PDF."""
        pytest.importorskip("fitz")
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "output.txt"

        with patch("fitz.open") as mock_fitz_open:
            mock_doc = MagicMock()
            mock_page = MagicMock()
            mock_page.get_text.return_value = "Test text"
            mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
            mock_fitz_open.return_value = mock_doc
            pdftool.pdf_extract_text(input_file, output_file)
            assert output_file.exists()


# ---------------------------------------------------------------------- #
# pdf_extract_images
# ---------------------------------------------------------------------- #
class TestPdfExtractImages:
    """Test pdf_extract_images function."""

    def test_pdf_extract_images_file(self, tmp_path: Path) -> None:
        """Should extract images from PDF."""
        pytest.importorskip("fitz")
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_dir = tmp_path / "images"

        with patch("fitz.open") as mock_fitz_open:
            mock_doc = MagicMock()
            mock_page = MagicMock()
            mock_page.get_images.return_value = [[0]]
            mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
            mock_doc.extract_image.return_value = {"image": b"image data", "ext": "png"}
            mock_fitz_open.return_value = mock_doc
            pdftool.pdf_extract_images(input_file, output_dir)
            assert output_dir.exists()


# ---------------------------------------------------------------------- #
# pdf_add_watermark
# ---------------------------------------------------------------------- #
class TestPdfAddWatermark:
    """Test pdf_add_watermark function."""

    def test_pdf_add_watermark_file(self, tmp_path: Path) -> None:
        """Should add watermark to PDF."""
        pytest.importorskip("fitz")
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "watermarked.pdf"

        with patch("fitz.open") as mock_fitz_open, patch("fitz.get_text_length") as mock_text_length:
            mock_doc = MagicMock()
            mock_page = MagicMock()
            mock_page.rect = MagicMock(width=800, height=600)
            mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
            mock_fitz_open.return_value = mock_doc
            mock_text_length.return_value = 100
            pdftool.pdf_add_watermark(input_file, output_file)
            assert mock_doc.save.called


# ---------------------------------------------------------------------- #
# pdf_rotate
# ---------------------------------------------------------------------- #
class TestPdfRotate:
    """Test pdf_rotate function."""

    def test_pdf_rotate_file_90(self, tmp_path: Path) -> None:
        """Should rotate PDF by 90 degrees."""
        pytest.importorskip("fitz")
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "rotated.pdf"

        with patch("fitz.open") as mock_fitz_open:
            mock_doc = MagicMock()
            mock_page = MagicMock()
            mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
            mock_fitz_open.return_value = mock_doc
            pdftool.pdf_rotate(input_file, output_file, rotation=90)
            assert mock_doc.save.called

    def test_pdf_rotate_file_180(self, tmp_path: Path) -> None:
        """Should rotate PDF by 180 degrees."""
        pytest.importorskip("fitz")
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "rotated.pdf"

        with patch("fitz.open") as mock_fitz_open:
            mock_doc = MagicMock()
            mock_page = MagicMock()
            mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
            mock_fitz_open.return_value = mock_doc
            pdftool.pdf_rotate(input_file, output_file, rotation=180)
            assert mock_doc.save.called


# ---------------------------------------------------------------------- #
# pdf_crop
# ---------------------------------------------------------------------- #
class TestPdfCrop:
    """Test pdf_crop function."""

    def test_pdf_crop_file(self, tmp_path: Path) -> None:
        """Should crop PDF."""
        pytest.importorskip("fitz")
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "cropped.pdf"

        with patch("fitz.open") as mock_fitz_open, patch("fitz.Rect"):
            mock_doc = MagicMock()
            mock_page = MagicMock()
            mock_page.rect = MagicMock(x0=0, y0=0, x1=800, y1=600)
            mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
            mock_fitz_open.return_value = mock_doc
            pdftool.pdf_crop(input_file, output_file, margins=(10, 10, 10, 10))
            assert mock_doc.save.called


# ---------------------------------------------------------------------- #
# pdf_info
# ---------------------------------------------------------------------- #
class TestPdfInfo:
    """Test pdf_info function."""

    def test_pdf_info_file(self, tmp_path: Path) -> None:
        """Should show PDF info."""
        pytest.importorskip("fitz")
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")

        with patch("fitz.open") as mock_fitz_open:
            mock_doc = MagicMock()
            mock_doc.page_count = 10
            mock_doc.metadata = {"title": "Test", "author": "Author"}
            mock_fitz_open.return_value = mock_doc
            pdftool.pdf_info(input_file)
            assert mock_fitz_open.called


# ---------------------------------------------------------------------- #
# pdf_ocr
# ---------------------------------------------------------------------- #
class TestPdfOcr:
    """Test pdf_ocr function."""

    def test_pdf_ocr_file(self, tmp_path: Path) -> None:
        """Should OCR PDF."""
        pytest.importorskip("fitz")
        pytest.importorskip("pytesseract")
        pytest.importorskip("PIL")
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "ocr.pdf"

        with patch("fitz.open") as mock_fitz_open, patch("PIL.Image.frombytes"), patch(
            "pytesseract.image_to_string"
        ) as mock_ocr:
            mock_doc = MagicMock()
            mock_page = MagicMock()
            mock_page.rect = MagicMock(width=800, height=600)
            mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
            mock_fitz_open.return_value = mock_doc
            mock_ocr.return_value = "OCR text"
            pdftool.pdf_ocr(input_file, output_file)
            # Should complete OCR


# ---------------------------------------------------------------------- #
# pdf_repair
# ---------------------------------------------------------------------- #
class TestPdfRepair:
    """Test pdf_repair function."""

    def test_pdf_repair_file(self, tmp_path: Path) -> None:
        """Should repair PDF."""
        pytest.importorskip("fitz")
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "repaired.pdf"

        with patch("fitz.open") as mock_fitz_open:
            mock_doc = MagicMock()
            mock_fitz_open.return_value = mock_doc
            pdftool.pdf_repair(input_file, output_file)
            assert mock_doc.save.called


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_merge_command(self, tmp_path: Path) -> None:
        """main() should handle merge command."""
        input_files = [tmp_path / "input1.pdf", tmp_path / "input2.pdf"]
        for f in input_files:
            f.write_bytes(b"PDF content")

        with patch("sys.argv", ["pdftool", "m", str(input_files[0]), str(input_files[1])]), patch.object(
            px, "run"
        ) as mock_run:
            pdftool.main()
            assert mock_run.called

    def test_main_split_command(self, tmp_path: Path) -> None:
        """main() should handle split command."""
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")

        with patch("sys.argv", ["pdftool", "s", str(input_file)]), patch.object(px, "run") as mock_run:
            pdftool.main()
            assert mock_run.called

    def test_main_compress_command(self, tmp_path: Path) -> None:
        """main() should handle compress command."""
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")

        with patch("sys.argv", ["pdftool", "c", str(input_file)]), patch.object(px, "run") as mock_run:
            pdftool.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help."""
        with patch("sys.argv", ["pdftool"]):
            pdftool.main()
            # Should print help and return
