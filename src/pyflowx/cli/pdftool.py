"""PDF 工具模块.

提供 PDF 文件操作的常用功能封装,
支持合并、拆分、压缩、加密、水印、OCR等功能.
"""

from __future__ import annotations

import argparse
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
# CLI Runner
# ============================================================================


def main() -> None:  # noqa: PLR0912
    """PDF 工具主函数."""
    parser = argparse.ArgumentParser(
        description="PDFTool - PDF 文件工具集",
        usage="pdftool <command> [options]",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 合并 PDF 命令
    merge_parser = subparsers.add_parser("m", help="合并 PDF 文件")
    merge_parser.add_argument("inputs", nargs="+", help="输入 PDF 文件路径")
    merge_parser.add_argument("--output", type=str, default="merged.pdf", help="输出文件路径")

    # 拆分 PDF 命令
    split_parser = subparsers.add_parser("s", help="拆分 PDF 文件为单页")
    split_parser.add_argument("input", help="输入 PDF 文件路径")
    split_parser.add_argument("--output-dir", type=str, default="split", help="输出目录")

    # 压缩 PDF 命令
    compress_parser = subparsers.add_parser("c", help="压缩 PDF 文件")
    compress_parser.add_argument("input", help="输入 PDF 文件路径")
    compress_parser.add_argument("--output", type=str, default="compressed.pdf", help="输出文件路径")

    # 加密 PDF 命令
    encrypt_parser = subparsers.add_parser("e", help="加密 PDF 文件")
    encrypt_parser.add_argument("input", help="输入 PDF 文件路径")
    encrypt_parser.add_argument("--output", type=str, default="encrypted.pdf", help="输出文件路径")
    encrypt_parser.add_argument("--password", type=str, required=True, help="密码")

    # 解密 PDF 命令
    decrypt_parser = subparsers.add_parser("d", help="解密 PDF 文件")
    decrypt_parser.add_argument("input", help="输入 PDF 文件路径")
    decrypt_parser.add_argument("--output", type=str, default="decrypted.pdf", help="输出文件路径")
    decrypt_parser.add_argument("--password", type=str, required=True, help="密码")

    # 提取文本命令
    extract_text_parser = subparsers.add_parser("xt", help="提取 PDF 文本")
    extract_text_parser.add_argument("input", help="输入 PDF 文件路径")
    extract_text_parser.add_argument("--output", type=str, default="output.txt", help="输出文件路径")

    # 提取图片命令
    extract_images_parser = subparsers.add_parser("xi", help="提取 PDF 图片")
    extract_images_parser.add_argument("input", help="输入 PDF 文件路径")
    extract_images_parser.add_argument("--output-dir", type=str, default="images", help="输出目录")

    # 添加水印命令
    watermark_parser = subparsers.add_parser("w", help="添加 PDF 水印")
    watermark_parser.add_argument("input", help="输入 PDF 文件路径")
    watermark_parser.add_argument("--output", type=str, default="watermarked.pdf", help="输出文件路径")
    watermark_parser.add_argument("--text", type=str, default="CONFIDENTIAL", help="水印文本")

    # 旋转 PDF 命令
    rotate_parser = subparsers.add_parser("r", help="旋转 PDF 页面")
    rotate_parser.add_argument("input", help="输入 PDF 文件路径")
    rotate_parser.add_argument("--output", type=str, default="rotated.pdf", help="输出文件路径")
    rotate_parser.add_argument("--rotation", type=int, default=90, help="旋转角度 (90, 180, 270)")

    # 裁剪 PDF 命令
    crop_parser = subparsers.add_parser("crop", help="裁剪 PDF 页面")
    crop_parser.add_argument("input", help="输入 PDF 文件路径")
    crop_parser.add_argument("--output", type=str, default="cropped.pdf", help="输出文件路径")
    crop_parser.add_argument("--left", type=int, default=10, help="左边裁剪")
    crop_parser.add_argument("--top", type=int, default=10, help="顶部裁剪")
    crop_parser.add_argument("--right", type=int, default=10, help="右边裁剪")
    crop_parser.add_argument("--bottom", type=int, default=10, help="底部裁剪")

    # 显示信息命令
    info_parser = subparsers.add_parser("i", help="显示 PDF 信息")
    info_parser.add_argument("input", help="输入 PDF 文件路径")

    # OCR 识别命令
    ocr_parser = subparsers.add_parser("ocr", help="PDF OCR 识别")
    ocr_parser.add_argument("input", help="输入 PDF 文件路径")
    ocr_parser.add_argument("--output", type=str, default="ocr.pdf", help="输出文件路径")
    ocr_parser.add_argument("--lang", type=str, default="chi_sim+eng", help="OCR 语言")

    # 转换图片命令
    to_images_parser = subparsers.add_parser("img", help="PDF 转图片")
    to_images_parser.add_argument("input", help="输入 PDF 文件路径")
    to_images_parser.add_argument("--output-dir", type=str, default="images", help="输出目录")
    to_images_parser.add_argument("--dpi", type=int, default=300, help="图片 DPI")

    # 修复 PDF 命令
    repair_parser = subparsers.add_parser("repair", help="修复 PDF 文件")
    repair_parser.add_argument("input", help="输入 PDF 文件路径")
    repair_parser.add_argument("--output", type=str, default="repaired.pdf", help="输出文件路径")

    args = parser.parse_args()

    if args.command == "m":
        graph = px.Graph.from_specs(
            [px.TaskSpec("pdf_merge", fn=pdf_merge, args=([Path(p) for p in args.inputs], Path(args.output)))]
        )
    elif args.command == "s":
        graph = px.Graph.from_specs(
            [px.TaskSpec("pdf_split", fn=pdf_split, args=(Path(args.input), Path(args.output_dir)))]
        )
    elif args.command == "c":
        graph = px.Graph.from_specs(
            [px.TaskSpec("pdf_compress", fn=pdf_compress, args=(Path(args.input), Path(args.output)))]
        )
    elif args.command == "e":
        graph = px.Graph.from_specs(
            [px.TaskSpec("pdf_encrypt", fn=pdf_encrypt, args=(Path(args.input), Path(args.output), args.password))]
        )
    elif args.command == "d":
        graph = px.Graph.from_specs(
            [px.TaskSpec("pdf_decrypt", fn=pdf_decrypt, args=(Path(args.input), Path(args.output), args.password))]
        )
    elif args.command == "xt":
        graph = px.Graph.from_specs(
            [px.TaskSpec("pdf_extract_text", fn=pdf_extract_text, args=(Path(args.input), Path(args.output)))]
        )
    elif args.command == "xi":
        graph = px.Graph.from_specs(
            [px.TaskSpec("pdf_extract_images", fn=pdf_extract_images, args=(Path(args.input), Path(args.output_dir)))]
        )
    elif args.command == "w":
        graph = px.Graph.from_specs(
            [
                px.TaskSpec(
                    "pdf_watermark",
                    fn=pdf_add_watermark,
                    args=(Path(args.input), Path(args.output)),
                    kwargs={"text": args.text},
                )
            ]
        )
    elif args.command == "r":
        graph = px.Graph.from_specs(
            [
                px.TaskSpec(
                    "pdf_rotate",
                    fn=pdf_rotate,
                    args=(Path(args.input), Path(args.output)),
                    kwargs={"rotation": args.rotation},
                )
            ]
        )
    elif args.command == "crop":
        graph = px.Graph.from_specs(
            [
                px.TaskSpec(
                    "pdf_crop",
                    fn=pdf_crop,
                    args=(Path(args.input), Path(args.output)),
                    kwargs={"margins": (args.left, args.top, args.right, args.bottom)},
                )
            ]
        )
    elif args.command == "i":
        graph = px.Graph.from_specs([px.TaskSpec("pdf_info", fn=pdf_info, args=(Path(args.input),))])
    elif args.command == "ocr":
        graph = px.Graph.from_specs(
            [px.TaskSpec("pdf_ocr", fn=pdf_ocr, args=(Path(args.input), Path(args.output)), kwargs={"lang": args.lang})]
        )
    elif args.command == "img":
        graph = px.Graph.from_specs(
            [
                px.TaskSpec(
                    "pdf_to_images",
                    fn=pdf_to_images,
                    args=(Path(args.input), Path(args.output_dir)),
                    kwargs={"dpi": args.dpi},
                )
            ]
        )
    elif args.command == "repair":
        graph = px.Graph.from_specs(
            [px.TaskSpec("pdf_repair", fn=pdf_repair, args=(Path(args.input), Path(args.output)))]
        )
    else:
        parser.print_help()
        return

    px.run(graph, strategy="thread")
