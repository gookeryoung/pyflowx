"""Tests for cli.pdftool module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import pyflowx as px
from pyflowx.cli import pdftool


# ---------------------------------------------------------------------- #
# pdf_merge
# ---------------------------------------------------------------------- #
class TestPdfMerge:
    """Test pdf_merge function."""

    def test_pdf_merge_single_file(self, tmp_path: Path) -> None:
        """Should merge single PDF file."""
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "merged.pdf"

        with patch("pypdf.PdfMerger") as mock_merger:
            pdftool.pdf_merge([input_file], output_file)
            assert mock_merger.called

    def test_pdf_merge_multiple_files(self, tmp_path: Path) -> None:
        """Should merge multiple PDF files."""
        input_files = [
            tmp_path / "input1.pdf",
            tmp_path / "input2.pdf",
            tmp_path / "input3.pdf",
        ]
        for f in input_files:
            f.write_bytes(b"PDF content")
        output_file = tmp_path / "merged.pdf"

        with patch("pypdf.PdfMerger") as mock_merger:
            pdftool.pdf_merge(input_files, output_file)
            assert mock_merger.called


# ---------------------------------------------------------------------- #
# pdf_split
# ---------------------------------------------------------------------- #
class TestPdfSplit:
    """Test pdf_split function."""

    def test_pdf_split_single_file(self, tmp_path: Path) -> None:
        """Should split single PDF file."""
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_dir = tmp_path / "split"
        output_dir.mkdir()

        with patch("pypdf.PdfReader") as mock_reader:
            mock_reader.return_value.pages = [MagicMock(), MagicMock()]
            pdftool.pdf_split(input_file, output_dir)
            assert mock_reader.called

    def test_pdf_split_creates_output_dir(self, tmp_path: Path) -> None:
        """Should create output directory if it doesn't exist."""
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_dir = tmp_path / "split"

        with patch("pypdf.PdfReader") as mock_reader:
            mock_reader.return_value.pages = [MagicMock()]
            pdftool.pdf_split(input_file, output_dir)
            assert output_dir.exists()


# ---------------------------------------------------------------------- #
# pdf_compress
# ---------------------------------------------------------------------- #
class TestPdfCompress:
    """Test pdf_compress function."""

    def test_pdf_compress_file(self, tmp_path: Path) -> None:
        """Should compress PDF file."""
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "compressed.pdf"

        with patch("pypdf.PdfReader") as mock_reader, patch("pypdf.PdfWriter") as mock_writer:
            pdftool.pdf_compress(input_file, output_file)
            assert mock_reader.called
            assert mock_writer.called


# ---------------------------------------------------------------------- #
# pdf_encrypt
# ---------------------------------------------------------------------- #
class TestPdfEncrypt:
    """Test pdf_encrypt function."""

    def test_pdf_encrypt_file(self, tmp_path: Path) -> None:
        """Should encrypt PDF file."""
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "encrypted.pdf"

        with patch("pypdf.PdfReader") as mock_reader, patch("pypdf.PdfWriter") as mock_writer:
            pdftool.pdf_encrypt(input_file, output_file, "password")
            assert mock_reader.called
            assert mock_writer.called


# ---------------------------------------------------------------------- #
# pdf_decrypt
# ---------------------------------------------------------------------- #
class TestPdfDecrypt:
    """Test pdf_decrypt function."""

    def test_pdf_decrypt_file(self, tmp_path: Path) -> None:
        """Should decrypt PDF file."""
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "decrypted.pdf"

        with patch("pypdf.PdfReader") as mock_reader, patch("pypdf.PdfWriter") as mock_writer:
            pdftool.pdf_decrypt(input_file, output_file, "password")
            assert mock_reader.called
            assert mock_writer.called


# ---------------------------------------------------------------------- #
# pdf_extract_text
# ---------------------------------------------------------------------- #
class TestPdfExtractText:
    """Test pdf_extract_text function."""

    def test_pdf_extract_text_file(self, tmp_path: Path) -> None:
        """Should extract text from PDF file."""
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "output.txt"

        with patch("pypdf.PdfReader") as mock_reader:
            mock_reader.return_value.pages = [MagicMock()]
            pdftool.pdf_extract_text(input_file, output_file)
            assert mock_reader.called


# ---------------------------------------------------------------------- #
# pdf_extract_images
# ---------------------------------------------------------------------- #
class TestPdfExtractImages:
    """Test pdf_extract_images function."""

    def test_pdf_extract_images_file(self, tmp_path: Path) -> None:
        """Should extract images from PDF file."""
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_dir = tmp_path / "images"
        output_dir.mkdir()

        with patch("pypdf.PdfReader") as mock_reader:
            mock_reader.return_value.pages = [MagicMock()]
            pdftool.pdf_extract_images(input_file, output_dir)
            assert mock_reader.called


