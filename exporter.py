import os
import re
import html
import time
import shutil
import tempfile
import base64
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pypandoc
from typing import List, Optional, Dict
from models import Question, QuestionType

# Tự động đảm bảo pandoc khả dụng
try:
    pypandoc.get_pandoc_version()
except OSError:
    pypandoc.download_pandoc()

# Khởi tạo Session với cơ chế tự động thử lại khi gặp lỗi Rate-limit (429, 500, 502, 503, 504)
_session = requests.Session()
_retries = Retry(
    total=4,
    backoff_factor=0.3,
    status_forcelist=[429, 500, 502, 503, 504],
    raise_on_status=False
)
_adapter = HTTPAdapter(max_retries=_retries, pool_connections=20, pool_maxsize=20)
_session.mount("http://", _adapter)
_session.mount("https://", _adapter)


def clean_statement_text(stmt: str) -> str:
    """Loại bỏ ký tự gạch đầu dòng hoặc dấu chấm tròn dư thừa trong các mệnh đề Đúng/Sai."""
    if not stmt:
        return ""
    return re.sub(r'^\s*[\-\*\•]\s*', '', stmt).strip()


def format_ds_statement_with_label(stmt: str, index: int) -> str:
    """Đảm bảo các mệnh đề luôn có tiền tố nhãn a), b), c), d) chuẩn xác."""
    labels = ['a', 'b', 'c', 'd']
    clean_stmt = clean_statement_text(stmt)
    if not re.match(r'^[a-dA-D][\.\)\:-]', clean_stmt):
        lbl = labels[index] if index < len(labels) else f"({index + 1})"
        clean_stmt = f"{lbl}) {clean_stmt}"
    return clean_stmt


def generate_ds_table(tf_statements: list, show_answers: bool = False) -> List[str]:
    lines = [
        "| Mệnh đề | Đ.S |",
        "| :" + "-" * 80 + " | :" + "-" * 5 + ": |"
    ]
    for stmt_idx, (stmt, status) in enumerate(tf_statements):
        clean_stmt = format_ds_statement_with_label(stmt, stmt_idx)
        if show_answers:
            chk_val = "Đ" if str(status).strip() in ["Đúng", "D", "True", "T", "Đ"] else (
                "S" if str(status).strip() in ["Sai", "S", "False", "F", "S"] else str(status)
            )
            lines.append(f"| {clean_stmt} | {chk_val} |")
        else:
            lines.append(f"| {clean_stmt} | |")
    lines.append("")
    return lines


OPENXML_TLN_TABLE = (
    "```{=openxml}\n"
    "<w:tbl>\n"
    "  <w:tblPr>\n"
    "    <w:jc w:val=\"right\"/>\n"
    "    <w:tblBorders>\n"
    "      <w:top w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>\n"
    "      <w:left w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>\n"
    "      <w:bottom w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>\n"
    "      <w:right w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>\n"
    "      <w:insideH w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>\n"
    "      <w:insideV w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>\n"
    "    </w:tblBorders>\n"
    "  </w:tblPr>\n"
    "  <w:tblGrid>\n"
    "    <w:gridCol w:w=\"454\"/>\n"
    "    <w:gridCol w:w=\"454\"/>\n"
    "    <w:gridCol w:w=\"454\"/>\n"
    "    <w:gridCol w:w=\"454\"/>\n"
    "    <w:gridCol w:w=\"454\"/>\n"
    "  </w:tblGrid>\n"
    "  <w:tr>\n"
    "    <w:trPr><w:trHeight w:val=\"454\" w:hRule=\"exact\"/></w:trPr>\n"
    "    <w:tc><w:tcPr><w:tcW w:w=\"454\" w:type=\"dxa\"/><w:vAlign w:val=\"center\"/></w:tcPr><w:p/></w:tc>\n"
    "    <w:tc><w:tcPr><w:tcW w:w=\"454\" w:type=\"dxa\"/><w:vAlign w:val=\"center\"/></w:tcPr><w:p/></w:tc>\n"
    "    <w:tc><w:tcPr><w:tcW w:w=\"454\" w:type=\"dxa\"/><w:vAlign w:val=\"center\"/></w:tcPr><w:p/></w:tc>\n"
    "    <w:tc><w:tcPr><w:tcW w:w=\"454\" w:type=\"dxa\"/><w:vAlign w:val=\"center\"/></w:tcPr><w:p/></w:tc>\n"
    "    <w:tc><w:tcPr><w:tcW w:w=\"454\" w:type=\"dxa\"/><w:vAlign w:val=\"center\"/></w:tcPr><w:p/></w:tc>\n"
    "  </w:tr>\n"
    "</w:tbl>\n"
    "```\n"
)

