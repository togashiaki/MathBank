import time
import requests
import cloudinary
import cloudinary.uploader
from cloud_db import load_all_questions_from_cloud, overwrite_all_questions_in_cloud

# 1. Cấu hình thông tin Cloudinary của bạn (Hoặc tự đọc từ st.secrets nếu chạy Streamlit)
CLOUDINARY_CLOUD_NAME = "điền_cloud_name_của_bạn"
CLOUDINARY_API_KEY = "điền_api_key_của_bạn"
CLOUDINARY_API_SECRET = "điền_api_secret_của_bạn"

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://imgbb.com/"
}


def transfer_url_to_cloudinary(old_url: str, public_id: str) -> str:
    """Tải ảnh từ ImgBB/Web về và đẩy thẳng lên Cloudinary."""
    if not old_url or not isinstance(old_url, str):
        return old_url
    
    old_url = old_url.strip()
    # Nếu ảnh đã nằm trên Cloudinary rồi thì bỏ qua
    if "cloudinary.com" in old_url or old_url.lower() in ["none", "null", ""]:
        return old_url

    try:
        print(f"  -> Đang chuyển đổi: {old_url}")
        # Tải dữ liệu ảnh từ link cũ
        res = requests.get(old_url, headers=headers, timeout=25)
        if res.status_code == 200 and len(res.content) > 100:
            upload_res = cloudinary.uploader.upload(
                res.content,
                folder="mathbank_images",
                public_id=public_id,
                overwrite=True,
                resource_type="image"
            )
            new_url = upload_res.get("secure_url") or upload_res.get("url")
            print(f"     ✅ Thành công -> Link mới: {new_url}")
            time.sleep(0.1) # Nghỉ nhẹ để tránh quá tải
            return new_url
        else:
            print(f"     ❌ Không tải được ảnh từ link cũ (Mã lỗi HTTP: {res.status_code})")
    except Exception as e:
        print(f"     ❌ Lỗi khi upload sang Cloudinary: {e}")

    return old_url


def run_migration():
    print("🚀 Bắt đầu đọc dữ liệu từ Google Sheet...")
    questions = load_all_questions_from_cloud()
    if not questions:
        print("❌ Không tìm thấy câu hỏi nào trên Sheet!")
        return

    print(f"📋 Tìm thấy {len(questions)} câu hỏi. Đang quét các ảnh cần chuyển đổi...")
    updated_count = 0

    for idx, q in enumerate(questions, start=1):
        modified = False
        
        # 1. Quét ảnh đề bài
        if q.image_path and "cloudinary.com" not in q.image_path:
            print(f"\n[Câu {idx} - Mã: {q.code}] Đang chuyển ảnh đề bài...")
            new_q_img = transfer_url_to_cloudinary(q.image_path, f"{q.code}_main")
            if new_q_img != q.image_path:
                q.image_path = new_q_img
                modified = True

        # 2. Quét ảnh lời giải
        sol_img = getattr(q, 'solution_image_path', None)
        if sol_img and "cloudinary.com" not in sol_img:
            print(f"\n[Câu {idx} - Mã: {q.code}] Đang chuyển ảnh lời giải...")
            new_sol_img = transfer_url_to_cloudinary(sol_img, f"{q.code}_sol")
            if new_sol_img != sol_img:
                q.solution_image_path = new_sol_img
                modified = True

        if modified:
            updated_count += 1

    if updated_count > 0:
        print(f"\n💾 Đang ghi đè {len(questions)} câu hỏi với link Cloudinary mới vào Google Sheet...")
        overwrite_all_questions_in_cloud(questions)
        print(f"🎉 Hoàn tất! Đã cập nhật thành công {updated_count} câu hỏi có ảnh sang Cloudinary.")
    else:
        print("\n✨ Tất cả ảnh đã ở Cloudinary hoặc không có ảnh nào cần chuyển đổi!")


if __name__ == "__main__":
    run_migration()