# ---------------------------------------------------------------------- #
# pdf_add_watermark
# ---------------------------------------------------------------------- #
class TestPdfAddWatermark:
    """Test pdf_add_watermark function."""

    def test_pdf_add_watermark_file(self, tmp_path: Path) -> None:
        """Should add watermark to PDF file."""
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "watermarked.pdf"

        with patch("pypdf.PdfReader") as mock_reader, patch("pypdf.PdfWriter") as mock_writer:
            pdftool.pdf_add_watermark(input_file, output_file, text="CONFIDENTIAL")
            assert mock_reader.called
            assert mock_writer.called


# ---------------------------------------------------------------------- #
# pdf_rotate
# ---------------------------------------------------------------------- #
class TestPdfRotate:
    """Test pdf_rotate function."""

    def test_pdf_rotate_file_90(self, tmp_path: Path) -> None:
        """Should rotate PDF file by 90 degrees."""
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "rotated.pdf"

        with patch("pypdf.PdfReader") as mock_reader, patch("pypdf.PdfWriter") as mock_writer:
            pdftool.pdf_rotate(input_file, output_file, rotation=90)
            assert mock_reader.called
            assert mock_writer.called

    def test_pdf_rotate_file_180(self, tmp_path: Path) -> None:
        """Should rotate PDF file by 180 degrees."""
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "rotated.pdf"

        with patch("pypdf.PdfReader") as mock_reader, patch("pypdf.PdfWriter") as mock_writer:
            pdftool.pdf_rotate(input_file, output_file, rotation=180)
            assert mock_reader.called
            assert mock_writer.called


# ---------------------------------------------------------------------- #
# pdf_crop
# ---------------------------------------------------------------------- #
class TestPdfCrop:
    """Test pdf_crop function."""

    def test_pdf_crop_file(self, tmp_path: Path) -> None:
        """Should crop PDF file."""
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "cropped.pdf"

        with patch("pypdf.PdfReader") as mock_reader, patch("pypdf.PdfWriter") as mock_writer:
            pdftool.pdf_crop(input_file, output_file, margins=(10, 10, 10, 10))
            assert mock_reader.called
            assert mock_writer.called


# ---------------------------------------------------------------------- #
# pdf_info
# ---------------------------------------------------------------------- #
class TestPdfInfo:
    """Test pdf_info function."""

    def test_pdf_info_file(self, tmp_path: Path) -> None:
        """Should show info of PDF file."""
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")

        with patch("pypdf.PdfReader") as mock_reader:
            pdftool.pdf_info(input_file)
            assert mock_reader.called


# ---------------------------------------------------------------------- #
# pdf_ocr
# ---------------------------------------------------------------------- #
class TestPdfOcr:
    """Test pdf_ocr function."""

    def test_pdf_ocr_file(self, tmp_path: Path) -> None:
        """Should OCR PDF file."""
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "ocr.pdf"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            pdftool.pdf_ocr(input_file, output_file, lang="chi_sim+eng")
            assert mock_run.called


# ---------------------------------------------------------------------- #
# pdf_to_images
# ---------------------------------------------------------------------- #
class TestPdfToImages:
    """Test pdf_to_images function."""

    def test_pdf_to_images_file(self, tmp_path: Path) -> None:
        """Should convert PDF to images."""
        pytest.importorskip("pdf2image")
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_dir = tmp_path / "images"
        output_dir.mkdir()

        with patch("pdf2image.convert_from_path") as mock_convert:
            mock_convert.return_value = [MagicMock()]
            pdftool.pdf_to_images(input_file, output_dir, dpi=300)
            assert mock_convert.called


