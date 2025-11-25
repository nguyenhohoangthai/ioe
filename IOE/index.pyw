import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import os
import sys
import threading
import time
import psutil
from datetime import datetime

class AdvancedIOEManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IOE Tool Manager - Advanced")
        self.root.state('zoomed')
        
        # Center the window
        self.center_window()
        
        # Configure style
        self.configure_styles()
        
        # Store running processes
        self.running_processes = {}
        
        # Create UI
        self.create_ui()
        
        # Start auto-update
        self.auto_update_status()
        
    def center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        width = 600
        height = 750
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def configure_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure styles
        style.configure('Title.TLabel', font=('Arial', 18, 'bold'), foreground='#2c3e50')
        style.configure('Subtitle.TLabel', font=('Arial', 10), foreground='#7f8c8d')
        style.configure('Action.TButton', font=('Arial', 11), padding=10)
        style.configure('Success.TLabel', foreground='green')
        style.configure('Warning.TLabel', foreground='orange')
        style.configure('Error.TLabel', foreground='red')
        
    def create_ui(self):
        """Create the user interface"""
        # Main frame with scrollbar
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = ttk.Label(header_frame, text="IOE Tool Manager", style='Title.TLabel')
        title_label.pack()
        
        subtitle_label = ttk.Label(header_frame, text="Quản lý các công cụ IOE - Phiên bản Nâng cao", style='Subtitle.TLabel')
        subtitle_label.pack()
        
        # File status frame
        status_frame = ttk.LabelFrame(main_frame, text="📊 Trạng thái file", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 15))
        
        # File status
        self.main_status = self.create_status_row(status_frame, "main.py", "File chính")
        self.account_status = self.create_status_row(status_frame, "account.py", "Quản lý tài khoản")
        self.manage_status = self.create_status_row(status_frame, "manage.py", "Quản lý câu hỏi")
        self.export_status = self.create_status_row(status_frame, "export.py", "Xuất câu hỏi")
        self.base_init = self.create_status_row(status_frame, "setting.exe", "Cập nhật tiến trình mới")
        
        # Running processes frame
        self.processes_frame = ttk.LabelFrame(main_frame, text="🔄 Tiến trình đang chạy", padding="10")
        self.processes_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.processes_content = ttk.Label(self.processes_frame, text="Không có tiến trình nào đang chạy", foreground="gray")
        self.processes_content.pack()
        
        # Buttons frame
        button_frame = ttk.LabelFrame(main_frame, text="🎯 Chức năng chính", padding="15")
        button_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Run Main button
        self.run_main_btn = ttk.Button(
            button_frame, 
            text="🚀 Chạy file chính (main.py)", 
            style='Action.TButton',
            command=lambda: self.run_file("main.py", "File chính")
        )
        self.run_main_btn.pack(fill=tk.X, pady=5)
        
        # Account Manager button
        self.account_btn = ttk.Button(
            button_frame, 
            text="👥 Quản lý tài khoản (account.py)", 
            style='Action.TButton',
            command=lambda: self.run_file("account.py", "Quản lý tài khoản")
        )
        self.account_btn.pack(fill=tk.X, pady=5)
        
        # Question Manager button
        self.question_btn = ttk.Button(
            button_frame, 
            text="📚 Quản lý câu hỏi (manage.py)", 
            style='Action.TButton',
            command=lambda: self.run_file("manage.py", "Quản lý câu hỏi")
        )
        self.question_btn.pack(fill=tk.X, pady=5)
        
        # Export Questions button
        self.export_btn = ttk.Button(
            button_frame, 
            text="📤 Xuất câu hỏi (export.py)", 
            style='Action.TButton',
            command=lambda: self.run_file("export.py", "Xuất câu hỏi")
        )
        self.export_btn.pack(fill=tk.X, pady=5)

        # Setting button
        self.setting_btn = ttk.Button(
            button_frame, 
            text="⚙️ Cập nhật tiến trình mới (setting.exe)", 
            style='Action.TButton',
            command=lambda: self.run_file("setting.exe", "Cài đặt gốc")
        )
        self.setting_btn.pack(fill=tk.X, pady=5)
        
        # Advanced functions frame
        advanced_frame = ttk.LabelFrame(main_frame, text="🔧 Chức năng nâng cao", padding="10")
        advanced_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Stop all processes button
        self.stop_all_btn = ttk.Button(
            advanced_frame,
            text="🛑 Dừng tất cả tiến trình",
            command=self.stop_all_processes
        )
        self.stop_all_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Open folder button
        self.open_folder_btn = ttk.Button(
            advanced_frame,
            text="📁 Mở thư mục hiện tại",
            command=self.open_current_folder
        )
        self.open_folder_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # System info button
        self.sysinfo_btn = ttk.Button(
            advanced_frame,
            text="💻 Thông tin hệ thống",
            command=self.show_system_info
        )
        self.sysinfo_btn.pack(side=tk.LEFT)
        
        # Control frame
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=10)
        
        # Refresh button
        self.refresh_btn = ttk.Button(
            control_frame, 
            text="🔄 Kiểm tra file", 
            command=self.check_files
        )
        self.refresh_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Exit button
        self.exit_btn = ttk.Button(
            control_frame, 
            text="❌ Thoát", 
            command=self.exit_app
        )
        self.exit_btn.pack(side=tk.RIGHT)
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Sẵn sàng - Kiểm tra file...", foreground="blue")
        self.status_label.pack(pady=(10, 0))
        
        # Version info
        version_label = ttk.Label(main_frame, text="Phiên bản 1.0 - © 2025 IOE Manager", foreground="gray", font=('Arial', 8))
        version_label.pack(pady=(5, 0))
        
        # Initial file check
        self.check_files()
    
    def create_status_row(self, parent, filename, description):
        """Create a status row for a file"""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=3)
        
        label = ttk.Label(frame, text=f"{description}:", width=20, anchor=tk.W)
        label.pack(side=tk.LEFT)
        
        status_label = ttk.Label(frame, text="Đang kiểm tra...", foreground="orange")
        status_label.pack(side=tk.LEFT)
        
        # Add file size info
        size_label = ttk.Label(frame, text="", foreground="gray", font=('Arial', 8))
        size_label.pack(side=tk.RIGHT)
        
        return {
            "filename": filename, 
            "description": description, 
            "label": status_label,
            "size_label": size_label
        }
    
    def check_files(self):
        """Check if all required files exist"""
        self.update_status("Đang kiểm tra file...", "blue")
        
        files_to_check = [
            self.main_status, 
            self.account_status, 
            self.manage_status, 
            self.export_status,
            self.base_init
        ]
        
        all_exists = True
        for file_info in files_to_check:
            filename = file_info["filename"]
            if os.path.exists(filename):
                file_info["label"].config(text="✓ Có", foreground="green")
                # Add file size information
                size = os.path.getsize(filename)
                size_kb = size / 1024
                file_info["size_label"].config(text=f"{size_kb:.1f} KB")
            else:
                file_info["label"].config(text="✗ Thiếu", foreground="red")
                file_info["size_label"].config(text="")
                all_exists = False
        
        if all_exists:
            self.update_status("✅ Tất cả file đã sẵn sàng!", "green")
        else:
            self.update_status("⚠️ Cảnh báo: Một số file bị thiếu!", "orange")
    
    def run_file(self, filename, description):
        """Run a Python file or executable"""
        if not os.path.exists(filename):
            self.update_status(f"❌ Lỗi: Không tìm thấy {filename}!", "red")
            messagebox.showerror("Lỗi", f"Không tìm thấy file {filename}!")
            return
        
        # Check if already running
        if filename in self.running_processes:
            if messagebox.askyesno("Xác nhận", f"{description} đang chạy. Bạn có muốn chạy thêm một instance khác?"):
                pass
            else:
                return
        
        self.update_status(f"⏳ Đang khởi chạy {description}...", "blue")
        
        try:
            if filename.endswith('.exe'):
                # Run executable directly
                process = subprocess.Popen([filename])
            else:
                # Run Python file
                python_executable = sys.executable
                process = subprocess.Popen([python_executable, filename])
            
            # Store process info
            self.running_processes[filename] = {
                'process': process,
                'description': description,
                'start_time': time.time(),
                'filename': filename
            }
            
            self.update_status(f"✅ {description} đã được khởi chạy!", "green")
            
            # Start monitoring thread
            monitor_thread = threading.Thread(
                target=self.monitor_process, 
                args=(process, filename, description),
                daemon=True
            )
            monitor_thread.start()
            
            # Update processes display
            self.update_processes_display()
            
        except Exception as e:
            self.update_status(f"❌ Lỗi khi chạy {description}: {str(e)}", "red")
            messagebox.showerror("Lỗi", f"Không thể chạy {description}:\n{str(e)}")
    
    def monitor_process(self, process, filename, description):
        """Monitor a running process"""
        process.wait()  # Wait for process to complete
        
        # Remove from running processes
        if filename in self.running_processes:
            del self.running_processes[filename]
        
        # Update status in main thread
        self.root.after(0, lambda: self.update_status(
            f"✅ {description} đã kết thúc (mã: {process.returncode})", 
            "green" if process.returncode == 0 else "orange"
        ))
        
        # Update processes display
        self.root.after(0, self.update_processes_display)
    
    def update_processes_display(self):
        """Update the running processes display"""
        if not self.running_processes:
            self.processes_content.config(text="Không có tiến trình nào đang chạy", foreground="gray")
            return
        
        processes_text = ""
        for filename, info in self.running_processes.items():
            running_time = time.time() - info['start_time']
            processes_text += f"• {info['description']} ({running_time:.0f}s)\n"
        
        self.processes_content.config(text=processes_text.strip(), foreground="green")
    
    def stop_all_processes(self):
        """Stop all running processes"""
        if not self.running_processes:
            messagebox.showinfo("Thông báo", "Không có tiến trình nào đang chạy")
            return
        
        if messagebox.askyesno("Xác nhận", f"Dừng tất cả {len(self.running_processes)} tiến trình đang chạy?"):
            stopped_count = 0
            for filename, info in list(self.running_processes.items()):
                try:
                    process = info['process']
                    # Terminate the process and its children
                    parent = psutil.Process(process.pid)
                    for child in parent.children(recursive=True):
                        child.terminate()
                    parent.terminate()
                    stopped_count += 1
                except:
                    try:
                        info['process'].terminate()
                        stopped_count += 1
                    except:
                        pass
            
            self.running_processes.clear()
            self.update_processes_display()
            self.update_status(f"✅ Đã dừng {stopped_count} tiến trình", "green")
    
    def open_current_folder(self):
        """Open the current folder in file explorer"""
        try:
            current_dir = os.getcwd()
            if os.name == 'nt':  # Windows
                os.startfile(current_dir)
            elif os.name == 'posix':  # macOS, Linux
                subprocess.Popen(['open', current_dir] if sys.platform == 'darwin' else ['xdg-open', current_dir])
            self.update_status("📁 Đã mở thư mục hiện tại", "blue")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở thư mục: {str(e)}")
    
    def show_system_info(self):
        """Show system information"""
        try:
            info_window = tk.Toplevel(self.root)
            info_window.title("Thông tin hệ thống")
            info_window.geometry("500x400")
            info_window.resizable(False, False)
            
            # Center the window
            info_window.update_idletasks()
            x = (info_window.winfo_screenwidth() // 2) - (500 // 2)
            y = (info_window.winfo_screenheight() // 2) - (400 // 2)
            info_window.geometry(f'500x400+{x}+{y}')
            
            # Create text widget
            text_widget = scrolledtext.ScrolledText(info_window, wrap=tk.WORD, width=60, height=20)
            text_widget.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
            
            # Gather system information
            info_text = "=== THÔNG TIN HỆ THỐNG ===\n\n"
            
            # Python information
            info_text += f"Python: {sys.version}\n"
            info_text += f"Thư mục làm việc: {os.getcwd()}\n\n"
            
            # System information
            info_text += f"Hệ điều hành: {os.name} - {sys.platform}\n"
            info_text += f"CPU count: {os.cpu_count()}\n\n"
            
            # File information
            info_text += "=== THÔNG TIN FILE ===\n\n"
            files_to_check = ["main.py", "account.py", "manage.py", "export.py", "setting.exe"]
            for file in files_to_check:
                if os.path.exists(file):
                    size = os.path.getsize(file)
                    mtime = datetime.fromtimestamp(os.path.getmtime(file))
                    info_text += f"{file}: {size/1024:.1f} KB (sửa lúc: {mtime.strftime('%Y-%m-%d %H:%M:%S')})\n"
                else:
                    info_text += f"{file}: KHÔNG TỒN TẠI\n"
            
            # Running processes
            info_text += f"\n=== TIẾN TRÌNH ĐANG CHẠY: {len(self.running_processes)} ===\n"
            for filename, info in self.running_processes.items():
                running_time = time.time() - info['start_time']
                info_text += f"• {info['description']} ({running_time:.0f}s)\n"
            
            text_widget.insert(tk.END, info_text)
            text_widget.config(state=tk.DISABLED)
            
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể hiển thị thông tin hệ thống: {str(e)}")
    
    def auto_update_status(self):
        """Auto-update status every 5 seconds"""
        self.update_processes_display()
        self.root.after(1000, self.auto_update_status)  # Update every 5 seconds
    
    def update_status(self, message, color="black"):
        """Update status label"""
        self.status_label.config(text=message, foreground=color)
    
    def exit_app(self):
        """Exit the application"""
        # Check if any processes are running
        if self.running_processes:
            running_apps = "\n".join([f"• {info['description']}" for info in self.running_processes.values()])
            if not messagebox.askokcancel(
                "Thoát", 
                f"Các ứng dụng sau đang chạy:\n{running_apps}\n\nThoát ứng dụng này sẽ không dừng các tiến trình đang chạy.\n\nTiếp tục?"
            ):
                return
        
        if messagebox.askokcancel("Thoát", "Bạn có chắc chắn muốn thoát?"):
            self.root.destroy()

def main():
    # Check if psutil is available, if not, install it
    try:
        import psutil
    except ImportError:
        print("Thư viện psutil chưa được cài đặt. Đang cài đặt...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil"])
            import psutil
            print("Cài đặt psutil thành công!")
        except:
            print("Không thể cài đặt psutil. Một số tính năng có thể bị hạn chế.")
    
    root = tk.Tk()
    app = AdvancedIOEManagerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()