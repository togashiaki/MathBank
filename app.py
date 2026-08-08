import os
import re
import time
import random
import sqlite3
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
from models import Question, QuestionType
from parser import QuestionDatabase
from exporter import export_questions_to_word

# 1. CẤU HÌNH TRANG STREAMLIT
st.set_page_config(
    page_title="Ngân hàng câu hỏi",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. TẠO COMPONENT MATHLIVE
COMPONENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mathlive_component")
os.makedirs(COMPONENT_DIR, exist_ok=True)
INDEX_HTML_PATH = os.path.join(COMPONENT_DIR, "index.html")

MATHLIVE_HTML_CONTENT = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script src="https://unpkg.com/mathlive"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600&display=swap');
        body { font-family: 'Plus Jakarta Sans', sans-serif; margin: 0; padding: 2px; background-color: transparent; color: #2c2825; }
        .editor-container { background-color: #faf8f5; border: 1px solid #e2dbd0; border-radius: 12px; padding: 14px 16px; min-height: 180px; line-height: 1.8; box-shadow: 0 1px 4px rgba(44,40,37,0.03); outline: none; }
        .plain-text { outline: none; display: inline; color: #2c2825; font-size: 0.98rem; white-space: pre-wrap; }
        math-field.inline-math-chip { display: inline-block; vertical-align: middle; background-color: #faf0ec !important; border: 1px solid #e8c4b8 !important; color: #a8412c !important; border-radius: 8px !important; padding: 2px 8px !important; margin: 2px 4px !important; font-size: 1.15rem !important; outline: none !important; box-shadow: 0 1px 3px rgba(184, 84, 63, 0.08); cursor: pointer; }
        math-field.inline-math-chip:focus-within { border-color: #b8543f !important; background-color: #ffffff !important; box-shadow: 0 0 0 3px rgba(184, 84, 63, 0.2) !important; }
    </style>
</head>
<body>
    <div id="editor" class="editor-container" contenteditable="true"></div>
    <script>
        let currentText = "";
        let isUserEditing = false;
        function sendToStreamlit(type, data) { window.parent.postMessage(Object.assign({ isStreamlitMessage: true, type: type }, data), "*"); }
        function getFullText() {
            const container = document.getElementById('editor');
            let fullText = "";
            container.childNodes.forEach(node => {
                if (node.nodeName && node.nodeName.toLowerCase() === 'math-field') { fullText += '$' + node.value + '$'; }
                else if (node.nodeType === Node.ELEMENT_NODE) { fullText += node.innerText; }
                else if (node.nodeType === Node.TEXT_NODE) { fullText += node.textContent; }
            });
            return fullText;
        }
        function syncWithStreamlit() { currentText = getFullText(); sendToStreamlit("streamlit:setComponentValue", { value: currentText }); sendToStreamlit("streamlit:setFrameHeight", { height: document.body.scrollHeight + 20 }); }
        function updateHeight() { sendToStreamlit("streamlit:setFrameHeight", { height: document.body.scrollHeight + 20 }); }
        function buildEditor(rawText) {
            const container = document.getElementById('editor');
            container.innerHTML = "";
            if (!rawText) {
                const span = document.createElement('span'); span.className = 'plain-text'; span.contentEditable = "true"; span.innerText = "";
                span.addEventListener('blur', () => { isUserEditing = false; syncWithStreamlit(); });
                span.addEventListener('focus', () => { isUserEditing = true; });
                container.appendChild(span); updateHeight(); return;
            }
            const tokens = rawText.split(/(\$\$.*?\$\$|\$.*?\$)/g);
            tokens.forEach((token) => {
                if (!token) return;
                if ((token.startsWith('$$') && token.endsWith('$$')) || (token.startsWith('$') && token.endsWith('$'))) {
                    const mf = document.createElement('math-field'); mf.className = 'inline-math-chip'; mf.value = token.slice(1, -1);
                    mf.addEventListener('change', syncWithStreamlit);
                    mf.addEventListener('blur', () => { isUserEditing = false; syncWithStreamlit(); });
                    mf.addEventListener('focus', () => { isUserEditing = true; });
                    container.appendChild(mf);
                } else {
                    const span = document.createElement('span'); span.className = 'plain-text'; span.contentEditable = "true"; span.innerText = token;
                    span.addEventListener('blur', () => { isUserEditing = false; syncWithStreamlit(); });
                    span.addEventListener('focus', () => { isUserEditing = true; });
                    container.appendChild(span);
                }
            });
            updateHeight();
        }
        const container = document.getElementById('editor');
        container.addEventListener('paste', function(e) {
            e.preventDefault();
            const pastedText = (e.clipboardData || window.clipboardData).getData('text/plain');
            const sel = window.getSelection();
            if (sel.rangeCount) { const range = sel.getRangeAt(0); range.deleteContents(); range.insertNode(document.createTextNode(pastedText)); }
            else { container.appendChild(document.createTextNode(pastedText)); }
            isUserEditing = false; currentText = getFullText(); buildEditor(currentText); syncWithStreamlit();
        });
        window.addEventListener("message", function(event) {
            if (event.data && event.data.type === "streamlit:render") {
                const args = event.data.args;
                if (args && args.text !== undefined && !isUserEditing && args.text !== currentText) { currentText = args.text; buildEditor(args.text); }
            }
        });
        window.addEventListener('load', () => { sendToStreamlit("streamlit:componentReady", { apiVersion: 1 }); });
    </script>
</body>
</html>"""

with open(INDEX_HTML_PATH, "w", encoding="utf-8") as f:
    f.write(MATHLIVE_HTML_CONTENT)

interactive_math_editor = components.declare_component("interactive_math_editor", path=COMPONENT_DIR)

# 3. KHỞI TẠO CƠ SỞ DỮ LIỆU & SESSION STATE
db = QuestionDatabase()
all_questions = db.get_all_questions()

if "selected_questions" not in st.session_state:
    st.session_state["selected_questions"] = set()

os.makedirs("images", exist_ok=True)


# HÀM TẠO THƯ MỤC LƯU ĐỀ THI THEO NGÀY
def get_export_dir() -> str:
    today_str = datetime.now().strftime("%d-%m-%Y")
    export_dir = os.path.join(r"D:\MathBank", "Đề tạo thành", f"Đề tạo ngày {today_str}")
    os.makedirs(export_dir, exist_ok=True)
    return export_dir


# POPUP CẤU HÌNH XUẤT FILE WORD VỚI 4 TÙY CHỌN TẢI
@st.dialog("📄 Cài đặt Tùy chọn Xuất file Word", width="large")
def show_export_config_modal(questions_to_export: list, test_code: str = ""):
    st.markdown("### ⚙️ Cấu hình định dạng file Word")
    st.caption(f"Đang chuẩn bị xuất **{len(questions_to_export)}** câu hỏi sang định dạng Word (.docx)")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 1. Câu Đúng / Sai")
        ds_fmt_choice = st.radio("Định dạng câu Đúng/Sai:", ["Dạng bảng 2 cột (Đúng/Sai)", "Từng dòng liên tiếp"], index=0)

    with col2:
        st.markdown("#### 2. Câu trả lời ngắn")
        tln_fmt_choice = st.radio("Định dạng ô điền trả lời ngắn:", ["Có ô điền (5 ô 0.8cm x 0.8cm sát lề phải)", "Không có ô điền"], index=0)

    st.divider()

    ds_tbl = (ds_fmt_choice == "Dạng bảng 2 cột (Đúng/Sai)")
    tln_box = (tln_fmt_choice == "Có ô điền (5 ô 0.8cm x 0.8cm sát lề phải)")
    export_dir = get_export_dir()
    file_suffix = f"_{test_code}" if test_code else ""

    if st.button("🚀 BẮT ĐẦU TẠO CÁC FILE WORD", type="primary", use_container_width=True):
        # 1. Bản Đề gốc
        path_degoc = os.path.join(export_dir, f"1_De_Thi_Goc{file_suffix}.docx")
        export_questions_to_word(questions_to_export, path_degoc, mode="de_goc", ds_table_format=ds_tbl, tln_box_format=tln_box, test_code=test_code)

        # 2. Bản Đề có dòng chữa bài
        path_dongchua = os.path.join(export_dir, f"2_De_Co_Dong_Chua_Bai{file_suffix}.docx")
        export_questions_to_word(questions_to_export, path_dongchua, mode="de_dong_chua", ds_table_format=ds_tbl, tln_box_format=tln_box, test_code=test_code)

        # 3. Bản Đáp án nhanh
        path_dapan = os.path.join(export_dir, f"3_Bang_Dap_An{file_suffix}.docx")
        export_questions_to_word(questions_to_export, path_dapan, mode="dap_an", ds_table_format=True, tln_box_format=tln_box, test_code=test_code)

        # 4. Bản Lời giải chi tiết
        path_loigiai = os.path.join(export_dir, f"4_Loi_Giai_Chi_Tiet{file_suffix}.docx")
        export_questions_to_word(questions_to_export, path_loigiai, mode="loi_giai_chi_tiet", ds_table_format=ds_tbl, tln_box_format=tln_box, test_code=test_code)

        st.session_state[f"export_paths_{test_code}"] = {
            "degoc": path_degoc,
            "dongchua": path_dongchua,
            "dapan": path_dapan,
            "loigiai": path_loigiai
        }
        st.success("🎉 Đã tạo thành công toàn bộ 4 bản Word! Chọn phiên bản bên dưới để tải về:")

    if f"export_paths_{test_code}" in st.session_state:
        paths = st.session_state[f"export_paths_{test_code}"]
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)

        with open(paths["degoc"], "rb") as f:
            c1.download_button("📝 Tải về đề thi gốc", f, file_name=os.path.basename(paths["degoc"]), use_container_width=True)

        with open(paths["dongchua"], "rb") as f:
            c2.download_button("✍️ Tải đề có dòng chữa bài", f, file_name=os.path.basename(paths["dongchua"]), use_container_width=True)

        with open(paths["dapan"], "rb") as f:
            c3.download_button("🔑 Tải về đáp án nhanh", f, file_name=os.path.basename(paths["dapan"]), use_container_width=True)

        with open(paths["loigiai"], "rb") as f:
            c4.download_button("📖 Tải về lời giải chi tiết", f, file_name=os.path.basename(paths["loigiai"]), use_container_width=True)


# HÀM XÓA CÂU HỎI KHỎI DATABASE
def delete_question_from_db(q_code: str, image_path: str = None, solution_image_path: str = None):
    if image_path and os.path.exists(image_path):
        try: os.remove(image_path)
        except Exception: pass

    if solution_image_path and os.path.exists(solution_image_path):
        try: os.remove(solution_image_path)
        except Exception: pass

    with sqlite3.connect(db.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM questions WHERE code = ?", (q_code,))
        conn.commit()


# POPUP XÁC NHẬN XÓA CÂU HỎI
@st.dialog("🗑️ Xác nhận xóa câu hỏi", width="small")
def confirm_delete_dialog(q: Question):
    st.write(f"Bạn có chắc chắn muốn xóa câu hỏi **{q.code}** khỏi cơ sở dữ liệu không?")
    st.caption("⚠️ Lưu ý: Thao tác này sẽ xóa vĩnh viễn câu hỏi và không thể hoàn tác.")

    col_yes, col_no = st.columns(2)
    if col_yes.button("❌ Có, xóa ngay", type="primary", use_container_width=True):
        delete_question_from_db(q.code, q.image_path, getattr(q, 'solution_image_path', None))
        st.session_state["selected_questions"].discard(q.code)
        st.success(f"Đã xóa câu hỏi {q.code} khỏi Database!")
        time.sleep(0.6)
        st.rerun()

    if col_no.button("Hủy bỏ", use_container_width=True):
        st.rerun()


# 4. QUẢN LÝ BẢNG DẠNG BÀI & NGUỒN ĐỀ ĐỘC LẬP
def init_topics_db(db_path: str):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                grade INTEGER,
                chapter INTEGER,
                topic_name TEXT,
                PRIMARY KEY (grade, chapter, topic_name)
            )
        """)
        cursor.execute("INSERT OR IGNORE INTO topics (grade, chapter, topic_name) SELECT DISTINCT grade, chapter, topic FROM questions WHERE topic IS NOT NULL AND topic != ''")
        conn.commit()


def register_topic(db_path: str, grade: int, chapter: int, topic_name: str):
    if not topic_name or not topic_name.strip(): return
    init_topics_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO topics (grade, chapter, topic_name) VALUES (?, ?, ?)", (grade, chapter, topic_name.strip()))
        conn.commit()


def get_chapter_topics(db_path: str, grade: int, chapter: int) -> list:
    init_topics_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT topic_name FROM topics WHERE grade = ? AND chapter = ? ORDER BY topic_name", (grade, chapter))
        rows = cursor.fetchall()
        return [r[0] for r in rows if r[0]]


def get_all_stored_topics(db_path: str, grade=None, chapter=None) -> list:
    init_topics_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        query = "SELECT DISTINCT topic_name FROM topics WHERE 1=1"
        params = []
        if grade is not None and grade != "Tất cả":
            query += " AND grade = ?"
            params.append(grade)
        if chapter is not None and chapter != "Tất cả":
            query += " AND chapter = ?"
            params.append(chapter)
        query += " ORDER BY topic_name"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [r[0] for r in rows if r[0]]


def get_all_stored_sources(db_path: str) -> list:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT source FROM questions WHERE source IS NOT NULL AND source != '' ORDER BY source")
        rows = cursor.fetchall()
        return [r[0] for r in rows if r[0]]


# 5. HÀM TẠO MÃ ID CÂU HỎI
def extract_topic_num_for_chapter(topic_str: str, chapter_topics: list) -> int:
    match = re.search(r'(?:Dạng|D)\s*(\d+)', topic_str, re.IGNORECASE)
    if match: return int(match.group(1))
    if topic_str in chapter_topics: return chapter_topics.index(topic_str) + 1
    return len(chapter_topics) + 1 if topic_str not in chapter_topics else 1


def generate_standard_code(db_questions: list, grade: int, chapter: int, topic: str) -> str:
    chap_topics = get_chapter_topics(db.db_path, grade, chapter)
    d_num = extract_topic_num_for_chapter(topic, chap_topics)
    prefix = f"TOAN{grade}_CH{chapter}_D{d_num}_"

    existing_seqs = []
    for q in db_questions:
        if q.code.startswith(prefix):
            try:
                seq_part = int(q.code.replace(prefix, ""))
                existing_seqs.append(seq_part)
            except ValueError: pass

    next_seq = max(existing_seqs) + 1 if existing_seqs else 1
    return f"{prefix}{next_seq:04d}"


def reindex_all_database_ids():
    questions = db.get_all_questions()
    if not questions: return 0

    grade_chap_groups = {}
    for q in questions:
        key = (q.grade, q.chapter)
        grade_chap_groups.setdefault(key, []).append(q)

    updated_questions = []

    for (g, c), gc_questions in grade_chap_groups.items():
        distinct_topics = get_chapter_topics(db.db_path, g, c)
        topic_groups = {}
        for q in gc_questions:
            topic_groups.setdefault(q.topic, []).append(q)

        for top, q_list in topic_groups.items():
            d_num = extract_topic_num_for_chapter(top, distinct_topics)
            prefix = f"TOAN{g}_CH{c}_D{d_num}_"
            
            for idx, q in enumerate(q_list, start=1):
                new_code = f"{prefix}{idx:04d}"
                
                if q.image_path and os.path.exists(q.image_path):
                    new_img_path = os.path.join("images", f"{new_code}.png")
                    try:
                        os.rename(q.image_path, new_img_path)
                        q.image_path = new_img_path
                    except Exception: pass

                sol_img = getattr(q, 'solution_image_path', None)
                if sol_img and os.path.exists(sol_img):
                    new_sol_img_path = os.path.join("images", f"{new_code}_sol.png")
                    try:
                        os.rename(sol_img, new_sol_img_path)
                        q.solution_image_path = new_sol_img_path
                    except Exception: pass

                q.code = new_code
                updated_questions.append(q)

    with sqlite3.connect(db.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM questions")
        conn.commit()

    db.save_questions(updated_questions)
    return len(updated_questions)


# 6. CSS GIAO DIỆN PHONG CÁCH PLANNER
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif !important; color: #2c2825 !important; }
    .stApp { background-color: #f7f4ed !important; }
    section[data-testid="stSidebar"] { background-color: #f0ebe1 !important; border-right: 1px solid #e2dbd0 !important; }
    .question-card { background-color: #faf8f5; border: 1px solid #e2dbd0; border-radius: 14px; padding: 22px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(44, 40, 37, 0.03); transition: all 0.25s ease; }
    .question-card:hover { border-color: #d1c5b8; box-shadow: 0 6px 16px rgba(44, 40, 37, 0.06); }
    .card-badge { background-color: #b8543f; color: #ffffff; padding: 4px 12px; border-radius: 8px; font-size: 0.82rem; font-weight: 600; font-family: 'JetBrains Mono', monospace; margin-bottom: 12px; display: inline-block; }
    .badge-fmt { background-color: #5e7a4e; color: #ffffff; padding: 4px 10px; border-radius: 8px; font-size: 0.76rem; font-weight: 600; margin-right: 8px; display: inline-block; }
    .stat-box { background-color: #faf8f5; border: 1px solid #e2dbd0; border-radius: 12px; padding: 18px; margin-top: 18px; }
    .stat-item { display: flex; justify-content: space-between; align-items: center; padding: 9px 0; border-bottom: 1px dashed #e5dfd5; font-size: 0.9rem; color: #57524e; }
    .stat-number { font-weight: 700; color: #b8543f; font-family: 'JetBrains Mono', monospace; }
    .answer-box { background-color: #f7ece8; border: 1px solid #e8c4b8; color: #a8412c; padding: 8px 16px; border-radius: 10px; font-weight: 600; font-size: 0.9rem; display: inline-block; margin-top: 12px; }
    .header-info-bar { background-color: #faf8f5; border: 1px solid #e2dbd0; border-radius: 14px; padding: 16px 24px; margin-bottom: 22px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 2px 6px rgba(44, 40, 37, 0.02); }
    .edit-q-box { background-color: #f0ebe1; border: 1px solid #dbd3c7; border-radius: 12px; padding: 16px 20px; margin-bottom: 18px; color: #2c2825; }
    .stButton>button { border-radius: 10px !important; border: 1px solid #d8cfc4 !important; background-color: #faf8f5 !important; color: #2c2825 !important; font-weight: 600 !important; padding: 8px 16px !important; transition: all 0.25s ease !important; }
    .stButton>button:hover { border-color: #b8543f !important; color: #b8543f !important; background-color: #f7ece8 !important; }
    .stButton>button[kind="primary"] { background-color: #b8543f !important; color: #ffffff !important; border: 1px solid #a34834 !important; }
    .stButton>button[kind="primary"]:hover { background-color: #a34834 !important; color: #ffffff !important; border-color: #8f3a2b !important; box-shadow: 0 3px 10px rgba(184, 84, 63, 0.25) !important; }
    .stTabs [data-baseweb="tab-list"] { display: flex !important; justify-content: center !important; align-items: center !important; gap: 12px !important; background-color: #e8e3d8 !important; padding: 8px 12px !important; border-radius: 16px !important; border: 1px solid #d8cfc4 !important; max-width: 820px !important; margin: 0 auto 28px auto !important; box-shadow: 0 4px 12px rgba(44, 40, 37, 0.04) !important; }
    .stTabs [data-baseweb="tab"] { height: 48px !important; border-radius: 10px !important; padding: 0px 28px !important; font-size: 1.02rem !important; font-weight: 600 !important; color: #6b635b !important; border: none !important; transition: all 0.25s ease !important; }
    .stTabs [aria-selected="true"] { background-color: #ffffff !important; color: #b8543f !important; box-shadow: 0 3px 8px rgba(44, 40, 37, 0.1) !important; transform: translateY(-1px); }
    div[data-baseweb="input"], div[data-baseweb="select"], div[data-baseweb="textarea"] { background-color: #faf8f5 !important; border-color: #d8cfc4 !important; border-radius: 10px !important; color: #2c2825 !important; }
</style>
""", unsafe_allow_html=True)


# 7. HÀM PHÂN TÍCH THÔNG MINH
def parse_raw_text_to_questions(raw_text: str, default_meta: dict) -> list[Question]:
    if not raw_text or not raw_text.strip(): return []

    pattern = r'\n(?=\s*(?:Câu|CÂU)(?:\s*hỏi)?(?:\s*\d+)?[\.:\s])'
    q_blocks = re.split(pattern, raw_text.strip())
    parsed_questions = []

    for block in q_blocks:
        block = block.strip()
        if not block: continue
        if not re.search(r'(?:Câu|CÂU)', block, re.IGNORECASE) and not re.search(r'^[a-d][\.\)]', block, re.MULTILINE): continue

        ans_match = re.search(r'(?:^|\n)\s*(?:Đáp án|ĐÁP ÁN|Đáp án:|ĐÁP ÁN:)\s*(.*?)(?=\n\s*(?:Lời giải|LỜI GIẢI)\s*:|$)', block, re.DOTALL | re.IGNORECASE)
        sol_match = re.search(r'(?:^|\n)\s*(?:Lời giải|LỜI GIẢI|Lời giải:|LỜI GIẢI:)\s*(.*)', block, re.DOTALL | re.IGNORECASE)

        extracted_ans = ""
        extracted_sol = ""
        clean_content = block

        if ans_match:
            extracted_ans = ans_match.group(1).strip()
            if ans_match.start() > 0: clean_content = clean_content[:ans_match.start()].strip()

        if sol_match:
            q_start = re.search(r'(?:Câu|CÂU)', block, re.IGNORECASE)
            q_idx = q_start.start() if q_start else 0
            if sol_match.start() >= q_idx:
                extracted_sol = sol_match.group(1).strip()
                if not ans_match and sol_match.start() > q_idx: clean_content = clean_content[:sol_match.start()].strip()

        clean_content = re.sub(r'^\s*(?:Câu|CÂU)(?:\s*hỏi)?(?:\s*\d+)?[\.:\s]*', '', clean_content, flags=re.IGNORECASE).strip()
        lines = [l.strip() for l in clean_content.split('\n') if l.strip()]

        has_tn = any(re.match(r'^[A-D][\.\)]\s*', l) for l in lines)
        has_ds = any(re.match(r'^[a-d][\.\)]\s*', l) for l in lines)

        content_lines = []
        options = {}
        tf_statements = []

        if has_ds and not has_tn: q_fmt = QuestionType.DS
        elif has_tn and not has_ds: q_fmt = QuestionType.TN
        elif has_ds: q_fmt = QuestionType.DS
        elif has_tn: q_fmt = QuestionType.TN
        else: q_fmt = QuestionType.TLN

        if q_fmt == QuestionType.DS:
            is_ds = False
            for line in lines:
                ds_match = re.match(r'^([a-d])[\.\)\:-]\s*(.*)', line)
                if ds_match:
                    is_ds = True
                    lbl = ds_match.group(1).lower()
                    val = ds_match.group(2).strip()
                    stmt_status = "Đúng"
                    if extracted_ans:
                        st_m = re.search(rf'{lbl}[\)\.\:-]?\s*(Đúng|Sai|Đ|S|True|False)', extracted_ans, re.IGNORECASE)
                        if st_m:
                            matched_val = st_m.group(1).upper()
                            stmt_status = "Sai" if matched_val in ['SAI', 'S', 'FALSE'] else "Đúng"
                    tf_statements.append((f"{lbl}) {val}", stmt_status))
                elif not is_ds: content_lines.append(line)
            final_ans = ", ".join([f"{l[0]}) {v}" for l, (_, v) in zip(['a', 'b', 'c', 'd'], tf_statements)]) if tf_statements else extracted_ans

        elif q_fmt == QuestionType.TN:
            is_opt = False
            for line in lines:
                opt_match = re.match(r'^([A-D])[\.\)]\s*', line)
                if opt_match:
                    is_opt = True
                    options[opt_match.group(1)] = opt_match.group(2).strip()
                elif not is_opt: content_lines.append(line)

            final_ans = "A"
            if extracted_ans:
                m_single = re.search(r'\b([A-D])\b', extracted_ans)
                if m_single: final_ans = m_single.group(1).upper()
                elif extracted_ans.upper() in ['A', 'B', 'C', 'D']: final_ans = extracted_ans.upper()

        else:
            q_fmt = QuestionType.TLN
            content_lines = lines
            final_ans = extracted_ans

        content = "\n".join(content_lines)

        parsed_questions.append(Question(
            code="TEMP_CODE", grade=default_meta['grade'], chapter=default_meta['chapter'], lesson=1,
            topic=default_meta['topic'], format=q_fmt, level=default_meta['level'], source=default_meta['source'],
            content=content, options=options, tf_statements=tf_statements, answer=final_ans, solution=extracted_sol, image_path=None
        ))

    return parsed_questions


# 8. POPUP SỬA 1 CÂU HỎI TẠI TAB 1
@st.dialog("✏️ Chỉnh sửa câu hỏi", width="large")
def show_single_question_edit_dialog(q: Question):
    st.subheader(f"Chỉnh sửa câu hỏi: {q.code}")

    col_a, col_b = st.columns(2)
    q.grade = col_a.selectbox("Khối lớp", [12, 11, 10], index=[12, 11, 10].index(q.grade))
    q.chapter = col_b.number_input("Chương", min_value=1, value=q.chapter)

    # DẠNG BÀI - MENU TÌM KIẾM TỰ ĐỘNG
    chap_topics = get_chapter_topics(db.db_path, q.grade, q.chapter)
    top_options = chap_topics + ["➕ Nhập dạng bài mới..."]
    default_top_idx = chap_topics.index(q.topic) if q.topic in chap_topics else (len(top_options)-1 if q.topic else 0)
    
    sel_topic = st.selectbox(f"Chọn hoặc tìm Dạng bài (Lớp {q.grade} - CH{q.chapter}):", top_options, index=default_top_idx, key=f"single_top_sel_{q.code}")
    if sel_topic == "➕ Nhập dạng bài mới...":
        q.topic = st.text_input("Nhập tên Dạng bài mới:", value="" if q.topic in chap_topics else q.topic, key=f"single_top_inp_{q.code}")
    else:
        q.topic = sel_topic

    col_f1, col_f2 = st.columns(2)
    q.level = col_f1.selectbox("Mức độ", [1, 2, 3], index=q.level-1)

    # NGUỒN ĐỀ - MENU TÌM KIẾM TỰ ĐỘNG
    all_sources = get_all_stored_sources(db.db_path)
    src_options = all_sources + ["➕ Nhập nguồn đề mới..."]
    default_src_idx = all_sources.index(q.source) if (q.source and q.source in all_sources) else (len(src_options)-1 if q.source else 0)
    
    sel_source = col_f2.selectbox("Chọn hoặc tìm Nguồn đề:", src_options, index=default_src_idx, key=f"single_src_sel_{q.code}")
    if sel_source == "➕ Nhập nguồn đề mới...":
        q.source = st.text_input("Nhập tên Nguồn đề mới:", value="" if (q.source and q.source in all_sources) else (q.source or ""), key=f"single_src_inp_{q.code}")
    else:
        q.source = sel_source

    st.divider()

    # 1. NỘI DUNG ĐỀ BÀI (MATHLIVE + LATEX THÔ)
    st.markdown("##### 📝 Chỉnh sửa đề bài (Bấm trực tiếp vào ô màu đỏ để sửa công thức MathLive):")
    if f"raw_content_{q.code}" not in st.session_state:
        st.session_state[f"raw_content_{q.code}"] = q.content

    curr_content = st.session_state.get(f"raw_content_{q.code}", q.content)
    updated_content = interactive_math_editor(key=f"editor_single_content_{q.code}", text=curr_content)
    if updated_content is not None and updated_content != curr_content:
        st.session_state[f"raw_content_{q.code}"] = updated_content
        q.content = updated_content

    with st.expander("🛠️ Xem / Chỉnh sửa mã LaTeX thô đề bài"):
        new_raw_content = st.text_area("Mã LaTeX thô đề bài:", value=st.session_state[f"raw_content_{q.code}"], height=80, key=f"raw_single_content_area_{q.code}")
        if new_raw_content != st.session_state[f"raw_content_{q.code}"]:
            st.session_state[f"raw_content_{q.code}"] = new_raw_content
            q.content = new_raw_content
            st.rerun()

    # 2. TẢI ÁNH ĐÍNH KÈM ĐỀ BÀI
    if q.image_path and os.path.exists(q.image_path):
        st.markdown("##### 🖼️ Ảnh đính kèm đề bài hiện tại:")
        img_col1, img_col2 = st.columns([2, 1])
        with img_col1: st.image(q.image_path, width=220)
        with img_col2:
            st.write(""); st.write("")
            if st.button("🗑️ Xóa ảnh đề bài", key=f"del_img_single_{q.code}"):
                if os.path.exists(q.image_path):
                    try: os.remove(q.image_path)
                    except Exception: pass
                q.image_path = None
                db.save_questions([q])
                st.success("Đã xóa ảnh đề bài thành công!")
                time.sleep(0.6)
                st.rerun()

    uploaded_img = st.file_uploader("🖼️ Thay đổi / Tải ảnh đính kèm đề bài mới:", type=["png", "jpg", "jpeg"], key=f"upload_img_single_{q.code}")
    if uploaded_img:
        img_save_path = os.path.join("images", f"{q.code}.png")
        with open(img_save_path, "wb") as f: f.write(uploaded_img.getbuffer())
        q.image_path = img_save_path

    st.divider()

    # 3. PHƯƠNG ÁN & ĐÁP ÁN
    if q.format == QuestionType.TN:
        st.markdown("##### 📌 Tùy chọn đáp án Trắc nghiệm (TN) - Sửa công thức trực tiếp bằng MathLive:")
        if not q.options: q.options = {'A': '', 'B': '', 'C': '', 'D': ''}
            
        opt_col1, opt_col2 = st.columns(2)
        with opt_col1:
            st.markdown("**Phương án A:**")
            opt_a = interactive_math_editor(key=f"editor_single_opt_{q.code}_A", text=q.options.get('A', ''))
            if opt_a is not None: q.options['A'] = opt_a
            st.markdown("**Phương án B:**")
            opt_b = interactive_math_editor(key=f"editor_single_opt_{q.code}_B", text=q.options.get('B', ''))
            if opt_b is not None: q.options['B'] = opt_b

        with opt_col2:
            st.markdown("**Phương án C:**")
            opt_c = interactive_math_editor(key=f"editor_single_opt_{q.code}_C", text=q.options.get('C', ''))
            if opt_c is not None: q.options['C'] = opt_c
            st.markdown("**Phương án D:**")
            opt_d = interactive_math_editor(key=f"editor_single_opt_{q.code}_D", text=q.options.get('D', ''))
            if opt_d is not None: q.options['D'] = opt_d

        q.answer = st.radio("🔑 Chọn đáp án đúng:", ['A', 'B', 'C', 'D'], index=['A', 'B', 'C', 'D'].index(q.answer) if q.answer in ['A', 'B', 'C', 'D'] else 0, horizontal=True)

    elif q.format == QuestionType.DS:
        st.markdown("##### 📌 Tùy chọn đáp án Đúng / Sai (ĐS) - Sửa công thức trực tiếp bằng MathLive:")
        new_tf = []
        labels = ['a', 'b', 'c', 'd']
        for i, label in enumerate(labels):
            raw_stmt_tuple = q.tf_statements[i] if i < len(q.tf_statements) else (f"{label}) Mệnh đề {label}", "Đúng")
            curr_stmt = raw_stmt_tuple[0]
            curr_val = raw_stmt_tuple[1]
            clean_stmt_text = re.sub(r'^[a-d][\.\)\:-]\s*', '', curr_stmt, flags=re.IGNORECASE).strip()
            
            c_stmt, c_val = st.columns([4, 1])
            with c_stmt:
                st.markdown(f"**Ý {label}):**")
                updated_stmt = interactive_math_editor(key=f"editor_single_ds_{q.code}_{label}", text=clean_stmt_text)
                stmt_text = updated_stmt if updated_stmt is not None else clean_stmt_text
            
            with c_val:
                val_choice = st.selectbox(f"Đ/S ({label})", ["Đúng", "Sai"], index=0 if curr_val in ["Đúng", "D"] else 1, key=f"dialog_tf_val_{label}")
            
            new_tf.append((f"{label}) {stmt_text}", val_choice))
        q.tf_statements = new_tf
        q.answer = ", ".join([f"{l[0]}) {v}" for l, (_, v) in zip(labels, new_tf)])

    else:
        q.answer = st.text_input("🔑 Đáp án Trả lời ngắn (TLN):", value=q.answer)

    st.divider()

    # 4. LỜI GIẢI CHI TIẾT (CHỈ GIỮ DUY NHẤT MATHLIVE THEO YÊU CẦU ẢNH 2)
    st.markdown("##### 📝 Chỉnh sửa Lời giải chi tiết (Bấm trực tiếp vào ô màu đỏ để sửa công thức MathLive):")
    updated_sol = interactive_math_editor(key=f"editor_single_sol_{q.code}", text=q.solution if q.solution else "")
    if updated_sol is not None:
        q.solution = updated_sol

    # 5. TẢI ÁNH LỜI GIẢI
    sol_img_path = getattr(q, 'solution_image_path', None)
    if sol_img_path and os.path.exists(sol_img_path):
        st.markdown("##### 🖼️ Ảnh lời giải hiện tại:")
        img_col1, img_col2 = st.columns([2, 1])
        with img_col1: st.image(sol_img_path, width=220)
        with img_col2:
            st.write(""); st.write("")
            if st.button("🗑️ Xóa ảnh lời giải", key=f"del_sol_img_single_{q.code}"):
                if os.path.exists(sol_img_path):
                    try: os.remove(sol_img_path)
                    except Exception: pass
                q.solution_image_path = None
                db.save_questions([q])
                st.success("Đã xóa ảnh lời giải thành công!")
                time.sleep(0.6)
                st.rerun()

    uploaded_sol_img = st.file_uploader("🖼️ Thay đổi / Tải ảnh lời giải mới:", type=["png", "jpg", "jpeg"], key=f"upload_sol_img_single_{q.code}")
    if uploaded_sol_img:
        sol_img_save_path = os.path.join("images", f"{q.code}_sol.png")
        with open(sol_img_save_path, "wb") as f: f.write(uploaded_sol_img.getbuffer())
        q.solution_image_path = sol_img_save_path

    st.divider()

    btn_col1, btn_col2 = st.columns([3, 1])
    if btn_col1.button("💾 LƯU THAY ĐỔI CÂU HỎI", type="primary", use_container_width=True):
        register_topic(db.db_path, q.grade, q.chapter, q.topic)
        db.save_questions([q])
        st.success("Đã cập nhật câu hỏi thành công!")
        time.sleep(0.8)
        st.rerun()

    if btn_col2.button("🗑️ Xóa câu hỏi này", use_container_width=True):
        confirm_delete_dialog(q)


# 9. POPUP TAB 3
@st.dialog("📥 Phân loại & Chỉnh sửa chi tiết từng câu", width="large")
def show_import_modal(raw_text: str):
    default_meta = {"grade": 12, "chapter": 1, "topic": "Dạng 1", "level": 2, "source": "Đề thi thử THPT 2026"}

    if "temp_questions" not in st.session_state or st.session_state.get("reset_temp"):
        st.session_state["temp_questions"] = parse_raw_text_to_questions(raw_text, default_meta)
        st.session_state["reset_temp"] = False

    st.markdown("### ⚡ 1. Thiết lặp thông tin phân loại chung")
    col_a, col_b = st.columns(2)
    g_val = col_a.selectbox("Khối lớp (Chung)", [12, 11, 10], index=0)
    c_val = col_b.number_input("Chương (Chung)", 1, 20, 1)

    global_chap_topics = get_chapter_topics(db.db_path, g_val, c_val)
    top_global_options = global_chap_topics + ["➕ Nhập dạng bài mới..."]
    
    col_d, col_e = st.columns([2, 1])
    sel_global_top = col_d.selectbox(f"Chọn hoặc tìm Dạng bài (Lớp {g_val} - CH{c_val}):", top_global_options, index=0, key="global_top_sel")
    if sel_global_top == "➕ Nhập dạng bài mới...":
        t_val = col_d.text_input("Nhập tên Dạng bài mới:", value="Dạng 1. Cực trị hàm số", key="global_top_inp")
    else:
        t_val = sel_global_top

    col_f1, col_f2 = st.columns(2)
    lvl_val = col_f1.selectbox("Mức độ (Chung)", [1, 2, 3], index=1)

    all_stored_srcs = get_all_stored_sources(db.db_path)
    src_global_options = all_stored_srcs + ["➕ Nhập nguồn đề mới..."]
    sel_global_src = col_f2.selectbox("Chọn hoặc tìm Nguồn đề (Chung):", src_global_options, index=0, key="global_src_sel")
    if sel_global_src == "➕ Nhập nguồn đề mới...":
        src_val = col_f2.text_input("Nhập tên Nguồn đề mới:", value="Đề thi thử THPT 2026", key="global_src_inp")
    else:
        src_val = sel_global_src

    if st.button("🔄 Gán thông tin chung phía trên cho TẤT CẢ các câu", use_container_width=True):
        for q in st.session_state["temp_questions"]:
            q.grade = g_val
            q.chapter = c_val
            q.topic = t_val
            q.level = lvl_val
            q.source = src_val
        st.success("Đã áp dụng thông tin chung cho toàn bộ danh sách!")
        st.rerun()

    st.divider()
    st.markdown(f"### ✏️ 2. Chỉnh sửa chi tiết & Sửa công thức trực quan TỪNG CÂU ({len(st.session_state['temp_questions'])} câu)")

    for idx, q in enumerate(st.session_state["temp_questions"]):
        with st.container():
            st.markdown(f"""<div class="edit-q-box"><b>Câu {idx + 1}</b> [{q.format.value}]</div>""", unsafe_allow_html=True)
            
            # 1. ĐỀ BÀI
            st.markdown("<b>Sửa nội dung đề bài (Bấm trực tiếp vào ô đỏ để sửa công thức MathLive):</b>", unsafe_allow_html=True)
            if f"t3_raw_content_{idx}" not in st.session_state:
                st.session_state[f"t3_raw_content_{idx}"] = q.content

            curr_c = st.session_state.get(f"t3_raw_content_{idx}", q.content)
            updated_t3_content = interactive_math_editor(key=f"editor_t3_content_{idx}", text=curr_c)
            if updated_t3_content is not None and updated_t3_content != curr_c:
                st.session_state[f"t3_raw_content_{idx}"] = updated_t3_content
                q.content = updated_t3_content

            with st.expander("🛠️ Xem / Chỉnh sửa mã LaTeX thô đề bài"):
                new_raw_c = st.text_area("Mã LaTeX thô đề bài:", value=st.session_state[f"t3_raw_content_{idx}"], height=80, key=f"raw_t3_content_area_{idx}")
                if new_raw_c != st.session_state[f"t3_raw_content_{idx}"]:
                    st.session_state[f"t3_raw_content_{idx}"] = new_raw_c
                    q.content = new_raw_c
                    st.rerun()

            # 2. ÁNH ĐÍNH KÈM ĐỀ BÀI
            if q.image_path and os.path.exists(q.image_path):
                st.markdown("<b>🖼️ Ảnh đính kèm đề bài hiện tại:</b>", unsafe_allow_html=True)
                t3_img_col1, t3_img_col2 = st.columns([2, 1])
                with t3_img_col1: st.image(q.image_path, width=200)
                with t3_img_col2:
                    st.write("")
                    if st.button("🗑️ Xóa ảnh đề bài", key=f"del_t3_img_{idx}"):
                        if os.path.exists(q.image_path):
                            try: os.remove(q.image_path)
                            except Exception: pass
                        q.image_path = None
                        st.rerun()

            uploaded_img = st.file_uploader(f"🖼️ Tải ảnh đính kèm đề bài mới (Câu {idx+1}):", type=["png", "jpg", "jpeg"], key=f"t3_img_{idx}")
            if uploaded_img:
                temp_img_path = os.path.join("images", f"temp_{idx}.png")
                with open(temp_img_path, "wb") as f: f.write(uploaded_img.getbuffer())
                q.image_path = temp_img_path
                st.rerun()

            # 3. THÔNG TIN PHÂN LOẠI
            ct1, ct2, ct3 = st.columns([2, 1, 1])
            q_chap_topics = get_chapter_topics(db.db_path, q.grade, q.chapter)
            t3_top_options = q_chap_topics + ["➕ Nhập dạng bài mới..."]
            t3_top_default_idx = q_chap_topics.index(q.topic) if q.topic in q_chap_topics else (len(t3_top_options)-1 if q.topic else 0)
            
            sel_t3_top = ct1.selectbox(f"Chọn hoặc tìm Dạng bài (Câu {idx+1}):", t3_top_options, index=t3_top_default_idx, key=f"t3_top_sel_{idx}")
            if sel_t3_top == "➕ Nhập dạng bài mới...":
                q.topic = ct1.text_input(f"Nhập Dạng mới (Câu {idx+1}):", value="" if q.topic in q_chap_topics else q.topic, key=f"t3_top_inp_{idx}")
            else:
                q.topic = sel_t3_top

            q.format = QuestionType(ct2.selectbox(f"Loại (Câu {idx+1})", ["TN", "DS", "TLN"], index=["TN", "DS", "TLN"].index(q.format.value), key=f"t3_fmt_{idx}"))
            q.level = ct3.selectbox(f"Mức độ (Câu {idx+1})", [1, 2, 3], index=q.level-1, key=f"t3_lvl_{idx}")

            # 4. PHƯƠNG ÁN & ĐÁP ÁN
            if q.format == QuestionType.TN:
                st.markdown("<b>Phương án & Đáp án Trắc nghiệm (Sửa trực tiếp bằng MathLive):</b>", unsafe_allow_html=True)
                if not q.options: q.options = {'A': '', 'B': '', 'C': '', 'D': ''}
                
                t3_opt_col1, t3_opt_col2 = st.columns(2)
                with t3_opt_col1:
                    st.markdown("**Phương án A:**")
                    opt_a = interactive_math_editor(key=f"editor_t3_opt_{idx}_A", text=q.options.get('A', ''))
                    if opt_a is not None: q.options['A'] = opt_a

                    st.markdown("**Phương án B:**")
                    opt_b = interactive_math_editor(key=f"editor_t3_opt_{idx}_B", text=q.options.get('B', ''))
                    if opt_b is not None: q.options['B'] = opt_b

                with t3_opt_col2:
                    st.markdown("**Phương án C:**")
                    opt_c = interactive_math_editor(key=f"editor_t3_opt_{idx}_C", text=q.options.get('C', ''))
                    if opt_c is not None: q.options['C'] = opt_c

                    st.markdown("**Phương án D:**")
                    opt_d = interactive_math_editor(key=f"editor_t3_opt_{idx}_D", text=q.options.get('D', ''))
                    if opt_d is not None: q.options['D'] = opt_d
                
                ans_idx = ['A', 'B', 'C', 'D'].index(q.answer) if q.answer in ['A', 'B', 'C', 'D'] else 0
                q.answer = st.radio(f"🔑 Chọn đáp án đúng (Câu {idx+1}):", ['A', 'B', 'C', 'D'], index=ans_idx, key=f"t3_tn_{idx}", horizontal=True)

            elif q.format == QuestionType.DS:
                st.markdown("<b>Mệnh đề & Chọn Đúng/Sai từng ý (Sửa trực tiếp bằng MathLive):</b>", unsafe_allow_html=True)
                new_tf = []
                labels = ['a', 'b', 'c', 'd']
                for stmt_idx, label in enumerate(labels):
                    raw_stmt_tuple = q.tf_statements[stmt_idx] if stmt_idx < len(q.tf_statements) else (f"{label}) Mệnh đề {label}", "Đúng")
                    curr_stmt = raw_stmt_tuple[0]
                    curr_val = raw_stmt_tuple[1]
                    clean_stmt_text = re.sub(r'^[a-d][\.\)\:-]\s*', '', curr_stmt, flags=re.IGNORECASE).strip()
                    
                    c_txt, c_sel = st.columns([4, 1])
                    with c_txt:
                        st.markdown(f"**Ý {label}):**")
                        updated_stmt = interactive_math_editor(key=f"editor_t3_ds_{idx}_{label}", text=clean_stmt_text)
                        stmt_input = updated_stmt if updated_stmt is not None else clean_stmt_text
                    
                    with c_sel:
                        choice = st.selectbox(f"Đ/S ({label})", ["Đúng", "Sai"], index=0 if curr_val in ["Đúng", "D"] else 1, key=f"t3_ds_val_{idx}_{label}")
                    
                    new_tf.append((f"{label}) {stmt_input}", choice))
                q.tf_statements = new_tf
                q.answer = ", ".join([f"{l}) {v}" for l, (_, v) in zip(labels, new_tf)])

            else:
                q.answer = st.text_input(f"🔑 Nhập đáp án Trả lời ngắn (Câu {idx+1}):", value=q.answer, key=f"t3_tln_{idx}")

            # 5. LỜI GIẢI CHI TIẾT (CHỈ GIỮ NGUYÊN MATHLIVE ACCORDING TO IMAGE 2)
            st.markdown("<b>Sửa lời giải chi tiết (Bấm trực tiếp vào ô đỏ để sửa công thức MathLive):</b>", unsafe_allow_html=True)
            updated_t3_sol = interactive_math_editor(key=f"editor_t3_sol_{idx}", text=q.solution if q.solution else "")
            if updated_t3_sol is not None:
                q.solution = updated_t3_sol

            # 6. ÁNH LỜI GIẢI
            sol_img_path = getattr(q, 'solution_image_path', None)
            if sol_img_path and os.path.exists(sol_img_path):
                st.markdown("<b>🖼️ Ảnh lời giải hiện tại:</b>", unsafe_allow_html=True)
                t3_sol_img_col1, t3_sol_img_col2 = st.columns([2, 1])
                with t3_sol_img_col1: st.image(sol_img_path, width=200)
                with t3_sol_img_col2:
                    st.write("")
                    if st.button("🗑️ Xóa ảnh lời giải", key=f"del_t3_sol_img_{idx}"):
                        if os.path.exists(sol_img_path):
                            try: os.remove(sol_img_path)
                            except Exception: pass
                        q.solution_image_path = None
                        st.rerun()

            uploaded_sol_img = st.file_uploader(f"🖼️ Tải ảnh lời giải mới (Câu {idx+1}):", type=["png", "jpg", "jpeg"], key=f"t3_sol_img_{idx}")
            if uploaded_sol_img:
                temp_sol_img_path = os.path.join("images", f"temp_sol_{idx}.png")
                with open(temp_sol_img_path, "wb") as f: f.write(uploaded_sol_img.getbuffer())
                q.solution_image_path = temp_sol_img_path
                st.rerun()

            st.markdown("---")

    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("💾 LƯU TẤT CẢ VÀO DATABASE", type="primary", use_container_width=True):
        db_qs = db.get_all_questions()
        for q in st.session_state["temp_questions"]:
            register_topic(db.db_path, q.grade, q.chapter, q.topic)
            std_code = generate_standard_code(db_qs, q.grade, q.chapter, q.topic)
            
            if q.image_path and os.path.exists(q.image_path):
                final_img_path = os.path.join("images", f"{std_code}.png")
                try:
                    os.rename(q.image_path, final_img_path)
                    q.image_path = final_img_path
                except Exception: pass

            sol_img = getattr(q, 'solution_image_path', None)
            if sol_img and os.path.exists(sol_img):
                final_sol_img_path = os.path.join("images", f"{std_code}_sol.png")
                try:
                    os.rename(sol_img, final_sol_img_path)
                    q.solution_image_path = final_sol_img_path
                except Exception: pass

            q.code = std_code
            db_qs.append(q)

        db.save_questions(st.session_state["temp_questions"])
        st.session_state["reset_temp"] = True
        st.success("🎉 Đã sinh mã ID chuẩn theo Chương-Dạng và lưu thành công tất cả câu hỏi vào Database!")
        time.sleep(1)
        st.rerun()

    if col_btn2.button("❌ Hủy bỏ", use_container_width=True):
        st.session_state["reset_temp"] = True
        st.rerun()


# 10. TẠO TABS CHỨC NĂNG CHÍNH
tab1, tab2, tab3 = st.tabs(["📋 Ngân hàng câu hỏi", "🎯 Barem Ma trận & Tạo đề", "📥 Hệ thống nhập liệu"])

# ==============================================================================
# TAB 1: DANH SÁCH CÂU HỎI (BỘ LỌC SIDEBAR BỔ SUNG THÊM NGUỒN ĐỀ)
# ==============================================================================
with tab1:
    st.sidebar.markdown("### 📚 Bộ lọc Ngân hàng")
    
    grade_options = ["Tất cả", 12, 11, 10]
    grade_selected = st.sidebar.selectbox("Khối lớp", grade_options, index=0)
    questions_filtered = all_questions if grade_selected == "Tất cả" else [q for q in all_questions if q.grade == grade_selected]

    chapters = sorted(list(set(q.chapter for q in questions_filtered)))
    selected_chapter = st.sidebar.selectbox("Chương", ["Tất cả"] + chapters, index=0)
    if selected_chapter != "Tất cả":
        questions_filtered = [q for q in questions_filtered if q.chapter == selected_chapter]

    stored_topics = get_all_stored_topics(db.db_path, grade_selected, selected_chapter)
    selected_topic = st.sidebar.selectbox("Dạng bài", ["Tất cả"] + stored_topics, index=0)
    if selected_topic != "Tất cả":
        questions_filtered = [q for q in questions_filtered if q.topic == selected_topic]

    stored_sources = get_all_stored_sources(db.db_path)
    selected_source = st.sidebar.selectbox("Nguồn đề", ["Tất cả"] + stored_sources, index=0)
    if selected_source != "Tất cả":
        questions_filtered = [q for q in questions_filtered if q.source == selected_source]

    cnt_tn = sum(1 for q in questions_filtered if q.format == QuestionType.TN)
    cnt_ds = sum(1 for q in questions_filtered if q.format == QuestionType.DS)
    cnt_tln = sum(1 for q in questions_filtered if q.format == QuestionType.TLN)
    cnt_total = len(questions_filtered)

    st.sidebar.markdown(f"""
    <div class="stat-box">
        <div style="font-weight:700; color:#2c2825; margin-bottom:8px; border-bottom:1px solid #e2dbd0; padding-bottom:6px;">📊 Thống kê bộ lọc</div>
        <div class="stat-item"><span>Trắc nghiệm (TN):</span><span class="stat-number">{cnt_tn}</span></div>
        <div class="stat-item"><span>Đúng / Sai (ĐS):</span><span class="stat-number">{cnt_ds}</span></div>
        <div class="stat-item"><span>Trả lời ngắn (TLN):</span><span class="stat-number">{cnt_tln}</span></div>
        <div class="stat-item" style="font-weight:700; color:#2c2825; border-top:1px solid #e2dbd0; margin-top:6px; padding-top:8px;"><span>TỔNG SỐ CÂU:</span><span style="color:#5e7a4e; font-size:1.05rem;">{cnt_total}</span></div>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    if st.sidebar.button("🔄 Chuẩn hóa & Đánh lại mã ID", use_container_width=True):
        count_reindexed = reindex_all_database_ids()
        st.sidebar.success(f"🎉 Đã đánh lại mã ID liên tục cho {count_reindexed} câu hỏi!")
        time.sleep(1)
        st.rerun()

    st.markdown(f"""
    <div class="header-info-bar">
        <div>
            <span style="font-size:1.25rem; font-weight:700; color:#2c2825;">NGÂN HÀNG CÂU HỎI </span>
            <span style="margin-left:12px; font-size:0.88rem; color:#78716c; background-color:#f0ebe1; padding:4px 10px; border-radius:6px;">MÔN TOÁN GDPT 2018</span>
        </div>
        <div>
            <span style="background-color:#f7ece8; color:#a8412c; border:1px solid #e8c4b8; padding:6px 16px; border-radius:20px; font-weight:600; font-size:0.88rem;">
                📌 Số câu hiện có: <b>{cnt_total}</b> câu [TN: {cnt_tn} | ĐS: {cnt_ds} | TLN: {cnt_tln}]
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c_search, c_act = st.columns([2, 1])
    with c_search:
        search_query = st.text_input("🔍 Tìm kiếm trong nội dung hoặc nguồn đề...", "", label_visibility="collapsed")

    display_questions = [
        q for q in questions_filtered
        if search_query.lower() in q.content.lower() or search_query.lower() in (q.source or "").lower()
    ]

    with c_act:
        ca, cb = st.columns(2)
        if ca.button("Chọn tất cả"):
            for q in display_questions:
                st.session_state[f"chk_{q.code}"] = True
                st.session_state["selected_questions"].add(q.code)
            st.rerun()

        if cb.button("Xóa chọn"):
            for q in display_questions:
                st.session_state[f"chk_{q.code}"] = False
                st.session_state["selected_questions"].discard(q.code)
            st.rerun()

    st.markdown("##### 📄 Tải file Word câu hỏi đã chọn:")
    selected_objs = [q for q in all_questions if q.code in st.session_state["selected_questions"]]

    if st.button("📄 XUẤT FILE WORD VÀ TÙY CHỈNH", type="primary", use_container_width=True):
        if not selected_objs:
            st.error("Vui lòng tích chọn ít nhất 1 câu hỏi!")
        else:
            show_export_config_modal(selected_objs)

    st.markdown("<br>", unsafe_allow_html=True)

    grid_cols = st.columns(2)
    for idx, q in enumerate(display_questions):
        with grid_cols[idx % 2]:
            st.markdown(f"""
            <div class="question-card">
                <div>
                    <span class="badge-fmt">{q.format.value}</span>
                    <span class="card-badge">Câu {idx + 1} | {q.code}</span>
                </div>
            """, unsafe_allow_html=True)
            
            c_edit, c_del, c_chk = st.columns([1, 1, 3])
            if c_edit.button("✏️ Sửa", key=f"btn_edit_{q.code}"):
                show_single_question_edit_dialog(q)

            if c_del.button("🗑️ Xóa", key=f"btn_del_{q.code}"):
                confirm_delete_dialog(q)

            is_selected = q.code in st.session_state["selected_questions"]
            if c_chk.checkbox(f"Chọn câu {q.code}", value=is_selected, key=f"chk_{q.code}"):
                st.session_state["selected_questions"].add(q.code)
            else:
                st.session_state["selected_questions"].discard(q.code)

            st.write(q.content)

            if q.image_path and os.path.exists(q.image_path):
                st.image(q.image_path, use_container_width=True)

            if q.format == QuestionType.TN and q.options:
                for k, v in q.options.items(): st.write(f"**{k}.** {v}")
            elif q.format == QuestionType.DS and q.tf_statements:
                for stmt, status in q.tf_statements: st.write(f"- {stmt} **[{status}]**")

            if q.answer:
                st.markdown(f'<div class="answer-box">Đáp án: {q.answer}</div>', unsafe_allow_html=True)

            if q.solution or getattr(q, 'solution_image_path', None):
                with st.expander("Lời giải chi tiết"):
                    if q.solution: st.write(q.solution)
                    sol_img = getattr(q, 'solution_image_path', None)
                    if sol_img and os.path.exists(sol_img): st.image(sol_img, use_container_width=True)

            st.markdown("</div>", unsafe_allow_html=True)


# ==============================================================================
# TAB 2: BAREM MA TRẬN & TẠO ĐỀ
# ==============================================================================
with tab2:
    st.title("🎯 Barem Ma trận Đề thi GDPT 2018")
    st.caption("Cấu hình số lượng câu theo chủ đề và cấp độ tư duy (1: Nhận biết, 2: Thông hiểu, 3: Vận dụng).")

    stored_topics = get_all_stored_topics(db.db_path)
    stored_chaps = sorted(list(set(q.chapter for q in all_questions))) if all_questions else [1]
    chap_options = [f"Chương {c}" for c in stored_chaps]
    
    matrix_options = chap_options + stored_topics
    if not matrix_options: matrix_options = ["Chương 1", "Dạng 1. Khảo sát tính đơn điệu"]

    default_matrix_data = [{
        "Chủ đề / Nội dung": matrix_options[0],
        "TN - 1": 1, "TN - 2": 1, "TN - 3": 0,
        "DS - 1": 1, "DS - 2": 0, "DS - 3": 0,
        "TLN - 1": 0, "TLN - 2": 1, "TLN - 3": 0,
    }]

    if "matrix_df" not in st.session_state:
        st.session_state["matrix_df"] = pd.DataFrame(default_matrix_data)

    edited_df = st.data_editor(
        st.session_state["matrix_df"], num_rows="dynamic", use_container_width=True,
        column_config={
            "Chủ đề / Nội dung": st.column_config.SelectboxColumn("Chủ đề / Nội dung (Chương hoặc Dạng)", options=matrix_options, required=True),
            "TN - 1": st.column_config.NumberColumn("TN (1)", min_value=0, default=0),
            "TN - 2": st.column_config.NumberColumn("TN (2)", min_value=0, default=0),
            "TN - 3": st.column_config.NumberColumn("TN (3)", min_value=0, default=0),
            "DS - 1": st.column_config.NumberColumn("ĐS (1)", min_value=0, default=0),
            "DS - 2": st.column_config.NumberColumn("ĐS (2)", min_value=0, default=0),
            "DS - 3": st.column_config.NumberColumn("ĐS (3)", min_value=0, default=0),
            "TLN - 1": st.column_config.NumberColumn("TLN (1)", min_value=0, default=0),
            "TLN - 2": st.column_config.NumberColumn("TLN (2)", min_value=0, default=0),
            "TLN - 3": st.column_config.NumberColumn("TLN (3)", min_value=0, default=0),
        },
        key="editor_matrix"
    )

    num_cols = ["TN - 1", "TN - 2", "TN - 3", "DS - 1", "DS - 2", "DS - 3", "TLN - 1", "TLN - 2", "TLN - 3"]
    calc_df = edited_df.copy()
    for col in num_cols: calc_df[col] = pd.to_numeric(calc_df[col], errors='coerce').fillna(0).astype(int)

    total_tn = calc_df[["TN - 1", "TN - 2", "TN - 3"]].sum().sum()
    total_ds = calc_df[["DS - 1", "DS - 2", "DS - 3"]].sum().sum()
    total_tln = calc_df[["TLN - 1", "TLN - 2", "TLN - 3"]].sum().sum()
    total_exam = calc_df[num_cols].sum().sum()

    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Trắc nghiệm (TN)", f"{total_tn} câu")
    m2.metric("Đúng / Sai (ĐS)", f"{total_ds} câu")
    m3.metric("Trả lời ngắn (TLN)", f"{total_tln} câu")
    m4.metric("TỔNG CẢ ĐỀ", f"{total_exam} câu")

    st.divider()

    st.subheader("⚙️ Cấu hình Tùy chỉnh danh sách Mã đề thi")
    num_exams_to_create = st.number_input("Số lượng mã đề thi cần tạo:", min_value=1, max_value=20, value=2)

    st.write("📝 **Nhập danh sách mã đề thi tương ứng:**")
    custom_exam_codes = []
    cols_code = st.columns(min(int(num_exams_to_create), 4))
    
    for i in range(int(num_exams_to_create)):
        with cols_code[i % min(int(num_exams_to_create), 4)]:
            code_input = st.text_input(f"Mã đề {i+1}:", value=f"{101 + i}", key=f"t2_custom_code_{i}")
            custom_exam_codes.append(code_input.strip())

    if st.button("🎲 TỰ ĐỘNG TRỘN & TẠO CÁC MÃ ĐỀ THI", type="primary", use_container_width=True):
        base_questions = []
        errors = []

        for _, row in calc_df.iterrows():
            topic_or_chap = row["Chủ đề / Nội dung"]
            spec_map = [
                ("TN - 1", QuestionType.TN, 1), ("TN - 2", QuestionType.TN, 2), ("TN - 3", QuestionType.TN, 3),
                ("DS - 1", QuestionType.DS, 1), ("DS - 2", QuestionType.DS, 2), ("DS - 3", QuestionType.DS, 3),
                ("TLN - 1", QuestionType.TLN, 1), ("TLN - 2", QuestionType.TLN, 2), ("TLN - 3", QuestionType.TLN, 3),
            ]

            for col_name, q_fmt, q_lvl in spec_map:
                req_count = int(row[col_name])
                if req_count > 0:
                    if topic_or_chap.startswith("Chương "):
                        try:
                            chap_num = int(topic_or_chap.replace("Chương ", "").strip())
                            candidates = [q for q in all_questions if q.chapter == chap_num and q.format == q_fmt and q.level == q_lvl]
                        except ValueError:
                            candidates = [q for q in all_questions if q.topic == topic_or_chap and q.format == q_fmt and q.level == q_lvl]
                    else:
                        candidates = [q for q in all_questions if q.topic == topic_or_chap and q.format == q_fmt and q.level == q_lvl]

                    if len(candidates) < req_count:
                        errors.append(f"⚠️ '{topic_or_chap}' [{q_fmt.value} - Cấp {q_lvl}]: Thiếu câu (Cần {req_count}, có {len(candidates)}).")
                        base_questions.extend(candidates)
                    else:
                        base_questions.extend(random.sample(candidates, req_count))

        if errors:
            for err in errors: st.warning(err)

        if base_questions:
            st.session_state["generated_exams_dict"] = {}
            for e_code in custom_exam_codes:
                shuffled_qs = list(base_questions)
                random.shuffle(shuffled_qs)
                st.session_state["generated_exams_dict"][e_code] = shuffled_qs

            st.success(f"🎉 Đã trộn ngẫu nhiên thành công **{len(custom_exam_codes)}** mã đề thi!")

    if "generated_exams_dict" in st.session_state and st.session_state["generated_exams_dict"]:
        st.markdown("### 📥 Tải về các Mã đề thi đã tạo:")
        for e_code, q_list in st.session_state["generated_exams_dict"].items():
            with st.expander(f"📌 MÃ ĐỀ THI: {e_code} ({len(q_list)} câu)", expanded=True):
                if st.button(f"📄 Tùy chỉnh & Tải file Word Mã đề {e_code}", key=f"btn_exp_modal_{e_code}", use_container_width=True):
                    show_export_config_modal(q_list, test_code=e_code)


# ==============================================================================
# TAB 3: NHẬP LIỆU NHANH (CHỈ HIỂN THỊ DUY NHẤT BỘ GÕ MATHLIVE CHIP ĐỎ - BỎ HẲN TEXTAREA LATEX THÔ)
# ==============================================================================
with tab3:
    st.title("📥 Hệ thống tự động phân loại câu hỏi")
    st.caption("Dán toàn bộ văn bản đề bài vào ô duy nhất dưới đây. Hệ thống tự nhận diện 'Câu hỏi:', 'Đáp án:' và 'Lời giải:'.")

    sample_paste_text = """Câu hỏi: Cho hàm số $y = \\dfrac{2x + 1}{x + 1}$. Mệnh đề nào đúng?
A. Hàm số đồng biến trên các khoảng $(-\\infty; -1)$ và $(-1; +\\infty)$.
B. Hàm số đồng biến trên $(-\\infty; -1) \\cup (-1; +\\infty)$.
C. Hàm số nghịch biến trên khoảng $(-1; 0)$.
D. Hàm số nghịch biến trên $(-2; -1)$.
Đáp án: A
Lời giải: Ta có đạo hàm $y' = \\dfrac{1}{(x+1)^2} > 0$ với mọi $x \\neq -1$.

Câu hỏi: Cho hàm số $y = f(x)$ có bảng xét dấu đạo hàm:
a) Hàm số đồng biến trên khoảng $(-3; 0)$.
b) Hàm số có 2 điểm cực đại.
c) Điểm cực tiểu là $x = -3$.
d) Giá trị cực đại là $f(-1)$.
Đáp án: a) Đúng, b) Sai, c) Đúng, d) Đúng
Lời giải: Dựa vào bảng xét dấu đạo hàm ta kết luận được các mệnh đề."""

    if "tab3_input_text" not in st.session_state:
        st.session_state["tab3_input_text"] = sample_paste_text

    st.markdown("##### 📝 Khung dán văn bản & Sửa công thức MathLive trực tiếp (Dán Ctrl+V từ ChatGPT/Word tại đây):")
    edited_live_text = interactive_math_editor(key="tab3_main_raw_editor", text=st.session_state["tab3_input_text"])
    if edited_live_text is not None and edited_live_text != st.session_state["tab3_input_text"]:
        st.session_state["tab3_input_text"] = edited_live_text

    if st.button("🔍 PHÂN TÍCH & MỞ POPUP ĐIỀU CHỈNH CHI TIẾT", type="primary", use_container_width=True):
        if not st.session_state["tab3_input_text"].strip():
            st.warning("Vui lòng dán văn bản câu hỏi trước khi nhấn phân tích!")
        else:
            st.session_state["reset_temp"] = True
            show_import_modal(st.session_state["tab3_input_text"])