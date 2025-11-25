import sys
import requests
import time
import re
import logging
import os
import platform
import zipfile, io, requests, shutil
import subprocess
import sqlite3
import pandas as pd
from urllib.parse import urlparse, parse_qs
from random import randint
from pathlib import Path
import assemblyai as aai
from google import genai
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# PyQt6 imports
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QTextEdit, QSpinBox, QProgressBar, QGroupBox,
                             QMessageBox, QFileDialog, QFrame, QTableWidget,
                             QTableWidgetItem, QHeaderView, QTabWidget,
                             QDialog, QDialogButtonBox, QCheckBox)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QIcon, QFont, QPalette, QColor, QTextCursor
from PyQt6.QtWidgets import QInputDialog
from PyQt6.QtCore import QEventLoop

# ================== LOGGING CONFIG ==================
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
logging.getLogger("assemblyai").setLevel(logging.ERROR)
logging.getLogger("google.genai").setLevel(logging.ERROR)

# ================== CONST ==================
BASE = "https://api-edu.go.vn/ioe-service/v2/game"
aai.settings.api_key = "30bfe710518645c0b879e97910e7b00e"
GEMINI_API_KEY = "AIzaSyCFyjQLP3_52QMWo3FyIyzmG8k1lfGn1BM"

username_xpath = "/html/body/div[1]/div/div/div[2]/div/form/div[1]/div[1]/input"
password_xpath = "/html/body/div[1]/div/div/div[2]/div/form/div[1]/div[2]/div/input"
enter_xpath = "/html/body/div[1]/div/div/div[2]/div/form/div[1]/div[5]/button"
btn = [
    "/html/body/div[5]/div/div/div/div[1]/ul/li[5]/div/div/div[1]/div[2]/table/tbody/tr[2]/td[2]/a",
    "/html/body/div[5]/div/div/div/div[1]/ul/li[5]/div/div/div[1]/div[2]/table/tbody/tr[3]/td[2]/a",
    "/html/body/div[5]/div/div/div/div[1]/ul/li[5]/div/div/div[1]/div[2]/table/tbody/tr[4]/td[2]/a",
    "/html/body/div[5]/div/div/div/div[1]/ul/li[5]/div/div/div[1]/div[2]/table/tbody/tr[5]/td[2]/a"
]
btn_next = "/html/body/div[5]/div/div/div/div[1]/ul/li[5]/div/div/div[1]/div[1]/div/a[1]"
btn_remake = "/html/body/div[5]/div/div/div/div[1]/ul/li[5]/div/div/div[1]/div[1]/div/a[2]"
btn_confirm = "/html/body/div[5]/div/div/div/div[1]/ul/li[5]/div/div/div[4]/div/div/div[3]/a[2]"
mark = "/html/body/div[5]/div/div/div/div[1]/ul/li[5]/div/div/div[1]/div[2]/table/tbody/tr[6]/td[4]"
close = "/html/body/div[8]/div/div/div[3]/div[2]/a"

# Ẩn log webdriver-manager
os.environ["WDM_LOG_LEVEL"] = "0"
logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")

class QuestionDatabase:
    """Quản lý cơ sở dữ liệu câu hỏi và đáp án"""
    
    def __init__(self, db_path="ioe_questions.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Khởi tạo cơ sở dữ liệu câu hỏi"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_text TEXT NOT NULL,
                    question_hash TEXT UNIQUE NOT NULL,
                    answer TEXT NOT NULL,
                    question_type INTEGER NOT NULL,
                    confirmed_correct BOOLEAN DEFAULT 0,
                    usage_count INTEGER DEFAULT 0,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tạo index để tìm kiếm nhanh hơn
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_question_hash ON questions(question_hash)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_question_text ON questions(question_text)')
            
            conn.commit()
            conn.close()
            logging.info("✅ Cơ sở dữ liệu câu hỏi đã được khởi tạo")
        except Exception as e:
            logging.error(f"❌ Lỗi khởi tạo cơ sở dữ liệu câu hỏi: {e}")
    
    def add_question(self, question_text, answer, question_type, confirmed_correct=False):
        """Thêm câu hỏi mới vào database"""
        try:
            # Tạo hash để so sánh nhanh
            question_hash = self._create_hash(question_text)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO questions 
                (question_text, question_hash, answer, question_type, confirmed_correct, usage_count, last_used)
                VALUES (?, ?, ?, ?, ?, COALESCE((SELECT usage_count FROM questions WHERE question_hash = ?), 0) + 1, CURRENT_TIMESTAMP)
            ''', (question_text, question_hash, answer, question_type, confirmed_correct, question_hash))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logging.error(f"❌ Lỗi khi thêm câu hỏi: {e}")
            return False
    
    def get_answer(self, question_text, question_type):
        """Tìm đáp án cho câu hỏi"""
        try:
            question_hash = self._create_hash(question_text)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT answer, confirmed_correct, usage_count 
                FROM questions 
                WHERE question_hash = ? OR question_text LIKE ?
                ORDER BY confirmed_correct DESC, usage_count DESC
                LIMIT 1
            ''', (question_hash, f"%{question_text}%"))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                answer, confirmed_correct, usage_count = result
                # Cập nhật số lần sử dụng
                if confirmed_correct:
                    self._increment_usage(question_hash)
                return answer, confirmed_correct
            return None, False
            
        except Exception as e:
            logging.error(f"❌ Lỗi khi tìm đáp án: {e}")
            return None, False
    
    def confirm_answer(self, question_text, answer):
        """Xác nhận đáp án là chính xác"""
        try:
            question_hash = self._create_hash(question_text)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE questions 
                SET confirmed_correct = 1, usage_count = usage_count + 1, last_used = CURRENT_TIMESTAMP
                WHERE question_hash = ? AND answer = ?
            ''', (question_hash, answer))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logging.error(f"❌ Lỗi khi xác nhận đáp án: {e}")
            return False
    
    def get_all_questions(self):
        """Lấy tất cả câu hỏi từ database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, question_text, answer, question_type, confirmed_correct, usage_count, last_used
                FROM questions 
                ORDER BY last_used DESC, usage_count DESC
            ''')
            
            questions = cursor.fetchall()
            conn.close()
            return questions
        except Exception as e:
            logging.error(f"❌ Lỗi khi lấy danh sách câu hỏi: {e}")
            return []
    
    def delete_question(self, question_id):
        """Xóa câu hỏi theo ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM questions WHERE id = ?', (question_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logging.error(f"❌ Lỗi khi xóa câu hỏi: {e}")
            return False
    
    def delete_all_questions(self):
        """Xóa tất cả câu hỏi"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM questions')
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logging.error(f"❌ Lỗi khi xóa tất cả câu hỏi: {e}")
            return False
    
    def export_to_excel(self, file_path):
        """Xuất câu hỏi ra file Excel"""
        try:
            questions = self.get_all_questions()
            if not questions:
                return False, "❌ Không có dữ liệu để xuất"
            
            # Tạo DataFrame từ dữ liệu
            df = pd.DataFrame(questions, columns=[
                'ID', 'Câu hỏi', 'Đáp án', 'Loại câu hỏi', 'Đã xác nhận', 'Số lần dùng', 'Lần dùng cuối'
            ])
            
            # Chuyển đổi giá trị boolean
            df['Đã xác nhận'] = df['Đã xác nhận'].apply(lambda x: '✅' if x else '❌')
            
            # Xuất ra Excel
            df.to_excel(file_path, index=False)
            return True, f"✅ Xuất thành công {len(questions)} câu hỏi ra file Excel"
            
        except Exception as e:
            return False, f"❌ Lỗi khi xuất file Excel: {str(e)}"
    
    def _create_hash(self, text):
        """Tạo hash đơn giản cho câu hỏi"""
        import hashlib
        # Chuẩn hóa text trước khi hash
        normalized_text = re.sub(r'\s+', ' ', text.strip().lower())
        return hashlib.md5(normalized_text.encode()).hexdigest()
    
    def _increment_usage(self, question_hash):
        """Tăng số lần sử dụng"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE questions 
                SET usage_count = usage_count + 1, last_used = CURRENT_TIMESTAMP
                WHERE question_hash = ?
            ''', (question_hash,))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"❌ Lỗi khi tăng số lần sử dụng: {e}")

class QuestionManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.question_db = QuestionDatabase()
        self.setWindowTitle("Quản lý câu hỏi và đáp án")
        self.setModal(True)
        self.resize(1200, 700)
        
        layout = QVBoxLayout(self)
        
        # Tiêu đề
        title_label = QLabel("📚 QUẢN LÝ CÂU HỎI VÀ ĐÁP ÁN")
        title_label.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #a6e22e; padding: 10px;")
        layout.addWidget(title_label)
        
        # Thống kê
        stats_layout = QHBoxLayout()
        self.stats_label = QLabel("Đang tải...")
        self.stats_label.setFont(QFont("Consolas", 11))
        self.stats_label.setStyleSheet("background-color: #3E3D32; padding: 8px; border-radius: 4px;")
        stats_layout.addWidget(self.stats_label)
        
        # Nút điều khiển
        control_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("🔄 Làm mới")
        self.refresh_button.clicked.connect(self.refresh_data)
        
        self.export_button = QPushButton("📤 Xuất Excel")
        self.export_button.clicked.connect(self.export_to_excel)
        
        self.delete_selected_button = QPushButton("🗑️ Xóa đã chọn")
        self.delete_selected_button.clicked.connect(self.delete_selected_questions)
        
        self.delete_all_button = QPushButton("🗑️ Xóa tất cả")
        self.delete_all_button.clicked.connect(self.delete_all_questions)
        
        self.filter_confirmed_checkbox = QCheckBox("Chỉ hiển thị đáp án đã xác nhận")
        self.filter_confirmed_checkbox.stateChanged.connect(self.refresh_data)
        
        control_layout.addWidget(self.refresh_button)
        control_layout.addWidget(self.export_button)
        control_layout.addWidget(self.delete_selected_button)
        control_layout.addWidget(self.delete_all_button)
        control_layout.addStretch()
        control_layout.addWidget(self.filter_confirmed_checkbox)
        
        layout.addLayout(stats_layout)
        layout.addLayout(control_layout)
        
        # Bảng câu hỏi
        self.questions_table = QTableWidget()
        self.questions_table.setColumnCount(7)
        self.questions_table.setHorizontalHeaderLabels([
            "Chọn", "ID", "Câu hỏi", "Đáp án", "Loại", "Xác nhận", "Số lần dùng"
        ])
        
        # Đặt tỷ lệ cột
        header = self.questions_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        
        self.questions_table.setColumnWidth(0, 50)
        self.questions_table.setColumnWidth(1, 60)
        self.questions_table.setColumnWidth(4, 80)
        self.questions_table.setColumnWidth(5, 100)
        self.questions_table.setColumnWidth(6, 100)
        
        layout.addWidget(self.questions_table)
        
        # Nút đóng
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.apply_dark_theme()
        self.refresh_data()
    
    def apply_dark_theme(self):
        """Áp dụng theme tối cho dialog"""
        self.setStyleSheet("""
            QDialog {
                background-color: #272822;
                color: #f8f8f2;
            }
            QPushButton {
                background-color: #3a3a33;
                border: 1px solid #555;
                padding: 6px 10px;
                border-radius: 4px;
                color: #f8f8f2;
            }
            QPushButton:hover {
                background-color: #4b4b40;
            }
            QTableWidget {
                background-color: #1E1E1E;
                border: 1px solid #3a3a33;
                color: #f8f8f2;
                gridline-color: #3a3a33;
            }
            QHeaderView::section {
                background-color: #2f2f2a;
                padding: 4px;
                border: 1px solid #444;
                color: #f8f8f2;
            }
            QTableWidget::item:selected {
                background-color: #66d9ef;
                color: #000;
            }
            QCheckBox {
                color: #f8f8f2;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #555;
                background-color: #1E1E1E;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #a6e22e;
                background-color: #a6e22e;
            }
        """)
        
        # Style cho các nút
        self.refresh_button.setStyleSheet("background-color: #66d9ef; color: #111;")
        self.export_button.setStyleSheet("background-color: #a6e22e; color: #111;")
        self.delete_selected_button.setStyleSheet("background-color: #fd971f; color: #111;")
        self.delete_all_button.setStyleSheet("background-color: #f92672; color: #111;")
    
    def refresh_data(self):
        """Làm mới dữ liệu"""
        try:
            # Lấy tất cả câu hỏi
            all_questions = self.question_db.get_all_questions()
            
            # Lọc theo trạng thái xác nhận nếu được chọn
            if self.filter_confirmed_checkbox.isChecked():
                questions = [q for q in all_questions if q[4]]  # confirmed_correct
            else:
                questions = all_questions
            
            # Cập nhật thống kê
            total_questions = len(all_questions)
            confirmed_questions = len([q for q in all_questions if q[4]])
            total_usage = sum(q[5] for q in all_questions)
            
            self.stats_label.setText(
                f"📊 Tổng số: {total_questions} câu hỏi | "
                f"✅ Đã xác nhận: {confirmed_questions} | "
                f"🔄 Tổng lần dùng: {total_usage}"
            )
            
            # Cập nhật bảng
            self.questions_table.setRowCount(len(questions))
            
            for row, question in enumerate(questions):
                id, question_text, answer, question_type, confirmed_correct, usage_count, last_used = question
                
                # Checkbox chọn
                checkbox_item = QTableWidgetItem()
                checkbox_item.setCheckState(Qt.CheckState.Unchecked)
                self.questions_table.setItem(row, 0, checkbox_item)
                
                # ID
                id_item = QTableWidgetItem(str(id))
                id_item.setFont(QFont("Consolas", 10))
                self.questions_table.setItem(row, 1, id_item)
                
                # Câu hỏi
                question_item = QTableWidgetItem(question_text)
                question_item.setFont(QFont("Consolas", 10))
                question_item.setToolTip(question_text)
                self.questions_table.setItem(row, 2, question_item)
                
                # Đáp án
                answer_item = QTableWidgetItem(answer)
                answer_item.setFont(QFont("Consolas", 10))
                answer_item.setToolTip(answer)
                self.questions_table.setItem(row, 3, answer_item)
                
                # Loại câu hỏi
                type_item = QTableWidgetItem(str(question_type))
                type_item.setFont(QFont("Consolas", 10))
                self.questions_table.setItem(row, 4, type_item)
                
                # Xác nhận
                confirmed_item = QTableWidgetItem("✅" if confirmed_correct else "❌")
                confirmed_item.setFont(QFont("Consolas", 10))
                confirmed_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if confirmed_correct:
                    confirmed_item.setBackground(QColor(38, 81, 36))  # Xanh đậm
                else:
                    confirmed_item.setBackground(QColor(90, 28, 28))  # Đỏ đậm
                self.questions_table.setItem(row, 5, confirmed_item)
                
                # Số lần dùng
                usage_item = QTableWidgetItem(str(usage_count))
                usage_item.setFont(QFont("Consolas", 10))
                usage_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.questions_table.setItem(row, 6, usage_item)
                
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể tải dữ liệu: {str(e)}")
    
    def get_selected_question_ids(self):
        """Lấy danh sách ID của các câu hỏi được chọn"""
        selected_ids = []
        for row in range(self.questions_table.rowCount()):
            checkbox_item = self.questions_table.item(row, 0)
            if checkbox_item and checkbox_item.checkState() == Qt.CheckState.Checked:
                id_item = self.questions_table.item(row, 1)
                if id_item:
                    selected_ids.append(int(id_item.text()))
        return selected_ids
    
    def delete_selected_questions(self):
        """Xóa các câu hỏi đã chọn"""
        selected_ids = self.get_selected_question_ids()
        if not selected_ids:
            QMessageBox.warning(self, "Thông báo", "Vui lòng chọn ít nhất một câu hỏi để xóa!")
            return
        
        reply = QMessageBox.question(
            self, "Xác nhận", 
            f"Bạn có chắc chắn muốn xóa {len(selected_ids)} câu hỏi đã chọn?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success_count = 0
            for question_id in selected_ids:
                if self.question_db.delete_question(question_id):
                    success_count += 1
            
            QMessageBox.information(self, "Thành công", f"Đã xóa {success_count} câu hỏi!")
            self.refresh_data()
    
    def delete_all_questions(self):
        """Xóa tất cả câu hỏi"""
        reply = QMessageBox.question(
            self, "Xác nhận", 
            "Bạn có CHẮC CHẮN muốn xóa TẤT CẢ câu hỏi?\nHành động này không thể hoàn tác!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.question_db.delete_all_questions():
                QMessageBox.information(self, "Thành công", "Đã xóa tất cả câu hỏi!")
                self.refresh_data()
            else:
                QMessageBox.critical(self, "Lỗi", "Không thể xóa tất cả câu hỏi!")
    
    def export_to_excel(self):
        """Xuất câu hỏi ra file Excel"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu file Excel",
            f"ioe_questions_{time.strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Excel Files (*.xlsx)"
        )
        
        if not file_path:
            return
        
        success, message = self.question_db.export_to_excel(file_path)
        
        if success:
            QMessageBox.information(self, "Thành công", message)
        else:
            QMessageBox.critical(self, "Lỗi", message)

