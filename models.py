from typing import Optional, Dict, List, Tuple
from enum import Enum
from pydantic import BaseModel, Field

class QuestionType(str, Enum):
    TN = "TN"
    DS = "DS"
    TLN = "TLN"

class Question(BaseModel):
    code: str
    grade: int
    chapter: int
    lesson: int = 1
    topic: str
    format: QuestionType
    level: int
    source: Optional[str] = ""
    content: str
    options: Optional[Dict[str, str]] = Field(default_factory=dict)
    tf_statements: Optional[List[Tuple[str, str]]] = Field(default_factory=list)
    answer: Optional[str] = ""
    solution: Optional[str] = ""
    image_path: Optional[str] = None
    solution_image_path: Optional[str] = None  # Đã khai báo bổ sung trường này
