import io
import time
import streamlit as st
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

def upload_image_to_drive(uploaded_file, filename=None, folder_id=None):
    """
    Tải ảnh trực tiếp lên Google Drive từ bộ nhớ RAM (BytesIO) và trả về URL ảnh công khai.
    Không lưu bất kỳ file tạm nào vào ổ cứng cục bộ.
    """
    if uploaded_file is None:
        return ""

    try:
        # Lấy Google Drive service đã khởi tạo từ service_account
        drive_service = get_drive_service() # Đảm bảo gọi đúng hàm khởi tạo service của bạn

        # Tạo tên file duy nhất nếu chưa có
        if not filename:
            filename = f"img_{int(time.time())}.png"

        # 1. Chuyển đổi dữ liệu sang io.BytesIO
        if hasattr(uploaded_file, "getvalue"):  # Streamlit UploadedFile
            file_bytes = uploaded_file.getvalue()
        elif isinstance(uploaded_file, bytes):
            file_bytes = uploaded_file
        elif hasattr(uploaded_file, "read"):
            file_bytes = uploaded_file.read()
        else:
            st.error("Định dạng file không hợp lệ để tải lên Drive.")
            return ""

        stream = io.BytesIO(file_bytes)
        stream.seek(0)

        # 2. Thiết lập metadata
        file_metadata = {'name': filename}
        
        # Lấy Folder ID từ secrets nếu có
        target_folder = folder_id or st.secrets.get("DRIVE_FOLDER_ID", None)
        if target_folder:
            file_metadata['parents'] = [target_folder]

        # 3. Chuẩn bị upload
        media = MediaIoBaseUpload(
            stream, 
            mimetype='image/png', 
            resumable=True
        )

        # 4. Gọi API upload
        uploaded_drive_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, webContentLink'
        ).execute()

        file_id = uploaded_drive_file.get('id')

        # 5. Cấp quyền xem công khai (anyone: reader) để ảnh load được trên App/Sheet
        try:
            drive_service.permissions().create(
                fileId=file_id,
                body={'type': 'anyone', 'role': 'reader'},
                fields='id'
            ).execute()
        except Exception:
            pass  # Bỏ qua nếu folder cha đã có quyền kế thừa

        # Trả về link trực tiếp (direct embed link)
        return f"https://drive.google.com/thumbnail?id={file_id}&sz=w1000"

    except HttpError as err:
        st.error(f"Lỗi Google Drive API: {err}")
        return ""
    except Exception as e:
        st.error(f"Lỗi tải ảnh lên Drive: {e}")
        return ""
