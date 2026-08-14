import os
import io
import time
import json
import gspread
import streamlit as st
from typing import List, Optional
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError
from models import Question, QuestionType

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# 1. KHỞI TẠO XÁC THỰC SERVICE ACCOUNT
def get_credentials():
    """Lấy credentials từ st.secrets hoặc file service_account.json."""
    if "gcp_service_account" in st.secrets:
        return Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
    elif "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
        return Credentials.from_service_account_info(dict(st.secrets["connections"]["gsheets"]), scopes=SCOPES)
    elif os.path.exists("service_account.json"):
        return Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
    else:
        st.error("⚠️ Chưa tìm thấy thông tin Service Account trong st.secrets!")
        return None

def get_drive_service():
    """Khởi tạo Google Drive API Service."""
    creds = get_credentials()
    if creds:
        return build("drive", "v3", credentials=creds)
    return None

def get_sheet():
    """Kết nối và mở Google Sheet lưu trữ dữ liệu."""
    creds = get_credentials()
    if not creds:
        return None
    gc = gspread.authorize(creds)
    
    sheet_name = st.secrets.get("GSHEET_NAME", "MathBank_DB")
    sheet_id = st.secrets.get("SPREADSHEET_ID", None)

    try:
        if sheet_id:
            sh = gc.open_by_key(sheet_id)
        else:
            sh = gc.open(sheet_name)
        return sh.sheet1
    except Exception:
        try:
            sh = gc.create(sheet_name)
            ws = sh.sheet1
            ws.append_row([
                "Code", "Grade", "Chapter", "Lesson", "Topic", "Format", 
                "Level", "Source", "Content", "Options", "TF_Statements", 
                "Answer", "Solution", "Image_Path", "Solution_Image_Path"
            ])
            return ws
        except Exception as e:
            st.error(f"Lỗi kết nối Google Sheets '{sheet_name}': {e}")
            return None


# 2. HÀM TẢI ẢNH LÊN GOOGLE DRIVE (TRỰC TIẾP TỪ RAM, KHÔNG LƯU CỤC BỘ)
def upload_image_to_drive(uploaded_file, filename: Optional[str] = None, folder_id: Optional[str] = None) -> Optional[str]:
    if uploaded_file is None:
        return None

    try:
        drive_service = get_drive_service()
        if not drive_service:
            return None

        if not filename:
            filename = f"img_{int(time.time())}.png"

        # Đọc dữ liệu ảnh thành byte stream
        if hasattr(uploaded_file, "getvalue"):
            file_bytes = uploaded_file.getvalue()
        elif isinstance(uploaded_file, bytes):
            file_bytes = uploaded_file
        elif hasattr(uploaded_file, "read"):
            file_bytes = uploaded_file.read()
        else:
            return None

        stream = io.BytesIO(file_bytes)
        stream.seek(0)

        file_metadata = {'name': filename}
        target_folder = folder_id or st.secrets.get("DRIVE_FOLDER_ID", None)
        if target_folder and target_folder.strip():
            file_metadata['parents'] = [target_folder.strip()]

        media = MediaIoBaseUpload(stream, mimetype='image/png', resumable=True)

        uploaded_drive_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webContentLink, webViewLink',
            supportsAllDrives=True
        ).execute()

        file_id = uploaded_drive_file.get('id')

        # Cấp quyền đọc công khai để hiển thị ảnh trên Web/Docx
        try:
            drive_service.permissions().create(
                fileId=file_id,
                body={'type': 'anyone', 'role': 'reader'},
                fields='id',
                supportsAllDrives=True
            ).execute()
        except Exception:
            pass

        return f"https://lh3.googleusercontent.com/d/{file_id}"

    except HttpError as err:
        st.error(f"Lỗi tải ảnh Google Drive (HttpError): {err}")
        return None
    except Exception as e:
        st.error(f"Lỗi khi upload ảnh lên Drive: {e}")
        return None


