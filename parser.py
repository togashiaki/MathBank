import re
import json
import sqlite3
from typing import List, Optional
from models import Question, QuestionType

def parse_markdown_to_questions(raw_text: str) -> List[Question]:
    """Phân tích chuỗi text chứa nhiều câu hỏi cách nhau bởi tag [END_CAU]."""
    blocks = raw_text.split("[END_CAU]")
    questions = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Trích xuất metadata từ thẻ tag
        ma_cau = re.search(r'\[MA_CAU:\s*(.*?)\]', block)
        lop = re.search(r'\[LOP:\s*(\d+)\]', block)
        chuong = re.search(r'\[CHUONG:\s*(\d+)\]', block)
        bai = re.search(r'\[BAI:\s*(\d+)\]', block)
        dang = re.search(r'\[DANG:\s*(.*?)\]', block)
        fmt = re.search(r'\[FORMAT:\s*(.*?)\]', block)
        lvl = re.search(r'\[LEVEL:\s*(\d+)\]', block)
        nguon = re.search(r'\[NGUON:\s*(.*?)\]', block)
        anh = re.search(r'\[ANH:\s*(.*?)\]', block)

        if not ma_cau:
            continue

        code_str = ma_cau.group(1).strip()
        grade_val = int(lop.group(1)) if lop else 12
        chapter_val = int(chuong.group(1)) if chuong else 1
        lesson_val = int(bai.group(1)) if bai else 1
        topic_str = dang.group(1).strip() if dang else "Tổng hợp"
        fmt_str = fmt.group(1).strip() if fmt else "TN"
        level_val = int(lvl.group(1)) if lvl else 1
        source_str = nguon.group(1).strip() if nguon else ""
        img_str = anh.group(1).strip() if anh else None

        q_format = QuestionType(fmt_str) if fmt_str in QuestionType.__members__ else QuestionType.TN

        # Hàm tách khối nội dung theo thẻ
        def get_section(start_tag: str, all_tags: list) -> str:
            pattern = f"{re.escape(start_tag)}(.*?)(?=" + "|".join([re.escape(t) for t in all_tags if t != start_tag]) + "|$)"
            match = re.search(pattern, block, re.DOTALL)
            return match.group(1).strip() if match else ""

        tags_list = ["[NOI_DUNG]", "[LUA_CHON]", "[Y_DUNG_SAI]", "[DAP_AN]", "[LOI_GIAI]"]

        content = get_section("[NOI_DUNG]", tags_list)
        options_raw = get_section("[LUA_CHON]", tags_list)
        ds_raw = get_section("[Y_DUNG_SAI]", tags_list)
        answer = get_section("[DAP_AN]", tags_list)
        solution = get_section("[LOI_GIAI]", tags_list)

        # Xử lý các lựa chọn A, B, C, D
        options = {}
        if options_raw:
            for line in options_raw.split('\n'):
                line = line.strip()
                if line and line[0] in ['A', 'B', 'C', 'D'] and (len(line) > 1 and line[1] in ['.', ':']):
                    options[line[0]] = line[2:].strip()

        # Xử lý mệnh đề Đúng / Sai
        tf_statements = []
        if ds_raw:
            for line in ds_raw.split('\n'):
                line = line.strip()
                if '|' in line:
                    stmt, status = line.rsplit('|', 1)
                    tf_statements.append((stmt.strip(), status.strip().upper()))

        questions.append(Question(
            code=code_str,
            grade=grade_val,
            chapter=chapter_val,
            lesson=lesson_val,
            topic=topic_str,
            format=q_format,
            level=level_val,
            source=source_str,
            image_path=img_str,
            content=content,
            options=options,
            tf_statements=tf_statements,
            answer=answer,
            solution=solution
        ))

    return questions


class QuestionDatabase:
    def __init__(self, db_path: str = "math_bank.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS questions (
                    code TEXT PRIMARY KEY,
                    grade INTEGER,
                    chapter INTEGER,
                    lesson INTEGER,
                    topic TEXT,
                    format TEXT,
                    level INTEGER,
                    source TEXT,
                    image_path TEXT,
                    content TEXT,
                    options TEXT,
                    tf_statements TEXT,
                    answer TEXT,
                    solution TEXT
                )
            """)
            conn.commit()

    def save_questions(self, questions: List[Question]):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for q in questions:
                cursor.execute("""
                    INSERT OR REPLACE INTO questions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    q.code, q.grade, q.chapter, q.lesson, q.topic,
                    q.format.value, q.level, q.source, q.image_path,
                    q.content, json.dumps(q.options, ensure_ascii=False),
                    json.dumps(q.tf_statements, ensure_ascii=False),
                    q.answer, q.solution
                ))
            conn.commit()

    def get_all_questions(self) -> List[Question]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM questions")
            rows = cursor.fetchall()
            
        questions = []
        for r in rows:
            questions.append(Question(
                code=r[0], grade=r[1], chapter=r[2], lesson=r[3], topic=r[4],
                format=QuestionType(r[5]), level=r[6], source=r[7], image_path=r[8],
                content=r[9],
                options=json.loads(r[10]),
                tf_statements=json.loads(r[11]),
                answer=r[12], solution=r[13]
            ))
        return questions