"""PDF 工具模块.

提供 PDF 文件操作的常用功能封装,
支持合并、拆分、压缩、加密、水印、OCR等功能.
"""

from __future__ import annotations

from pathlib import Path

import pyflowx as px

try:
    import fitz  # PyMuPDF

    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    import pypdf

    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False


# ============================================================================
# 配置
# ============================================================================

PDF_SUFFIX = ".pdf"
DEFAULT_QUALITY = 75
DEFAULT_PASSWORD = ""


# ============================================================================
# 辅助函数
# ============================================================================


def pdf_merge(input_paths: list[Path], output_path: Path) -> None:
    """合并多个 PDF 文件."""
    if not HAS_PYPDF:
        print("未安装 pypdf 库，请安装: pip install pypdf")
        return

    writer = pypdf.PdfWriter()
    for input_path in input_paths:
        if input_path.exists():
            reader = pypdf.PdfReader(str(input_path))
            for page in reader.pages:
                writer.add_page(page)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)

    print(f"合并完成: {output_path}")


def pdf_split(input_path: Path, output_dir: Path) -> None:
    """拆分 PDF 文件为单页."""
    if not HAS_PYPDF:
        print("未安装 pypdf 库，请安装: pip install pypdf")
        return

    reader = pypdf.PdfReader(str(input_path))
    output_dir.mkdir(parents=True, exist_ok=True)

    for i, page in enumerate(reader.pages):
        writer = pypdf.PdfWriter()
        writer.add_page(page)
        output_file = output_dir / f"{input_path.stem}_page_{i + 1}.pdf"
        with open(output_file, "wb") as f:
            writer.write(f)

    print(f"拆分完成: {output_dir}")


def pdf_compress(input_path: Path, output_path: Path) -> None:
    """压缩 PDF 文件."""
    if not HAS_PYMUPDF:
        print("未安装 PyMuPDF 库，请安装: pip install PyMuPDF")
        return

    doc = fitz.open(str(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path), garbage=4, deflate=True, clean=True)
    doc.close()

    original_size = input_path.stat().st_size
    new_size = output_path.stat().st_size
    ratio = (1 - new_size / original_size) * 100
    print(f"压缩完成: {output_path} (缩小 {ratio:.1f}%)")


def pdf_encrypt(input_path: Path, output_path: Path, password: str) -> None:
    """加密 PDF 文件."""
    if not HAS_PYPDF:
        print("未安装 pypdf 库，请安装: pip install pypdf")
        return

    reader = pypdf.PdfReader(str(input_path))
    writer = pypdf.PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    writer.encrypt(user_password=password, owner_password=password, use_128bit=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)

    print(f"加密完成: {output_path}")


def pdf_decrypt(input_path: Path, output_path: Path, password: str) -> None:
    """解密 PDF 文件."""
    if not HAS_PYPDF:
        print("未安装 pypdf 库，请安装: pip install pypdf")
        return

    reader = pypdf.PdfReader(str(input_path))
    if reader.is_encrypted:
        reader.decrypt(password)

    writer = pypdf.PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)

    print(f"解密完成: {output_path}")


def pdf_extract_text(input_path: Path, output_path: Path) -> None:
    """提取 PDF 文本."""
    if not HAS_PYMUPDF:
        print("未安装 PyMuPDF 库，请安装: pip install PyMuPDF")
        return

    doc = fitz.open(str(input_path))
    text = ""
    for page in doc:
        text += page.get_text() + "\n\n"
    doc.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    print(f"文本提取完成: {output_path}")


def pdf_extract_images(input_path: Path, output_dir: Path) -> None:
    """提取 PDF 图片."""
    if not HAS_PYMUPDF:
        print("未安装 PyMuPDF 库，请安装: pip install PyMuPDF")
        return

    doc = fitz.open(str(input_path))
    output_dir.mkdir(parents=True, exist_ok=True)

    image_count = 0
    for page_num, page in enumerate(doc):
        images = page.get_images(full=True)
        for img_idx, img in enumerate(images):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_data = base_image["image"]
            image_ext = base_image["ext"]
            image_path = output_dir / f"page_{page_num + 1}_img_{img_idx + 1}.{image_ext}"
            image_path.write_bytes(image_data)
            image_count += 1

    doc.close()
    print(f"图片提取完成: {output_dir} (共 {image_count} 张)")


def pdf_add_watermark(input_path: Path, output_path: Path, text: str = "CONFIDENTIAL") -> None:
    """添加 PDF 水印."""
    if not HAS_PYMUPDF:
        print("未安装 PyMuPDF 库，请安装: pip install PyMuPDF")
        return

    doc = fitz.open(str(input_path))
    for page in doc:
        rect = page.rect
        text_width = fitz.get_text_length(text, fontsize=48)
        x = (rect.width - text_width) / 2
        y = rect.height / 2
        page.insert_text((x, y), text, fontsize=48, rotate=45, color=(0, 0, 0))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()
    print(f"水印添加完成: {output_path}")