# 3. HÀM ĐỌC DỮ LIỆU TỪ GOOGLE SHEET
def load_all_questions_from_cloud() -> List[Question]:
    ws = get_sheet()
    if not ws:
        return []

    try:
        records = ws.get_all_records()
        questions = []
        for r in records:
            if not r.get("Code"):
                continue

            # Format
            fmt_str = str(r.get("Format", "TN")).strip().upper()
            try:
                q_fmt = QuestionType(fmt_str)
            except Exception:
                q_fmt = QuestionType.TN

            # Options
            opts = {}
            raw_opts = r.get("Options", "")
            if raw_opts:
                if isinstance(raw_opts, dict):
                    opts = raw_opts
                else:
                    try:
                        opts = json.loads(str(raw_opts))
                    except Exception:
                        opts = {}

            # TF_Statements
            tf_stmts = []
            raw_tf = r.get("TF_Statements", "")
            if raw_tf:
                if isinstance(raw_tf, list):
                    tf_stmts = [tuple(x) for x in raw_tf]
                else:
                    try:
                        parsed = json.loads(str(raw_tf))
                        tf_stmts = [tuple(x) for x in parsed]
                    except Exception:
                        tf_stmts = []

            # Level & Chapter & Grade
            try:
                lvl = int(r.get("Level", 2))
            except Exception:
                lvl = 2
            try:
                chap = int(r.get("Chapter", 1))
            except Exception:
                chap = 1
            try:
                lesson = int(r.get("Lesson", 1))
            except Exception:
                lesson = 1

            grade = r.get("Grade", 12)
            if str(grade).isdigit():
                grade = int(grade)

            q = Question(
                code=str(r.get("Code", "")).strip(),
                grade=grade,
                chapter=chap,
                lesson=lesson,
                topic=str(r.get("Topic", "")).strip(),
                format=q_fmt,
                level=lvl,
                source=str(r.get("Source", "")).strip(),
                content=str(r.get("Content", "")).strip(),
                options=opts,
                tf_statements=tf_stmts,
                answer=str(r.get("Answer", "")).strip(),
                solution=str(r.get("Solution", "")).strip(),
                image_path=str(r.get("Image_Path", "")).strip() or None,
                solution_image_path=str(r.get("Solution_Image_Path", "")).strip() or None
            )
            questions.append(q)
        return questions
    except Exception as e:
        st.error(f"Lỗi khi đọc câu hỏi từ Google Sheet: {e}")
        return []


# 4. HÀM LƯU / CẬP NHẬT CÂU HỎI LÊN GOOGLE SHEET
def save_questions_to_cloud(questions: List[Question]):
    ws = get_sheet()
    if not ws or not questions:
        return

    try:
        all_values = ws.get_all_values()
        headers = [
            "Code", "Grade", "Chapter", "Lesson", "Topic", "Format", 
            "Level", "Source", "Content", "Options", "TF_Statements", 
            "Answer", "Solution", "Image_Path", "Solution_Image_Path"
        ]

        if not all_values:
            ws.append_row(headers)
            all_values = [headers]

        code_to_row = {}
        for row_idx, row in enumerate(all_values[1:], start=2):
            if row:
                code_to_row[row[0].strip()] = row_idx

        rows_to_append = []
        for q in questions:
            row_data = [
                q.code,
                str(q.grade),
                int(q.chapter),
                int(getattr(q, 'lesson', 1)),
                q.topic or "",
                q.format.value if hasattr(q.format, 'value') else str(q.format),
                int(q.level),
                q.source or "",
                q.content or "",
                json.dumps(q.options, ensure_ascii=False) if q.options else "",
                json.dumps(q.tf_statements, ensure_ascii=False) if q.tf_statements else "",
                q.answer or "",
                q.solution or "",
                q.image_path or "",
                getattr(q, 'solution_image_path', "") or ""
            ]

            if q.code in code_to_row:
                row_num = code_to_row[q.code]
                ws.update(f"A{row_num}:O{row_num}", [row_data])
            else:
                rows_to_append.append(row_data)

        if rows_to_append:
            ws.append_rows(rows_to_append)

    except Exception as e:
        st.error(f"Lỗi khi lưu câu hỏi vào Google Sheet: {e}")


# 5. HÀM XÓA CÂU HỎI TRÊN GOOGLE SHEET
def delete_question_from_cloud(question_code: str):
    ws = get_sheet()
    if not ws or not question_code:
        return
    try:
        all_values = ws.get_all_values()
        for row_idx, row in enumerate(all_values[1:], start=2):
            if row and row[0].strip() == question_code.strip():
                ws.delete_rows(row_idx)
                break
    except Exception as e:
        st.error(f"Lỗi khi xóa câu hỏi {question_code} trên Google Sheet: {e}")