LINE_STRING = "________________________________________________________________________________\n\n"


def generate_header_html(header_info: dict) -> str:
    """Tạo bảng tiêu đề 2x2 định dạng OpenXML chuẩn cho file Word (.docx)."""
    if not header_info:
        return ""
    school_name = html.escape(header_info.get("school_name", "").strip().upper())
    exam_title = html.escape(header_info.get("exam_title", "").strip().upper())
    sub_title = html.escape(header_info.get("sub_title", "").strip())
    duration = str(header_info.get("duration", 90))

    openxml = (
        "```{=openxml}\n"
        "<w:tbl>\n"
        "  <w:tblPr>\n"
        "    <w:tblW w:w=\"0\" w:type=\"auto\"/>\n"
        "    <w:jc w:val=\"center\"/>\n"
        "    <w:tblBorders>\n"
        "      <w:top w:val=\"none\" w:sz=\"0\" w:space=\"0\" w:color=\"auto\"/>\n"
        "      <w:left w:val=\"none\" w:sz=\"0\" w:space=\"0\" w:color=\"auto\"/>\n"
        "      <w:bottom w:val=\"none\" w:sz=\"0\" w:space=\"0\" w:color=\"auto\"/>\n"
        "      <w:right w:val=\"none\" w:sz=\"0\" w:space=\"0\" w:color=\"auto\"/>\n"
        "      <w:insideH w:val=\"none\" w:sz=\"0\" w:space=\"0\" w:color=\"auto\"/>\n"
        "      <w:insideV w:val=\"none\" w:sz=\"0\" w:space=\"0\" w:color=\"auto\"/>\n"
        "    </w:tblBorders>\n"
        "  </w:tblPr>\n"
        "  <w:tblGrid>\n"
        "    <w:gridCol w:w=\"4300\"/>\n"
        "    <w:gridCol w:w=\"5300\"/>\n"
        "  </w:tblGrid>\n"
        "  <w:tr>\n"
        "    <w:tc>\n"
        "      <w:tcPr><w:tcW w:w=\"4300\" w:type=\"dxa\"/><w:vAlign w:val=\"top\"/></w:tcPr>\n"
        "      <w:p>\n"
        "        <w:pPr><w:jc w:val=\"center\"/></w:pPr>\n"
        "        <w:r><w:rPr><w:rFonts w:ascii=\"Times New Roman\" w:hAnsi=\"Times New Roman\"/><w:b/><w:sz w:val=\"22\"/></w:rPr><w:t>" + school_name + "</w:t></w:r>\n"
        "      </w:p>\n"
        "    </w:tc>\n"
        "    <w:tc>\n"
        "      <w:tcPr><w:tcW w:w=\"5300\" w:type=\"dxa\"/><w:vAlign w:val=\"top\"/></w:tcPr>\n"
        "      <w:p>\n"
        "        <w:pPr><w:jc w:val=\"center\"/></w:pPr>\n"
        "        <w:r><w:rPr><w:rFonts w:ascii=\"Times New Roman\" w:hAnsi=\"Times New Roman\"/><w:b/><w:sz w:val=\"22\"/></w:rPr><w:t>" + exam_title + "</w:t></w:r>\n"
        "      </w:p>\n"
        "    </w:tc>\n"
        "  </w:tr>\n"
        "  <w:tr>\n"
        "    <w:tc>\n"
        "      <w:tcPr><w:tcW w:w=\"4300\" w:type=\"dxa\"/><w:vAlign w:val=\"top\"/></w:tcPr>\n"
        "      <w:p>\n"
        "        <w:pPr><w:jc w:val=\"center\"/></w:pPr>\n"
        "        <w:r><w:rPr><w:rFonts w:ascii=\"Times New Roman\" w:hAnsi=\"Times New Roman\"/><w:b/><w:sz w:val=\"22\"/></w:rPr><w:t>" + sub_title + "</w:t></w:r>\n"
        "      </w:p>\n"
        "    </w:tc>\n"
        "    <w:tc>\n"
        "      <w:tcPr><w:tcW w:w=\"5300\" w:type=\"dxa\"/><w:vAlign w:val=\"top\"/></w:tcPr>\n"
        "      <w:p>\n"
        "        <w:pPr><w:jc w:val=\"center\"/></w:pPr>\n"
        "        <w:r><w:rPr><w:rFonts w:ascii=\"Times New Roman\" w:hAnsi=\"Times New Roman\"/><w:sz w:val=\"22\"/></w:rPr><w:t>Thời gian: " + duration + " phút (không kể thời gian phát đề)</w:t></w:r>\n"
        "      </w:p>\n"
        "    </w:tc>\n"
        "  </w:tr>\n"
        "</w:tbl>\n"
        "<w:p>\n"
        "  <w:pPr>\n"
        "    <w:pBdr>\n"
        "      <w:bottom w:val=\"single\" w:sz=\"8\" w:space=\"1\" w:color=\"auto\"/>\n"
        "    </w:pBdr>\n"
        "  </w:pPr>\n"
        "</w:p>\n"
        "```\n"
    )
    return openxml