class ChromeDriverManager:
    def __init__(self):
        self.driver_dir = os.path.dirname(os.path.abspath(__file__))
        self.driver_path = os.path.join(self.driver_dir, "chromedriver.exe")

    def get_chrome_version(self):
        try:
            result = subprocess.run(
                ['reg', 'query', r'HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon', '/v', 'version'],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            version = result.stdout.strip().split()[-1]
            return version
        except Exception as e:
            print("Không phát hiện được Chrome version:", e)
            return None

    def get_major_version(self, version):
        return version.split('.')[0] if version else None

    def setup_driver(self):
        # Nếu có sẵn driver hợp lệ thì dùng luôn
        if os.path.exists(self.driver_path):
            return self.driver_path

        version = self.get_chrome_version()
        major = self.get_major_version(version)
        if not major:
            raise Exception("Không phát hiện được phiên bản Chrome.")

        # Lấy bản ChromeDriver tương ứng trên Chrome for Testing
        url = f"https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_{major}"
        driver_version = requests.get(url, timeout=10).text.strip()

        zip_url = f"https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/{driver_version}/win32/chromedriver-win32.zip"
        print("📥 Đang tải ChromeDriver:", driver_version)
        r = requests.get(zip_url, timeout=20)

        temp_dir = os.path.join(self.driver_dir, "tmp_driver")
        os.makedirs(temp_dir, exist_ok=True)

        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            z.extractall(temp_dir)

        # 🔧 Di chuyển file thực tế từ folder con về thư mục chính
        extracted_path = os.path.join(temp_dir, "chromedriver-win32", "chromedriver.exe")
        if not os.path.exists(extracted_path):
            raise Exception("Không tìm thấy file chromedriver.exe sau khi giải nén!")

        shutil.move(extracted_path, self.driver_path)
        shutil.rmtree(temp_dir, ignore_errors=True)

        print("✅ Tải và thiết lập ChromeDriver thành công:", self.driver_path)
        return self.driver_path



class AccountManager:
    """Quản lý cơ sở dữ liệu tài khoản IOE"""
    
    def __init__(self, db_path="ioe_accounts.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    current_round INTEGER DEFAULT 0,
                    total_rounds INTEGER DEFAULT 8,
                    amount TEXT DEFAULT '',
                    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'Chưa kiểm tra'
                )
            ''')
            
            conn.commit()
            conn.close()
            logging.info("✅ Cơ sở dữ liệu tài khoản đã được khởi tạo")
        except Exception as e:
            logging.error(f"❌ Lỗi khởi tạo cơ sở dữ liệu: {e}")
    
    def add_account(self, username, password, full_name, total_rounds=8, amount=""):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO accounts 
                (username, password, full_name, total_rounds, amount, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, password, full_name, total_rounds, amount, 'Chưa kiểm tra'))
            
            conn.commit()
            conn.close()
            return True, "✅ Thêm tài khoản thành công"
        except Exception as e:
            return False, f"❌ Lỗi khi thêm tài khoản: {e}"
    
    def delete_account(self, username):
        """Xóa tài khoản"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM accounts WHERE username = ?', (username,))
            
            conn.commit()
            conn.close()
            return True, "✅ Xóa tài khoản thành công"
        except Exception as e:
            return False, f"❌ Lỗi khi xóa tài khoản: {e}"
    
    def get_all_accounts(self):
        """Lấy tất cả tài khoản"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT username, password, full_name, current_round, total_rounds, 
                       amount, last_checked, status 
                FROM accounts 
                ORDER BY last_checked DESC
            ''')
            
            accounts = cursor.fetchall()
            conn.close()
            return accounts
        except Exception as e:
            logging.error(f"❌ Lỗi khi lấy danh sách tài khoản: {e}")
            return []
    
    def update_account_progress(self, username, current_round, status):
        """Cập nhật tiến độ tài khoản"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE accounts 
                SET current_round = ?, status = ?, last_checked = CURRENT_TIMESTAMP
                WHERE username = ?
            ''', (current_round, status, username))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logging.error(f"❌ Lỗi cập nhật tiến độ: {e}")
            return False

    def update_account_info(self, old_username, new_username, password, full_name, total_rounds, amount):
        """Cập nhật thông tin tài khoản"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE accounts 
                SET username = ?, password = ?, full_name = ?, total_rounds = ?, amount = ?
                WHERE username = ?
            ''', (new_username, password, full_name, total_rounds, amount, old_username))
            
            conn.commit()
            conn.close()
            return True, "✅ Cập nhật tài khoản thành công"
        except Exception as e:
            return False, f"❌ Lỗi khi cập nhật tài khoản: {e}"

    def import_from_excel(self, file_path):
        """
        Import tài khoản từ file Excel, hỗ trợ nhận dạng cột linh hoạt.
        Các cột có thể xuất hiện:
            - Username  | Tài khoản
            - Password  | Mật khẩu
            - Full name | Tên người dùng | Họ và tên
            - Vòng hiện tại | Current Round
            - Tổng vòng | Total Rounds
            - Chuyển tiền | Amount
        """

        try:
            df = pd.read_excel(file_path)

            # Map tên cột linh hoạt
            column_map = {
                "username": ["username", "tài khoản", "account"],
                "password": ["password", "mật khẩu"],
                "full_name": ["tên người dùng", "họ và tên", "full name", "name"],
                "current_round": ["vòng hiện tại", "current round"],
                "total_rounds": ["tổng vòng", "total rounds"],
                "amount": ["chuyển tiền", "amount"]
            }

            def find_column(possible_names):
                for col in possible_names:
                    for df_col in df.columns:
                        if df_col.strip().lower() == col.lower():
                            return df_col
                return None

            # Bắt buộc phải có Username, Password, Full Name
            required_fields = ["username", "password", "full_name"]
            resolved_columns = {}

            for field in required_fields:
                resolved_columns[field] = find_column(column_map[field])
                if not resolved_columns[field]:
                    return False, f"❌ File thiếu cột bắt buộc: {field}"

            # Các cột tùy chọn
            resolved_columns["current_round"] = find_column(column_map["current_round"])
            resolved_columns["total_rounds"] = find_column(column_map["total_rounds"])
            resolved_columns["amount"] = find_column(column_map["amount"])

            # Bắt đầu import
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            success_count = 0
            error_count = 0
            errors = []

            for index, row in df.iterrows():
                try:
                    username = str(row[resolved_columns["username"]]).strip()
                    password = str(row[resolved_columns["password"]]).strip()
                    full_name = str(row[resolved_columns["full_name"]]).strip()

                    # Giá trị mặc định
                    current_round = 0
                    total_rounds = 8
                    amount = ""

                    # Nếu có cột thì lấy
                    if resolved_columns["current_round"]:
                        val = row[resolved_columns["current_round"]]
                        if pd.notna(val):
                            try: current_round = int(val)
                            except: pass

                    if resolved_columns["total_rounds"]:
                        val = row[resolved_columns["total_rounds"]]
                        if pd.notna(val):
                            try: total_rounds = int(val)
                            except: pass

                    if resolved_columns["amount"]:
                        val = row[resolved_columns["amount"]]
                        if pd.notna(val):
                            amount = str(val).strip()

                    # Ghi vào DB
                    cursor.execute('''
                        INSERT OR REPLACE INTO accounts
                        (username, password, full_name, current_round, total_rounds, amount, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (username, password, full_name, current_round, total_rounds, amount, "Chưa kiểm tra"))

                    success_count += 1

                except Exception as e:
                    error_count += 1
                    errors.append(f"Dòng {index + 2}: {e}")

            conn.commit()
            conn.close()

            msg = f"✅ Import thành công {success_count}"
            if error_count > 0:
                msg += f", lỗi {error_count}"
                if errors:
                    msg += "\n\n--- Lỗi mẫu ---\n" + "\n".join(errors[:5])

            return True, msg

        except Exception as e:
            return False, f"❌ Lỗi khi đọc file Excel: {e}"

    def export_to_excel(self, file_path):
        """Xuất tài khoản ra file Excel"""
        try:
            accounts = self.get_all_accounts()
            if not accounts:
                return False, "❌ Không có dữ liệu để xuất"
            
            # Tạo DataFrame từ dữ liệu
            df = pd.DataFrame(accounts, columns=[
                'Username', 'Password', 'Họ và tên', 'Vòng hiện tại', 
                'Tổng vòng', 'Số tiền', 'Lần kiểm tra cuối', 'Trạng thái'
            ])
            
            # Xuất ra Excel
            df.to_excel(file_path, index=False)
            return True, f"✅ Xuất thành công {len(accounts)} tài khoản ra file Excel"
            
        except Exception as e:
            return False, f"❌ Lỗi khi xuất file Excel: {str(e)}"