# ---------------------------------------------------------------------- #
# pdf_repair
# ---------------------------------------------------------------------- #
class TestPdfRepair:
    """Test pdf_repair function."""

    def test_pdf_repair_file(self, tmp_path: Path) -> None:
        """Should repair PDF file."""
        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "repaired.pdf"

        with patch("pypdf.PdfReader") as mock_reader, patch("pypdf.PdfWriter") as mock_writer:
            pdftool.pdf_repair(input_file, output_file)
            assert mock_reader.called
            assert mock_writer.called


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_merge_single_file(self) -> None:
        """main() should handle merge command with single file."""
        with patch("sys.argv", ["pdftool", "m", "input.pdf"]), patch.object(px, "run") as mock_run, patch.object(
            pdftool, "pdf_merge"
        ):
            pdftool.main()
            assert mock_run.called

    def test_main_merge_multiple_files(self) -> None:
        """main() should handle merge command with multiple files."""
        with patch("sys.argv", ["pdftool", "m", "input1.pdf", "input2.pdf", "input3.pdf"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(pdftool, "pdf_merge"):
            pdftool.main()
            assert mock_run.called

    def test_main_merge_custom_output(self) -> None:
        """main() should handle merge command with custom output."""
        with patch("sys.argv", ["pdftool", "m", "input.pdf", "--output", "custom.pdf"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(pdftool, "pdf_merge"):
            pdftool.main()
            assert mock_run.called

    def test_main_split_file(self) -> None:
        """main() should handle split command."""
        with patch("sys.argv", ["pdftool", "s", "input.pdf"]), patch.object(px, "run") as mock_run, patch.object(
            pdftool, "pdf_split"
        ):
            pdftool.main()
            assert mock_run.called

    def test_main_split_custom_output_dir(self) -> None:
        """main() should handle split command with custom output dir."""
        with patch("sys.argv", ["pdftool", "s", "input.pdf", "--output-dir", "split"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(pdftool, "pdf_split"):
            pdftool.main()
            assert mock_run.called

    def test_main_compress_file(self) -> None:
        """main() should handle compress command."""
        with patch("sys.argv", ["pdftool", "c", "input.pdf"]), patch.object(px, "run") as mock_run, patch.object(
            pdftool, "pdf_compress"
        ):
            pdftool.main()
            assert mock_run.called

    def test_main_encrypt_file(self) -> None:
        """main() should handle encrypt command."""
        with patch("sys.argv", ["pdftool", "e", "input.pdf", "--password", "pass"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(pdftool, "pdf_encrypt"):
            pdftool.main()
            assert mock_run.called

    def test_main_decrypt_file(self) -> None:
        """main() should handle decrypt command."""
        with patch("sys.argv", ["pdftool", "d", "input.pdf", "--password", "pass"]), patch.object(
            px, "run"
        ) as mock_run, patch.object(pdftool, "pdf_decrypt"):
            pdftool.main()
            assert mock_run.called

    def test_main_extract_text_file(self) -> None:
        """main() should handle extract text command."""
        with patch("sys.argv", ["pdftool", "xt", "input.pdf"]), patch.object(px, "run") as mock_run, patch.object(
            pdftool, "pdf_extract_text"
        ):
            pdftool.main()
            assert mock_run.called

    def test_main_extract_images_file(self) -> None:
        """main() should handle extract images command."""
        with patch("sys.argv", ["pdftool", "xi", "input.pdf"]), patch.object(px, "run") as mock_run, patch.object(
            pdftool, "pdf_extract_images"
        ):
            pdftool.main()
            assert mock_run.called

    def test_main_watermark_file(self) -> None:
        """main() should handle watermark command."""
        with patch("sys.argv", ["pdftool", "w", "input.pdf"]), patch.object(px, "run") as mock_run, patch.object(
            pdftool, "pdf_add_watermark"
        ):
            pdftool.main()
            assert mock_run.called

    def test_main_rotate_file(self) -> None:
        """main() should handle rotate command."""
        with patch("sys.argv", ["pdftool", "r", "input.pdf"]), patch.object(px, "run") as mock_run, patch.object(
            pdftool, "pdf_rotate"
        ):
            pdftool.main()
            assert mock_run.called

    def test_main_crop_file(self) -> None:
        """main() should handle crop command."""
        with patch("sys.argv", ["pdftool", "crop", "input.pdf"]), patch.object(px, "run") as mock_run, patch.object(
            pdftool, "pdf_crop"
        ):
            pdftool.main()
            assert mock_run.called

    def test_main_info_file(self) -> None:
        """main() should handle info command."""
        with patch("sys.argv", ["pdftool", "i", "input.pdf"]), patch.object(px, "run") as mock_run, patch.object(
            pdftool, "pdf_info"
        ):
            pdftool.main()
            assert mock_run.called

    def test_main_ocr_file(self) -> None:
        """main() should handle ocr command."""
        with patch("sys.argv", ["pdftool", "ocr", "input.pdf"]), patch.object(px, "run") as mock_run, patch.object(
            pdftool, "pdf_ocr"
        ):
            pdftool.main()
            assert mock_run.called

    def test_main_to_images_file(self) -> None:
        """main() should handle to images command."""
        with patch("sys.argv", ["pdftool", "img", "input.pdf"]), patch.object(px, "run") as mock_run, patch.object(
            pdftool, "pdf_to_images"
        ):
            pdftool.main()
            assert mock_run.called

    def test_main_repair_file(self) -> None:
        """main() should handle repair command."""
        with patch("sys.argv", ["pdftool", "repair", "input.pdf"]), patch.object(px, "run") as mock_run, patch.object(
            pdftool, "pdf_repair"
        ):
            pdftool.main()
            assert mock_run.called

    def test_main_with_no_args_shows_help(self) -> None:
        """main() with no args should show help and exit."""
        with patch("sys.argv", ["pdftool"]), pytest.raises(SystemExit) as exc_info:
            pdftool.main()
        assert exc_info.value.code == 2

    def test_main_creates_task_spec_with_correct_name(self) -> None:
        """main() should create TaskSpec with correct name."""
        with patch("sys.argv", ["pdftool", "m", "input.pdf"]), patch.object(px, "run") as mock_run, patch.object(
            pdftool, "pdf_merge"
        ):
            pdftool.main()
            graph = mock_run.call_args[0][0]
            task_names = list(graph.all_specs().keys())
            assert "pdf_merge" in task_names

    def test_main_uses_thread_strategy(self) -> None:
        """main() should use thread strategy."""
        with patch("sys.argv", ["pdftool", "m", "input.pdf"]), patch.object(px, "run") as mock_run, patch.object(
            pdftool, "pdf_merge"
        ):
            pdftool.main()
            assert mock_run.call_args[1]["strategy"] == "thread"
