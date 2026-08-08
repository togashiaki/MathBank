import json
import io
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from models import Question, QuestionType

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

@st.cache_resource
def get_google_services():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key("13Ck1FfpBolHEsWrRU2uQ6zoe9BIk1Wr0vWCta_PtUSs").sheet1
    drive_service = build('drive', 'v3', credentials=creds)
    return sheet, drive_service

sheet, drive_service = get_google_services()
DRIVE_FOLDER_ID = st.secrets["DRIVE_FOLDER_ID"]

def load_all_questions_from_cloud() -> list[Question]:
    """Đọc toàn bộ danh sách câu hỏi từ Google Sheet an toàn"""
    try:
        records = sheet.get_all_records()
    except Exception as e:
        st.error(f"Lỗi kết nối đọc Google Sheet: {e}")
        return []
        
    questions = []
    for idx, r in enumerate(records, start=2): # Hàng 2 là dòng dữ liệu đầu tiên
        try:
            # Ép kiểu an toàn cho grade, chapter, level
            grade_val = int(r.get('grade')) if str(r.get('grade', '')).strip().isdigit() else 12
            chap_val = int(r.get('chapter')) if str(r.get('chapter', '')).strip().isdigit() else 1
            lvl_val = int(r.get('level')) if str(r.get('level', '')).strip().isdigit() else 1

            # Chuẩn hóa format
            fmt_str = str(r.get('format', 'TN')).strip().upper()
            if fmt_str not in ['TN', 'DS', 'TLN']:
                fmt_str = 'TN'
            fmt_enum = QuestionType(fmt_str)

            # Parse options
            options = {}
            if r.get('options'):
                try:
                    raw_opt = str(r['options']).strip()
                    options = eval(raw_opt) if raw_opt.startswith('{') else {}
                except Exception:
                    options = {}

            # Parse tf_statements
            tf_statements = []
            if r.get('tf_statements'):
                try:
                    raw_tf = str(r['tf_statements']).strip()
                    tf_statements = eval(raw_tf) if raw_tf.startswith('[') else []
                except Exception:
                    tf_statements = []

            q = Question(
                code=str(r.get('code', f'Q_{idx}')),
                grade=grade_val,
                chapter=chap_val,
                lesson=1,
                topic=str(r.get('topic', '')),
                format=fmt_enum,
                level=lvl_val,
                source=str(r.get('source', '')),
                content=str(r.get('content', '')),
                options=options,
                tf_statements=tf_statements,
                answer=str(r.get('answer', '')),
                solution=str(r.get('solution', '')),
                image_path=str(r.get('image_path', '')).strip() or None
            )
            setattr(q, 'solution_image_path', str(r.get('solution_image_path', '')).strip() or None)
            
            # Chỉ lấy những câu có nội dung đề bài
            if q.content.strip():
                questions.append(q)

        except Exception as err:
            st.warning(f"⚠️ Không đọc được câu hỏi tại Dòng {idx} trên Google Sheet: {err}")
            continue
            
    return questions

def save_questions_to_cloud(questions: list[Question]):
    """Cập nhật hoặc thêm mới danh sách câu hỏi vào Google Sheet"""
    all_rows = sheet.get_all_records()
    existing_codes = {str(r['code']): idx + 2 for idx, r in enumerate(all_rows)} # Dòng 1 là tiêu đề
    
    for q in questions:
        row_data = [
            q.code,
            q.grade,
            q.chapter,
            q.topic,
            q.format.value,
            q.level,
            q.source or "",
            q.content,
            str(q.options) if q.options else "",
            str(q.tf_statements) if q.tf_statements else "",
            q.answer or "",
            q.solution or "",
            q.image_path or "",
            getattr(q, 'solution_image_path', '') or ""
        ]
        
        if q.code in existing_codes:
            row_idx = existing_codes[q.code]
            sheet.update(f"A{row_idx}:N{row_idx}", [row_data])
        else:
            sheet.append_row(row_data)

def delete_question_from_cloud(q_code: str):
    """Xóa 1 câu hỏi khỏi Google Sheet"""
    all_rows = sheet.get_all_records()
    for idx, r in enumerate(all_rows):
        if str(r.get('code')) == q_code:
            sheet.delete_rows(idx + 2)
            break

def upload_image_to_drive(uploaded_file, file_name: str) -> str:
    """Tải file ảnh lên Google Drive và trả về đường link trực tiếp"""
    file_metadata = {
        'name': file_name,
        'parents': [DRIVE_FOLDER_ID]
    }
    media = MediaIoBaseUpload(
        io.BytesIO(uploaded_file.getvalue()),
        mimetype=uploaded_file.type,
        resumable=True
    )
    file = drive_service.files().create(
        body=file_metadata, media_body=media, fields='id'
    ).execute()
    
    file_id = file.get('id')
    return f"https://lh3.googleusercontent.com/d/{file_id}"
