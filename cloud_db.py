import os
import io
import time
import json
import ast
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

# ID GOOGLE SHEET VÀ GOOGLE DRIVE FOLDER CỦA BẠN
DEFAULT_SPREADSHEET_ID = "13Ck1FfpBolHEsWrRU2uQ6zoe9BIk1Wr0vWCta_PtUSs"
DEFAULT_DRIVE_FOLDER_ID = "1z9L_y8ohfr6TmfQXLSoAxiBMcrLtIepQ"


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
    """Mở trực tiếp Google Sheet bằng ID đã được cấp quyền."""
    creds = get_credentials()
    if not creds:
        return None
    gc = gspread.authorize(creds)
    
    sheet_id = st.secrets.get("SPREADSHEET_ID", DEFAULT_SPREADSHEET_ID)

    try:
        sh = gc.open_by_key(sheet_id)
        ws = sh.sheet1
        
        # Tự động tạo header nếu trang tính còn hoàn toàn trống
        existing_values = ws.get_all_values()
        if not existing_values:
            ws.append_row([
                "code", "grade", "chapter", "lesson", "topic", "format", 
                "level", "source", "content", "options", "tf_statements", 
                "answer", "solution", "image_path", "solution_image_path"
            ])
        return ws
    except Exception as e:
        st.error(f"Lỗi mở Google Sheet (ID: {sheet_id}): {e}")
        return None


# 2. HÀM TẢI ẢNH LÊN GOOGLE DRIVE
def upload_image_to_drive(uploaded_file, filename: Optional[str] = None, folder_id: Optional[str] = None) -> Optional[str]:
    if uploaded_file is None:
        return None

    try:
        drive_service = get_drive_service()
        if not drive_service:
            return None

        if not filename:
            filename = f"img_{int(time.time())}.png"

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

        target_folder = folder_id or st.secrets.get("DRIVE_FOLDER_ID", DEFAULT_DRIVE_FOLDER_ID)
        file_metadata = {'name': filename}
        if target_folder:
            file_metadata['parents'] = [target_folder.strip()]

        media = MediaIoBaseUpload(stream, mimetype='image/png', resumable=True)

        uploaded_drive_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webContentLink, webViewLink',
            supportsAllDrives=True
        ).execute()

        file_id = uploaded_drive_file.get('id')

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
        st.error(f"Lỗi tải ảnh Google Drive: {err}")
        return None
    except Exception as e:
        st.error(f"Lỗi upload ảnh: {e}")
        return None


# 3. HÀM ĐỌC DỮ LIỆU TỪ GOOGLE SHEET (KHÔNG PHÂN BIỆT HOA/THƯỜNG)
def load_all_questions_from_cloud() -> List[Question]:
    ws = get_sheet()
    if not ws:
        return []

    try:
        records = ws.get_all_records()
        questions = []
        for r in records:
            # Chuẩn hóa toàn bộ key cột về chữ thường và bỏ khoảng trắng thừa
            r_clean = {str(k).strip().lower(): v for k, v in r.items()}

            code_val = str(r_clean.get("code", "")).strip()
            if not code_val:
                continue

            # Format
            fmt_str = str(r_clean.get("format", "TN")).strip().upper()
            try:
                q_fmt = QuestionType(fmt_str)
            except Exception:
                q_fmt = QuestionType.TN

            # Options
            opts = {}
            raw_opts = r_clean.get("options", "")
            if raw_opts:
                if isinstance(raw_opts, dict):
                    opts = raw_opts
                else:
                    try:
                        opts = ast.literal_eval(str(raw_opts))
                    except Exception:
                        try:
                            opts = json.loads(str(raw_opts))
                        except Exception:
                            opts = {}

            # TF_Statements
            tf_stmts = []
            raw_tf = r_clean.get("tf_statements", "")
            if raw_tf:
                if isinstance(raw_tf, list):
                    tf_stmts = [tuple(x) for x in raw_tf]
                else:
                    try:
                        parsed = ast.literal_eval(str(raw_tf))
                        tf_stmts = [tuple(x) for x in parsed]
                    except Exception:
                        try:
                            parsed = json.loads(str(raw_tf))
                            tf_stmts = [tuple(x) for x in parsed]
                        except Exception:
                            tf_stmts = []

            # Level & Chapter & Grade
            try:
                lvl = int(r_clean.get("level", 2))
            except Exception:
                lvl = 2
            try:
                chap = int(r_clean.get("chapter", 1))
            except Exception:
                chap = 1
            try:
                lesson = int(r_clean.get("lesson", 1))
            except Exception:
                lesson = 1

            grade = r_clean.get("grade", 12)
            if str(grade).isdigit():
                grade = int(grade)

            q = Question(
                code=code_val,
                grade=grade,
                chapter=chap,
                lesson=lesson,
                topic=str(r_clean.get("topic", "")).strip(),
                format=q_fmt,
                level=lvl,
                source=str(r_clean.get("source", "")).strip(),
                content=str(r_clean.get("content", "")).strip(),
                options=opts,
                tf_statements=tf_stmts,
                answer=str(r_clean.get("answer", "")).strip(),
                solution=str(r_clean.get("solution", "")).strip(),
                image_path=str(r_clean.get("image_path", "")).strip() or None,
                solution_image_path=str(r_clean.get("solution_image_path", "")).strip() or None
            )
            questions.append(q)
        return questions
    except Exception as e:
        st.error(f"Lỗi khi đọc câu hỏi từ Google Sheet: {e}")
        return []


# 4. HÀM LƯU DỮ LIỆU TỰ ĐỘNG KHỚP THEO TIÊU ĐỀ CỘT TRÊN SHEET
def save_questions_to_cloud(questions: List[Question]):
    ws = get_sheet()
    if not ws or not questions:
        return

    try:
        all_values = ws.get_all_values()
        if not all_values:
            standard_headers = [
                "code", "grade", "chapter", "lesson", "topic", "format", 
                "level", "source", "content", "options", "tf_statements", 
                "answer", "solution", "image_path", "solution_image_path"
            ]
            ws.append_row(standard_headers)
            all_values = [standard_headers]

        header_row = [str(h).strip().lower() for h in all_values[0]]
        
        # Tự động gán đúng dữ liệu vào vị trí cột tương ứng trên Sheet
        def build_row_data(q: Question, headers: list) -> list:
            q_dict = {
                "code": q.code,
                "grade": str(q.grade),
                "chapter": int(q.chapter),
                "lesson": int(getattr(q, 'lesson', 1)),
                "topic": q.topic or "",
                "format": q.format.value if hasattr(q.format, 'value') else str(q.format),
                "level": int(q.level),
                "source": q.source or "",
                "content": q.content or "",
                "options": json.dumps(q.options, ensure_ascii=False) if q.options else "",
                "tf_statements": json.dumps(q.tf_statements, ensure_ascii=False) if q.tf_statements else "",
                "answer": q.answer or "",
                "solution": q.solution or "",
                "image_path": q.image_path or "",
                "solution_image_path": getattr(q, 'solution_image_path', "") or ""
            }
            return [q_dict.get(h, "") for h in headers]

        code_to_row = {}
        for row_idx, row in enumerate(all_values[1:], start=2):
            if row and row[0].strip():
                code_to_row[row[0].strip()] = row_idx

        rows_to_append = []
        for q in questions:
            row_data = build_row_data(q, header_row)
            if q.code in code_to_row:
                row_num = code_to_row[q.code]
                col_end_letter = gspread.utils.rowcol_to_a1(row_num, len(header_row))
                ws.update(f"A{row_num}:{col_end_letter}", [row_data])
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
