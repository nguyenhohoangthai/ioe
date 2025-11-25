import sys
import sqlite3
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHBoxLayout, QMessageBox, QLineEdit, QLabel, QFormLayout,
    QDialog, QComboBox, QCheckBox
)
from PyQt6.QtCore import Qt

DB_PATH = "ioe_questions.db"


class DBManager:
    def __init__(self, db_path=DB_PATH):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def get_all(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM questions ORDER BY id")
        return cur.fetchall()

    def add_question(self, data):
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO questions (question_text, question_hash, answer, question_type, confirmed_correct)
            VALUES (?, ?, ?, ?, ?)
            """,
            data,
        )
        self.conn.commit()

    def update_question(self, qid, data):
        cur = self.conn.cursor()
        cur.execute(
            """
            UPDATE questions
            SET question_text = ?, question_hash = ?, answer = ?, question_type = ?, confirmed_correct = ?
            WHERE id = ?
            """,
            (*data, qid),
        )
        self.conn.commit()

    def delete_question(self, qid):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM questions WHERE id = ?", (qid,))
        self.conn.commit()


class EditDialog(QDialog):
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.setWindowTitle("Chỉnh sửa câu hỏi")

        layout = QFormLayout(self)

        self.text = QLineEdit(data["question_text"])
        self.hash = QLineEdit(data["question_hash"])
        self.answer = QLineEdit(data["answer"])

        self.type_box = QComboBox()
        self.type_box.addItems(["0", "1", "2", "3", "4"])
        self.type_box.setCurrentText(str(data["question_type"]))

        self.confirmed = QCheckBox()
        self.confirmed.setChecked(bool(data["confirmed_correct"]))

        layout.addRow("Question:", self.text)
        layout.addRow("Hash:", self.hash)
        layout.addRow("Answer:", self.answer)
        layout.addRow("Type:", self.type_box)
        layout.addRow("Confirmed Correct:", self.confirmed)

        btn_save = QPushButton("Lưu")
        btn_save.clicked.connect(self.accept)
        layout.addWidget(btn_save)

    def get_data(self):
        return (
            self.text.text(),
            self.hash.text(),
            self.answer.text(),
            int(self.type_box.currentText()),
            1 if self.confirmed.isChecked() else 0,
        )


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Quản lý Database IOE - PyQt6")
        self.db = DBManager()

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        layout.addWidget(self.table)

        btns = QHBoxLayout()
        self.btn_reload = QPushButton("Tải lại")
        self.btn_edit = QPushButton("Sửa")
        self.btn_delete = QPushButton("Xoá")

        btns.addWidget(self.btn_reload)
        btns.addWidget(self.btn_edit)
        btns.addWidget(self.btn_delete)
        layout.addLayout(btns)

        self.btn_reload.clicked.connect(self.load_data)
        self.btn_edit.clicked.connect(self.edit_row)
        self.btn_delete.clicked.connect(self.delete_row)

        self.load_data()

    def load_data(self):
        rows = self.db.get_all()
        self.table.setRowCount(len(rows))
        self.table.setColumnCount(len(rows[0]) if rows else 0)
        self.table.setHorizontalHeaderLabels(rows[0].keys() if rows else [])

        for i, row in enumerate(rows):
            for j, key in enumerate(row.keys()):
                self.table.setItem(i, j, QTableWidgetItem(str(row[key])))

    def get_selected_id(self):
        selected = self.table.currentRow()
        if selected < 0:
            return None
        return int(self.table.item(selected, 0).text())

    def edit_row(self):
        qid = self.get_selected_id()
        if qid is None:
            QMessageBox.warning(self, "Lỗi", "Hãy chọn 1 dòng!")
            return

        cur = self.db.conn.cursor()
        cur.execute("SELECT * FROM questions WHERE id = ?", (qid,))
        data = cur.fetchone()

        dialog = EditDialog(self, data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.get_data()
            self.db.update_question(qid, new_data)
            self.load_data()

    def delete_row(self):
        qid = self.get_selected_id()
        if qid is None:
            QMessageBox.warning(self, "Lỗi", "Hãy chọn 1 dòng!")
            return

        confirm = QMessageBox.question(
            self,
            "Xác nhận",
            f"Bạn có chắc muốn xoá ID {qid}?",
        )

        if confirm == QMessageBox.StandardButton.Yes:
            self.db.delete_question(qid)
            self.load_data()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(900, 500)
    win.show()
    sys.exit(app.exec())