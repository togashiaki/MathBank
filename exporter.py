import os
import re
import html
import pypandoc
from typing import List, Optional, Dict
from models import Question, QuestionType

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
    """Tạo bảng tiêu đề 2x2 định dạng OpenXML chuẩn cho file Word (.docx) cỡ chữ 11pt."""
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
    md_lines = []

    if header_info:
        header_xml = generate_header_html(header_info)
        if header_xml:
            md_lines.append(header_xml)

    md_lines.append("\n")

    for idx, q in enumerate(questions, start=1):
        if mode in ["de_goc", "de_dong_chua"]:
            md_lines.append(f"**Câu {idx}.** {q.content}\n")

            if q.image_path and os.path.exists(q.image_path):
                md_lines.append(f"\n![Hình ảnh câu {idx}]({q.image_path})\n")

            if q.format == QuestionType.TN and q.options:
                md_lines.append("")
                for k in ['A', 'B', 'C', 'D']:
                    if k in q.options:
                        md_lines.append(f"**{k}.** {q.options[k]}\n")

            elif q.format == QuestionType.DS and q.tf_statements:
                md_lines.append("")
                if ds_table_format:
                    # Cột 1: Mệnh đề (~78%), Cột 2: Đ/S (~22% chiều rộng cột)
                    md_lines.append("| Mệnh đề | Đ/S |")
                    md_lines.append("| :-------------------------------------------------------------------------- | :-----------------------: |")
                    for stmt_idx, (stmt, _) in enumerate(q.tf_statements):
                        clean_stmt = format_ds_statement_with_label(stmt, stmt_idx)
                        md_lines.append(f"| {clean_stmt} | |")
                    md_lines.append("")
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
                md_lines.append("| Mệnh đề | Đ/S |")
                md_lines.append("| :-------------------------------------------------------------------------- | :-----------------------: |")
                for stmt_idx, (stmt, status) in enumerate(q.tf_statements):
                    clean_stmt = format_ds_statement_with_label(stmt, stmt_idx)
                    chk_val = "Đ" if status in ["Đúng", "D", "True", "T"] else ("S" if status in ["Sai", "S", "False", "F"] else status)
                    md_lines.append(f"| {clean_stmt} | {chk_val} |")
                md_lines.append("\n")

            elif q.format == QuestionType.TLN:
                md_lines.append(f"Đáp án: **{q.answer}**\n\n")

        else: # Lời giải chi tiết
            md_lines.append(f"**Câu {idx}.** {q.content}\n")

            if q.image_path and os.path.exists(q.image_path):
                md_lines.append(f"\n![Hình ảnh câu {idx}]({q.image_path})\n")

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
                    md_lines.append("| Mệnh đề | Đ/S |")
                    md_lines.append("| :-------------------------------------------------------------------------- | :-----------------------: |")
                    for stmt_idx, (stmt, status) in enumerate(q.tf_statements):
                        clean_stmt = format_ds_statement_with_label(stmt, stmt_idx)
                        chk_val = "Đ" if status in ["Đúng", "D", "True", "T"] else ("S" if status in ["Sai", "S", "False", "F"] else status)
                        md_lines.append(f"| {clean_stmt} | {chk_val} |")
                    md_lines.append("")
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
            if sol_img and os.path.exists(sol_img):
                md_lines.append(f"\n![Ảnh lời giải câu {idx}]({sol_img})\n")

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

    md_lines.append("\n")

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
            md_lines.append(f"**Câu {idx}.** {q.content}\n")

            if q.image_path and os.path.exists(q.image_path):
                md_lines.append(f"\n![Hình ảnh câu {idx}]({q.image_path})\n")

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
                    md_lines.append("| Mệnh đề | Đ/S |")
                    md_lines.append("| :-------------------------------------------------------------------------- | :-----------------------: |")
                    for stmt_idx, (stmt, status) in enumerate(q.tf_statements):
                        clean_stmt = format_ds_statement_with_label(stmt, stmt_idx)
                        chk_val = "Đ" if status in ["Đúng", "D", "True", "T"] else ("S" if status in ["Sai", "S", "False", "F"] else status)
                        md_lines.append(f"| {clean_stmt} | {chk_val} |")
                    md_lines.append("")
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
            if sol_img and os.path.exists(sol_img):
                md_lines.append(f"\n![Ảnh lời giải câu {idx}]({sol_img})\n")

            md_lines.append("\n")

        md_lines.append("\n\n---\n\n")

    full_markdown = "\n".join(md_lines)
    pypandoc.convert_text(full_markdown, 'docx', format='markdown', outputfile=output_path)