def pdf_rotate(input_path: Path, output_path: Path, rotation: int = 90) -> None:
    """旋转 PDF 页面."""
    if not HAS_PYMUPDF:
        print("未安装 PyMuPDF 库，请安装: pip install PyMuPDF")
        return

    doc = fitz.open(str(input_path))
    for page in doc:
        page.set_rotation(rotation)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()
    print(f"旋转完成: {output_path}")


def pdf_crop(input_path: Path, output_path: Path, margins: tuple[int, int, int, int]) -> None:
    """裁剪 PDF 页面."""
    if not HAS_PYMUPDF:
        print("未安装 PyMuPDF 库，请安装: pip install PyMuPDF")
        return

    doc = fitz.open(str(input_path))
    left, top, right, bottom = margins

    for page in doc:
        rect = page.rect
        new_rect = fitz.Rect(
            rect.x0 + left,
            rect.y0 + top,
            rect.x1 - right,
            rect.y1 - bottom,
        )
        page.set_cropbox(new_rect)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()
    print(f"裁剪完成: {output_path}")


def pdf_info(input_path: Path) -> None:
    """显示 PDF 信息."""
    if not HAS_PYMUPDF:
        print("未安装 PyMuPDF 库，请安装: pip install PyMuPDF")
        return

    doc = fitz.open(str(input_path))
    print(f"文件: {input_path}")
    print(f"页数: {doc.page_count}")
    print(f"标题: {doc.metadata.get('title', 'N/A')}")
    print(f"作者: {doc.metadata.get('author', 'N/A')}")
    print(f"创建日期: {doc.metadata.get('creationDate', 'N/A')}")
    print(f"修改日期: {doc.metadata.get('modDate', 'N/A')}")
    print(f"文件大小: {input_path.stat().st_size / 1024:.1f} KB")
    doc.close()


