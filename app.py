# -*- coding: utf-8 -*-
"""
招标信息监控 - GUI 应用
使用 CustomTkinter 构建现代界面
"""

import sys
import threading
import logging
import customtkinter as ctk
from datetime import datetime

# ============================================================
# 日志 Handler：将日志输出到 GUI 文本框
# ============================================================

class TextHandler(logging.Handler):
    """自定义日志处理器，将日志写入 CTkTextbox"""

    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        # 在主线程中更新 UI
        self.text_widget.after(0, self._append, msg)

    def _append(self, msg):
        self.text_widget.configure(state="normal")
        self.text_widget.insert("end", msg + "\n")
        self.text_widget.see("end")
        self.text_widget.configure(state="disabled")


# ============================================================
# 主应用窗口
# ============================================================

class BidMonitorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 窗口配置
        self.title("📋 招标信息监控")
        self.geometry("750x580")
        self.minsize(600, 450)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # 状态变量
        self.running = False
        self.stop_event = threading.Event()
        self.worker_thread = None

        # 构建界面
        self._build_ui()

        # 配置日志
        self._setup_logging()

    def _build_ui(self):
        """构建界面布局"""

        # ---------- 顶部标题栏 ----------
        header = ctk.CTkFrame(self, fg_color="#1a5276", corner_radius=0, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="📋 招标信息监控",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="white",
        ).pack(side="left", padx=20, pady=10)

        # 版本标签
        ctk.CTkLabel(
            header,
            text="v1.0",
            font=ctk.CTkFont(size=12),
            text_color="#85c1e9",
        ).pack(side="left", padx=5)

        # ---------- 按钮区域 ----------
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(15, 5))

        self.btn_start = ctk.CTkButton(
            btn_frame,
            text="▶  开始监控",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=160,
            height=40,
            fg_color="#27ae60",
            hover_color="#219a52",
            command=self._on_start,
        )
        self.btn_start.pack(side="left", padx=(0, 10))

        self.btn_stop = ctk.CTkButton(
            btn_frame,
            text="⏹  停止",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=120,
            height=40,
            fg_color="#e74c3c",
            hover_color="#c0392b",
            command=self._on_stop,
            state="disabled",
        )
        self.btn_stop.pack(side="left", padx=(0, 10))

        # 清空日志按钮
        self.btn_clear = ctk.CTkButton(
            btn_frame,
            text="🗑 清空日志",
            font=ctk.CTkFont(size=13),
            width=100,
            height=40,
            fg_color="#7f8c8d",
            hover_color="#6c7a7d",
            command=self._clear_log,
        )
        self.btn_clear.pack(side="right")

        # ---------- 状态栏 ----------
        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.pack(fill="x", padx=20, pady=(5, 5))

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="💤 状态：等待中...",
            font=ctk.CTkFont(size=13),
            anchor="w",
        )
        self.status_label.pack(side="left")

        # 进度条
        self.progress_bar = ctk.CTkProgressBar(status_frame, width=200)
        self.progress_bar.pack(side="right", padx=(10, 0))
        self.progress_bar.set(0)

        # ---------- 日志区域 ----------
        log_frame = ctk.CTkFrame(self, fg_color="transparent")
        log_frame.pack(fill="both", expand=True, padx=20, pady=(5, 5))

        ctk.CTkLabel(
            log_frame,
            text="运行日志",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(fill="x")

        self.log_text = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=12),
            state="disabled",
            fg_color="#2b2b2b",
            text_color="#e0e0e0",
            corner_radius=8,
        )
        self.log_text.pack(fill="both", expand=True, pady=(5, 0))

        # ---------- 底部结果栏 ----------
        footer = ctk.CTkFrame(self, fg_color="#1a252f", corner_radius=0, height=40)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        self.result_label = ctk.CTkLabel(
            footer,
            text="今日结果：-  |  邮件：-",
            font=ctk.CTkFont(size=12),
            text_color="#85c1e9",
        )
        self.result_label.pack(side="left", padx=20)

    def _setup_logging(self):
        """配置日志系统"""
        handler = TextHandler(self.log_text)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        ))

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        # 清除已有的 handler（避免重复）
        root_logger.handlers.clear()
        root_logger.addHandler(handler)

    def _on_start(self):
        """点击开始按钮"""
        self.running = True
        self.stop_event.clear()

        # 更新按钮状态
        self.btn_start.configure(state="disabled", fg_color="#555555")
        self.btn_stop.configure(state="normal", fg_color="#e74c3c")
        self.status_label.configure(text="🔄 状态：正在运行...")
        self.progress_bar.set(0)
        self.result_label.configure(text="今日结果：运行中...  |  邮件：-")

        # 在子线程中运行爬虫
        self.worker_thread = threading.Thread(target=self._run_task, daemon=True)
        self.worker_thread.start()

    def _on_stop(self):
        """点击停止按钮"""
        self.stop_event.set()
        self.status_label.configure(text="⏹ 状态：正在停止...")
        self.btn_stop.configure(state="disabled", fg_color="#555555")

    def _run_task(self):
        """在子线程中执行爬虫任务"""
        try:
            # 导入 main 模块
            from main import main as run_main

            result = run_main(stop_event=self.stop_event)

            # 更新 UI（回到主线程）
            self.after(0, self._on_task_complete, result)

        except Exception as e:
            logging.error(f"程序异常: {e}")
            self.after(0, self._on_task_error, str(e))

    def _on_task_complete(self, result):
        """任务完成回调"""
        self.running = False

        # 恢复按钮状态
        self.btn_start.configure(state="normal", fg_color="#27ae60")
        self.btn_stop.configure(state="disabled", fg_color="#555555")
        self.progress_bar.set(1.0)

        if result.get("stopped"):
            self.status_label.configure(text="⏹ 状态：已停止")
            self.result_label.configure(
                text=f"今日结果：已获取 {result['total']} 条（未完成）  |  邮件：未发送"
            )
        else:
            filtered = result.get("filtered", 0)
            email_status = "已发送 ✅" if result.get("email_sent") else "未发送 ❌"
            self.status_label.configure(text="✅ 状态：完成")
            self.result_label.configure(
                text=f"今日结果：{filtered} 条  |  邮件：{email_status}"
            )

    def _on_task_error(self, error_msg):
        """任务异常回调"""
        self.running = False
        self.btn_start.configure(state="normal", fg_color="#27ae60")
        self.btn_stop.configure(state="disabled", fg_color="#555555")
        self.status_label.configure(text="❌ 状态：出错")
        self.result_label.configure(text=f"错误：{error_msg[:50]}")

    def _clear_log(self):
        """清空日志"""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    app = BidMonitorApp()
    app.mainloop()