def _save_image_to_workspace(img_src: Optional[str], temp_dir: str, filename_base: str) -> Optional[str]:
    """Tải hoặc sao chép ảnh vào workspace tạm thời, đảm bảo không bị lỗi đường dẫn hoặc chặn mạng."""
    if not img_src or not isinstance(img_src, str):
        return None
    
    img_src = img_src.strip()
    if not img_src or img_src.lower() in ["none", "null", ""]:
        return None

    # 1. File cục bộ
    if os.path.exists(img_src):
        try:
            ext = os.path.splitext(img_src)[1] or ".png"
            target_filename = f"{filename_base}{ext}"
            target_path = os.path.join(temp_dir, target_filename)
            shutil.copy2(img_src, target_path)
            return target_filename
        except Exception:
            return None

    # 2. Base64
    if img_src.startswith("data:image/"):
        try:
            header, encoded = img_src.split(",", 1)
            ext = ".png"
            if "jpeg" in header or "jpg" in header:
                ext = ".jpg"
            elif "webp" in header:
                ext = ".webp"
            data = base64.b64decode(encoded)
            target_filename = f"{filename_base}{ext}"
            target_path = os.path.join(temp_dir, target_filename)
            with open(target_path, "wb") as f:
                f.write(data)
            return target_filename
        except Exception as e:
            print(f"Lỗi giải mã Base64: {e}")
            return None

    # 3. URL Trực tuyến (ImgBB, Google Drive...)
    if img_src.startswith("http://") or img_src.startswith("https://"):
        try:
            if "drive.google.com" in img_src:
                m = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', img_src)
                if m:
                    g_id = m.group(1)
                    img_src = f"https://lh3.googleusercontent.com/d/{g_id}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Referer": "https://imgbb.com/"
            }
            
            res = _session.get(img_src, headers=headers, timeout=20, allow_redirects=True)

            # Xử lý nếu link là trang HTML Viewer của ImgBB
            content_type = res.headers.get("Content-Type", "").lower()
            if "text/html" in content_type:
                html_text = res.text
                og_match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html_text)
                if not og_match:
                    og_match = re.search(r'<img[^>]+src=["\'](https?://i\.ibb\.co/[^"\']+)["\']', html_text)
                
                if og_match:
                    direct_url = og_match.group(1)
                    res = _session.get(direct_url, headers=headers, timeout=20)
                    content_type = res.headers.get("Content-Type", "").lower()

            if res.status_code == 200 and len(res.content) > 100:
                ext = ".png"
                if "jpeg" in content_type or ".jpg" in img_src.lower() or ".jpeg" in img_src.lower():
                    ext = ".jpg"
                elif "webp" in content_type or ".webp" in img_src.lower():
                    ext = ".webp"

                target_filename = f"{filename_base}{ext}"
                target_path = os.path.join(temp_dir, target_filename)
                with open(target_path, "wb") as f:
                    f.write(res.content)
                time.sleep(0.04)  # Nghỉ ngắn tránh kích hoạt giới hạn Cloudflare khi tải hàng loạt
                return target_filename
            else:
                print(f"Không thể tải ảnh ({img_src}) - HTTP Status: {res.status_code}")
        except Exception as e:
            print(f"Lỗi kết nối khi tải ảnh ({img_src}): {e}")
            return None

    return None