def pdf_ocr(input_path: Path, output_path: Path, lang: str = "chi_sim+eng") -> None:
    """PDF OCR 识别."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        print("未安装 OCR 相关库，请安装: pip install pytesseract pillow")
        return

    if not HAS_PYMUPDF:
        print("未安装 PyMuPDF 库，请安装: pip install PyMuPDF")
        return

    doc = fitz.open(str(input_path))
    new_doc = fitz.open()

    for page in doc:
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        ocr_text = pytesseract.image_to_string(img, lang=lang)

        new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
        new_page.insert_image(new_page.rect, pixmap=pix)
        text_rect = fitz.Rect(0, 0, page.rect.width, page.rect.height)
        new_page.insert_textbox(text_rect, ocr_text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    new_doc.save(str(output_path))
    new_doc.close()
    doc.close()
    print(f"OCR 识别完成: {output_path}")


def pdf_reorder(input_path: Path, output_path: Path, order: list[int]) -> None:
    """重排 PDF 页面顺序."""
    if not HAS_PYPDF:
        print("未安装 pypdf 库，请安装: pip install pypdf")
        return

    reader = pypdf.PdfReader(str(input_path))
    writer = pypdf.PdfWriter()

    for page_num in order:
        if 0 <= page_num < len(reader.pages):
            writer.add_page(reader.pages[page_num])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)

    print(f"重排完成: {output_path}")


def pdf_to_images(input_path: Path, output_dir: Path, dpi: int = 300) -> None:
    """PDF 转图片."""
    if not HAS_PYMUPDF:
        print("未安装 PyMuPDF 库，请安装: pip install PyMuPDF")
        return

    doc = fitz.open(str(input_path))
    output_dir.mkdir(parents=True, exist_ok=True)

    for page_num, page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi)
        image_path = output_dir / f"{input_path.stem}_page_{page_num + 1}.png"
        pix.save(str(image_path))

    doc.close()
    print(f"转换完成: {output_dir}")


def pdf_repair(input_path: Path, output_path: Path) -> None:
    """修复 PDF 文件."""
    if not HAS_PYMUPDF:
        print("未安装 PyMuPDF 库，请安装: pip install PyMuPDF")
        return

    doc = fitz.open(str(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path), garbage=4, deflate=True, clean=True)
    doc.close()
    print(f"修复完成: {output_path}")


# ============================================================================
# TaskSpec 定义
# ============================================================================

# PDF 合并
pdf_merge_default: px.TaskSpec = px.TaskSpec("pdf_merge", fn=lambda: pdf_merge([], Path("merged.pdf")))

# PDF 拆分
pdf_split_default: px.TaskSpec = px.TaskSpec("pdf_split", fn=lambda: pdf_split(Path("input.pdf"), Path("split")))

# PDF 压缩
pdf_compress_default: px.TaskSpec = px.TaskSpec(
    "pdf_compress", fn=lambda: pdf_compress(Path("input.pdf"), Path("compressed.pdf"))
)

# PDF 加密
pdf_encrypt_default: px.TaskSpec = px.TaskSpec(
    "pdf_encrypt", fn=lambda: pdf_encrypt(Path("input.pdf"), Path("encrypted.pdf"), "password")
)

# PDF 解密
pdf_decrypt_default: px.TaskSpec = px.TaskSpec(
    "pdf_decrypt", fn=lambda: pdf_decrypt(Path("input.pdf"), Path("decrypted.pdf"), "password")
)

# PDF 提取文本
pdf_extract_text_default: px.TaskSpec = px.TaskSpec(
    "pdf_extract_text", fn=lambda: pdf_extract_text(Path("input.pdf"), Path("output.txt"))
)

# PDF 提取图片
pdf_extract_images_default: px.TaskSpec = px.TaskSpec(
    "pdf_extract_images", fn=lambda: pdf_extract_images(Path("input.pdf"), Path("images"))
)

# PDF 添加水印
pdf_watermark_default: px.TaskSpec = px.TaskSpec(
    "pdf_watermark", fn=lambda: pdf_add_watermark(Path("input.pdf"), Path("watermarked.pdf"))
)

# PDF 旋转
pdf_rotate_default: px.TaskSpec = px.TaskSpec(
    "pdf_rotate", fn=lambda: pdf_rotate(Path("input.pdf"), Path("rotated.pdf"), 90)
)

# PDF 裁剪
pdf_crop_default: px.TaskSpec = px.TaskSpec(
    "pdf_crop", fn=lambda: pdf_crop(Path("input.pdf"), Path("cropped.pdf"), (10, 10, 10, 10))
)

# PDF 信息
pdf_info_default: px.TaskSpec = px.TaskSpec("pdf_info", fn=lambda: pdf_info(Path("input.pdf")))

# PDF OCR
pdf_ocr_default: px.TaskSpec = px.TaskSpec("pdf_ocr", fn=lambda: pdf_ocr(Path("input.pdf"), Path("ocr.pdf")))

# PDF 重排
pdf_reorder_default: px.TaskSpec = px.TaskSpec(
    "pdf_reorder", fn=lambda: pdf_reorder(Path("input.pdf"), Path("reordered.pdf"), [])
)

# PDF 转图片
pdf_to_images_default: px.TaskSpec = px.TaskSpec(
    "pdf_to_images", fn=lambda: pdf_to_images(Path("input.pdf"), Path("images"))
)

# PDF 修复
pdf_repair_default: px.TaskSpec = px.TaskSpec(
    "pdf_repair", fn=lambda: pdf_repair(Path("input.pdf"), Path("repaired.pdf"))
)


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """PDF 工具主函数."""
    runner = px.CliRunner(
        strategy="thread",
        description="PDFTool - PDF 文件工具集",
        graphs={
            # 合并 PDF
            "m": px.Graph.from_specs([pdf_merge_default]),
            # 拆分 PDF
            "s": px.Graph.from_specs([pdf_split_default]),
            # 压缩 PDF
            "c": px.Graph.from_specs([pdf_compress_default]),
            # 加密 PDF
            "e": px.Graph.from_specs([pdf_encrypt_default]),
            # 解密 PDF
            "d": px.Graph.from_specs([pdf_decrypt_default]),
            # 提取文本
            "xt": px.Graph.from_specs([pdf_extract_text_default]),
            # 提取图片
            "xi": px.Graph.from_specs([pdf_extract_images_default]),
            # 添加水印
            "w": px.Graph.from_specs([pdf_watermark_default]),
            # 旋转 PDF
            "r": px.Graph.from_specs([pdf_rotate_default]),
            # 裁剪 PDF
            "crop": px.Graph.from_specs([pdf_crop_default]),
            # 显示信息
            "i": px.Graph.from_specs([pdf_info_default]),
            # OCR 识别
            "ocr": px.Graph.from_specs([pdf_ocr_default]),
            # 重排页面
            "order": px.Graph.from_specs([pdf_reorder_default]),
            # 转换图片
            "img": px.Graph.from_specs([pdf_to_images_default]),
            # 修复 PDF
            "repair": px.Graph.from_specs([pdf_repair_default]),
        },
    )
    runner.run_cli()
