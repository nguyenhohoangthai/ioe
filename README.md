# 📚 IOE TOOL
Công cụ hỗ trợ làm bài tập IOE một cách tự động và hiệu quả.

## Link hướng dẫn sử dụng
[https://facebook.com]

## 👤 Tác giả
Một học sinh tại Cần Thơ  
📩 **Liên hệ:**  
[nguyenhohoangthai0310@gmail.com]

---

## 🎯 Mục đích
- Tự động làm bài tập IOE  
- Hỗ trợ chạy nhiều tài khoản cùng lúc  
- Cho phép cộng đồng remix, tùy chỉnh và phát triển thành các phiên bản tốt hơn

---

## 🚀 Mục tiêu tương lai
Mình đã public toàn bộ source code để:
- Ai cũng có thể xem, cải tiến, tái sử dụng  
- Nếu bạn remix thành bản tốt hơn, vui lòng gửi lại cho mình qua email  
- App vẫn còn một vài lỗi khi:
  - Chạy nhiều tài khoản song song
  - Kết nối mạng yếu gây nghẽn  
→ Rất mong các bạn hỗ trợ fix và phát triển thêm

> Do API Key có thể bị giới hạn khi gửi quá nhiều request cùng lúc → có thể xử lý bằng cách:
>- Sinh nhiều API Key
> - Hoặc chuyển sang AI Local như **Ollama**

---

## 🧠 Một chút thú vị
App được viết:
- 40% bằng ChatGPT  
- 40% bằng DeepSeek  
- 10% Gemini  
- 10% chính tay mình  

Nên nếu bạn đem code lên cho AI sửa thì cũng rất dễ dàng 😆

---

## 📝 Tóm tắt phiên bản
- **Version 1 – Upload ngày 24/11/2025**
- Hỗ trợ đầy đủ các chức năng IOE cơ bản
- Giao diện PyQt6 trực quan
- Xử lý Selenium hoàn toàn tự động

---

# 🧩 Cấu trúc dự án

| File | Mô tả |
|---|---|
| `account.py` | Xử lý quản lý tài khoản người dùng |
| `chromedriver.exe` | Trình điều khiển Selenium (auto download nếu chưa có) |
| `export.py` | Xuất câu hỏi từ database `ioe_questions.db` |
| `IOE.exe` | File chạy chính |
| `index.py` | Source của giao diện chính – chạy file này để mở app |
| `ioe_accounts.db` | Database quản lý tài khoản |
| `ioe_questions.db` | Database quản lý câu hỏi – đáp án |
| `logo.ico` | Icon của ứng dụng |
| `main.py` | Xử lý logic chính – làm bài IOE |
| `manage.py` | Màn hình quản lý người dùng |

---

# 📦 Thư viện cần cài
Mình có liệt kê các thư viện chính gồm:

- Selenium  
- Pandas  
- OpenAI  
- Google-GenAI  
- OpenPyXL  
- PyQt6  
- Requests  
- AssemblyAI  
- sqlite-utils
- psutil
- Và một số thư viện khác trong source

Cài đặt bằng pip:
```bash
pip install selenium pandas openai google-genai openpyxl PyQt6 requests assemblyai sqlite-utils psutil
```
## Vậy là đã kết thúc phần giới thiệu về app, hi vọng bạn sẽ có trải nghiệm tốt, nếu có feedback hoặc collab, hãy liên hệ tôi thông qua email ở phần trên