class EditAccountDialog(QDialog):
    def __init__(self, account_data, parent=None):
        super().__init__(parent)
        self.account_data = account_data
        self.setWindowTitle("Chỉnh sửa tài khoản")
        self.setModal(True)
        self.resize(420, 350)
        
        layout = QVBoxLayout(self)
        
        username_layout = QHBoxLayout()
        username_label = QLabel("Tên đăng nhập:")
        self.username_input = QLineEdit()
        self.username_input.setText(account_data[0])
        username_layout.addWidget(username_label)
        username_layout.addWidget(self.username_input)
        layout.addLayout(username_layout)
        
        password_layout = QHBoxLayout()
        password_label = QLabel("Mật khẩu:")
        self.password_input = QLineEdit()
        self.password_input.setText(account_data[1])
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        layout.addLayout(password_layout)
        
        full_name_layout = QHBoxLayout()
        full_name_label = QLabel("Họ và tên:")
        self.full_name_input = QLineEdit()
        self.full_name_input.setText(account_data[2])
        full_name_layout.addWidget(full_name_label)
        full_name_layout.addWidget(self.full_name_input)
        layout.addLayout(full_name_layout)
        
        rounds_layout = QHBoxLayout()
        rounds_label = QLabel("Tổng số vòng:")
        self.rounds_input = QLineEdit()
        self.rounds_input.setText(str(account_data[4] if account_data[4] is not None else 8))
        rounds_layout.addWidget(rounds_label)
        rounds_layout.addWidget(self.rounds_input)
        layout.addLayout(rounds_layout)
        
        amount_layout = QHBoxLayout()
        amount_label = QLabel("Số tiền:")
        self.amount_input = QLineEdit()
        self.amount_input.setText(str(account_data[5]) if account_data[5] is not None else "")
        amount_layout.addWidget(amount_label)
        amount_layout.addWidget(self.amount_input)
        layout.addLayout(amount_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_data(self):
        return (
            self.username_input.text().strip(),
            self.password_input.text().strip(),
            self.full_name_input.text().strip(),
            self.rounds_input.text().strip(),
            self.amount_input.text().strip()
        )


class RoundCheckerThread(QThread):    
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()
    
    def __init__(self, accounts, driver_path):
        super().__init__()
        self.accounts = accounts
        self.driver_path = driver_path
        self.account_manager = AccountManager()
        self._is_running = True
    
    def stop(self):
        self._is_running = False
    
    def log(self, message):
        self.log_signal.emit(message)
    
    def check_round_for_account(self, username, password, full_name):
        """Kiểm tra số vòng đã hoàn thành cho một tài khoản"""
        try:
            service = Service(executable_path=self.driver_path)
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            
            driver = webdriver.Chrome(service=service, options=options)
            
            driver.get("https://ioe.vn/tu-luyen")
            
            username_xpath = "/html/body/div[1]/div/div/div[2]/div/form/div[1]/div[1]/input"
            password_xpath = "/html/body/div[1]/div/div/div[2]/div/form/div[1]/div[2]/div/input"
            login_button_xpath = "/html/body/div[1]/div/div/div[2]/div/form/div[1]/div[5]/button"
            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, username_xpath))
            )
            
            driver.find_element(By.XPATH, username_xpath).send_keys(username)
            driver.find_element(By.XPATH, password_xpath).send_keys(password)
            driver.find_element(By.XPATH, login_button_xpath).click()
            
            time.sleep(3)
            
            if "tu-luyen" not in driver.current_url:
                self.log(f"❌ {full_name} ({username}): Đăng nhập thất bại")
                driver.quit()
                self.account_manager.update_account_progress(username, 0, "Đăng nhập thất bại")
                return False
            
            driver.get("https://ioe.vn/hoc-sinh")

            round_xpath = "/html/body/div[1]/main/section[2]/div/div[1]/div[3]/div[1]/div[2]/div/div[1]/h3[2]/span"
            
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, round_xpath))
                )
                
                round_element = driver.find_element(By.XPATH, round_xpath)
                current_round = int(round_element.text.strip().split("/")[0])
                
                self.log(f"✅ {full_name} ({username}): Đã hoàn thành {current_round} vòng")
                self.account_manager.update_account_progress(username, current_round, f"Đã hoàn thành {current_round} vòng")
                
            except (TimeoutException, NoSuchElementException):
                self.log(f"⚠️ {full_name} ({username}): Không tìm thấy thông tin số vòng")
                self.account_manager.update_account_progress(username, 0, "Không tìm thấy thông tin")
            
            driver.quit()
            return True
            
        except Exception as e:
            self.log(f"❌ {full_name} ({username}): Lỗi khi kiểm tra - {str(e)}")
            self.account_manager.update_account_progress(username, 0, f"Lỗi: {str(e)}")
            return False
    
    def run(self):
        total_accounts = len(self.accounts)
        
        for index, account in enumerate(self.accounts):
            if not self._is_running:
                break
                
            username, password, full_name = account[0], account[1], account[2]
            
            progress = int((index + 1) / total_accounts * 100)
            self.progress_signal.emit(progress)
            
            self.log(f"🔍 Đang kiểm tra: {full_name} ({username})")
            self.check_round_for_account(username, password, full_name)
            
            time.sleep(2)
        
        self.log("✅ Đã hoàn thành kiểm tra tất cả tài khoản")
        self.finished_signal.emit()


class BatchAutomationThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    account_progress_signal = pyqtSignal(int, int, str)
    start_automation_signal = pyqtSignal(str, str, int)
    finished_signal = pyqtSignal()
    automation_completed_signal = pyqtSignal(bool)
    
    def __init__(self, accounts, target_round, driver_path):
        super().__init__()
        self.accounts = accounts
        self.target_round = target_round
        self.driver_path = driver_path
        self.account_manager = AccountManager()
        self._is_running = True
        self.current_automation_complete = False
        self.waiting_for_completion = False
    
    def stop(self):
        self._is_running = False
    
    def on_automation_completed(self, success):
        """Callback khi automation hoàn thành"""
        self.current_automation_complete = True
        self.waiting_for_completion = False
        if not success:
            self.log_signal.emit("⚠️ Automation hoàn thành với trạng thái lỗi")
    
    def wait_for_automation_completion(self):
        """Chờ thực sự cho đến khi automation hoàn thành"""
        self.waiting_for_completion = True
        self.current_automation_complete = False
        
        # Tạo event loop để chờ
        loop = QEventLoop()
        timeout_timer = QTimer()
        timeout_timer.setSingleShot(True)
        timeout_timer.timeout.connect(loop.quit)
        
        # Timeout sau 10 phút cho mỗi tài khoản
        timeout_timer.start(10 * 60 * 1000)
        
        # Kiểm tra mỗi 100ms xem đã hoàn thành chưa
        check_timer = QTimer()
        
        def check_completion():
            if self.current_automation_complete or not self._is_running:
                loop.quit()
        
        check_timer.timeout.connect(check_completion)
        check_timer.start(100)
        
        loop.exec()
        
        check_timer.stop()
        timeout_timer.stop()
        
        if not self.current_automation_complete and self._is_running:
            self.log_signal.emit("❌ Timeout khi chờ automation hoàn thành")
    
    def run(self):
        total_accounts = len(self.accounts)
        
        for index, account in enumerate(self.accounts):
            if not self._is_running:
                break
                
            username, password, full_name, current_round, total_rounds, amount, last_checked, status = account
            
            # Cập nhật tiến trình tổng
            progress = int((index) / total_accounts * 100)
            self.progress_signal.emit(progress)
            self.account_progress_signal.emit(index + 1, total_accounts, full_name)
            
            # Kiểm tra nếu tài khoản đã đạt vòng mục tiêu
            current_round = current_round if current_round else 0
            if current_round >= self.target_round:
                self.log_signal.emit(f"⏭️ {full_name} ({username}): Đã đạt vòng {current_round}, bỏ qua")
                continue
            
            # Tính số vòng cần chạy
            rounds_to_run = self.target_round - current_round
            
            self.log_signal.emit(f"🚀 Bắt đầu chạy {full_name} ({username}): {rounds_to_run} vòng")
            
            # Gửi signal để bắt đầu automation trong tab tự động hóa
            self.start_automation_signal.emit(username, password, rounds_to_run)
            
            # Chờ cho automation hoàn thành
            self.wait_for_automation_completion()
            
            if not self._is_running:
                break
                
            # Cập nhật vòng hiện tại trong database
            self.account_manager.update_account_progress(username, self.target_round, f"Đã chạy đến vòng {self.target_round}")
            self.log_signal.emit(f"✅ {full_name} ({username}): Đã hoàn thành {self.target_round} vòng")
            
            # Nghỉ giữa các tài khoản
            time.sleep(2)
        
        self.progress_signal.emit(100)
        self.finished_signal.emit()