def _resolve_all_inline_images(text: str, temp_dir: str, prefix: str) -> str:
    """Tải và chuyển đổi toàn bộ ảnh nhúng Markdown ![alt](url) có sẵn trong chuỗi văn bản."""
    if not text:
        return ""
    
    md_img_pattern = r'!\[(.*?)\]\((https?://[^\s\)]+|data:image/[^\)]+)\)'
    counter = [0]

    def replace_match(match):
        alt = match.group(1)
        src = match.group(2)
        counter[0] += 1
        local_filename = _save_image_to_workspace(src, temp_dir, f"{prefix}_inline_{counter[0]}")
        if local_filename:
            return f"\n\n![{alt}]({local_filename})\n\n"
        return match.group(0)

    return re.sub(md_img_pattern, replace_match, text)


def _compile_markdown_to_docx(full_markdown: str, temp_dir: str, output_path: str):
    """Thực thi biên dịch Markdown sang Docx ngay tại workspace cục bộ."""
    input_md_path = os.path.join(temp_dir, "document.md")
    with open(input_md_path, "w", encoding="utf-8") as f:
        f.write(full_markdown)

    abs_output_path = os.path.abspath(output_path)
    orig_cwd = os.getcwd()
    try:
        os.chdir(temp_dir)
        pypandoc.convert_file(
            "document.md",
            'docx',
            format='markdown',
            outputfile=abs_output_path,
            extra_args=['--standalone']
        )
    finally:
        os.chdir(orig_cwd)


