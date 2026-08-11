import os
import re
import pypandoc
from typing import List, Optional, Dict
from models import Question, QuestionType

def clean_statement_text(stmt: str) -> str:
    """Loại bỏ ký tự gạch đầu dòng hoặc dấu chấm tròn dư thừa trong các mệnh đề Đúng/Sai."""
    if not stmt:
        return ""
    return re.sub(r'^\s*[\-\*\•]\s*', '', stmt).strip()


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
    """Tạo bảng tiêu đề 2x2 định dạng HTML không viền cho đề thi."""
    if not header_info:
        return ""
    school_name = header_info.get("school_name", "").strip()
    exam_title = header_info.get("exam_title", "").strip()
    sub_title = header_info.get("sub_title", "").strip()
    duration = header_info.get("duration", 90)

    sub_title_html = f"<b>{sub_title}</b>" if sub_title else "&nbsp;"

    html = f"""
    <table style="width: 100%; border-collapse: collapse; border: none; margin-bottom: 20px; font-family: 'Times New Roman', serif;">
      <tr style="border: none;">
        <td style="width: 45%; text-align: center; font-weight: bold; vertical-align: top; border: none; font-size: 13pt;">
          {school_name.upper()}
        </td>
        <td style="width: 55%; text-align: center; font-weight: bold; vertical-align: top; border: none; font-size: 13pt;">
          {exam_title.upper()}
        </td>
      </tr>
      <tr style="border: none;">
        <td style="width: 45%; text-align: center; vertical-align: top; border: none; font-size: 12pt;">
          {sub_title_html}
        </td>
        <td style="width: 55%; text-align: center; vertical-align: top; border: none; font-size: 12pt;">
          Thời gian: {duration} phút (không kể thời gian phát đề)
        </td>
      </tr>
    </table>
    <hr style="border: none; border-top: 1px solid #000; margin-top: 5px; margin-bottom: 15px;" />
    """
    return html


def export_questions_to_word(
    questions: List[Question], 
    output_path: str, 
    mode: str = "de_goc",
    ds_table_format: bool = True,
    tln_box_format: bool = True,
    test_code: str = "",
    header_info: Optional[dict] = None
):
    """Xuất từng đề riêng lẻ (Đề gốc, Đề có dòng chữa bài)."""
    md_lines = []

    if header_info:
        header_html = generate_header_html(header_info)
        if header_html:
            md_lines.append(header_html)

    if mode == "de_goc":
        md_lines.append("# ĐỀ THI MÔN TOÁN GDPT 2018\n")
    elif mode == "de_dong_chua":
        md_lines.append("# ĐỀ THI MÔN TOÁN\n")

    if test_code:
        md_lines.append(f"### MÃ ĐỀ THI: {test_code}\n")

    md_lines.append("\n")

    for idx, q in enumerate(questions, start=1):
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
                md_lines.append("| Mệnh đề | Đúng | Sai |")
                md_lines.append("| :--- | :---: | :---: |")
                for stmt, _ in q.tf_statements:
                    clean_stmt = clean_statement_text(stmt)
                    md_lines.append(f"| {clean_stmt} | | |")
                md_lines.append("")
            else:
                for stmt, _ in q.tf_statements:
                    clean_stmt = clean_statement_text(stmt)
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

    # Tạo bảng Markdown: Cột 1 là Số câu, các cột sau là Mã đề
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

    md_lines.append("# LỜI GIẢI CHI TIẾT TẤT CẢ MÃ ĐỀ THI\n\n")

    for e_code, questions in generated_exams.items():
        md_lines.append(f"## MÃ ĐỀ THI: {e_code}\n")
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
                    md_lines.append("| Mệnh đề | Đúng | Sai |")
                    md_lines.append("| :--- | :---: | :---: |")
                    for stmt, status in q.tf_statements:
                        clean_stmt = clean_statement_text(stmt)
                        chk_d = "X" if status in ["Đúng", "D"] else ""
                        chk_s = "X" if status in ["Sai", "S"] else ""
                        md_lines.append(f"| {clean_stmt} | {chk_d} | {chk_s} |")
                    md_lines.append("")
                else:
                    for stmt, status in q.tf_statements:
                        clean_stmt = clean_statement_text(stmt)
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
