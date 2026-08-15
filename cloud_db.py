import os
import io
import time
import json
import base64
import ast
import requests
import gspread
import streamlit as st
import cloudinary
import cloudinary.uploader
from typing import List, Optional
from google.oauth2.service_account import Credentials
from models import Question, QuestionType

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets"
]

DEFAULT_SPREADSHEET_ID = "13Ck1FfpBolHEsWrRU2uQ6zoe9BIk1Wr0vWCta_PtUSs"

STANDARD_HEADERS = [
    "code", "grade", "chapter", "lesson", "topic", "format", 
    "level", "source", "content", "options", "tf_statements", 
    "answer", "solution", "image_path", "solution_image_path"
]

# 1. KHỞI TẠO XÁC THỰC GOOGLE SHEET
def get_credentials():
    if "gcp_service_account" in st.secrets:
        return Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
    elif "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
        return Credentials.from_service_account_info(dict(st.secrets["connections"]["gsheets"]), scopes=SCOPES)
    elif os.path.exists("service_account.json"):
        return Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
    else:
        st.error("⚠️ Chưa tìm thấy thông tin Service Account trong st.secrets!")
        return None

def get_sheet():
    creds = get_credentials()
    if not creds:
        return None
    try:
        gc = gspread.authorize(creds)
        sheet_id = st.secrets.get("SPREADSHEET_ID", DEFAULT_SPREADSHEET_ID)
        sh = gc.open_by_key(sheet_id)
        ws = sh.sheet1
        existing_values = ws.get_all_values()
        if not existing_values:
            ws.append_row(STANDARD_HEADERS)
        return ws
    except Exception as e:
        st.error(f"Lỗi mở Google Sheet: {e}")
        return None


# 2. HÀM TẢI ẢNH LÊN CLOUDINARY
def upload_image_to_drive(uploaded_file, filename: Optional[str] = None, folder_id: Optional[str] = None) -> Optional[str]:
    """
    Tải ảnh trực tiếp lên Cloudinary CDN vĩnh viễn, không lo bị chặn tải.
    """
    if uploaded_file is None:
        return None

    try:
        cloud_name = st.secrets.get("CLOUDINARY_CLOUD_NAME", "")
        api_key = st.secrets.get("CLOUDINARY_API_KEY", "")
        api_secret = st.secrets.get("CLOUDINARY_API_SECRET", "")

        if hasattr(uploaded_file, "getvalue"):
            file_bytes = uploaded_file.getvalue()
        elif isinstance(uploaded_file, bytes):
            file_bytes = uploaded_file
        elif hasattr(uploaded_file, "read"):
            file_bytes = uploaded_file.read()
        else:
            return None

        # Nếu đã cấu hình Cloudinary
        if cloud_name and api_key and api_secret:
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret,
                secure=True
            )

            # Đặt public_id nếu có filename (bỏ phần mở rộng)
            public_id = os.path.splitext(filename)[0] if filename else None

            upload_result = cloudinary.uploader.upload(
                file_bytes,
                folder="mathbank_images",
                public_id=public_id,
                overwrite=True,
                resource_type="image"
            )
            # Trả về link trực tiếp bảo mật HTTPS
            return upload_result.get("secure_url") or upload_result.get("url")

        # Dự phòng: Nếu có key ImgBB cũ
        imgbb_key = st.secrets.get("IMGBB_API_KEY", "")
        if imgbb_key:
            url = "https://api.imgbb.com/1/upload"
            payload = {
                "key": imgbb_key,
                "image": base64.b64encode(file_bytes).decode("utf-8")
            }
            if filename:
                payload["name"] = filename
            response = requests.post(url, data=payload, timeout=30)
            res_json = response.json()
            if response.status_code == 200 and res_json.get("success"):
                return res_json["data"]["url"]

        # Dự phòng cuối: Base64
        base64_str = base64.b64encode(file_bytes).decode("utf-8")
        return f"data:image/png;base64,{base64_str}"

    except Exception as e:
        st.error(f"Lỗi khi upload ảnh lên Cloud: {e}")
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
            r_clean = {str(k).strip().lower(): v for k, v in r.items()}
            code_val = str(r_clean.get("code", "")).strip()
            if not code_val:
                continue

            fmt_str = str(r_clean.get("format", "TN")).strip().upper()
            try:
                q_fmt = QuestionType(fmt_str)
            except Exception:
                q_fmt = QuestionType.TN

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


def _build_row_data(q: Question, headers: list) -> list:
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


# 4. HÀM LƯU / CẬP NHẬT CÂU HỎI LÊN GOOGLE SHEET
def save_questions_to_cloud(questions: List[Question]):
    ws = get_sheet()
    if not ws or not questions:
        return

    try:
        all_values = ws.get_all_values()
        if not all_values:
            ws.append_row(STANDARD_HEADERS)
            all_values = [STANDARD_HEADERS]

        header_row = [str(h).strip().lower() for h in all_values[0]]
        
        code_to_row = {}
        for row_idx, row in enumerate(all_values[1:], start=2):
            if row and len(row) > 0 and str(row[0]).strip():
                code_to_row[str(row[0]).strip()] = row_idx

        rows_to_append = []
        for q in questions:
            row_data = _build_row_data(q, header_row)
            if q.code in code_to_row:
                row_num = code_to_row[q.code]
                col_end_letter = gspread.utils.rowcol_to_a1(row_num, len(header_row))
                ws.update(values=[row_data], range_name=f"A{row_num}:{col_end_letter}")
            else:
                rows_to_append.append(row_data)

        if rows_to_append:
            ws.append_rows(rows_to_append)

    except Exception as e:
        st.error(f"Lỗi khi lưu câu hỏi vào Google Sheet: {e}")


# 5. HÀM GHI ĐÈ TOÀN BỘ SHEET
def overwrite_all_questions_in_cloud(questions: List[Question]):
    ws = get_sheet()
    if not ws:
        return
    try:
        rows_data = [STANDARD_HEADERS]
        for q in questions:
            rows_data.append(_build_row_data(q, STANDARD_HEADERS))
        
        ws.clear()
        ws.update(values=rows_data, range_name="A1")
    except Exception as e:
        st.error(f"Lỗi khi ghi đè Google Sheet: {e}")


# 6. HÀM XÓA CÂU HỎI TRÊN GOOGLE SHEET
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
        st.error(f"Lỗi khi xóa câu hỏi {question_code}: {e}")

