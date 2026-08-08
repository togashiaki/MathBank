import os
import re
import pypandoc
from typing import List
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

def export_questions_to_word(
    questions: List[Question], 
    output_path: str, 
    mode: str = "de_goc",
    ds_table_format: bool = True,
    tln_box_format: bool = True,
    test_code: str = ""
):
    md_lines = []

    if mode == "de_goc":
        md_lines.append("# ĐỀ THI MÔN TOÁN GDPT 2018\n")
    elif mode == "de_dong_chua":
        md_lines.append("# ĐỀ THI MÔN TOÁN\n")
    elif mode == "dap_an":
        md_lines.append("# BẢNG ĐÁP ÁN MÔN TOÁN\n")
    else:
        md_lines.append("# ĐỀ THI VÀ LỜI GIẢI CHI TIẾT MÔN TOÁN\n")

    if test_code:
        md_lines.append(f"### MÃ ĐỀ THI: {test_code}\n")

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

        elif mode == "dap_an":
            md_lines.append(f"**Câu {idx}.** ")
            
            if q.format == QuestionType.TN:
                md_lines.append(f"Đáp án: **{q.answer}**\n\n")

            elif q.format == QuestionType.DS and q.tf_statements:
                md_lines.append("Đáp án mệnh đề Đúng/Sai:\n")
                md_lines.append("| Mệnh đề | Đúng | Sai |")
                md_lines.append("| :--- | :---: | :---: |")
                for stmt, status in q.tf_statements:
                    clean_stmt = clean_statement_text(stmt)
                    chk_d = "X" if status in ["Đúng", "D"] else ""
                    chk_s = "X" if status in ["Sai", "S"] else ""
                    md_lines.append(f"| {clean_stmt} | {chk_d} | {chk_s} |")
                md_lines.append("\n")

            elif q.format == QuestionType.TLN:
                md_lines.append(f"Đáp án: **{q.answer}**\n\n")

        else:
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

    full_markdown = "\n".join(md_lines)
    pypandoc.convert_text(
        full_markdown, 
        'docx', 
        format='markdown', 
        outputfile=output_path
    )