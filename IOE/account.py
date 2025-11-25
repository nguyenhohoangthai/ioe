import sys
import sqlite3
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QLineEdit, QPushButton, QHBoxLayout, QGridLayout, QMessageBox
)

DB_PATH = "ioe_accounts.db"   # ĐƯỜNG DẪN TỚI DATABASE


class AccountManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Account Manager - PyQt6")
        self.resize(1000, 650)

        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()

        # Lấy danh sách cột động
        self.cursor.execute("PRAGMA table_info(accounts)")
        self.columns = [row[1] for row in self.cursor.fetchall()]

        # Layout chính
        layout = QVBoxLayout(self)

        # ----- BẢNG HIỂN THỊ -----
        self.table = QTableWidget()
        layout.addWidget(self.table)

        # ----- FORM NHẬP LIỆU -----
        form = QGridLayout()
        self.inputs = {}  # map column -> QLineEdit

        for i, col in enumerate(self.columns):
            label = QLabel(col)
            edit = QLineEdit()
            self.inputs[col] = edit
            form.addWidget(label, i, 0)
            form.addWidget(edit, i, 1)

        layout.addLayout(form)

        # ----- NÚT -----
        btn_row = QHBoxLayout()

        self.btn_add = QPushButton("Thêm mới")
        self.btn_update = QPushButton("Cập nhật")
        self.btn_delete = QPushButton("Xóa")

        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_update)
        btn_row.addWidget(self.btn_delete)

        layout.addLayout(btn_row)

        # Sự kiện
        self.btn_add.clicked.connect(self.add_record)
        self.btn_update.clicked.connect(self.update_record)
        self.btn_delete.clicked.connect(self.delete_record)
        self.table.cellClicked.connect(self.load_to_form)

        # Load dữ liệu
        self.load_data()

    # ---------------------- LOAD DỮ LIỆU ----------------------
    def load_data(self):
        self.cursor.execute("SELECT * FROM accounts")
        rows = self.cursor.fetchall()

        self.table.setRowCount(len(rows))
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)

        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem(str(value)))

    # ---------------------- LOAD DÒNG VÀO FORM ----------------------
    def load_to_form(self, row, col):
        for c, column in enumerate(self.columns):
            item = self.table.item(row, c)
            if item:
                self.inputs[column].setText(item.text())

    # ---------------------- THÊM TÀI KHOẢN ----------------------
    def add_record(self):
        values = []
        columns_no_id = self.columns.copy()

        # Cột ID để trống (autoincrement)
        if "id" in columns_no_id:
            columns_no_id.remove("id")

        for col in columns_no_id:
            values.append(self.inputs[col].text())

        fields = ", ".join(columns_no_id)
        placeholders = ", ".join(["?"] * len(columns_no_id))

        self.cursor.execute(
            f"INSERT INTO accounts({fields}) VALUES ({placeholders})",
            values
        )
        self.conn.commit()
        self.load_data()
        QMessageBox.information(self, "Success", "Đã thêm tài khoản!")

    # ---------------------- CẬP NHẬT TÀI KHOẢN ----------------------
    def update_record(self):
        if "id" not in self.columns:
            QMessageBox.warning(self, "Error", "Không có cột ID để cập nhật.")
            return

        acc_id = self.inputs["id"].text()
        if acc_id == "":
            QMessageBox.warning(self, "Error", "Bạn chưa chọn tài khoản.")
            return

        values = []
        update_fields = []
        for col in self.columns:
            if col == "id":
                continue
            update_fields.append(f"{col}=?")
            values.append(self.inputs[col].text())

        values.append(acc_id)

        self.cursor.execute(
            f"UPDATE accounts SET {', '.join(update_fields)} WHERE id=?",
            values
        )
        self.conn.commit()
        self.load_data()
        QMessageBox.information(self, "Success", "Đã cập nhật tài khoản!")

    # ---------------------- XÓA TÀI KHOẢN ----------------------
    def delete_record(self):
        acc_id = self.inputs["id"].text()

        if acc_id == "":
            QMessageBox.warning(self, "Error", "Chưa chọn tài khoản để xóa.")
            return

        confirm = QMessageBox.question(
            self,
            "Xác nhận",
            f"Bạn có chắc muốn xóa tài khoản ID = {acc_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm == QMessageBox.StandardButton.No:
            return

        self.cursor.execute("DELETE FROM accounts WHERE id=?", (acc_id,))
        self.conn.commit()
        self.load_data()
        QMessageBox.information(self, "Success", "Đã xóa tài khoản!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AccountManager()
    window.show()
    sys.exit(app.exec())