def export_questions_to_word(
    questions: List[Question], 
    output_path: str, 
    mode: str = "de_goc",
    ds_table_format: bool = True,
    tln_box_format: bool = True,
    test_code: str = "",
    header_info: Optional[dict] = None
):
    """Xuất từng đề riêng lẻ (Đề gốc, Đề có dòng chữa bài, Đáp án, Lời giải)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        md_lines = []

        if header_info:
            header_xml = generate_header_html(header_info)
            if header_xml:
                md_lines.append(header_xml)

        md_lines.append("\n")

        for idx, q in enumerate(questions, start=1):
            # Xử lý ảnh trong trường dữ liệu riêng và ảnh nhúng inline
            clean_q_content = _resolve_all_inline_images(q.content, temp_dir, f"q_{idx}")
            clean_q_sol = _resolve_all_inline_images(q.solution or "", temp_dir, f"sol_{idx}")

            q_img_file = _save_image_to_workspace(q.image_path, temp_dir, f"q_main_{idx}")
            sol_img_file = _save_image_to_workspace(getattr(q, 'solution_image_path', None), temp_dir, f"sol_main_{idx}")

            if mode in ["de_goc", "de_dong_chua"]:
                md_lines.append(f"**Câu {idx}.** {clean_q_content}\n\n")

                if q_img_file:
                    md_lines.append(f"![]({q_img_file})\n\n")

                if q.format == QuestionType.TN and q.options:
                    md_lines.append("")
                    for k in ['A', 'B', 'C', 'D']:
                        if k in q.options:
                            opt_text = _resolve_all_inline_images(q.options[k], temp_dir, f"q_{idx}_opt_{k}")
                            md_lines.append(f"**{k}.** {opt_text}\n")

                elif q.format == QuestionType.DS and q.tf_statements:
                    md_lines.append("")
                    if ds_table_format:
                        md_lines.extend(generate_ds_table(q.tf_statements, show_answers=False))
                    else:
                        for stmt_idx, (stmt, _) in enumerate(q.tf_statements):
                            clean_stmt = format_ds_statement_with_label(stmt, stmt_idx)
                            clean_stmt = _resolve_all_inline_images(clean_stmt, temp_dir, f"q_{idx}_ds_{stmt_idx}")
                            md_lines.append(f"{clean_stmt}\n")

                elif q.format == QuestionType.TLN:
                    if tln_box_format:
                        md_lines.append(OPENXML_TLN_TABLE)

                if mode == "de_dong_chua":
                    md_lines.append("\n")
                    lines_count = 4 if q.format == QuestionType.TN else (12 if q.format == QuestionType.DS else 15)
                    for _ in range(lines_count):
                        md_lines.append(LINE_STRING)

                md_lines.append("\n")

            elif mode == "dap_an":
                md_lines.append(f"**Câu {idx}.** ")
                
                if q.format == QuestionType.TN:
                    md_lines.append(f"Đáp án: **{q.answer}**\n\n")

                elif q.format == QuestionType.DS and q.tf_statements:
                    md_lines.append("Đáp án mệnh đề Đúng/Sai:\n")
                    md_lines.extend(generate_ds_table(q.tf_statements, show_answers=True))
                    md_lines.append("\n")

                elif q.format == QuestionType.TLN:
                    md_lines.append(f"Đáp án: **{q.answer}**\n\n")

            else:  # Lời giải chi tiết
                md_lines.append(f"**Câu {idx}.** {clean_q_content}\n\n")

                if q_img_file:
                    md_lines.append(f"![]({q_img_file})\n\n")

                if q.format == QuestionType.TN and q.options:
                    md_lines.append("")
                    for k in ['A', 'B', 'C', 'D']:
                        if k in q.options:
                            opt_text = _resolve_all_inline_images(q.options[k], temp_dir, f"q_{idx}_opt_{k}")
                            is_correct = (k == (q.answer or "").strip().upper())
                            if is_correct:
                                md_lines.append(f"**<u>{k}. {opt_text}</u>**\n")
                            else:
                                md_lines.append(f"**{k}.** {opt_text}\n")

                elif q.format == QuestionType.DS and q.tf_statements:
                    md_lines.append("")
                    if ds_table_format:
                        md_lines.extend(generate_ds_table(q.tf_statements, show_answers=True))
                    else:
                        for stmt_idx, (stmt, status) in enumerate(q.tf_statements):
                            clean_stmt = format_ds_statement_with_label(stmt, stmt_idx)
                            clean_stmt = _resolve_all_inline_images(clean_stmt, temp_dir, f"q_{idx}_ds_{stmt_idx}")
                            md_lines.append(f"{clean_stmt} **[{status}]**\n")

                elif q.format == QuestionType.TLN:
                    if tln_box_format:
                        md_lines.append(OPENXML_TLN_TABLE)

                md_lines.append(f"\n**Đáp án:** {q.answer}\n")
                if clean_q_sol:
                    md_lines.append(f"**Lời giải chi tiết:**\n{clean_q_sol}\n\n")
                
                if sol_img_file:
                    md_lines.append(f"![Ảnh lời giải câu {idx}]({sol_img_file})\n\n")

                md_lines.append("\n")

        full_markdown = "\n".join(md_lines)
        _compile_markdown_to_docx(full_markdown, temp_dir, output_path)


def export_consolidated_answers_to_word(
    generated_exams: Dict[str, List[Question]], 
    output_path: str, 
    header_info: Optional[dict] = None
):
    """Xuất 1 FILE DUY NHẤT chứa BẢNG ĐÁP ÁN tổng hợp của tất cả các mã đề."""
    md_lines = []
    
    if header_info:
        info_copy = header_info.copy()
        info_copy["sub_title"] = "BẢNG ĐÁP ÁN TỔNG HỢP CÁC MÃ ĐỀ"
        md_lines.append(generate_header_html(info_copy))

    md_lines.append("# BẢNG ĐÁP ÁN TỔNG HỢP\n\n")

    codes = list(generated_exams.keys())
    if not codes:
        return

    max_q = max(len(qs) for qs in generated_exams.values())

    headers = ["Câu"] + [f"Mã đề {c}" for c in codes]
    md_lines.append("| " + " | ".join(headers) + " |")
    md_lines.append("| " + " | ".join([":---:"] * len(headers)) + " |")

    for idx in range(max_q):
        row = [f"**Câu {idx + 1}**"]
        for c in codes:
            qs = generated_exams[c]
            if idx < len(qs):
                q = qs[idx]
                row.append(str(q.answer or ""))
            else:
                row.append("-")
        md_lines.append("| " + " | ".join(row) + " |")

    full_markdown = "\n".join(md_lines)
    with tempfile.TemporaryDirectory() as temp_dir:
        _compile_markdown_to_docx(full_markdown, temp_dir, output_path)


def export_consolidated_solutions_to_word(
    generated_exams: Dict[str, List[Question]], 
    output_path: str, 
    ds_table_format: bool = True,
    tln_box_format: bool = True,
    header_info: Optional[dict] = None
):
    """Xuất 1 FILE DUY NHẤT chứa ĐÁP ÁN CHI TIẾT gộp chung của tất cả mã đề."""
    with tempfile.TemporaryDirectory() as temp_dir:
        md_lines = []
        
        if header_info:
            info_copy = header_info.copy()
            info_copy["sub_title"] = "LỜI GIẢI CHI TIẾT TẤT CẢ MÃ ĐỀ"
            md_lines.append(generate_header_html(info_copy))

        md_lines.append("\n")

        for e_code, questions in generated_exams.items():
            md_lines.append(f"**MÃ ĐỀ THI: {e_code}**\n")
            md_lines.append("---\n\n")

            for idx, q in enumerate(questions, start=1):
                clean_q_content = _resolve_all_inline_images(q.content, temp_dir, f"{e_code}_q_{idx}")
                clean_q_sol = _resolve_all_inline_images(q.solution or "", temp_dir, f"{e_code}_sol_{idx}")

                q_img_file = _save_image_to_workspace(q.image_path, temp_dir, f"{e_code}_q_main_{idx}")
                sol_img_file = _save_image_to_workspace(getattr(q, 'solution_image_path', None), temp_dir, f"{e_code}_sol_main_{idx}")

                md_lines.append(f"**Câu {idx}.** {clean_q_content}\n\n")

                if q_img_file:
                    md_lines.append(f"![]({q_img_file})\n\n")

                if q.format == QuestionType.TN and q.options:
                    md_lines.append("")
                    for k in ['A', 'B', 'C', 'D']:
                        if k in q.options:
                            opt_text = _resolve_all_inline_images(q.options[k], temp_dir, f"{e_code}_q_{idx}_opt_{k}")
                            is_correct = (k == (q.answer or "").strip().upper())
                            if is_correct:
                                md_lines.append(f"**<u>{k}. {opt_text}</u>**\n")
                            else:
                                md_lines.append(f"**{k}.** {opt_text}\n")

                elif q.format == QuestionType.DS and q.tf_statements:
                    md_lines.append("")
                    if ds_table_format:
                        md_lines.extend(generate_ds_table(q.tf_statements, show_answers=True))
                    else:
                        for stmt_idx, (stmt, status) in enumerate(q.tf_statements):
                            clean_stmt = format_ds_statement_with_label(stmt, stmt_idx)
                            clean_stmt = _resolve_all_inline_images(clean_stmt, temp_dir, f"{e_code}_q_{idx}_ds_{stmt_idx}")
                            md_lines.append(f"{clean_stmt} **[{status}]**\n")

                elif q.format == QuestionType.TLN:
                    if tln_box_format:
                        md_lines.append(OPENXML_TLN_TABLE)

                md_lines.append(f"\n**Đáp án:** {q.answer}\n")
                if clean_q_sol:
                    md_lines.append(f"**Lời giải chi tiết:**\n{clean_q_sol}\n\n")
                
                if sol_img_file:
                    md_lines.append(f"![Ảnh lời giải câu {idx}]({sol_img_file})\n\n")

                md_lines.append("\n")

            md_lines.append("\n\n---\n\n")

        full_markdown = "\n".join(md_lines)
        _compile_markdown_to_docx(full_markdown, temp_dir, output_path)