class IOEAccountManagerUI(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.account_manager = AccountManager()
        self.checker_thread = None
        self.batch_thread = None
        self.driver_path = None
        self.main_window = main_window
        # THÊM CÁC BIẾN MÀU
        self.bg = "#272822"
        self.surface = "#3E3D32"
        self.fg = "#F8F8F2"
        self.accent_orange = "#FD971F"
        self.accent_pink = "#F92672"
        self.accent_green = "#A6E22E"
        self.accent_blue = "#66D9EF"
        
        self.init_ui()
        self.setup_driver()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 12, 18, 12)
        
        title_label = QLabel("QUẢN LÝ TÀI KHOẢN IOE")
        title_label.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #f8f8f2; padding: 8px;")
        layout.addWidget(title_label)
        
        tabs = QTabWidget()
        tabs.setStyleSheet("QTabBar::tab { height: 30px; padding: 6px 12px; }")
        
        add_tab = QWidget()
        add_layout = QVBoxLayout(add_tab)
        
        add_group = QGroupBox("Thêm tài khoản mới")
        add_group.setFont(QFont("Consolas", 12))
        add_group_layout = QVBoxLayout(add_group)
        
        username_layout = QHBoxLayout()
        username_label = QLabel("Tên đăng nhập:")
        username_label.setFont(QFont("Consolas", 11))
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Nhập username IOE")
        username_layout.addWidget(username_label)
        username_layout.addWidget(self.username_input)
        add_group_layout.addLayout(username_layout)
        
        password_layout = QHBoxLayout()
        password_label = QLabel("Mật khẩu:")
        password_label.setFont(QFont("Consolas", 11))
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Nhập mật khẩu")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        add_group_layout.addLayout(password_layout)
        
        full_name_layout = QHBoxLayout()
        full_name_label = QLabel("Họ và tên:")
        full_name_label.setFont(QFont("Consolas", 11))
        self.full_name_input = QLineEdit()
        self.full_name_input.setPlaceholderText("Nhập họ và tên đầy đủ")
        full_name_layout.addWidget(full_name_label)
        full_name_layout.addWidget(self.full_name_input)
        add_group_layout.addLayout(full_name_layout)
        
        rounds_layout = QHBoxLayout()
        rounds_label = QLabel("Tổng số vòng:")
        rounds_label.setFont(QFont("Consolas", 11))
        self.rounds_input = QLineEdit()
        self.rounds_input.setPlaceholderText("Mặc định: 8")
        self.rounds_input.setText("8")
        rounds_layout.addWidget(rounds_label)
        rounds_layout.addWidget(self.rounds_input)
        add_group_layout.addLayout(rounds_layout)
        
        amount_layout = QHBoxLayout()
        amount_label = QLabel("Số tiền:")
        amount_label.setFont(QFont("Consolas", 11))
        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("VD: 50k, 30k, Free...")
        amount_layout.addWidget(amount_label)
        amount_layout.addWidget(self.amount_input)
        add_group_layout.addLayout(amount_layout)
        
        self.add_button = QPushButton("Thêm tài khoản")
        self.add_button.clicked.connect(self.add_account)
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_group_layout.addWidget(self.add_button)
        
        add_layout.addWidget(add_group)
        add_tab.setLayout(add_layout)
        
        list_tab = QWidget()
        list_layout = QVBoxLayout(list_tab)
        
        control_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("🔄 Làm mới")
        self.refresh_button.clicked.connect(self.refresh_accounts)
        
        self.check_all_button = QPushButton("🔍 Kiểm tra tất cả")
        self.check_all_button.clicked.connect(self.check_all_accounts)

        self.check_selected_button = QPushButton("✅ Kiểm tra tài khoản đã chọn")
        self.check_selected_button.clicked.connect(self.check_selected_accounts)

        self.import_button = QPushButton("📥 Import Excel")
        self.import_button.clicked.connect(self.import_from_excel)
        
        # THÊM NÚT XUẤT EXCEL
        self.export_button = QPushButton("📤 Xuất Excel")
        self.export_button.clicked.connect(self.export_to_excel)
        
        self.edit_button = QPushButton("✏️ Chỉnh sửa")
        self.edit_button.clicked.connect(self.edit_account)
        
        self.delete_button = QPushButton("🗑️ Xóa")
        self.delete_button.clicked.connect(self.delete_account)
        
        self.run_all_to_round_button = QPushButton("🚀 Chạy tất cả đến vòng")
        self.run_all_to_round_button.clicked.connect(self.run_all_to_round)

        # THÊM NÚT CHẠY ĐẾN VÒNG HIỆN TẠI
        self.run_to_current_button = QPushButton("🚀 Chạy đến vòng hiện tại")
        self.run_to_current_button.clicked.connect(self.run_to_current_round)
        
        # THÊM NÚT QUẢN LÝ CÂU HỎI
        self.manage_questions_button = QPushButton("📚 Quản lý câu hỏi")
        self.manage_questions_button.clicked.connect(self.manage_questions)
        
        control_layout.addWidget(self.refresh_button)
        control_layout.addWidget(self.check_all_button)
        control_layout.addWidget(self.check_selected_button)
        control_layout.addWidget(self.import_button)
        control_layout.addWidget(self.export_button)  # Thêm nút xuất Excel
        control_layout.addWidget(self.edit_button)
        control_layout.addWidget(self.delete_button)
        control_layout.addWidget(self.run_all_to_round_button)
        control_layout.addWidget(self.run_to_current_button)  # Thêm nút chạy đến vòng hiện tại
        control_layout.addWidget(self.manage_questions_button)  # Thêm nút quản lý câu hỏi
        control_layout.addStretch()
        
        list_layout.addLayout(control_layout)
        
        self.accounts_table = QTableWidget()
        self.accounts_table.setColumnCount(8)
        self.accounts_table.setHorizontalHeaderLabels([
            "Username", "Mật khẩu", "Họ và tên", "Vòng hiện tại", 
            "Tổng vòng", "Số tiền", "Lần kiểm tra cuối", "Trạng thái"
        ])
        
        header = self.accounts_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        list_layout.addWidget(self.accounts_table)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        list_layout.addWidget(self.progress_bar)
        
        log_group = QGroupBox("Nhật ký hoạt động")
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(150)
        self.log_output.setFont(QFont("Consolas", 11))
        log_layout = QVBoxLayout(log_group)
        log_layout.addWidget(self.log_output)
        list_layout.addWidget(log_group)
        
        list_tab.setLayout(list_layout)
        
        tabs.addTab(add_tab, "➕ Thêm tài khoản")
        tabs.addTab(list_tab, "📋 Danh sách tài khoản")
        
        layout.addWidget(tabs)

        self.run_all_to_round_button.setStyleSheet(f"background-color: {self.accent_green}; color: #111; padding:6px; border-radius:4px;")
        self.manage_questions_button.setStyleSheet(f"background-color: {self.accent_blue}; color: #111; padding:6px; border-radius:4px;")
        
        self.apply_monokai_styles()
        self.refresh_accounts()

    def manage_questions(self):
        """Mở dialog quản lý câu hỏi"""
        dialog = QuestionManagerDialog(self)
        dialog.exec()

    def start_batch_automation(self, accounts, target_round):
        """Bắt đầu chạy automation cho tất cả tài khoản thông qua tab tự động hóa"""
        if not self.driver_path:
            QMessageBox.critical(self, "Lỗi", "ChromeDriver chưa được thiết lập!")
            return
        
        # Vô hiệu hóa các nút
        self.disable_all_buttons()
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Tạo label hiển thị tiến trình tài khoản hiện tại
        if not hasattr(self, 'current_account_label'):
            self.current_account_label = QLabel("")
            self.current_account_label.setFont(QFont("Consolas", 11))
            self.current_account_label.setStyleSheet("color: #66d9ef; padding: 4px;")
            self.layout().insertWidget(2, self.current_account_label)
        
        self.current_account_label.setVisible(True)
        
        self.batch_thread = BatchAutomationThread(accounts, target_round, self.driver_path)
        self.batch_thread.log_signal.connect(self.log_message)
        self.batch_thread.progress_signal.connect(self.progress_bar.setValue)
        self.batch_thread.account_progress_signal.connect(self.update_current_account)
        self.batch_thread.start_automation_signal.connect(self.start_automation_in_tab)
        self.batch_thread.finished_signal.connect(self.on_batch_finished)
        
        # 🔥 KẾT NỐI SIGNAL MỚI
        self.batch_thread.automation_completed_signal.connect(self.batch_thread.on_automation_completed)
        
        self.batch_thread.start()

    def start_automation_in_tab(self, username, password, rounds_to_run):
        """Bắt đầu automation trong tab tự động hóa"""
        if self.main_window:
            # Chuyển sang tab tự động hóa
            self.main_window.tabs.setCurrentIndex(1)
            automation_ui = self.main_window.automation_ui
            
            # 🔥 KẾT NỐI SIGNAL HOÀN THÀNH
            automation_ui.automation_completed.connect(self.on_single_automation_completed)
            
            # Thiết lập thông tin đăng nhập và số vòng
            automation_ui.username_input.setText(username)
            automation_ui.password_input.setText(password)
            automation_ui.rounds_input.setValue(rounds_to_run)
            
            # Bắt đầu automation
            QTimer.singleShot(500, automation_ui.start_automation)
            
            self.log_message(f"✅ Đã chuyển thông tin {username} sang tab tự động hóa")
            self.log_message(f"📊 Số vòng cần chạy: {rounds_to_run} vòng")
        else:
            self.log_message("❌ Không thể chuyển sang tab tự động hóa!")

    def on_single_automation_completed(self, success):
        """Callback khi một tài khoản hoàn thành automation"""
        if self.batch_thread and self.batch_thread.isRunning():
            self.batch_thread.automation_completed_signal.emit(success)

    def update_current_account(self, current, total, account_name):
        """Cập nhật hiển thị tài khoản đang chạy"""
        self.current_account_label.setText(f"Đang chạy: {account_name} ({current}/{total})")

    def disable_all_buttons(self):
        """Vô hiệu hóa tất cả các nút"""
        buttons = [
            self.refresh_button, self.check_all_button, self.check_selected_button,
            self.import_button, self.export_button, self.edit_button, self.delete_button,
            self.run_to_current_button, self.run_all_to_round_button, self.add_button,
            self.manage_questions_button
        ]
        for button in buttons:
            button.setEnabled(False)

    def enable_all_buttons(self):
        """Kích hoạt lại tất cả các nút"""
        buttons = [
            self.refresh_button, self.check_all_button, self.check_selected_button,
            self.import_button, self.export_button, self.edit_button, self.delete_button,
            self.run_to_current_button, self.run_all_to_round_button, self.add_button,
            self.manage_questions_button
        ]
        for button in buttons:
            button.setEnabled(True)

    def on_batch_finished(self):
        """Khi hoàn thành chạy tất cả tài khoản"""
        self.enable_all_buttons()
        self.progress_bar.setVisible(False)
        if hasattr(self, 'current_account_label'):
            self.current_account_label.setVisible(False)
        
        self.refresh_accounts()
        QMessageBox.information(self, "Thành công", "Đã hoàn thành chạy tự động hóa cho tất cả tài khoản!")

    def run_all_to_round(self):
        """Chạy tất cả tài khoản đến vòng chỉ định thông qua tab tự động hóa"""
        # Hiển thị hộp thoại nhập vòng
        target_round, ok = QInputDialog.getInt(
            self,
            "Chạy đến vòng",
            "Nhập vòng mong muốn:",
            min=1, max=50, value=15
        )
        
        if not ok:
            return
        
        accounts = self.account_manager.get_all_accounts()
        
        if not accounts:
            QMessageBox.warning(self, "Thông báo", "Không có tài khoản nào để chạy!")
            return
        
        # Xác nhận thực hiện
        reply = QMessageBox.question(
            self, "Xác nhận", 
            f"Bạn có chắc chắn muốn chạy {len(accounts)} tài khoản đến vòng {target_round}?\n\nToàn bộ quá trình sẽ chạy trong tab Tự động hóa IOE để bạn có thể sử dụng các chức năng như nộp bài ngay.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.log_message(f"🚀 Bắt đầu chạy {len(accounts)} tài khoản đến vòng {target_round}...")
            self.log_message("📝 Toàn bộ quá trình sẽ chạy trong tab Tự động hóa IOE")
            self.log_message("⏩ Bạn có thể sử dụng nút 'Nộp bài ngay' trong tab đó")
            self.start_batch_automation(accounts, target_round)

    def start_checking(self, accounts):
        """Bắt đầu kiểm tra danh sách tài khoản"""
        if not hasattr(self, "driver_path") or not self.driver_path:
            QMessageBox.critical(self, "Lỗi", "ChromeDriver chưa được thiết lập!")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Gọi luồng kiểm tra riêng (ví dụ RoundCheckerThread)
        self.checker_thread = RoundCheckerThread(accounts, self.driver_path)
        self.checker_thread.log_signal.connect(self.log_message)
        self.checker_thread.progress_signal.connect(self.progress_bar.setValue)
        self.checker_thread.finished_signal.connect(self.on_checking_finished)
        self.checker_thread.start()

    
    def check_selected_accounts(self):
        selected_rows = set(index.row() for index in self.accounts_table.selectedIndexes())
        if not selected_rows:
            QMessageBox.warning(self, "Thông báo", "Vui lòng chọn ít nhất một tài khoản để kiểm tra!")
            return
        accounts = []
        all_accounts = self.account_manager.get_all_accounts()
        for i in selected_rows:
            if i < len(all_accounts):
                accounts.append(all_accounts[i])
        if not accounts:
            QMessageBox.warning(self, "Thông báo", "Không có tài khoản hợp lệ được chọn!")
            return
        self.log_message(f"🚀 Bắt đầu kiểm tra {len(accounts)} tài khoản đã chọn...")
        self.start_checking(accounts)

    def apply_monokai_styles(self):
        bg = self.bg
        surface = self.surface
        fg = self.fg
        accent_orange = self.accent_orange
        accent_pink = self.accent_pink
        accent_green = self.accent_green
        accent_blue = self.accent_blue

        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window, QColor(bg))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(fg))
        pal.setColor(QPalette.ColorRole.Base, QColor("#1E1E1E"))
        pal.setColor(QPalette.ColorRole.AlternateBase, QColor(surface))
        pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(fg))
        pal.setColor(QPalette.ColorRole.ToolTipText, QColor(fg))
        pal.setColor(QPalette.ColorRole.Text, QColor(fg))
        pal.setColor(QPalette.ColorRole.Button, QColor(surface))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor(fg))
        pal.setColor(QPalette.ColorRole.Highlight, QColor(accent_blue))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))
        QApplication.instance().setPalette(pal)

        qss = f"""
        QWidget {{
            background-color: {bg};
            color: {fg};
            font-family: Consolas, monospace;
            font-size: 11pt;
        }}
        QGroupBox {{
            border: 1px solid #44403a;
            margin-top: 8px;
            padding: 8px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 3px;
            color: {accent_orange};
            font-weight: bold;
        }}
        QPushButton {{
            background-color: #3a3a33;
            border: 1px solid #555;
            padding: 6px 10px;
            border-radius: 4px;
        }}
        QPushButton:hover {{
            background-color: #4b4b40;
        }}
        QLineEdit, QTextEdit, QTableWidget {{
            background-color: #1E1E1E;
            border: 1px solid #3a3a33;
            color: {fg};
            selection-background-color: {accent_blue};
            selection-color: #000000;
        }}
        QHeaderView::section {{
            background-color: #2f2f2a;
            padding: 4px;
            border: 1px solid #444;
            color: {fg};
        }}
        QTableWidget::item:selected {{
            background-color: {accent_blue};
            color: #000;
        }}
        QMessageBox {{
            background-color: {bg};
            color: {fg};
        }}
        QProgressBar {{
            border: 1px solid #555;
            text-align: center;
            height: 18px;
            border-radius: 4px;
        }}
        QProgressBar::chunk {{
            background-color: {accent_green};
            width: 10px;
        }}
        """

        QApplication.instance().setStyleSheet(qss)

        self.add_button.setStyleSheet(f"background-color: {accent_green}; color: #111; font-weight: bold; padding: 8px; border-radius:4px;")
        self.check_all_button.setStyleSheet(f"background-color: {accent_orange}; color: #111; padding:6px; border-radius:4px;")
        self.check_selected_button.setStyleSheet(f"background-color: {accent_orange}; color: #111; padding:6px; border-radius:4px;")
        self.import_button.setStyleSheet(f"background-color: {accent_blue}; color: #111; padding:6px; border-radius:4px;")
        self.export_button.setStyleSheet(f"background-color: {accent_blue}; color: #111; padding:6px; border-radius:4px;")  # Style cho nút xuất Excel
        self.refresh_button.setStyleSheet("background-color: #5a5a52; color: #fff; padding:6px; border-radius:4px;")
        self.edit_button.setStyleSheet(f"background-color: {accent_blue}; color: #111; padding:6px; border-radius:4px;")
        self.delete_button.setStyleSheet(f"background-color: {accent_pink}; color: #111; padding:6px; border-radius:4px;")
        self.run_to_current_button.setStyleSheet(f"background-color: {accent_green}; color: #111; padding:6px; border-radius:4px;")  # Style cho nút chạy đến vòng hiện tại

    def setup_driver(self):
        try:
            driver_manager = ChromeDriverManager()
            self.driver_path = driver_manager.setup_driver()
            self.log_message("✅ Đã thiết lập ChromeDriver thành công")
        except Exception as e:
            self.log_message(f"❌ Lỗi thiết lập ChromeDriver: {str(e)}")
            QMessageBox.critical(self, "Lỗi", str(e))
    
    def log_message(self, message):
        self.log_output.append(f"[{time.strftime('%H:%M:%S')}] {message}")
    
    def add_account(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        full_name = self.full_name_input.text().strip()
        rounds_text = self.rounds_input.text().strip()
        amount = self.amount_input.text().strip()
        
        if not username or not password or not full_name:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập đầy đủ thông tin!")
            return
        
        try:
            total_rounds = int(rounds_text) if rounds_text else 8
        except ValueError:
            QMessageBox.warning(self, "Lỗi", "Số vòng phải là số nguyên!")
            return
        
        success, message = self.account_manager.add_account(username, password, full_name, total_rounds, amount)
        
        if success:
            QMessageBox.information(self, "Thành công", message)
            self.username_input.clear()
            self.password_input.clear()
            self.full_name_input.clear()
            self.rounds_input.setText("8")
            self.amount_input.clear()
            self.refresh_accounts()
        else:
            QMessageBox.critical(self, "Lỗi", message)
    
    def refresh_accounts(self):
        accounts = self.account_manager.get_all_accounts()
        
        self.accounts_table.setRowCount(len(accounts))
        
        for row, account in enumerate(accounts):
            for col, value in enumerate(account):
                item = QTableWidgetItem(str(value))
                item.setFont(QFont("Consolas", 11))
                
                if col == 3:
                    current_round = int(value) if str(value).isdigit() else 0
                    total_rounds = int(account[4]) if str(account[4]).isdigit() else 8
                    
                    if current_round >= total_rounds:
                        item.setBackground(QColor(38, 81, 36))
                    elif current_round > 0:
                        item.setBackground(QColor(84, 77, 0))
                    else:
                        item.setBackground(QColor(90, 28, 28))
                
                self.accounts_table.setItem(row, col, item)

    def edit_account(self):
        current_row = self.accounts_table.currentRow()
        
        if current_row == -1:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn tài khoản để chỉnh sửa!")
            return
        
        account_data = []
        for col in range(8):
            item = self.accounts_table.item(current_row, col)
            account_data.append(item.text() if item else "")
        
        dialog = EditAccountDialog(account_data, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_username, new_password, new_full_name, new_rounds, new_amount = dialog.get_data()
            
            if not new_username or not new_password or not new_full_name:
                QMessageBox.warning(self, "Lỗi", "Vui lòng nhập đầy đủ thông tin!")
                return
            
            try:
                total_rounds = int(new_rounds) if new_rounds else 8
            except ValueError:
                QMessageBox.warning(self, "Lỗi", "Số vòng phải là số nguyên!")
                return
            
            old_username = account_data[0]
            success, message = self.account_manager.update_account_info(
                old_username, new_username, new_password, new_full_name, total_rounds, new_amount
            )
            
            if success:
                QMessageBox.information(self, "Thành công", message)
                self.refresh_accounts()
            else:
                QMessageBox.critical(self, "Lỗi", message)

    def delete_account(self):
        current_row = self.accounts_table.currentRow()
        
        if current_row == -1:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn tài khoản để xóa!")
            return
        
        username = self.accounts_table.item(current_row, 0).text()
        full_name = self.accounts_table.item(current_row, 2).text()
        
        reply = QMessageBox.question(
            self, "Xác nhận", 
            f"Bạn có chắc chắn muốn xóa tài khoản:\n{full_name} ({username})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success, message = self.account_manager.delete_account(username)
            
            if success:
                QMessageBox.information(self, "Thành công", message)
                self.refresh_accounts()
            else:
                QMessageBox.critical(self, "Lỗi", message)

    def import_from_excel(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file Excel",
            "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            success, message = self.account_manager.import_from_excel(file_path)
            
            if success:
                QMessageBox.information(self, "Thành công", message)
                self.refresh_accounts()
            else:
                QMessageBox.critical(self, "Lỗi", message)
                
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi khi import file Excel: {str(e)}")

    def export_to_excel(self):
        """Xuất danh sách tài khoản ra file Excel"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu file Excel",
            f"ioe_accounts_{time.strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Excel Files (*.xlsx)"
        )
        
        if not file_path:
            return
        
        try:
            success, message = self.account_manager.export_to_excel(file_path)
            
            if success:
                QMessageBox.information(self, "Thành công", message)
            else:
                QMessageBox.critical(self, "Lỗi", message)
                
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi khi xuất file Excel: {str(e)}")

    def check_all_accounts(self):
        if not self.driver_path:
            QMessageBox.critical(self, "Lỗi", "ChromeDriver chưa được thiết lập!")
            return
        
        accounts = self.account_manager.get_all_accounts()
        
        if not accounts:
            QMessageBox.warning(self, "Thông báo", "Không có tài khoản nào để kiểm tra!")
            return
        
        self.check_all_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.import_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.add_button.setEnabled(False)
        self.run_to_current_button.setEnabled(False)
        self.manage_questions_button.setEnabled(False)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.log_output.clear()
        self.log_message("🚀 Bắt đầu kiểm tra tất cả tài khoản...")
        
        self.checker_thread = RoundCheckerThread(accounts, self.driver_path)
        self.checker_thread.log_signal.connect(self.log_message)
        self.checker_thread.progress_signal.connect(self.progress_bar.setValue)
        self.checker_thread.finished_signal.connect(self.on_checking_finished)
        self.checker_thread.start()
    
    def on_checking_finished(self):
        self.check_all_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.import_button.setEnabled(True)
        self.export_button.setEnabled(True)
        self.edit_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        self.add_button.setEnabled(True)
        self.run_to_current_button.setEnabled(True)
        self.manage_questions_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        self.refresh_accounts()
        QMessageBox.information(self, "Thành công", "Đã hoàn thành kiểm tra tất cả tài khoản!")

    def check_selected_accounts(self):
        if not self.driver_path:
            QMessageBox.critical(self, "Lỗi", "ChromeDriver chưa được thiết lập!")
            return

        selected_rows = set(index.row() for index in self.accounts_table.selectedIndexes())
        if not selected_rows:
            QMessageBox.warning(self, "Thông báo", "Vui lòng chọn ít nhất một tài khoản để kiểm tra!")
            return

        all_accounts = self.account_manager.get_all_accounts()
        accounts = [all_accounts[i] for i in selected_rows if i < len(all_accounts)]
        if not accounts:
            QMessageBox.warning(self, "Thông báo", "Không có tài khoản hợp lệ được chọn!")
            return

        self.check_all_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.import_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.add_button.setEnabled(False)
        self.run_to_current_button.setEnabled(False)
        self.manage_questions_button.setEnabled(False)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.log_output.clear()
        self.log_message(f"🚀 Bắt đầu kiểm tra {len(accounts)} tài khoản đã chọn...")

        self.checker_thread = RoundCheckerThread(accounts, self.driver_path)
        self.checker_thread.log_signal.connect(self.log_message)
        self.checker_thread.progress_signal.connect(self.progress_bar.setValue)
        self.checker_thread.finished_signal.connect(self.on_checking_finished)
        self.checker_thread.start()

    def run_to_current_round(self):
        """Chạy tự động hóa cho tài khoản được chọn đến vòng hiện tại"""
        current_row = self.accounts_table.currentRow()
        
        if current_row == -1:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn một tài khoản!")
            return
        
        # Lấy thông tin tài khoản được chọn
        username = self.accounts_table.item(current_row, 0).text()
        password = self.accounts_table.item(current_row, 1).text()
        full_name = self.accounts_table.item(current_row, 2).text()
        current_round = int(self.accounts_table.item(current_row, 3).text())
        total_rounds = int(self.accounts_table.item(current_row, 4).text())
        
        # Tính số vòng cần chạy
        rounds_to_run = total_rounds - current_round
        
        if rounds_to_run <= 0:
            QMessageBox.information(self, "Thông báo", 
                                  f"Tài khoản {full_name} đã hoàn thành tất cả {total_rounds} vòng!")
            return
        
        # Chuyển sang tab tự động hóa và thiết lập thông tin
        if self.main_window:
            self.main_window.tabs.setCurrentIndex(1)  # Chuyển sang tab tự động hóa
            automation_ui = self.main_window.automation_ui
            
            # Thiết lập thông tin đăng nhập và số vòng
            automation_ui.username_input.setText(username)
            automation_ui.password_input.setText(password)
            automation_ui.rounds_input.setValue(rounds_to_run)
            
            self.log_message(f"✅ Đã chuyển thông tin tài khoản {full_name} sang tab tự động hóa")
            self.log_message(f"📊 Số vòng cần chạy: {rounds_to_run} vòng")
            
            QTimer.singleShot(300, automation_ui.start_automation)
        else:
            QMessageBox.critical(self, "Lỗi", "Không thể chuyển sang tab tự động hóa!")

class ThemeManager:
    @staticmethod
    def get_dark_monokai_theme():
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(39, 40, 34))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(248, 248, 242))
        palette.setColor(QPalette.ColorRole.Base, QColor(30, 31, 28))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(39, 40, 34))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(39, 40, 34))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(248, 248, 242))
        palette.setColor(QPalette.ColorRole.Text, QColor(248, 248, 242))
        palette.setColor(QPalette.ColorRole.Button, QColor(65, 67, 57))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(248, 248, 242))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(249, 38, 114))
        palette.setColor(QPalette.ColorRole.Link, QColor(102, 217, 239))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(166, 226, 46))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(39, 40, 34))

        return palette


class IOEWorker(QThread):
    log_signal = pyqtSignal(str, str)
    progress_signal = pyqtSignal(int)
    countdown_signal = pyqtSignal(int)
    round_progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(bool)
    submit_now_signal = pyqtSignal()

    def __init__(self, username, password, min_score, finish_delay_min, finish_delay_max, total_rounds):
        super().__init__()
        self.username = username
        self.password = password
        self.min_score = min_score
        self.finish_delay_min = finish_delay_min
        self.finish_delay_max = finish_delay_max
        self.total_rounds = total_rounds
        self._is_running = True
        self._submit_now = False
        self.current_answers = []
        self.current_tokenrq = None
        self.current_examKey = None
        # THÊM: Khởi tạo database câu hỏi
        self.question_db = QuestionDatabase()

    def stop(self):
        self._is_running = False

    def submit_now(self):
        self._submit_now = True

    def log(self, message, color="#f8f8f2"):
        self.log_signal.emit(message, color)

    def setup_chrome_driver(self):
        try:
            driver_manager = ChromeDriverManager()
            
            final_driver_path = driver_manager.setup_driver()
            
            # Thêm các options để tránh detection và popup
            options = Options()
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--disable-popup-blocking')
            options.add_argument('--disable-notifications')
            options.add_argument('--disable-extensions')
            options.add_argument('--no-first-run')
            options.add_argument('--no-default-browser-check')
            options.add_argument('--disable-translate')
            options.add_argument('--disable-infobars')
            options.add_argument('--window-size=1920,1080')
            
            self.log(f"✅ Thiết lập ChromeDriver thành công", "#a6e22e")
            return final_driver_path
            
        except Exception as e:
            self.log(f"❌ Lỗi khi thiết lập ChromeDriver: {e}", "#f92672")
            raise

    def handle_popups(self, driver):
        """Xử lý các popup/quảng cáo có thể che phủ nút"""
        try:
            # Danh sách các selector popup thường gặp trên IOE
            popup_selectors = [
                "div[class*='popup']",
                "div[class*='modal']", 
                "div[class*='overlay']",
                "div[id*='popup']",
                "div[id*='modal']",
                "button[class*='close']",
                "span[class*='close']",
                "a[class*='close']"
            ]
            
            for selector in popup_selectors:
                try:
                    popups = driver.find_elements(By.CSS_SELECTOR, selector)
                    for popup in popups:
                        if popup.is_displayed():
                            driver.execute_script("arguments[0].style.display = 'none';", popup)
                            self.log("🚫 Đã ẩn popup", "#66d9ef")
                except:
                    continue
                    
        except Exception as e:
            self.log(f"⚠️ Không thể xử lý popup: {str(e)}", "#fd971f")

    def get_link_with_retry(self, driver, i, max_retries=3):
        """Lấy link với cơ chế retry"""
        for attempt in range(max_retries):
            try:
                self.log(f"🔄 Thử lấy link bài {i}, lần {attempt + 1}", "#fd971f")
                
                link = self.get_link(driver, i)
                
                if link and "ioe.vn" in link:
                    return link
                else:
                    self.log(f"🔄 Thử lại lấy link bài {i}, lần {attempt + 2}", "#fd971f")
                    time.sleep(3)  # Chờ lâu hơn giữa các lần thử
                    
            except Exception as e:
                self.log(f"❌ Lỗi lần {attempt + 1}: {str(e)}", "#f92672")
                time.sleep(3)
        
        return ""

    def audio_to_text(self, url: str) -> str:
        self.log(f"[Audio] Đang chuyển audio sang text: {url}", "#66d9ef")
        config = aai.TranscriptionConfig(speech_model=aai.SpeechModel.universal)
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(url)
        while transcript.status in ["queued", "processing"] and self._is_running:
            time.sleep(1)
            transcript = transcriber.get_transcript(transcript.id)
        if transcript.status == "error":
            raise RuntimeError(f"Transcription failed: {transcript.error}")
        text = transcript.text.strip().lower()
        text = re.sub(r'[^\w\s]', '', text)
        self.log(f"[Audio] Transcript: {text}", "#66d9ef")
        return text

    def fill_mask_with_gemini(self, masked_sentence: str, audio_transcript: str = "") -> str:
        cached_answer, confirmed = self.question_db.get_answer(masked_sentence, 2)
        if cached_answer and confirmed:
            self.log(f"💾 Sử dụng đáp án đã lưu: {cached_answer}", "#a6e22e")
            return cached_answer
        
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception:
            self.log("⚠️ Không thể khởi tạo Gemini Client.", "#fd971f")
            return ""

        system_prompt, user_prompt = "", ""
        if audio_transcript:
            system_prompt = (
                "You are a helpful English assistant. Fill in the missing word(s) base on the transcript"
                "Only return the single word for the first blank. Only return the characters being hide by '*', don't return along with prefix or suffix"
                "For example if the transcript is: 'Politicians are powerful people' and the orignial sentence is: 'Poli******* are powerful people', so you need to return 'ticians'"
                "Remember, the length of your answer must be exactly the same with the number of '*' characters"
            )
            user_prompt = (
                f"Original sentence: \"{masked_sentence}\"\n"
                f"Transcript: \"{audio_transcript}\""
            )
        else:
            system_prompt = (
                "You are a helpful English assistant. Guess and fill in the missing word(s). "
                "Only return the single word for the first blank. Only return the characters being hide by '*', don't return along with prefix or suffix"
                "For example if the sentence is 'Urbanisation leads to the shift of the working population from agr******** to industries.', your answer is 'agriculture', however, only return 'iculture' since 'agr' is already filled"
                "Notice: the return answer must have the same length with the number of character '*'. For example, 'FUN*TION' and the correct word is 'FUNCTION', so that you just need to return 'C'"
                "One more example: 'Please use a reusable co******* to avoid plastic waste', only return 'ntainer'"
                "Remember, the length of your answer must be exactly the same with the number of '*' characters"
            )
            user_prompt = f"Sentence: \"{masked_sentence}\""
        try:
            self.log(f"[Gemini] Gửi request: {masked_sentence} | transcript: {audio_transcript}", "#ae81ff")
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[system_prompt, user_prompt],
            )
            ans = response.text.strip().lower()
            self.log(f"[Gemini] Đáp án nhận được: {ans}", "#ae81ff")
            
            self.question_db.add_question(masked_sentence, ans, 2, confirmed_correct=False)
            
            return ans
        except Exception as e:
            self.log(f"[Gemini] Lỗi: {e}", "#f92672")
        self.log(f"Đang thử gửi lại", "#f92672")
        time.sleep(1)
        self.log(f"[Gemini] Gửi request: {masked_sentence} | transcript: {audio_transcript}", "#ae81ff")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[system_prompt, user_prompt],
        )
        ans = response.text.strip().lower()
        self.log(f"[Gemini] Đáp án nhận được: {ans}", "#ae81ff")
        
        self.question_db.add_question(masked_sentence, ans, 2, confirmed_correct=False)
        
        return ans

    def fill_from_audio(self, masked_sentence: str, audio_transcript: str) -> str:
        self.log(f"[Transcript]:{masked_sentence}")
        self.log(f"[Audio] Điền từ dựa vào transcript: {audio_transcript}", "#66d9ef")
        return self.fill_mask_with_gemini(masked_sentence, audio_transcript)

    def get_audio_url_from_question(self, q: dict) -> str | None:
        description_content = q.get("Description", {}).get("content")
        if description_content and isinstance(description_content, str) and (
                description_content.endswith(".mp3") or "audio" in description_content.lower()):
            return description_content
        for key in ["audio", "audioUrl", "soundUrl", "file_audio"]:
            if q.get(key):
                return q[key]
        return None

    def get_token_from_url(self, url: str) -> str:
        try:
            q = parse_qs(urlparse(url).query)
            return q.get("token", [None])[0]
        except Exception:
            return None

    def post_json(self, path: str, payload: dict) -> dict:
        url = f"{BASE}/{path}"
        r = requests.post(url, json=payload, timeout=15)
        try:
            return r.json()
        except:
            return {"raw": r.text, "status": r.status_code}

    def get_info(self, token: str) -> dict:
        payload = {"IPClient": "", "api_key": "gameioe", "deviceId": "",
                   "serviceCode": "IOE", "token": token}
        return self.post_json("getinfo", payload)

    def start_game(self, token: str, examKey: str) -> dict:
        payload = {"api_key": "gameioe", "serviceCode": "IOE", "token": token,
                   "gameId": 0, "examKey": examKey, "deviceId": "", "IPClient": ""}
        return self.post_json("startgame", payload)

    def answer_check(self, token: str, examKey: str, questId: int, point: int, ans_value: str) -> dict:
        payload = {"api_key": "gameioe", "serviceCode": "IOE", "token": token,
                   "examKey": examKey, "ans": {"questId": questId, "point": point, "ans": ans_value},
                   "IPClient": "", "deviceId": ""}
        return self.post_json("answercheck", payload)

    def finish_game(self, token: str, examKey: str, answers: list) -> dict:
        payload = {"api_key": "gameioe", "token": token, "serviceCode": "IOE",
                   "examKey": examKey, "ans": answers, "IPClient": "", "deviceId": ""}
        return requests.post(f"{BASE}/finishgame", json=payload, timeout=15).json()

    def join_order_true(self, arr):
        return " ".join([x.get("content", "") for x in sorted(arr, key=lambda a: a.get("orderTrue", 0))])

    def pipe_order_true(self, arr):
        sorted_arr = sorted(arr, key=lambda a: a.get("orderTrue", 0))
        if len(sorted_arr) > 10:
            sorted_arr = sorted_arr[:-1]
        return "|".join([x.get("content", "") for x in sorted_arr if x.get("content")])

    def pair_text_image(self, q):
        t = q.get("content", {}).get("content", "")
        img = q.get("ans", [{}])[0].get("content", "")
        return f"{t}|{img}"

    def build_bank(self, info):
        return [x.get("ans", "").lower() for x in (info.get("data", {}).get("game", {}).get("ans") or []) if
                x.get("ans")]

    def enhanced_build_bank(self, info):
        word_bank = []
        game_ans = info.get("data", {}).get("game", {}).get("ans") or []
        for x in game_ans:
            if x.get("ans"):
                word = x.get("ans", "").lower().strip()
                if word and word not in word_bank:
                    word_bank.append(word)
        
        questions = info.get("data", {}).get("game", {}).get("question") or []
        for q in questions:
            if q.get("type") == 2:
                ans_list = q.get("ans", [])
                for ans_item in ans_list:
                    content = ans_item.get("content", "").lower().strip()
                    if content and content not in word_bank:
                        word_bank.append(content)
        
        self.log(f"📚 Danh sách từ cần điền ({len(word_bank)} từ): {word_bank}", "#66d9ef")
        return word_bank
    
    def run_automation(self, link: str, delay: float = 0.6):
        if not self._is_running: return

        token = self.get_token_from_url(link)
        if not token:
            self.log("❌ Không tìm thấy token.", "#f92672")
            return

        info = self.get_info(token)

        if not info.get("IsSuccessed"):
            self.log(f"❌ getinfo fail: {info}", "#f92672")
            return
        self.current_tokenrq = info["data"]["token"]
        self.current_examKey = info["data"]["game"]["examKey"]
        questions = info["data"]["game"]["question"] or []
        self.log(f"✅ Có {len(questions)} câu hỏi.", "#a6e22e")
        sres = self.start_game(self.current_tokenrq, self.current_examKey)
        if not sres.get("IsSuccessed"):
            self.log(f"❌ startgame fail: {sres}", "#f92672")
            return

        word_bank = self.enhanced_build_bank(info)

        answers, TF = [], ["True", "False"]
        cnt = 0
        for idx, q in enumerate(questions):
            if not self._is_running: return

            cnt += 1
            qid, qtype, point = q["id"], q.get("type"), q.get("Point", 10)
            masked_raw = q.get("content", {}).get("content", "")
            self.log(f"Câu: {cnt}", "#f8f8f2")
            self.log(f"Câu hỏi: {masked_raw}", "#f8f8f2")
            self.log(f"Loại câu: {qtype}")
            numTChar = q.get("numTChar", 0)

            progress = int((idx + 1) / len(questions) * 100)
            self.progress_signal.emit(progress)

            chosen, transcript = "", ""
            
            # THÊM: Kiểm tra database trước khi xử lý
            cached_answer, confirmed = self.question_db.get_answer(masked_raw, qtype)
            if cached_answer and confirmed:
                self.log(f"💾 Sử dụng đáp án đã lưu: {cached_answer}", "#a6e22e")
                chosen = cached_answer
                # THÊM: Kiểm tra đáp án từ database
                time.sleep(delay)
                resp = self.answer_check(self.current_tokenrq, self.current_examKey, qid, point, chosen)
                dp = resp.get("data", {}).get("point", 0)
                
                if dp >= point:
                    self.log(f"✅ Đáp án từ database chính xác!", "#a6e22e")
                else:
                    self.log(f"❌ Đáp án từ database không chính xác, tìm đáp án mới...", "#f92672")
                    chosen = ""  # Reset để tìm đáp án mới
            
            if not chosen:
                if qtype == 5:
                    chosen = "|".join(list(self.join_order_true(q.get("ans", []))))

                elif qtype == 7:
                    chosen = self.pair_text_image(q)

                elif qtype == 3:
                    chosen = self.pipe_order_true(q.get("ans", []))
                    if (masked_raw == "She didn't take an umbrella so she got wet."): chosen = "because|she"

                elif qtype == 2:
                    audio_url = self.get_audio_url_from_question(q)
                    chosen = masked_raw
                    if audio_url:
                        try:
                            transcript = self.audio_to_text(audio_url)
                            chosen = self.fill_from_audio(masked_raw, transcript)
                        except Exception as e:
                            self.log(f"[Audio] Lỗi: {e}", "#f92672")
                    else:
                        if (len(word_bank) >= len(questions)):
                            self.log(f"🔍 Tìm từ cho type 2 với {numTChar} ký tự", "#66d9ef")
                            
                            suitable_words = [word for word in word_bank if len(word) == numTChar]
                            self.log(f"📋 Từ phù hợp ({numTChar} ký tự): {suitable_words}", "#66d9ef")
                            
                            found = False
                            for word in suitable_words:
                                if not self._is_running: return
                                
                                self.log(f"[AnswerCheck] Thử từ: '{word}'", "#fd971f")
                                time.sleep(delay)
                                
                                resp = self.answer_check(self.current_tokenrq, self.current_examKey, qid, point, word)
                                dp = resp.get("data", {}).get("point", 0)
                                
                                if dp >= point:
                                    chosen = word
                                    self.log(f"✅ Tìm thấy đáp án đúng: '{chosen}'", "#a6e22e")
                                    # THÊM: Lưu câu hỏi và đáp án đã xác nhận
                                    self.question_db.confirm_answer(masked_raw, chosen)
                                    found = True
                                    break
                                else:
                                    self.log(f"❌ Từ '{word}' không đúng", "#f92672")
                            
                            if not found and word_bank:
                                self.log("🔄 Không tìm thấy từ phù hợp, thử tất cả các từ...", "#fd971f")
                                for word in word_bank:
                                    if not self._is_running: return
                                    
                                    if word in suitable_words:
                                        continue
                                        
                                    self.log(f"[AnswerCheck] Thử từ: '{word}'", "#fd971f")
                                    time.sleep(delay)
                                    
                                    resp = self.answer_check(self.current_tokenrq, self.current_examKey, qid, point, word)
                                    dp = resp.get("data", {}).get("point", 0)
                                    
                                    if dp >= point:
                                        chosen = word
                                        self.log(f"✅ Tìm thấy đáp án đúng: '{chosen}'", "#a6e22e")
                                        # THÊM: Lưu câu hỏi và đáp án đã xác nhận
                                        self.question_db.confirm_answer(masked_raw, chosen)
                                        found = True
                                        break
                        else:
                        # if not found and not chosen and masked_raw and not self.is_audio_url(masked_raw):
                            self.log("🤖 Sử dụng Gemini...", "#fd971f")
                            gemini_answer = self.fill_mask_with_gemini(masked_raw)
                            if gemini_answer:
                                self.log(f"[Gemini] Đề xuất: {gemini_answer}", "#ae81ff")
                                
                                time.sleep(delay)
                                resp = self.answer_check(self.current_tokenrq, self.current_examKey, qid, point, gemini_answer)
                                chosen = gemini_answer
                                dp = resp.get("data", {}).get("point", 0)
                                
                                # THÊM: Nếu đáp án từ Gemini đúng, xác nhận và lưu
                                if dp >= point:
                                    self.question_db.confirm_answer(masked_raw, chosen)

                elif qtype == 8:
                    chosen = self.fill_mask_with_gemini(masked_raw)

                elif qtype in (1, 10):
                    opts = [o.get("content") for o in (q.get("ans") or []) if o.get("content")]
                    candidates = opts if opts else TF
                    for cand in candidates:
                        if not self._is_running:
                            return
                        self.log(f"[AnswerCheck] Thử đáp án: {cand}", "#fd971f")
                        time.sleep(delay)
                        resp = self.answer_check(self.current_tokenrq, self.current_examKey, qid, point, cand)
                        dp = resp.get("data", {}).get("point", 0)
                        if dp >= point:
                            chosen = cand
                            # THÊM: Lưu câu hỏi và đáp án đã xác nhận
                            self.question_db.confirm_answer(masked_raw, chosen)
                            break

            self.log(f"➡️ Đáp án: {chosen}", "#a6e22e")
            answers.append({"questId": qid, "ans": chosen, "Point": point})

        self.current_answers = [a for a in answers if a.get("ans")]
        self.log("\n📤 Đang chờ nộp bài", "#f8f8f2")

        wait_time = randint(self.finish_delay_min, self.finish_delay_max)
        for remaining in range(wait_time, 0, -1):
            if not self._is_running:
                return
            if self._submit_now:
                self.log("🚀 Người dùng yêu cầu nộp bài ngay!", "#a6e22e")
                self._submit_now = False
                break
            self.countdown_signal.emit(remaining)
            time.sleep(1)

        self.countdown_signal.emit(0)
        self.submit_current_answers()

    def submit_current_answers(self):
        if self.current_tokenrq and self.current_examKey and self.current_answers:
            fin = self.finish_game(self.current_tokenrq, self.current_examKey, self.current_answers)
            self.log(f"🎯 Kết quả: {fin.get('data', {})}", "#a6e22e")
            self.current_answers = []
            self.current_tokenrq = None
            self.current_examKey = None

    def login(self, driver):
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, username_xpath)))
            driver.find_element(By.XPATH, username_xpath).send_keys(self.username)
            driver.find_element(By.XPATH, password_xpath).send_keys(self.password)
            driver.find_element(By.XPATH, enter_xpath).send_keys(Keys.RETURN)
            time.sleep(2)
            return True
        except TimeoutException:
            self.log("❌ Lỗi đăng nhập: Không tìm thấy trường nhập liệu", "#f92672")
            return False

    def get_link(self, driver, i):
        try:
            # Xử lý popup trước khi click
            self.handle_popups(driver)
            
            # Chờ element có thể click được với timeout dài hơn
            btn_element = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, btn[i]))
            )
            
            # Scroll element vào viewport một cách an toàn
            driver.execute_script("""
                arguments[0].scrollIntoView({
                    behavior: 'smooth',
                    block: 'center',
                    inline: 'center'
                });
            """, btn_element)
            
            # Chờ một chút để animation hoàn tất
            time.sleep(2)
            
            # Thử click bằng JavaScript (tránh interception)
            driver.execute_script("arguments[0].click();", btn_element)
            
            # Chờ URL thay đổi với timeout dài hơn
            WebDriverWait(driver, 20).until(
                lambda d: d.current_url != "https://ioe.vn/tu-luyen" and "ioe.vn" in d.current_url
            )
            
            link = driver.current_url
            
            # Quay lại trang chính
            driver.back()
            
            # Chờ trang load lại hoàn toàn
            WebDriverWait(driver, 20).until(
                lambda d: d.current_url == "https://ioe.vn/tu-luyen"
            )
            
            # Thêm delay để đảm bảo trang ổn định
            time.sleep(3)
            
            self.log(f"✅ Lấy link bài {i} thành công: {link}", "#a6e22e")
            return link
            
        except TimeoutException:
            self.log(f"⚠️ Timeout: Không tìm thấy bài số {i} sau 20 giây", "#fd971f")
            return ""
        except Exception as e:
            self.log(f"❌ Lỗi khi lấy link bài {i}: {str(e)}", "#f92672")
            return ""

    def submit_task(self, driver):
        try:
            btn_next_search = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, btn_next)))
            btn_next_search.click()
            btn_confirm_search = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, btn_confirm)))
            btn_confirm_search.click()
            btn_close_search = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, close)))
            btn_close_search.click()
            return True
        except:
            return False

    def reset_task(self, driver):
        try:
            btn_remake_search = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, btn_remake)))
            btn_remake_search.click()
            btn_confirm_search = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, btn_confirm)))
            btn_confirm_search.click()
            btn_close_search = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, close)))
            btn_close_search.click()
            return True
        except:
            return False

    def get_point(self, driver):
        try:
            mark_search = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, mark)))
            return int(mark_search.text)
        except:
            return 0

    def run(self):
        try:
            self.log("🔍 Đang kiểm tra ChromeDriver...", "#66d9ef")
            final_driver_path = self.setup_chrome_driver()
            
            service = Service(executable_path=final_driver_path)
            options = Options()
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--disable-popup-blocking')
            options.add_argument('--disable-notifications')
            options.add_argument('--disable-extensions')
            options.add_argument('--no-first-run')
            options.add_argument('--no-default-browser-check')
            options.add_argument('--disable-translate')
            options.add_argument('--disable-infobars')
            options.add_argument('--window-size=1920,1080')
            
            driver = webdriver.Chrome(service=service, options=options)

            driver.get("https://ioe.vn/tu-luyen")

            if not self.login(driver):
                self.finished_signal.emit(False)
                return

            self.log("✅ Đăng nhập thành công!", "#a6e22e")
            driver.get("https://ioe.vn/tu-luyen")

            for current_round in range(self.total_rounds):
                if not self._is_running: break

                self.round_progress_signal.emit(current_round + 1, self.total_rounds)

                driver.refresh()
                self.log(f"\n🎯 Vòng {current_round + 1}/{self.total_rounds}", "#a6e22e")

                for i in range(4):
                    if not self._is_running: break

                    self.log(f"🔍 Đang tìm bài số: {i+1}", "#f8f8f2")
                    
                    # Refresh và chờ trang load
                    driver.refresh()
                    WebDriverWait(driver, 15).until(
                        lambda d: d.current_url == "https://ioe.vn/tu-luyen"
                    )
                    time.sleep(3)  # Chờ thêm để trang ổn định

                    # Sử dụng hàm get_link_with_retry mới
                    link = self.get_link_with_retry(driver, i, max_retries=3)
                    
                    if link and "ioe.vn" in link:
                        self.log(f"📝 Đã tìm thấy bài số: {i+1}", "#a6e22e")
                        self.log(f"🔗 Link: {link}", "#66d9ef")
                        self.run_automation(link, delay=0.8)  # Tăng delay lên 0.8
                    else:
                        self.log(f"⏭️ Bài số {i} không có hoặc không truy cập được sau 3 lần thử", "#fd971f")

                if not self._is_running:
                    break

                driver.refresh()
                time.sleep(2)
                current_point = self.get_point(driver)
                self.log(f"📊 Điểm hiện tại: {current_point}", "#f8f8f2")

                if current_point >= self.min_score:
                    cnt = 0
                    while cnt < 2:
                        driver.refresh()
                        if self.submit_task(driver):
                            self.log("✅ Đã nộp bài", "#a6e22e")
                            break
                        else:
                            cnt += 1
                            self.log(f"🔄 Thử nộp bài lần {cnt}", "#fd971f")
                            
                    if cnt >= 2:
                        self.log("❌ Không tự nộp bài được, hãy thực hiện thủ công", "#f92672")
                else:
                    cnt = 0
                    while cnt < 2:
                        driver.refresh()
                        if self.reset_task(driver):
                            self.log("🔄 Đã làm lại bài", "#a6e22e")
                            break
                        else:
                            cnt += 1
                            self.log(f"🔄 Thử làm lại bài lần {cnt}", "#fd971f")
                            
                    if cnt >= 2:
                        self.log("❌ Không tự tải lại bài được, hãy thực hiện thủ công", "#f92672")

            driver.quit()
            self.log("✅ Hoàn thành tất cả vòng!", "#a6e22e")
            self.finished_signal.emit(True)

        except Exception as e:
            self.log(f"❌ Lỗi nghiêm trọng: {str(e)}", "#f92672")
            self.finished_signal.emit(False)


class IOEAutomationUI(QWidget):
    automation_completed = pyqtSignal(bool)
    def __init__(self):
        super().__init__()
        self.worker = None
        self.settings_visible = True
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 15, 20, 15)

        header_layout = QHBoxLayout()

        self.title_label = QLabel("IOE Automation Tool")
        self.title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #a6e22e; padding: 5px;")

        self.toggle_settings_button = QPushButton("▲ Thu nhỏ")
        self.toggle_settings_button.setFont(QFont("Segoe UI", 10))
        self.toggle_settings_button.setMinimumHeight(30)
        self.toggle_settings_button.setMaximumWidth(100)
        self.toggle_settings_button.clicked.connect(self.toggle_settings_visibility)

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.toggle_settings_button)

        layout.addLayout(header_layout)

        self.input_group = QGroupBox("Thông tin đăng nhập")
        self.input_group.setFont(QFont("Segoe UI", 12))
        input_layout = QVBoxLayout(self.input_group)
        input_layout.setSpacing(8)

        username_layout = QHBoxLayout()
        username_label = QLabel("Tên đăng nhập:")
        username_label.setFont(QFont("Segoe UI", 12))
        username_layout.addWidget(username_label)
        self.username_input = QLineEdit()
        self.username_input.setFont(QFont("Segoe UI", 12))
        self.username_input.setPlaceholderText("Nhập username tài khoản IOE")
        self.username_input.setMinimumHeight(32)
        username_layout.addWidget(self.username_input)
        input_layout.addLayout(username_layout)

        password_layout = QHBoxLayout()
        password_label = QLabel("Mật khẩu:")
        password_label.setFont(QFont("Segoe UI", 12))
        password_layout.addWidget(password_label)
        self.password_input = QLineEdit()
        self.password_input.setFont(QFont("Segoe UI", 12))
        self.password_input.setPlaceholderText("Nhập mật khẩu tài khoản IOE")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setMinimumHeight(32)
        password_layout.addWidget(self.password_input)
        input_layout.addLayout(password_layout)

        self.settings_group = QGroupBox("Cài đặt tự động hóa")
        self.settings_group.setFont(QFont("Segoe UI", 12))
        settings_layout = QVBoxLayout(self.settings_group)
        settings_layout.setSpacing(10)

        score_layout = QHBoxLayout()
        score_label = QLabel("Điểm tối thiểu:")
        score_label.setFont(QFont("Segoe UI", 12))
        score_layout.addWidget(score_label)
        self.min_score_input = QSpinBox()
        self.min_score_input.setFont(QFont("Segoe UI", 12))
        self.min_score_input.setRange(270, 360)
        self.min_score_input.setValue(300)
        self.min_score_input.setSuffix(" điểm")
        self.min_score_input.setMinimumHeight(32)
        score_layout.addWidget(self.min_score_input)
        score_layout.addStretch()
        settings_layout.addLayout(score_layout)

        rounds_layout = QHBoxLayout()
        rounds_label = QLabel("Số vòng luyện tập:")
        rounds_label.setFont(QFont("Segoe UI", 12))
        rounds_layout.addWidget(rounds_label)
        self.rounds_input = QSpinBox()
        self.rounds_input.setFont(QFont("Segoe UI", 12))
        self.rounds_input.setRange(1, 50)
        self.rounds_input.setValue(8)
        self.rounds_input.setSuffix(" vòng")
        self.rounds_input.setMinimumHeight(32)
        rounds_layout.addWidget(self.rounds_input)
        rounds_layout.addStretch()
        settings_layout.addLayout(rounds_layout)

        delay_layout = QHBoxLayout()
        delay_label = QLabel("Thời gian chờ ngẫu nhiên:")
        delay_label.setFont(QFont("Segoe UI", 12))
        delay_layout.addWidget(delay_label)

        delay_min_layout = QVBoxLayout()
        delay_min_label = QLabel("Tối thiểu")
        delay_min_label.setFont(QFont("Segoe UI", 11))
        delay_min_layout.addWidget(delay_min_label)
        self.delay_min_input = QSpinBox()
        self.delay_min_input.setFont(QFont("Segoe UI", 12))
        self.delay_min_input.setRange(10, 300)
        self.delay_min_input.setValue(90)
        self.delay_min_input.setSuffix("s")
        self.delay_min_input.setMinimumHeight(32)
        delay_min_layout.addWidget(self.delay_min_input)

        delay_max_layout = QVBoxLayout()
        delay_max_label = QLabel("Tối đa")
        delay_max_label.setFont(QFont("Segoe UI", 11))
        delay_max_layout.addWidget(delay_max_label)
        self.delay_max_input = QSpinBox()
        self.delay_max_input.setFont(QFont("Segoe UI", 12))
        self.delay_max_input.setRange(10, 300)
        self.delay_max_input.setValue(120)
        self.delay_max_input.setSuffix("s")
        self.delay_max_input.setMinimumHeight(32)
        delay_max_layout.addWidget(self.delay_max_input)

        delay_layout.addLayout(delay_min_layout)
        delay_layout.addLayout(delay_max_layout)
        delay_layout.addStretch()
        settings_layout.addLayout(delay_layout)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.start_button = QPushButton("Bắt đầu")
        self.start_button.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.start_button.clicked.connect(self.start_automation)
        self.start_button.setMinimumHeight(35)
        self.start_button.setMinimumWidth(120)

        self.stop_button = QPushButton("Dừng lại")
        self.stop_button.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.stop_button.clicked.connect(self.stop_automation)
        self.stop_button.setEnabled(False)
        self.stop_button.setMinimumHeight(35)
        self.stop_button.setMinimumWidth(120)

        self.submit_now_button = QPushButton("⏩ Nộp bài ngay")
        self.submit_now_button.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.submit_now_button.clicked.connect(self.submit_now)
        self.submit_now_button.setEnabled(False)
        self.submit_now_button.setMinimumHeight(35)
        self.submit_now_button.setMinimumWidth(120)

        button_layout.addStretch()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.submit_now_button)
        button_layout.addStretch()

        progress_group = QGroupBox("Tiến trình thực hiện")
        progress_group.setFont(QFont("Segoe UI", 12))
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setSpacing(8)

        self.round_label = QLabel("Vòng: 0/0")
        self.round_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.round_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFont(QFont("Segoe UI", 10))
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumHeight(18)

        self.countdown_label = QLabel("")
        self.countdown_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setVisible(False)

        progress_layout.addWidget(self.round_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.countdown_label)

        log_group = QGroupBox("Nhật ký hoạt động")
        log_group.setFont(QFont("Segoe UI", 12))
        log_layout = QVBoxLayout(log_group)

        self.log_output = QTextEdit()
        self.log_output.setFont(QFont("Consolas", 12))
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Nhật ký hoạt động sẽ hiển thị ở đây...")
        self.log_output.setMinimumHeight(180)
        
        self.log_output.setStyleSheet("""
            QTextEdit {
                background-color: #1e1f1c;
                color: #f8f8f2;
                border: 1px solid #414339;
                border-radius: 6px;
                padding: 6px;
                font-size: 18px;
            }
        """)
        
        log_layout.addWidget(self.log_output)

        layout.addWidget(self.input_group)
        layout.addWidget(self.settings_group)
        layout.addWidget(progress_group)
        layout.addLayout(button_layout)
        layout.addWidget(log_group)

        self.apply_dark_monokai_theme()

    def set_window_icon(self):
        try:
            if os.path.exists('logo.ico'):
                self.setWindowIcon(QIcon('logo.ico'))
                return
                
            icon_formats = ['logo.png', 'logo.jpg', 'icon.png', 'app.png']
            for icon_file in icon_formats:
                if os.path.exists(icon_file):
                    self.setWindowIcon(QIcon(icon_file))
                    return
        except Exception:
            pass

    def toggle_settings_visibility(self):
        self.settings_visible = not self.settings_visible
        
        if self.settings_visible:
            self.input_group.show()
            self.settings_group.show()
            self.toggle_settings_button.setText("▲ Thu nhỏ")
        else:
            self.input_group.hide()
            self.settings_group.hide()
            self.toggle_settings_button.setText("▼ Mở rộng")

    def apply_dark_monokai_theme(self):
        app = QApplication.instance()
        app.setPalette(ThemeManager.get_dark_monokai_theme())

        monokai_stylesheet = """
            QMainWindow {
                background-color: #272822;
            }
            QGroupBox {
                color: #f8f8f2;
                border: 2px solid #414339;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 12px;
                background-color: #2a2b24;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #a6e22e;
            }
            QPushButton {
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                opacity: 0.9;
            }
            QPushButton:disabled {
                opacity: 0.6;
            }
            QProgressBar {
                border: 1px solid #414339;
                border-radius: 8px;
                text-align: center;
                background-color: #2a2b24;
                color: #f8f8f2;
            }
            QProgressBar::chunk {
                background-color: #66d9ef;
                border-radius: 7px;
            }
            QTextEdit {
                background-color: #1e1f1c;
                color: #f8f8f2;
                border: 1px solid #414339;
                border-radius: 6px;
                padding: 6px;
                font-size: 18px;
            }
            QSpinBox, QLineEdit {
                background-color: #1e1f1c;
                color: #f8f8f2;
                border: 1px solid #414339;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QLabel {
                color: #f8f8f2;
            }
        """

        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #a6e22e;
                color: #272822;
            }
            QPushButton:hover {
                background-color: #b6f23e;
            }
            QPushButton:disabled {
                background-color: #75715e;
                color: #95979d;
            }
        """)

        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #f92672;
                color: #f8f8f2;
            }
            QPushButton:hover {
                background-color: #ff4080;
            }
            QPushButton:disabled {
                background-color: #75715e;
                color: #95979d;
            }
        """)

        self.submit_now_button.setStyleSheet("""
            QPushButton {
                background-color: #fd971f;
                color: #272822;
            }
            QPushButton:hover {
                background-color: #ffa94d;
            }
            QPushButton:disabled {
                background-color: #75715e;
                color: #95979d;
            }
        """)

        self.toggle_settings_button.setStyleSheet("""
            QPushButton {
                background-color: #66d9ef;
                color: #272822;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #76e9ff;
            }
        """)

        self.countdown_label.setStyleSheet(
            "color: #fd971f; padding: 6px; background-color: #414339; border-radius: 4px;")

        self.setStyleSheet(monokai_stylesheet)

    def log_message(self, message, color="#f8f8f2"):
        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        html_message = f'<span style="color: {color}; font-size: 18px;">[{time.strftime("%H:%M:%S")}] {message}</span>'
        
        self.log_output.textCursor().insertHtml(html_message + "<br>")
        
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_round_progress(self, current_round, total_rounds):
        self.round_label.setText(f"Vòng: {current_round}/{total_rounds}")
        overall_progress = int((current_round / total_rounds) * 100)
        self.progress_bar.setValue(overall_progress)

    def update_countdown(self, seconds):
        if seconds > 0:
            self.countdown_label.setText(f"Đang chờ nộp bài: {seconds} giây")
            self.countdown_label.setVisible(True)
        else:
            self.countdown_label.setVisible(False)

    def submit_now(self):
        if self.worker and self.worker.isRunning():
            self.worker.submit_now()
            self.log_message("🚀 Đã yêu cầu nộp bài ngay!", "#fd971f")

    def start_automation(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập username và password!")
            return

        self.username_input.setEnabled(False)
        self.password_input.setEnabled(False)
        self.min_score_input.setEnabled(False)
        self.rounds_input.setEnabled(False)
        self.delay_min_input.setEnabled(False)
        self.delay_max_input.setEnabled(False)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.submit_now_button.setEnabled(True)
        self.toggle_settings_button.setEnabled(False)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.round_label.setText(f"Vòng: 0/{self.rounds_input.value()}")

        self.log_output.clear()

        self.worker = IOEWorker(
            username=username,
            password=password,
            min_score=self.min_score_input.value(),
            finish_delay_min=self.delay_min_input.value(),
            finish_delay_max=self.delay_max_input.value(),
            total_rounds=self.rounds_input.value()
        )

        self.worker.log_signal.connect(self.log_message)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.round_progress_signal.connect(self.update_round_progress)
        self.worker.countdown_signal.connect(self.update_countdown)
        self.worker.finished_signal.connect(self.automation_finished)
        self.worker.submit_now_signal.connect(self.submit_now)

        self.worker.start()

    def stop_automation(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(5000)
            self.log_message("⏹️ Đã dừng automation", "#fd971f")

    def automation_finished(self, success):
        self.username_input.setEnabled(True)
        self.password_input.setEnabled(True)
        self.min_score_input.setEnabled(True)
        self.rounds_input.setEnabled(True)
        self.delay_min_input.setEnabled(True)
        self.delay_max_input.setEnabled(True)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.submit_now_button.setEnabled(False)
        self.toggle_settings_button.setEnabled(True)

        self.progress_bar.setVisible(False)
        self.countdown_label.setVisible(False)

        if success:
            self.log_message("✅ Automation hoàn thành!", "#a6e22e")
            # THÊM: Phát signal thông báo hoàn thành
            self.automation_completed.emit(True)
        else:
            self.log_message("❌ Automation kết thúc với lỗi!", "#f92672")
            # THÊM: Phát signal thông báo lỗi
            self.automation_completed.emit(False)

        self.worker = None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IOE Tool - Quản lý tài khoản & Tự động hóa")
        self.setGeometry(100, 100, 1400, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        self.tabs = QTabWidget()
        
        # Truyền tham chiếu đến main_window cho account_manager_ui
        self.account_manager_ui = IOEAccountManagerUI(main_window=self)
        self.automation_ui = IOEAutomationUI()
        
        self.tabs.addTab(self.account_manager_ui, "📊 Quản lý tài khoản")
        self.tabs.addTab(self.automation_ui, "🤖 Tự động hóa IOE")
        
        layout.addWidget(self.tabs)
        
        # KẾT NỐI SIGNAL TỪ AUTOMATION_UI ĐẾN ACCOUNT_MANAGER_UI
        self.automation_ui.automation_completed.connect(self.on_automation_completed)
    
    def on_automation_completed(self, success):
        """Callback khi automation hoàn thành"""
        self.current_automation_complete = True
        self.waiting_for_completion = False
        if not success: print("⚠️ Automation hoàn thành với trạng thái lỗi")


def main():
    app = QApplication(sys.argv)

    app.setApplicationName("IOE Tool")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("IOE Assistant")
    app.setWindowIcon(QIcon("logo.ico"))
    
    app.setFont(QFont("Consolas", 11))

    window = MainWindow()
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()