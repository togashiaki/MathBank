from enum import Enum
from typing import List, Dict, Optional, Tuple
from pydantic import BaseModel, Field

class QuestionType(str, Enum):
    TN = "TN"   # Trắc nghiệm 4 lựa chọn
    DS = "DS"   # Đúng / Sai (4 ý)
    TLN = "TLN" # Trả lời ngắn

class DifficultyLevel(int, Enum):
    NHAN_BIET = 1
    THONG_HIEU = 2
    VAN_DUNG = 3

class Question(BaseModel):
    code: str                           # Mã câu hỏi (ví dụ: TOAN12_CH1_B1_D01_001)
    grade: int = 12                     # Khối lớp (10, 11, 12)
    chapter: int = 1                    # Chương
    lesson: int = 1                     # Bài
    topic: str = ""                     # Dạng bài
    format: QuestionType = QuestionType.TN
    level: int = 1                      # 1: Nhận biết, 2: Thông hiểu, 3: Vận dụng
    source: Optional[str] = ""          # Nguồn đề thi
    image_path: Optional[str] = None    # Đường dẫn ảnh đính kèm
    content: str                        # Nội dung đề bài (chứa LaTeX)
    options: Dict[str, str] = Field(default_factory=dict)         # Các lựa chọn A, B, C, D (cho dạng TN)
    tf_statements: List[Tuple[str, str]] = Field(default_factory=list) # Danh sách [(ý a, "D/S"), ...]
    answer: Optional[str] = ""          # Đáp án (cho dạng TLN hoặc chữ cái A/B/C/D)
    solution: Optional[str] = ""        # Lời giải chi tiết

class MatrixConfig(BaseModel):
    # Cấu hình số lượng câu cho Barem tạo đề
    tn_l1: int = 0
    tn_l2: int = 0
    tn_l3: int = 0
    ds_l1: int = 0
    ds_l2: int = 0
    ds_l3: int = 0
    tln_l1: int = 0
    tln_l2: int = 0
    tln_l3: int = 0