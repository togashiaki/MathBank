import os
import docx
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

def add_header_table(doc: docx.Document, header_info: dict, test_code: str = ""):
    """Chèn bảng tiêu đề 2x2 chuẩn định dạng đề thi vào đầu document."""
    if not header_info:
        return

    school_name = str(header_info.get("school_name", "")).strip().upper()
    exam_title = str(header_info.get("exam_title", "")).strip().upper()
    sub_title = str(header_info.get("sub_title", "")).strip()
    duration = header_info.get("duration", 90)

    # Nếu có test_code mà sub_title chưa có thì gán vào sub_title
    if test_code and f"Mã đề: {test_code}" not in sub_title:
        sub_title = f"{sub_title} - Mã đề: {test_code}" if sub_title else f"Mã đề: {test_code}"

    # Tạo bảng 2x2 không viền
    table = doc.add_table(rows=2, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    # Chỉnh độ rộng cột
    for row in table.rows:
        row.cells[0].width = Inches(3.2)
        row.cells[1].width = Inches(3.8)

    # Ô (0,0): Tên trường / Trung tâm
    p00 = table.cell(0, 0).paragraphs[0]
    p00.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r00 = p00.add_run(school_name)
    r00.bold = True
    r00.font.size = Pt(11)

    # Ô (0,1): Tên đề thi
    p01 = table.cell(0, 1).paragraphs[0]
    p01.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r01 = p01.add_run(exam_title)
    r01.bold = True
    r01.font.size = Pt(11)

    # Ô (1,0): Ghi chú / Môn học / Mã đề
    p10 = table.cell(1, 0).paragraphs[0]
    p10.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r10 = p10.add_run(sub_title)
    r10.font.size = Pt(10.5)

    # Ô (1,1): Thời gian làm bài
    p11 = table.cell(1, 1).paragraphs[0]
    p11.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r11 = p11.add_run(f"Thời gian: {duration} phút (không kể thời gian phát đề)")
    r11.font.size = Pt(10.5)

    # Dòng kẻ phân cách tiêu đề và nội dung
    p_line = doc.add_paragraph()
    p_line.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_line.paragraph_format.space_after = Pt(14)
    r_line = p_line.add_run("────────────────────────────────────────")
    r_line.font.size = Pt(9)


def export_questions_to_word(
    questions: list,
    output_filepath: str,
    mode: str = "de_goc",
    ds_table_format: bool = True,
    tln_box_format: bool = True,
    test_code: str = "",
    header_info: dict = None
):
    """Hàm chính xuất danh sách câu hỏi ra file Word (.docx)."""
    doc = docx.Document()

    # Cấu hình lề trang 2cm
    for section in doc.sections:
        section.top_margin = Inches(0.78)
        section.bottom_margin = Inches(0.78)
        section.left_margin = Inches(0.78)
        section.right_margin = Inches(0.78)

    # 1. Chèn bảng tiêu đề 4 ô nếu có cấu hình header
    if header_info and mode in ["de_goc", "de_dong_chua"]:
        add_header_table(doc, header_info, test_code)

    # 2. Xuất nội dung câu hỏi theo mode
    # (Đoạn code duyệt loop questions và chèn nội dung câu hỏi/đáp án/lời giải của bạn tiếp tục ở đây)
    # ...

    doc.save(output_filepath)
