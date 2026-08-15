import os
import re
import html
import base64
import tempfile
import requests
import pypandoc
from typing import List, Optional, Dict
from models import Question, QuestionType


def resolve_image_path(img_src: Optional[str], temp_dir: str) -> Optional[str]:
    """
    Xử lý đường dẫn ảnh cho Pandoc:
    - Nếu là file cục bộ có sẵn -> dùng trực tiếp.
    - Nếu là URL (ImgBB https://...) -> tải về thư mục tạm.
    - Nếu là base64 Data URL -> giải mã và lưu file tạm.
    """
    if not img_src or not str(img_src).strip():
        return None

    img_src = str(img_src).strip()

    # 1. Đường dẫn file cục bộ
    if os.path.exists(img_src):
        return img_src.replace("\\", "/")

    # 2. Data URL Base64 (data:image/...;base64,...)
    if img_src.startswith("data:image"):
        try:
            match = re.match(r'data:image/(\w+);base64,(.+)', img_src)
            if match:
                ext = match.group(1)
                data = base64.b64decode(match.group(2))
                temp_file = tempfile.NamedTemporaryFile(delete=False, dir=temp_dir, suffix=f".{ext}")
                temp_file.write(data)
                temp_file.close()
                return temp_file.name.replace("\\", "/")
        except Exception:
            return None

    # 3. URL Web trực tiếp (ImgBB, Web...)
    if img_src.startswith("http://") or img_src.startswith("https://"):
        try:
            res = requests.get(img_src, timeout=20)
            if res.status_code == 200:
                ext = ".png"
                lower_url = img_src.lower()
                if ".jpg" in lower_url or ".jpeg" in lower_url:
                    ext = ".jpg"
                elif ".webp" in lower_url:
                    ext = ".webp"
                elif ".gif" in lower_url:
                    ext = ".gif"

                temp_file = tempfile.NamedTemporaryFile(delete=False, dir=temp_dir, suffix=ext)
                temp_file.write(res.content)
                temp_file.close()
                return temp_file.name.replace("\\", "/")
        except Exception as e:
            print(f"Lỗi tải ảnh từ URL ({img_src}): {e}")
            return None

    return None


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
            img_local = resolve_image_path(q.image_path, temp_dir)

            if mode in ["de_goc", "de_dong_chua"]:
                md_lines.append(f"**Câu {idx}.** {q.content}\n")

                if img_local:
                    md_lines.append(f"\n![Hình ảnh câu {idx}]({img_local})\n")

                if q.format == QuestionType.TN and q.options:
                    md_lines.append("")
                    for k in ['A', 'B', 'C', 'D']:
                        if k in q.options:
                            md_lines.append(f"**{k}.** {q.options[k]}\n")

                elif q.format == QuestionType.DS and q.tf_statements:
                    md_lines.append("")
                    if ds_table_format:
                        md_lines.extend(generate_ds_table(q.tf_statements, show_answers=False))
                    else:
                        for stmt_idx, (stmt, _) in enumerate(q.tf_statements):
                            clean_stmt = format_ds_statement_with_label(stmt, stmt_idx)
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

            else: # Lời giải chi tiết
                md_lines.append(f"**Câu {idx}.** {q.content}\n")

                if img_local:
                    md_lines.append(f"\n![Hình ảnh câu {idx}]({img_local})\n")

                if q.format == QuestionType.TN and q.options:
                    md_lines.append("")
                    for k in ['A', 'B', 'C', 'D']:
                        if k in q.options:
                            is_correct = (k == (q.answer or "").strip().upper())
                            if is_correct:
                                md_lines.append(f"**<u>{k}. {q.options[k]}</u>**\n")
                            else:
                                md_lines.append(f"**{k}.** {q.options[k]}\n")

                elif q.format == QuestionType.DS and q.tf_statements:
                    md_lines.append("")
                    if ds_table_format:
                        md_lines.extend(generate_ds_table(q.tf_statements, show_answers=True))
                    else:
                        for stmt_idx, (stmt, status) in enumerate(q.tf_statements):
                            clean_stmt = format_ds_statement_with_label(stmt, stmt_idx)
                            md_lines.append(f"{clean_stmt} **[{status}]**\n")

                elif q.format == QuestionType.TLN:
                    if tln_box_format:
                        md_lines.append(OPENXML_TLN_TABLE)

                md_lines.append(f"\n**Đáp án:** {q.answer}\n")
                if q.solution:
                    md_lines.append(f"**Lời giải chi tiết:**\n{q.solution}\n")
                
                sol_img = getattr(q, 'solution_image_path', None)
                sol_img_local = resolve_image_path(sol_img, temp_dir)
                if sol_img_local:
                    md_lines.append(f"\n![Ảnh lời giải câu {idx}]({sol_img_local})\n")

                md_lines.append("\n")

        full_markdown = "\n".join(md_lines)
        pypandoc.convert_text(
            full_markdown, 
            'docx', 
            format='markdown', 
            outputfile=output_path
        )


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
    pypandoc.convert_text(full_markdown, 'docx', format='markdown', outputfile=output_path)


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
                img_local = resolve_image_path(q.image_path, temp_dir)
                md_lines.append(f"**Câu {idx}.** {q.content}\n")

                if img_local:
                    md_lines.append(f"\n![Hình ảnh câu {idx}]({img_local})\n")

                if q.format == QuestionType.TN and q.options:
                    md_lines.append("")
                    for k in ['A', 'B', 'C', 'D']:
                        if k in q.options:
                            is_correct = (k == (q.answer or "").strip().upper())
                            if is_correct:
                                md_lines.append(f"**<u>{k}. {q.options[k]}</u>**\n")
                            else:
                                md_lines.append(f"**{k}.** {q.options[k]}\n")

                elif q.format == QuestionType.DS and q.tf_statements:
                    md_lines.append("")
                    if ds_table_format:
                        md_lines.extend(generate_ds_table(q.tf_statements, show_answers=True))
                    else:
                        for stmt_idx, (stmt, status) in enumerate(q.tf_statements):
                            clean_stmt = format_ds_statement_with_label(stmt, stmt_idx)
                            md_lines.append(f"{clean_stmt} **[{status}]**\n")

                elif q.format == QuestionType.TLN:
                    if tln_box_format:
                        md_lines.append(OPENXML_TLN_TABLE)

                md_lines.append(f"\n**Đáp án:** {q.answer}\n")
                if q.solution:
                    md_lines.append(f"**Lời giải chi tiết:**\n{q.solution}\n")
                
                sol_img = getattr(q, 'solution_image_path', None)
                sol_img_local = resolve_image_path(sol_img, temp_dir)
                if sol_img_local:
                    md_lines.append(f"\n![Ảnh lời giải câu {idx}]({sol_img_local})\n")

                md_lines.append("\n")

            md_lines.append("\n\n---\n\n")

        full_markdown = "\n".join(md_lines)
        pypandoc.convert_text(full_markdown, 'docx', format='markdown', outputfile=output_path)
