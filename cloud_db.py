import io
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Kết nối lấy thông tin từ Secrets
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=SCOPES
)

gc = gspread.authorize(creds)
sheet = gc.open("MathBank_Database").sheet1
drive_service = build('drive', 'v3', credentials=creds)
DRIVE_FOLDER_ID = st.secrets["DRIVE_FOLDER_ID"]

def load_all_questions_from_sheet():
    return sheet.get_all_records()

def append_question_to_sheet(row_data: list):
    sheet.append_row(row_data)

def upload_image_to_drive(uploaded_file, file_name: str) -> str:
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