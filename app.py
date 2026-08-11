import os
import re
import time
import random
import io
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
from streamlit_paste_button import paste_image_button
from models import Question, QuestionType
from exporter import export_questions_to_word
from cloud_db import (
    load_all_questions_from_cloud,
    save_questions_to_cloud,
    delete_question_from_cloud,
    upload_image_to_drive
)

# 1. CẤU HÌNH TRANG STREAMLIT
st.set_page_config(
    page_title="Ngân hàng câu hỏi",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# KHÓA MẬT KHẨU TRUY CẬP APP (NẾU CÓ TRONG SECRETS)
def check_password():
    if "APP_PASSWORD" not in st.secrets:
        return True
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        st.title("🔒 Đăng nhập Ngân hàng câu hỏi")
        pwd = st.text_input("Nhập mật khẩu truy cập:", type="password")
        if st.button("Đăng nhập", type="primary"):
            if pwd == st.secrets["APP_PASSWORD"]:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Mật khẩu không chính xác!")
        return False
    return True

if not check_password():
    st.stop()

# 2. KHỞI TẠO COMPONENT MATHLIVE CHUẨN NGUYÊN BẢN
COMPONENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mathlive_component")
if not os.path.exists(COMPONENT_DIR):
    os.makedirs(COMPONENT_DIR, exist_ok=True)

interactive_math_editor_comp = components.declare_component(
    "interactive_math_editor",
    path=COMPONENT_DIR
)

def interactive_math_editor(key: str, text: str, height_mode: str = "compact") -> str:
    """Wrapper gọi bộ soạn thảo MathLive an toàn - Mở rộng khung dán Tab 3 lên 600px"""
    h_val = 600 if height_mode == "large" else 180
    val = interactive_math_editor_comp(key=key, text=text, height_mode=height_mode, default=text, height=h_val)
    return val if val is not None else text

# 3. KHỞI TẠO DỮ LIỆU TỪ GOOGLE SHEETS / CLOUD
all_questions = load_all_questions_from_cloud()

if "selected_questions" not in st.session_state:
    st.session_state["selected_questions"] = set()

if "show_import_modal" not in st.session_state:
    st.session_state["show_import_modal"] = False

# HÀM TẠO THƯ MỤC LƯU FILE WORD XUẤT RA
def get_export_dir() -> str:
    today_str = datetime.now().strftime("%d-%m-%Y")
    export_dir = os.path.join(os.getcwd(), "exports", f"Đề tạo ngày {today_str}")
    os.makedirs(export_dir, exist_ok=True)
    return export_dir

# POPUP XUẤT WORD
@st.dialog("📄 Cài đặt Tùy chọn Xuất file Word", width="large")
def show_export_config_modal(questions_to_export: list, test_code: str = ""):
    st.markdown("### ⚙️ Cấu hình định dạng file Word")
    st.caption(f"Đang chuẩn bị xuất **{len(questions_to_export)}** câu hỏi sang định dạng Word (.docx)")

    col1, col2 = st.columns(2)
    with col1:
        ds_fmt_choice = st.radio("Định dạng câu Đúng/Sai:", ["Dạng bảng 2 cột (Đúng/Sai)", "Từng dòng liên tiếp"], index=0)
    with col2:
        tln_fmt_choice = st.radio("Định dạng ô điền trả lời ngắn:", ["Có ô điền (5 ô 0.8cm x 0.8cm sát lề phải)", "Không có ô điền"], index=0)

    st.divider()

    ds_tbl = (ds_fmt_choice == "Dạng bảng 2 cột (Đúng/Sai)")
    tln_box = (tln_fmt_choice == "Có ô điền (5 ô 0.8cm x 0.8cm sát lề phải)")
    export_dir = get_export_dir()
    file_suffix = f"_{test_code}" if test_code else ""

    if st.button("🚀 BẮT ĐẦU TẠO CÁC FILE WORD", type="primary", width="stretch"):
        path_degoc = os.path.join(export_dir, f"1_De_Thi_Goc{file_suffix}.docx")
        export_questions_to_word(questions_to_export, path_degoc, mode="de_goc", ds_table_format=ds_tbl, tln_box_format=tln_box, test_code=test_code)

        path_dongchua = os.path.join(export_dir, f"2_De_Co_Dong_Chua_Bai{file_suffix}.docx")
        export_questions_to_word(questions_to_export, path_dongchua, mode="de_dong_chua", ds_table_format=ds_tbl, tln_box_format=tln_box, test_code=test_code)

        path_dapan = os.path.join(export_dir, f"3_Bang_Dap_An{file_suffix}.docx")
        export_questions_to_word(questions_to_export, path_dapan, mode="dap_an", ds_table_format=True, tln_box_format=tln_box, test_code=test_code)

        path_loigiai = os.path.join(export_dir, f"4_Loi_Giai_Chi_Tiet{file_suffix}.docx")
        export_questions_to_word(questions_to_export, path_loigiai, mode="loi_giai_chi_tiet", ds_table_format=ds_tbl, tln_box_format=tln_box, test_code=test_code)

        st.session_state[f"export_paths_{test_code}"] = {
            "degoc": path_degoc, "dongchua": path_dongchua, "dapan": path_dapan, "loigiai": path_loigiai
        }
        st.success("🎉 Đã tạo thành công toàn bộ 4 bản Word! Chọn phiên bản bên dưới để tải về:")

    if f"export_paths_{test_code}" in st.session_state:
        paths = st.session_state[f"export_paths_{test_code}"]
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        with open(paths["degoc"], "rb") as f: c1.download_button("📝 Tải về đề thi gốc", f, file_name=os.path.basename(paths["degoc"]), width="stretch")
        with open(paths["dongchua"], "rb") as f: c2.download_button("✍️ Tải đề có dòng chữa bài", f, file_name=os.path.basename(paths["dongchua"]), width="stretch")
        with open(paths["dapan"], "rb") as f: c3.download_button("🔑 Tải về đáp án nhanh", f, file_name=os.path.basename(paths["dapan"]), width="stretch")
        with open(paths["loigiai"], "rb") as f: c4.download_button("📖 Tải về lời giải chi tiết", f, file_name=os.path.basename(paths["loigiai"]), width="stretch")

# POPUP XÓA CÂU HỎI
@st.dialog("🗑️ Xác nhận xóa câu hỏi", width="small")
def confirm_delete_dialog(q: Question):
    st.write(f"Bạn có chắc chắn muốn xóa câu hỏi **{q.code}** khỏi cơ sở dữ liệu không?")
    col_yes, col_no = st.columns(2)
    if col_yes.button("❌ Có, xóa ngay", type="primary", width="stretch"):
        delete_question_from_cloud(q.code)
        st.session_state["selected_questions"].discard(q.code)
        st.success(f"Đã xóa câu hỏi {q.code}!")
        time.sleep(0.6)
        st.rerun()

    if col_no.button("Hủy bỏ", width="stretch"):
        st.rerun()

def get_chapter_topics(questions: list, grade: int, chapter: int) -> list:
    return sorted(list(set(q.topic for q in questions if q.grade == grade and q.chapter == chapter and q.topic)))

def get_all_stored_topics(questions: list) -> list:
    return sorted(list(set(q.topic for q in questions if q.topic)))

def get_all_stored_sources(questions: list) -> list:
    return sorted(list(set(q.source for q in questions if q.source)))

def extract_topic_num_for_chapter(topic_str: str, chapter_topics: list) -> int:
    match = re.search(r'(?:Dạng|D)\s*(\d+)', topic_str, re.IGNORECASE)
    if match: return int(match.group(1))
    if topic_str in chapter_topics: return chapter_topics.index(topic_str) + 1
    return len(chapter_topics) + 1 if topic_str not in chapter_topics else 1

def generate_standard_code(questions: list, grade: int, chapter: int, topic: str) -> str:
    chap_topics = get_chapter_topics(questions, grade, chapter)
    d_num = extract_topic_num_for_chapter(topic, chap_topics)
    prefix = f"TOAN{grade}_CH{chapter}_D{d_num}_"
    existing_seqs = [int(q.code.replace(prefix, "")) for q in questions if q.code.startswith(prefix) and q.code.replace(prefix, "").isdigit()]
    next_seq = max(existing_seqs) + 1 if existing_seqs else 1
    return f"{prefix}{next_seq:04d}"

# HÀM CHUẨN HÓA VÀ ĐÁNH LẠI MÃ ID CHO TOÀN BỘ NGÂN HÀNG
def reindex_all_database_ids() -> int:
    questions = load_all_questions_from_cloud()
    if not questions: return 0

    grade_chap_groups = {}
    for q in questions:
        key = (q.grade, q.chapter)
        grade_chap_groups.setdefault(key, []).append(q)

    updated_questions = []

    for (g, c), gc_questions in grade_chap_groups.items():
        distinct_topics = get_chapter_topics(questions, g, c)
        topic_groups = {}
        for q in gc_questions:
            topic_groups.setdefault(q.topic, []).append(q)

        for top, q_list in topic_groups.items():
            d_num = extract_topic_num_for_chapter(top, distinct_topics)
            prefix = f"TOAN{g}_CH{c}_D{d_num}_"
            
            for idx, q in enumerate(q_list, start=1):
                new_code = f"{prefix}{idx:04d}"
                q.code = new_code
                updated_questions.append(q)

    save_questions_to_cloud(updated_questions)
    return len(updated_questions)

# CSS ĐỒNG BỘ GOOGLE SANS VÀ CAN GIỮA TABS
st.markdown("""
<style>
    @import url('https://fonts.cdnfonts.com/css/google-sans');
    
    html, body, [class*="css"], .stApp { 
        font-family: 'Google Sans', -apple-system, BlinkMacSystemFont, sans-serif !important; 
        color: #2c2825 !important; 
        background-color: #f7f4ed !important; 
    }
    
    section[data-testid="stSidebar"] { 
        background-color: #f0ebe1 !important; 
        border-right: 1px solid #e2dbd0 !important; 
        padding-top: 1rem;
    }

    div[data-testid="stTabs"] {
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        width: 100% !important;
        background: transparent !important;
    }

    div[data-testid="stTabs"] > div[data-baseweb="tab-list"],
    div[data-baseweb="tab-list"] { 
        display: inline-flex !important; 
        justify-content: center !important; 
        align-items: center !important; 
        gap: 10px !important; 
        background-color: #ffffff !important; 
        padding: 8px 12px !important; 
        border-radius: 999px !important; 
        border: 1px solid #e2dbd0 !important; 
        width: fit-content !important;
        margin: 0 auto 28px auto !important; 
        box-shadow: 0 8px 24px rgba(44, 40, 37, 0.08) !important; 
    }

    button[data-baseweb="tab"] { 
        height: 52px !important; 
        min-width: 220px !important; 
        border-radius: 999px !important; 
        padding: 0px 32px !important; 
        font-family: 'Google Sans', sans-serif !important;
        font-size: 1.05rem !important; 
        font-weight: 700 !important; 
        color: #57524e !important; 
        border: none !important; 
        background-color: transparent !important; 
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        cursor: pointer !important;
        transition: all 0.22s ease-in-out !important;
    }

    button[data-baseweb="tab"]:hover {
        background-color: #f7ece8 !important;
        color: #b8543f !important;
    }

    button[data-baseweb="tab"][aria-selected="true"] { 
        background-color: #b8543f !important; 
        color: #ffffff !important; 
        box-shadow: 0 4px 16px rgba(184, 84, 63, 0.35) !important; 
    }
    
    div[data-baseweb="tab-highlight-title"], 
    div[data-baseweb="tab-border"] { 
        display: none !important; 
    }

    .stButton > button { 
        font-family: 'Google Sans', sans-serif !important;
        border-radius: 16px !important; 
        border: 1px solid #d8cfc4 !important; 
        background-color: #ffffff !important; 
        color: #2c2825 !important; 
        font-weight: 600 !important; 
        padding: 12px 20px !important; 
        min-height: 48px !important;
        cursor: pointer !important;
        transition: all 0.2s ease !important; 
        box-shadow: 0 2px 8px rgba(0,0,0,0.03) !important;
    }
    .stButton > button:hover { 
        border-color: #b8543f !important; 
        color: #b8543f !important; 
        background-color: #f7ece8 !important; 
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 16px rgba(184, 84, 63, 0.15) !important;
    }
    .stButton > button[kind="primary"] { 
        background-color: #b8543f !important; 
        color: #ffffff !important; 
        border: 1px solid #a34834 !important; 
        box-shadow: 0 4px 14px rgba(184, 84, 63, 0.25) !important;
    }
    .stButton > button[kind="primary"]:hover { 
        background-color: #a34834 !important; 
        color: #ffffff !important; 
        box-shadow: 0 8px 20px rgba(184, 84, 63, 0.35) !important;
    }

    .question-card { 
        background-color: #ffffff !important; 
        border: 1px solid #e8e2d8 !important; 
        border-radius: 20px !important; 
        padding: 22px !important; 
        margin-bottom: 20px !important; 
        box-shadow: 0 8px 24px rgba(44, 40, 37, 0.04) !important; 
    }
    .card-badge { 
        background-color: #b8543f !important; 
        color: #ffffff !important; 
        padding: 6px 14px !important; 
        border-radius: 999px !important; 
        font-size: 0.8rem !important; 
        font-weight: 700 !important; 
        font-family: 'JetBrains Mono', monospace !important; 
    }
    .badge-fmt { 
        background-color: #5e7a4e !important; 
        color: #ffffff !important; 
        padding: 6px 12px !important; 
        border-radius: 999px !important; 
        font-size: 0.78rem !important; 
        font-weight: 700 !important; 
        margin-right: 8px !important; 
    }
    .stat-box { 
        background-color: #ffffff !important; 
        border: 1px solid #e8e2d8 !important; 
        border-radius: 18px !important; 
        padding: 18px !important; 
        margin-top: 18px !important; 
    }
    .stat-item { 
        display: flex !important; 
        justify-content: space-between !important; 
        align-items: center !important; 
        padding: 8px 0 !important; 
        border-bottom: 1px dashed #eae3d8 !important; 
        font-size: 0.88rem !important; 
    }
    .stat-number { 
        font-weight: 700 !important; 
        color: #b8543f !important; 
        font-family: 'JetBrains Mono', monospace !important; 
    }
    .answer-box { 
        background-color: #f7ece8 !important; 
        border: 1px solid #e8c4b8 !important; 
        color: #a8412c !important; 
        padding: 8px 16px !important; 
        border-radius: 12px !important; 
        font-weight: 700 !important; 
        display: inline-block !important; 
        margin-top: 12px !important; 
    }
    .header-info-bar { 
        background-color: #ffffff !important; 
        border: 1px solid #e8e2d8 !important; 
        border-radius: 20px !important; 
        padding: 18px 24px !important; 
        margin-bottom: 22px !important; 
        display: flex !important; 
        align-items: center !important; 
        justify-content: space-between !important; 
        box-shadow: 0 6px 18px rgba(44, 40, 37, 0.03) !important; 
    }

    div[data-baseweb="input"], div[data-baseweb="select"], div[data-baseweb="textarea"] { 
        background-color: #ffffff !important; 
        border-color: #d8cfc4 !important; 
        border-radius: 12px !important; 
    }

    iframe[title*="interactive_math_editor"] { 
        width: 100% !important; 
        border-radius: 16px !important; 
    }
</style>
""", unsafe_allow_html=True)

# PARSER THÔNG MINH
def parse_raw_text_to_questions(raw_text: str, default_meta: dict) -> list[Question]:
    if not raw_text or not raw_text.strip(): return []
    pattern = r'\n(?=\s*(?:Câu|CÂU)(?:\s*hỏi)?(?:\s*\d+)?[\.:\s])'
    q_blocks = re.split(pattern, raw_text.strip())
    parsed_questions = []

    for block in q_blocks:
        block = block.strip()
        if not block or (not re.search(r'(?:Câu|CÂU)', block, re.IGNORECASE) and not re.search(r'^[a-d][\.\)]', block, re.MULTILINE)): continue

        ans_match = re.search(r'(?:^|\n)\s*(?:Đáp án|ĐÁP ÁN|Đáp án:|ĐÁP ÁN:)\s*(.*?)(?=\n\s*(?:Lời giải|LỜI GIẢI)\s*:|$)', block, re.DOTALL | re.IGNORECASE)
        sol_match = re.search(r'(?:^|\n)\s*(?:Lời giải|LỜI GIẢI|Lời giải:|LỜI GIẢI:)\s*(.*)', block, re.DOTALL | re.IGNORECASE)

        extracted_ans, extracted_sol, clean_content = "", "", block

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

        content_lines, options, tf_statements = [], {}, []
        q_fmt = QuestionType.DS if (has_ds and not has_tn) else (QuestionType.TN if (has_tn and not has_ds) else (QuestionType.DS if has_ds else (QuestionType.TN if has_tn else QuestionType.TLN)))

        if q_fmt == QuestionType.DS:
            is_ds = False
            for line in lines:
                ds_match = re.match(r'^([a-d])[\.\)\:-]\s*(.*)', line)
                if ds_match:
                    is_ds = True
                    lbl, val = ds_match.group(1).lower(), ds_match.group(2).strip()
                    stmt_status = "Đúng"
                    if extracted_ans:
                        st_m = re.search(rf'{lbl}[\)\.\:-]?\s*(Đúng|Sai|Đ|S|True|False)', extracted_ans, re.IGNORECASE)
                        if st_m: stmt_status = "Sai" if st_m.group(1).upper() in ['SAI', 'S', 'FALSE'] else "Đúng"
                    tf_statements.append((f"{lbl}) {val}", stmt_status))
                elif not is_ds: content_lines.append(line)
            final_ans = ", ".join([f"{l[0]}) {v}" for l, (_, v) in zip(['a', 'b', 'c', 'd'], tf_statements)]) if tf_statements else extracted_ans

        elif q_fmt == QuestionType.TN:
            is_opt = False
            for line in lines:
                opt_match = re.match(r'^([A-D])[\.\)]\s*(.*)', line)
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
            content_lines, final_ans = lines, extracted_ans

        parsed_questions.append(Question(
            code="TEMP_CODE", grade=default_meta['grade'], chapter=default_meta['chapter'], lesson=1,
            topic=default_meta['topic'], format=q_fmt, level=default_meta['level'], source=default_meta['source'],
            content="\n".join(content_lines), options=options, tf_statements=tf_statements, answer=final_ans, solution=extracted_sol, image_path=None
        ))

    return parsed_questions

# POPUP SỬA 1 CÂU HỎI
@st.dialog("✏️ Chỉnh sửa câu hỏi", width="large")
def show_single_question_edit_dialog(q: Question):
    st.subheader(f"Chỉnh sửa câu hỏi: {q.code}")

    col_a, col_b = st.columns(2)
    q.grade = col_a.selectbox("Khối lớp", [12, 11, 10], index=[12, 11, 10].index(q.grade))
    q.chapter = col_b.number_input("Chương", min_value=1, value=q.chapter)

    key_custom_top_s = f"custom_top_single_{q.code}"
    if key_custom_top_s not in st.session_state: st.session_state[key_custom_top_s] = False

    chap_topics = get_chapter_topics(all_questions, q.grade, q.chapter)
    if st.session_state[key_custom_top_s]:
        c_i, c_b = st.columns([5, 1])
        q.topic = c_i.text_input("Nhập tên Dạng bài mới:", value=q.topic if q.topic not in chap_topics else "", key=f"single_top_inp_{q.code}")
        if c_b.button("↩️", key=f"btn_canc_single_top_{q.code}"):
            st.session_state[key_custom_top_s] = False
            st.rerun()
    else:
        top_options = chap_topics + ["➕ Nhập dạng bài mới..."]
        default_top_idx = chap_topics.index(q.topic) if q.topic in chap_topics else 0
        sel_topic = st.selectbox(f"Dạng bài (Lớp {q.grade} - CH{q.chapter}):", top_options, index=default_top_idx, key=f"single_top_sel_{q.code}")
        if sel_topic == "➕ Nhập dạng bài mới...":
            st.session_state[key_custom_top_s] = True
            st.rerun()
        else:
            q.topic = sel_topic

    col_f1, col_f2 = st.columns(2)
    q.level = col_f1.selectbox("Mức độ", [1, 2, 3], index=q.level-1)

    key_custom_src_s = f"custom_src_single_{q.code}"
    if key_custom_src_s not in st.session_state: st.session_state[key_custom_src_s] = False

    all_sources = get_all_stored_sources(all_questions)
    if st.session_state[key_custom_src_s]:
        c_i, c_b = col_f2.columns([4, 1])
        q.source = c_i.text_input("Nhập Nguồn đề mới:", value=q.source if (q.source and q.source not in all_sources) else "", key=f"single_src_inp_{q.code}")
        if c_b.button("↩️", key=f"btn_canc_single_src_{q.code}"):
            st.session_state[key_custom_src_s] = False
            st.rerun()
    else:
        src_options = all_sources + ["➕ Nhập nguồn đề mới..."]
        default_src_idx = all_sources.index(q.source) if (q.source and q.source in all_sources) else 0
        sel_source = col_f2.selectbox("Nguồn đề:", src_options, index=default_src_idx, key=f"single_src_sel_{q.code}")
        if sel_source == "➕ Nhập nguồn đề mới...":
            st.session_state[key_custom_src_s] = True
            st.rerun()
        else:
            q.source = sel_source

    st.divider()

    st.markdown("##### 📝 Chỉnh sửa đề bài (Sửa trực tiếp bằng MathLive):")
    updated_content = interactive_math_editor(key=f"editor_single_content_{q.code}", text=q.content, height_mode="compact")
    if updated_content is not None: q.content = updated_content

    if q.image_path:
        st.markdown("##### 🖼️ Ảnh đính kèm đề bài hiện tại:")
        img_col1, img_col2 = st.columns([2, 1])
        with img_col1: st.image(q.image_path, width=220)
        with img_col2:
            if st.button("🗑️ Xóa ảnh đề bài", key=f"del_img_single_{q.code}"):
                q.image_path = None
                save_questions_to_cloud([q])
                st.success("Đã xóa ảnh đề bài thành công!")
                time.sleep(0.6)
                st.rerun()

    st.markdown("##### 🖼️ Tải/Dán ảnh đính kèm đề bài mới:")
    col_p1, col_p2 = st.columns([1, 1])
    with col_p1:
        paste_res_q = paste_image_button(
            label="📋 Dán từ Clipboard (1-Click)",
            background_color="#b8543f",
            text_color="#ffffff",
            hover_color="#a34834",
            key=f"paste_img_single_{q.code}"
        )
    with col_p2:
        uploaded_img = st.file_uploader("Tải file ảnh từ máy", type=["png", "jpg", "jpeg"], key=f"upload_img_single_{q.code}", label_visibility="collapsed")

    img_to_upload = None
    if paste_res_q.image_data is not None:
        buf = io.BytesIO()
        paste_res_q.image_data.save(buf, format="PNG")
        buf.seek(0)
        img_to_upload = buf
    elif uploaded_img is not None:
        img_to_upload = uploaded_img

    if img_to_upload is not None:
        q.image_path = upload_image_to_drive(img_to_upload, f"{q.code}.png")

    st.divider()

    if q.format == QuestionType.TN:
        st.markdown("##### 📌 Tùy chọn đáp án Trắc nghiệm (TN):")
        if not q.options: q.options = {'A': '', 'B': '', 'C': '', 'D': ''}
        opt_col1, opt_col2 = st.columns(2)
        with opt_col1:
            st.markdown("**Phương án A:**")
            opt_a = interactive_math_editor(key=f"editor_single_opt_{q.code}_A", text=q.options.get('A', ''), height_mode="compact")
            if opt_a is not None: q.options['A'] = opt_a
            st.markdown("**Phương án B:**")
            opt_b = interactive_math_editor(key=f"editor_single_opt_{q.code}_B", text=q.options.get('B', ''), height_mode="compact")
            if opt_b is not None: q.options['B'] = opt_b

        with opt_col2:
            st.markdown("**Phương án C:**")
            opt_c = interactive_math_editor(key=f"editor_single_opt_{q.code}_C", text=q.options.get('C', ''), height_mode="compact")
            if opt_c is not None: q.options['C'] = opt_c
            st.markdown("**Phương án D:**")
            opt_d = interactive_math_editor(key=f"editor_single_opt_{q.code}_D", text=q.options.get('D', ''), height_mode="compact")
            if opt_d is not None: q.options['D'] = opt_d

        q.answer = st.radio("🔑 Chọn đáp án đúng:", ['A', 'B', 'C', 'D'], index=['A', 'B', 'C', 'D'].index(q.answer) if q.answer in ['A', 'B', 'C', 'D'] else 0, horizontal=True)

    elif q.format == QuestionType.DS:
        st.markdown("##### 📌 Tùy chọn đáp án Đúng / Sai (ĐS):")
        new_tf, labels = [], ['a', 'b', 'c', 'd']
        for i, label in enumerate(labels):
            raw_stmt_tuple = q.tf_statements[i] if i < len(q.tf_statements) else (f"{label}) Mệnh đề {label}", "Đúng")
            clean_stmt_text = re.sub(r'^[a-d][\.\)\:-]\s*', '', raw_stmt_tuple[0], flags=re.IGNORECASE).strip()
            c_stmt, c_val = st.columns([4, 1])
            with c_stmt:
                st.markdown(f"**Ý {label}):**")
                updated_stmt = interactive_math_editor(key=f"editor_single_ds_{q.code}_{label}", text=clean_stmt_text, height_mode="compact")
                stmt_text = updated_stmt if updated_stmt is not None else clean_stmt_text
            with c_val:
                val_choice = st.selectbox(f"Đ/S ({label})", ["Đúng", "Sai"], index=0 if raw_stmt_tuple[1] in ["Đúng", "D"] else 1, key=f"dialog_tf_val_{label}")
            new_tf.append((f"{label}) {stmt_text}", val_choice))
        q.tf_statements = new_tf
        q.answer = ", ".join([f"{l[0]}) {v}" for l, (_, v) in zip(labels, new_tf)])

    else:
        q.answer = st.text_input("🔑 Đáp án Trả lời ngắn (TLN):", value=q.answer)

    st.divider()

    st.markdown("##### 📝 Chỉnh sửa Lời giải chi tiết (MathLive):")
    updated_sol = interactive_math_editor(key=f"editor_single_sol_{q.code}", text=q.solution if q.solution else "", height_mode="compact")
    if updated_sol is not None: q.solution = updated_sol

    sol_img_path = getattr(q, 'solution_image_path', None)
    if sol_img_path:
        st.markdown("##### 🖼️ Ảnh lời giải hiện tại:")
        img_col1, img_col2 = st.columns([2, 1])
        with img_col1: st.image(sol_img_path, width=220)
        with img_col2:
            if st.button("🗑️ Xóa ảnh lời giải", key=f"del_sol_img_single_{q.code}"):
                q.solution_image_path = None
                save_questions_to_cloud([q])
                st.success("Đã xóa ảnh lời giải thành công!")
                time.sleep(0.6)
                st.rerun()

    st.markdown("##### 🖼️ Tải/Dán ảnh lời giải mới:")
    col_ps1, col_ps2 = st.columns([1, 1])
    with col_ps1:
        paste_res_sol = paste_image_button(
            label="📋 Dán từ Clipboard (1-Click)",
            background_color="#b8543f",
            text_color="#ffffff",
            hover_color="#a34834",
            key=f"paste_sol_img_single_{q.code}"
        )
    with col_ps2:
        uploaded_sol_img = st.file_uploader("Tải file ảnh lời giải từ máy", type=["png", "jpg", "jpeg"], key=f"upload_sol_img_single_{q.code}", label_visibility="collapsed")

    sol_img_to_upload = None
    if paste_res_sol.image_data is not None:
        buf = io.BytesIO()
        paste_res_sol.image_data.save(buf, format="PNG")
        buf.seek(0)
        sol_img_to_upload = buf
    elif uploaded_sol_img is not None:
        sol_img_to_upload = uploaded_sol_img

    if sol_img_to_upload is not None:
        q.solution_image_path = upload_image_to_drive(sol_img_to_upload, f"{q.code}_sol.png")

    st.divider()

    btn_col1, btn_col2 = st.columns([3, 1])
    if btn_col1.button("💾 LƯU THAY ĐỔI CÂU HỎI", type="primary", width="stretch"):
        save_questions_to_cloud([q])
        st.success("Đã cập nhật câu hỏi lên Google Sheet thành công!")
        time.sleep(0.8)
        st.rerun()

    if btn_col2.button("🗑️ Xóa câu hỏi này", width="stretch"):
        confirm_delete_dialog(q)

# POPUP NHẬP LIỆU NHANH TAB 3
@st.dialog("📥 Phân loại & Chỉnh sửa chi tiết từng câu", width="large")
def show_import_modal(raw_text: str):
    default_meta = {"grade": 12, "chapter": 1, "topic": "Dạng 1", "level": 2, "source": "Đề thi thử THPT 2026"}

    if "temp_questions" not in st.session_state or st.session_state.get("reset_temp"):
        st.session_state["temp_questions"] = parse_raw_text_to_questions(raw_text, default_meta)
        st.session_state["reset_temp"] = False

    if "custom_top_global" not in st.session_state: st.session_state["custom_top_global"] = False
    if "custom_src_global" not in st.session_state: st.session_state["custom_src_global"] = False

    st.markdown("### ⚡ 1. Thiết lập thông tin phân loại chung")
    col_a, col_b = st.columns(2)
    g_val = col_a.selectbox("Khối lớp (Chung)", [12, 11, 10], index=0)
    c_val = col_b.number_input("Chương (Chung)", 1, 20, 1)

    col_d, col_e = st.columns(2)

    global_chap_topics = get_chapter_topics(all_questions, g_val, c_val)
    if st.session_state["custom_top_global"]:
        c_inp, c_btn = col_d.columns([5, 1])
        t_val = c_inp.text_input(f"Nhập Dạng bài mới (Lớp {g_val} - CH{c_val}):", value="Dạng 1. Cực trị hàm số", key="global_top_inp")
        if c_btn.button("↩️", help="Quay lại chọn từ danh sách", key="btn_cancel_top_g"):
            st.session_state["custom_top_global"] = False
            st.rerun()
    else:
        top_global_options = global_chap_topics + ["➕ Nhập dạng bài mới..."]
        sel_global_top = col_d.selectbox(f"Chọn Dạng bài (Lớp {g_val} - CH{c_val}):", top_global_options, index=0, key="global_top_sel")
        if sel_global_top == "➕ Nhập dạng bài mới...":
            st.session_state["custom_top_global"] = True
            st.rerun()
        else:
            t_val = sel_global_top

    all_stored_srcs = get_all_stored_sources(all_questions)
    if st.session_state["custom_src_global"]:
        c_inp, c_btn = col_e.columns([5, 1])
        src_val = c_inp.text_input("Nhập Nguồn đề mới (Chung):", value="Đề thi thử THPT 2026", key="global_src_inp")
        if c_btn.button("↩️", help="Quay lại chọn từ danh sách", key="btn_cancel_src_g"):
            st.session_state["custom_src_global"] = False
            st.rerun()
    else:
        src_global_options = all_stored_srcs + ["➕ Nhập nguồn đề mới..."]
        sel_global_src = col_e.selectbox("Chọn Nguồn đề (Chung):", src_global_options, index=0, key="global_src_sel")
        if sel_global_src == "➕ Nhập nguồn đề mới...":
            st.session_state["custom_src_global"] = True
            st.rerun()
        else:
            src_val = sel_global_src

    lvl_val = st.selectbox("Mức độ (Chung)", [1, 2, 3], index=1)

    if st.button("🔄 Gán thông tin chung phía trên cho TẤT CẢ các câu", width="stretch"):
        for q in st.session_state["temp_questions"]:
            q.grade, q.chapter, q.topic, q.level, q.source = g_val, c_val, t_val, lvl_val, src_val
        st.success("Đã áp dụng thông tin chung cho toàn bộ danh sách!")
        st.rerun()

    st.divider()
    st.markdown(f"### ✏️ 2. Chỉnh sửa chi tiết & Sửa công thức TỪNG CÂU ({len(st.session_state['temp_questions'])} câu)")

    for idx, q in enumerate(st.session_state["temp_questions"]):
        with st.container():
            st.markdown(f"""<div class="edit-q-box"><b>Câu {idx + 1}</b> [{q.format.value}]</div>""", unsafe_allow_html=True)
            
            st.markdown("<b>Sửa nội dung đề bài (MathLive):</b>", unsafe_allow_html=True)
            updated_t3_content = interactive_math_editor(key=f"editor_t3_content_{idx}", text=q.content, height_mode="compact")
            if updated_t3_content is not None: q.content = updated_t3_content

            st.markdown(f"<b>🖼️ Tải/Dán ảnh đính kèm đề bài (Câu {idx+1}):</b>", unsafe_allow_html=True)
            col_tp1, col_tp2 = st.columns([1, 1])
            with col_tp1:
                paste_res_t3 = paste_image_button(
                    label="📋 Dán từ Clipboard (1-Click)",
                    background_color="#b8543f",
                    text_color="#ffffff",
                    hover_color="#a34834",
                    key=f"paste_t3_img_{idx}"
                )
            with col_tp2:
                uploaded_img = st.file_uploader(f"Tải file ảnh (Câu {idx+1})", type=["png", "jpg", "jpeg"], key=f"t3_img_{idx}", label_visibility="collapsed")

            t3_img_to_upload = None
            if paste_res_t3.image_data is not None:
                buf = io.BytesIO()
                paste_res_t3.image_data.save(buf, format="PNG")
                buf.seek(0)
                t3_img_to_upload = buf
            elif uploaded_img is not None:
                t3_img_to_upload = uploaded_img

            if t3_img_to_upload is not None:
                q.image_path = upload_image_to_drive(t3_img_to_upload, f"temp_{idx}.png")

            ct1, ct2, ct3 = st.columns([2, 1, 1])
            q_chap_topics = get_chapter_topics(all_questions, q.grade, q.chapter)
            
            key_custom_top_q = f"custom_top_q_{idx}"
            if key_custom_top_q not in st.session_state: st.session_state[key_custom_top_q] = False

            if st.session_state[key_custom_top_q]:
                c_i, c_b = ct1.columns([4, 1])
                q.topic = c_i.text_input(f"Nhập Dạng bài mới (Câu {idx+1}):", value=q.topic if q.topic not in q_chap_topics else "", key=f"t3_top_inp_{idx}")
                if c_b.button("↩️", key=f"btn_canc_top_{idx}"):
                    st.session_state[key_custom_top_q] = False
                    st.rerun()
            else:
                t3_top_options = q_chap_topics + ["➕ Nhập dạng bài mới..."]
                t3_top_default_idx = q_chap_topics.index(q.topic) if q.topic in q_chap_topics else 0
                sel_t3_top = ct1.selectbox(f"Dạng bài (Câu {idx+1}):", t3_top_options, index=t3_top_default_idx, key=f"t3_top_sel_{idx}")
                if sel_t3_top == "➕ Nhập dạng bài mới...":
                    st.session_state[key_custom_top_q] = True
                    st.rerun()
                else:
                    q.topic = sel_t3_top

            q.format = QuestionType(ct2.selectbox(f"Loại (Câu {idx+1})", ["TN", "DS", "TLN"], index=["TN", "DS", "TLN"].index(q.format.value), key=f"t3_fmt_{idx}"))
            q.level = ct3.selectbox(f"Mức độ (Câu {idx+1})", [1, 2, 3], index=q.level-1, key=f"t3_lvl_{idx}")

            if q.format == QuestionType.TN:
                st.markdown("<b>Phương án & Đáp án Trắc nghiệm:</b>", unsafe_allow_html=True)
                if not q.options: q.options = {'A': '', 'B': '', 'C': '', 'D': ''}
                t3_opt_col1, t3_opt_col2 = st.columns(2)
                with t3_opt_col1:
                    opt_a = interactive_math_editor(key=f"editor_t3_opt_{idx}_A", text=q.options.get('A', ''), height_mode="compact")
                    if opt_a is not None: q.options['A'] = opt_a
                    opt_b = interactive_math_editor(key=f"editor_t3_opt_{idx}_B", text=q.options.get('B', ''), height_mode="compact")
                    if opt_b is not None: q.options['B'] = opt_b
                with t3_opt_col2:
                    opt_c = interactive_math_editor(key=f"editor_t3_opt_{idx}_C", text=q.options.get('C', ''), height_mode="compact")
                    if opt_c is not None: q.options['C'] = opt_c
                    opt_d = interactive_math_editor(key=f"editor_t3_opt_{idx}_D", text=q.options.get('D', ''), height_mode="compact")
                    if opt_d is not None: q.options['D'] = opt_d
                
                ans_idx = ['A', 'B', 'C', 'D'].index(q.answer) if q.answer in ['A', 'B', 'C', 'D'] else 0
                q.answer = st.radio(f"🔑 Chọn đáp án đúng (Câu {idx+1}):", ['A', 'B', 'C', 'D'], index=ans_idx, key=f"t3_tn_{idx}", horizontal=True)

            elif q.format == QuestionType.DS:
                st.markdown("<b>Mệnh đề & Chọn Đúng/Sai từng ý:</b>", unsafe_allow_html=True)
                new_tf, labels = [], ['a', 'b', 'c', 'd']
                for stmt_idx, label in enumerate(labels):
                    raw_stmt_tuple = q.tf_statements[stmt_idx] if stmt_idx < len(q.tf_statements) else (f"{label}) Mệnh đề {label}", "Đúng")
                    clean_stmt_text = re.sub(r'^[a-d][\.\)\:-]\s*', '', raw_stmt_tuple[0], flags=re.IGNORECASE).strip()
                    c_txt, c_sel = st.columns([4, 1])
                    with c_txt:
                        updated_stmt = interactive_math_editor(key=f"editor_t3_ds_{idx}_{label}", text=clean_stmt_text, height_mode="compact")
                        stmt_input = updated_stmt if updated_stmt is not None else clean_stmt_text
                    with c_sel:
                        choice = st.selectbox(f"Đ/S ({label})", ["Đúng", "Sai"], index=0 if raw_stmt_tuple[1] in ["Đúng", "D"] else 1, key=f"t3_ds_val_{idx}_{label}")
                    new_tf.append((f"{label}) {stmt_input}", choice))
                q.tf_statements = new_tf
                q.answer = ", ".join([f"{l}) {v}" for l, (_, v) in zip(labels, new_tf)])

            else:
                q.answer = st.text_input(f"🔑 Nhập đáp án Trả lời ngắn (Câu {idx+1}):", value=q.answer, key=f"t3_tln_{idx}")

            st.markdown("<b>Sửa lời giải chi tiết (MathLive):</b>", unsafe_allow_html=True)
            updated_t3_sol = interactive_math_editor(key=f"editor_t3_sol_{idx}", text=q.solution if q.solution else "", height_mode="compact")
            if updated_t3_sol is not None: q.solution = updated_t3_sol

            st.markdown(f"<b>🖼️ Tải/Dán ảnh lời giải (Câu {idx+1}):</b>", unsafe_allow_html=True)
            col_tsp1, col_tsp2 = st.columns([1, 1])
            with col_tsp1:
                paste_res_t3_sol = paste_image_button(
                    label="📋 Dán từ Clipboard (1-Click)",
                    background_color="#b8543f",
                    text_color="#ffffff",
                    hover_color="#a34834",
                    key=f"paste_t3_sol_img_{idx}"
                )
            with col_tsp2:
                uploaded_sol_img = st.file_uploader(f"Tải file ảnh lời giải (Câu {idx+1})", type=["png", "jpg", "jpeg"], key=f"t3_sol_img_{idx}", label_visibility="collapsed")

            t3_sol_img_to_upload = None
            if paste_res_t3_sol.image_data is not None:
                buf = io.BytesIO()
                paste_res_t3_sol.image_data.save(buf, format="PNG")
                buf.seek(0)
                t3_sol_img_to_upload = buf
            elif uploaded_sol_img is not None:
                t3_sol_img_to_upload = uploaded_sol_img

            if t3_sol_img_to_upload is not None:
                q.solution_image_path = upload_image_to_drive(t3_sol_img_to_upload, f"temp_sol_{idx}.png")

            st.markdown("---")

    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("💾 LƯU TẤT CẢ VÀO GOOGLE SHEET", type="primary", width="stretch"):
        for q in st.session_state["temp_questions"]:
            std_code = generate_standard_code(all_questions, q.grade, q.chapter, q.topic)
            q.code = std_code
            all_questions.append(q)

        save_questions_to_cloud(st.session_state["temp_questions"])
        st.session_state["reset_temp"] = True
        st.session_state["show_import_modal"] = False
        st.success("🎉 Đã lưu thành công tất cả câu hỏi lên Google Sheet!")
        time.sleep(1)
        st.rerun()

    if col_btn2.button("❌ Hủy bỏ", width="stretch"):
        st.session_state["reset_temp"] = True
        st.session_state["show_import_modal"] = False
        st.rerun()

# 10. TẠO TABS CHỨC NĂNG CHÍNH
tab1, tab2, tab3 = st.tabs(["📋 Ngân hàng câu hỏi", "🎯 Barem Ma trận & Tạo đề", "📥 Hệ thống nhập liệu"])

# TAB 1
with tab1:
    st.sidebar.markdown("### 📚 Bộ lọc Ngân hàng")
    grade_options = ["Tất cả", 12, 11, 10]
    grade_selected = st.sidebar.selectbox("Khối lớp", grade_options, index=0)
    questions_filtered = all_questions if grade_selected == "Tất cả" else [q for q in all_questions if q.grade == grade_selected]

    chapters = sorted(list(set(q.chapter for q in questions_filtered)))
    selected_chapter = st.sidebar.selectbox("Chương", ["Tất cả"] + chapters, index=0)
    if selected_chapter != "Tất cả":
        questions_filtered = [q for q in questions_filtered if q.chapter == selected_chapter]

    stored_topics = get_all_stored_topics(questions_filtered)
    selected_topic = st.sidebar.selectbox("Dạng bài", ["Tất cả"] + stored_topics, index=0)
    if selected_topic != "Tất cả":
        questions_filtered = [q for q in questions_filtered if q.topic == selected_topic]

    stored_sources = get_all_stored_sources(questions_filtered)
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
    if st.sidebar.button("🔄 Chuẩn hóa & Đánh lại mã ID", width="stretch"):
        count_reindexed = reindex_all_database_ids()
        st.sidebar.success(f"🎉 Đã đánh lại mã ID liên tục cho {count_reindexed} câu hỏi!")
        time.sleep(1)
        st.rerun()

    st.markdown(f"""
    <div class="header-info-bar">
        <div>
            <span style="font-size:1.25rem; font-weight:800; color:#2c2825; letter-spacing: -0.02em;">NGÂN HÀNG CÂU HỎI </span>
            <span style="margin-left:12px; font-size:0.85rem; color:#78716c; background-color:#f0ebe1; padding:6px 14px; border-radius:999px; font-weight:600;">MÔN TOÁN GDPT 2018</span>
        </div>
        <div>
            <span style="background-color:#f7ece8; color:#a8412c; border:1px solid #e8c4b8; padding:8px 20px; border-radius:999px; font-weight:700; font-size:0.88rem; box-shadow:0 2px 8px rgba(184,84,63,0.08);">
                📌 Số câu hiện có: <b>{cnt_total}</b> câu [TN: {cnt_tn} | ĐS: {cnt_ds} | TLN: {cnt_tln}]
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c_search, c_act = st.columns([2, 1])
    with c_search: search_query = st.text_input("🔍 Tìm kiếm trong nội dung hoặc nguồn đề...", "", label_visibility="collapsed")

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

    if st.button("📄 XUẤT FILE WORD VÀ TÙY CHỈNH", type="primary", width="stretch"):
        if not selected_objs: st.error("Vui lòng tích chọn ít nhất 1 câu hỏi!")
        else: show_export_config_modal(selected_objs)

    st.markdown("<br>", unsafe_allow_html=True)

    grid_cols = st.columns(2)
    for idx, q in enumerate(display_questions):
        with grid_cols[idx % 2]:
            st.markdown(f"""
            <div class="question-card">
                <div style="margin-bottom:12px;">
                    <span class="badge-fmt">{q.format.value}</span>
                    <span class="card-badge">Câu {idx + 1} | {q.code}</span>
                </div>
            """, unsafe_allow_html=True)
            
            c_edit, c_del, c_chk = st.columns([1, 1, 3])
            if c_edit.button("✏️ Sửa", key=f"btn_edit_{q.code}"): show_single_question_edit_dialog(q)
            if c_del.button("🗑️ Xóa", key=f"btn_del_{q.code}"): confirm_delete_dialog(q)

            is_selected = q.code in st.session_state["selected_questions"]
            if c_chk.checkbox(f"Chọn câu {q.code}", value=is_selected, key=f"chk_{q.code}"):
                st.session_state["selected_questions"].add(q.code)
            else:
                st.session_state["selected_questions"].discard(q.code)

            st.write(q.content)
            if q.image_path: st.image(q.image_path, width="stretch")

            if q.format == QuestionType.TN and q.options:
                for k, v in q.options.items(): st.write(f"**{k}.** {v}")
            elif q.format == QuestionType.DS and q.tf_statements:
                for stmt, status in q.tf_statements: st.write(f"- {stmt} **[{status}]**")

            if q.answer: st.markdown(f'<div class="answer-box">Đáp án: {q.answer}</div>', unsafe_allow_html=True)

            if q.solution or getattr(q, 'solution_image_path', None):
                with st.expander("Lời giải chi tiết"):
                    if q.solution: st.write(q.solution)
                    sol_img = getattr(q, 'solution_image_path', None)
                    if sol_img: st.image(sol_img, width="stretch")

            st.markdown("</div>", unsafe_allow_html=True)

# TAB 2
with tab2:
    st.title("🎯 Barem Ma trận Đề thi GDPT 2018")
    st.caption("Cấu hình số lượng câu theo chủ đề và cấp độ tư duy.")

    stored_topics = get_all_stored_topics(all_questions)
    stored_chaps = sorted(list(set(q.chapter for q in all_questions))) if all_questions else [1]
    matrix_options = [f"Chương {c}" for c in stored_chaps] + stored_topics
    if not matrix_options: matrix_options = ["Chương 1", "Dạng 1. Khảo sát tính đơn điệu"]

    default_matrix_data = [{
        "Chủ đề / Nội dung": matrix_options[0],
        "TN - 1": 1, "TN - 2": 1, "TN - 3": 0, "DS - 1": 1, "DS - 2": 0, "DS - 3": 0, "TLN - 1": 0, "TLN - 2": 1, "TLN - 3": 0,
    }]

    if "matrix_df" not in st.session_state: st.session_state["matrix_df"] = pd.DataFrame(default_matrix_data)

    edited_df = st.data_editor(
        st.session_state["matrix_df"], num_rows="dynamic", width="stretch",
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

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Trắc nghiệm (TN)", f"{calc_df[['TN - 1', 'TN - 2', 'TN - 3']].sum().sum()} câu")
    m2.metric("Đúng / Sai (ĐS)", f"{calc_df[['DS - 1', 'DS - 2', 'DS - 3']].sum().sum()} câu")
    m3.metric("Trả lời ngắn (TLN)", f"{calc_df[['TLN - 1', 'TLN - 2', 'TLN - 3']].sum().sum()} câu")
    m4.metric("TỔNG CẢ ĐỀ", f"{calc_df[num_cols].sum().sum()} câu")

    st.divider()

    num_exams_to_create = st.number_input("Số lượng mã đề thi cần tạo:", min_value=1, max_value=20, value=2)
    custom_exam_codes = []
    cols_code = st.columns(min(int(num_exams_to_create), 4))
    for i in range(int(num_exams_to_create)):
        with cols_code[i % min(int(num_exams_to_create), 4)]:
            code_input = st.text_input(f"Mã đề {i+1}:", value=f"{101 + i}", key=f"t2_custom_code_{i}")
            custom_exam_codes.append(code_input.strip())

    if st.button("🎲 TỰ ĐỘNG TRỘN & TẠO CÁC MÃ ĐỀ THI", type="primary", width="stretch"):
        base_questions, errors = [], []
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
                if st.button(f"📄 Tùy chỉnh & Tải file Word Mã đề {e_code}", key=f"btn_exp_modal_{e_code}", width="stretch"):
                    show_export_config_modal(q_list, test_code=e_code)

# TAB 3
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
    
    # BỐ CỤC SONG SONG CÓ THẺ NÚT BO TRÒN SANG TRỌNG BÊN PHẢI
    col_editor, col_action = st.columns([5, 1.2])

    with col_editor:
        edited_live_text = interactive_math_editor(key="tab3_main_raw_editor", text=st.session_state["tab3_input_text"], height_mode="large")

    with col_action:
        st.write("")
        st.write("")
        btn_analyze = st.button("🔍 PHÂN TÍCH &\nMỞ POPUP", type="primary", use_container_width=True, key="btn_tab3_analyze")

    if edited_live_text is not None and edited_live_text != st.session_state["tab3_input_text"]:
        st.session_state["tab3_input_text"] = edited_live_text

    if btn_analyze:
        if not st.session_state["tab3_input_text"].strip():
            st.warning("Vui lòng dán văn bản câu hỏi trước khi nhấn phân tích!")
        else:
            st.session_state["reset_temp"] = True
            st.session_state["show_import_modal"] = True

    if st.session_state["show_import_modal"]:
        show_import_modal(st.session_state["tab3_input_text"])
