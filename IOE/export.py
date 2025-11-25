import sqlite3
import pandas as pd

# Đường dẫn file .db
db_path = "ioe_questions.db"

# Kết nối database
conn = sqlite3.connect(db_path)

# Đọc toàn bộ bảng
df = pd.read_sql_query("SELECT * FROM questions;", conn)

# Xuất sang Excel
df.to_excel("questions_export.xlsx", index=False)

conn.close()
