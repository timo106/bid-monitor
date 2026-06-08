# -*- coding: utf-8 -*-
"""
招标信息监控 - GUI 应用
使用 CustomTkinter 构建现代界面
"""

import sys
import threading
import logging
import json
import os
import customtkinter as ctk
from datetime import datetime, timedelta

# ============================================================
# 配置文件
# ============================================================

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schedule_config.json")


def load_schedule_config() -> dict:
    default = {"enabled": False, "hour": 9, "minute": 0, "repeat": True}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def save_schedule_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ============================================================
# 日志 Handler
# ============================================================

class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
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

        self.title("📋 招标信息监控")
        self.geometry("780x680")
        self.minsize(650, 550)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # 状态
        self.running = False          # 爬虫是否在运行
        self.monitoring = False       # 定时监控是否启用
        self.stop_event = threading.Event()
        self.worker_thread = None

        # 定时配置
        self.schedule_config = load_schedule_config()

        self._build_ui()
        self._setup_logging()

        # 启动定时检查器
        self._scheduler_tick()

        # 关闭时保存
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ============================================================
    # UI 构建
    # ============================================================

    def _build_ui(self):

        # ---------- 标题栏 ----------
        header = ctk.CTkFrame(self, fg_color="#1a5276", corner_radius=0, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="📋 招标信息监控",
            font=ctk.CTkFont(size=20, weight="bold"), text_color="white",
        ).pack(side="left", padx=20, pady=10)

        ctk.CTkLabel(
            header, text="v2.0", font=ctk.CTkFont(size=12), text_color="#85c1e9",
        ).pack(side="left", padx=5)

        # ---------- 定时设置区域 ----------
        schedule_frame = ctk.CTkFrame(self, fg_color="#1e3a4f", corner_radius=8)
        schedule_frame.pack(fill="x", padx=20, pady=(12, 5))

        # 第一行：标题
        row1 = ctk.CTkFrame(schedule_frame, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(10, 5))

        ctk.CTkLabel(
            row1, text="⏰ 定时设置", font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left")

        self.monitor_status_label = ctk.CTkLabel(
            row1, text="未启用", font=ctk.CTkFont(size=11), text_color="#888",
        )
        self.monitor_status_label.pack(side="right")

        # 第二行：时间选择 + 每天重复
        row2 = ctk.CTkFrame(schedule_frame, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(0, 5))

        ctk.CTkLabel(row2, text="执行时间：", font=ctk.CTkFont(size=12)).pack(side="left")

        self.hour_var = ctk.StringVar(value=str(self.schedule_config.get("hour", 9)).zfill(2))
        self.hour_menu = ctk.CTkOptionMenu(
            row2, variable=self.hour_var,
            values=[str(i).zfill(2) for i in range(24)],
            width=60, font=ctk.CTkFont(size=13), command=self._on_time_change,
        )
        self.hour_menu.pack(side="left", padx=(8, 2))
        ctk.CTkLabel(row2, text="时", font=ctk.CTkFont(size=12)).pack(side="left")

        self.minute_var = ctk.StringVar(value=str(self.schedule_config.get("minute", 0)).zfill(2))
        self.minute_menu = ctk.CTkOptionMenu(
            row2, variable=self.minute_var,
            values=[str(i).zfill(2) for i in range(0, 60, 5)],
            width=60, font=ctk.CTkFont(size=13), command=self._on_time_change,
        )
        self.minute_menu.pack(side="left", padx=(8, 2))
        ctk.CTkLabel(row2, text="分", font=ctk.CTkFont(size=12)).pack(side="left")

        self.next_run_label = ctk.CTkLabel(
            row2, text="", font=ctk.CTkFont(size=11), text_color="#85c1e9",
        )
        self.next_run_label.pack(side="right")

        # ---------- 按钮区域 ----------
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(10, 5))

        # 实时监控（立即执行）
        self.btn_realtime = ctk.CTkButton(
            btn_frame, text="🔍  实时监控", font=ctk.CTkFont(size=14, weight="bold"),
            width=150, height=42, fg_color="#e67e22", hover_color="#d35400",
            command=self._on_realtime,
        )
        self.btn_realtime.pack(side="left", padx=(0, 10))

        # 开始监控（定时模式）
        self.btn_start = ctk.CTkButton(
            btn_frame, text="▶  开始监控", font=ctk.CTkFont(size=14, weight="bold"),
            width=150, height=42, fg_color="#27ae60", hover_color="#219a52",
            command=self._on_start_monitor,
        )
        self.btn_start.pack(side="left", padx=(0, 10))

        # 停止
        self.btn_stop = ctk.CTkButton(
            btn_frame, text="⏹  停止", font=ctk.CTkFont(size=14, weight="bold"),
            width=100, height=42, fg_color="#e74c3c", hover_color="#c0392b",
            command=self._on_stop, state="disabled",
        )
        self.btn_stop.pack(side="left", padx=(0, 10))

        # 清空日志
        self.btn_clear = ctk.CTkButton(
            btn_frame, text="🗑", font=ctk.CTkFont(size=14),
            width=40, height=42, fg_color="#7f8c8d", hover_color="#6c7a7d",
            command=self._clear_log,
        )
        self.btn_clear.pack(side="right")

        # ---------- 状态栏 ----------
        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.pack(fill="x", padx=20, pady=(5, 5))

        self.status_label = ctk.CTkLabel(
            status_frame, text="💤 状态：等待中...", font=ctk.CTkFont(size=13), anchor="w",
        )
        self.status_label.pack(side="left")

        self.progress_bar = ctk.CTkProgressBar(status_frame, width=200)
        self.progress_bar.pack(side="right", padx=(10, 0))
        self.progress_bar.set(0)

        # ---------- 日志区域 ----------
        log_frame = ctk.CTkFrame(self, fg_color="transparent")
        log_frame.pack(fill="both", expand=True, padx=20, pady=(5, 5))

        ctk.CTkLabel(
            log_frame, text="运行日志", font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
        ).pack(fill="x")

        self.log_text = ctk.CTkTextbox(
            log_frame, font=ctk.CTkFont(family="Consolas", size=12),
            state="disabled", fg_color="#2b2b2b", text_color="#e0e0e0", corner_radius=8,
        )
        self.log_text.pack(fill="both", expand=True, pady=(5, 0))

        # ---------- 底部栏 ----------
        footer = ctk.CTkFrame(self, fg_color="#1a252f", corner_radius=0, height=40)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        self.result_label = ctk.CTkLabel(
            footer, text="今日结果：-  |  邮件：-",
            font=ctk.CTkFont(size=12), text_color="#85c1e9",
        )
        self.result_label.pack(side="left", padx=20)

    # ============================================================
    # 日志
    # ============================================================

    def _setup_logging(self):
        handler = TextHandler(self.log_text)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S",
        ))
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.handlers.clear()
        root_logger.addHandler(handler)

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    # ============================================================
    # 定时调度
    # ============================================================

    def _on_time_change(self, *args):
        self.schedule_config["hour"] = int(self.hour_var.get())
        self.schedule_config["minute"] = int(self.minute_var.get())
        save_schedule_config(self.schedule_config)
        self._update_next_run_label()

    def _get_next_run_time(self) -> datetime | None:
        if not self.monitoring:
            return None
        now = datetime.now()
        target = now.replace(
            hour=self.schedule_config.get("hour", 9),
            minute=self.schedule_config.get("minute", 0),
            second=0, microsecond=0,
        )
        if target <= now:
            target += timedelta(days=1)
        return target

    def _update_next_run_label(self):
        next_run = self._get_next_run_time()
        if next_run:
            self.next_run_label.configure(text=f"下次执行：{next_run.strftime('%m月%d日 %H:%M')}")
        else:
            self.next_run_label.configure(text="")

    def _scheduler_tick(self):
        """每 30 秒检查一次是否到执行时间"""
        if self.monitoring and not self.running:
            now = datetime.now()
            h = self.schedule_config.get("hour", 9)
            m = self.schedule_config.get("minute", 0)
            if now.hour == h and now.minute == m:
                logging.info(f"⏰ 定时触发：{h:02d}:{m:02d}，开始执行...")
                self._run_task_async()
        self.after(30000, self._scheduler_tick)

    # ============================================================
    # 按钮事件
    # ============================================================

    def _on_realtime(self):
        """实时监控：立即抓取并发送邮件"""
        if self.running:
            return
        logging.info("🔍 实时监控：立即抓取...")
        self._run_task_async()

    def _on_start_monitor(self):
        """开始监控：启用定时模式"""
        if self.monitoring:
            # 已在监控中，点击则关闭
            self.monitoring = False
            self.btn_start.configure(text="▶  开始监控", fg_color="#27ae60")
            self.monitor_status_label.configure(text="未启用", text_color="#888")
            self.next_run_label.configure(text="")
            self.schedule_config["enabled"] = False
            save_schedule_config(self.schedule_config)
            logging.info("定时监控已关闭")
            return

        self.monitoring = True
        self.schedule_config["enabled"] = True
        save_schedule_config(self.schedule_config)

        h = self.schedule_config.get("hour", 9)
        m = self.schedule_config.get("minute", 0)

        self.btn_start.configure(text="⏸  停止监控", fg_color="#f39c12")
        self.monitor_status_label.configure(
            text=f"✅ 每天 {h:02d}:{m:02d} 自动执行", text_color="#27ae60",
        )
        self._update_next_run_label()

        logging.info(f"定时监控已启用：每天 {h:02d}:{m:02d} 自动执行")

    def _on_stop(self):
        """停止当前任务"""
        self.stop_event.set()
        self.status_label.configure(text="⏹ 状态：正在停止...")
        self.btn_stop.configure(state="disabled", fg_color="#555555")

    # ============================================================
    # 任务执行
    # ============================================================

    def _run_task_async(self):
        """异步启动爬虫任务"""
        self.running = True
        self.stop_event.clear()

        self.btn_realtime.configure(state="disabled", fg_color="#555555")
        self.btn_stop.configure(state="normal", fg_color="#e74c3c")
        self.status_label.configure(text="🔄 状态：正在运行...")
        self.progress_bar.set(0)
        self.result_label.configure(text="今日结果：运行中...  |  邮件：-")

        self.worker_thread = threading.Thread(target=self._run_task, daemon=True)
        self.worker_thread.start()

    def _run_task(self):
        """子线程中执行爬虫"""
        try:
            from main import main as run_main
            result = run_main(stop_event=self.stop_event)
            self.after(0, self._on_task_complete, result)
        except Exception as e:
            logging.error(f"程序异常: {e}")
            self.after(0, self._on_task_error, str(e))

    def _on_task_complete(self, result):
        """任务完成"""
        self.running = False
        self.btn_realtime.configure(state="normal", fg_color="#e67e22")
        self.btn_stop.configure(state="disabled", fg_color="#555555")
        self.progress_bar.set(1.0)

        if self.monitoring:
            self.btn_start.configure(text="⏸  停止监控", fg_color="#f39c12")

        if result.get("stopped"):
            self.status_label.configure(text="⏹ 状态：已停止")
            self.result_label.configure(
                text=f"今日结果：已获取 {result['total']} 条（未完成）  |  邮件：未发送"
            )
        else:
            filtered = result.get("filtered", 0)
            email_status = "已发送 ✅" if result.get("email_sent") else "未发送 ❌"
            self.status_label.configure(text="✅ 状态：完成")
            self.result_label.configure(text=f"今日结果：{filtered} 条  |  邮件：{email_status}")

        self._update_next_run_label()

    def _on_task_error(self, error_msg):
        """任务异常"""
        self.running = False
        self.btn_realtime.configure(state="normal", fg_color="#e67e22")
        self.btn_stop.configure(state="disabled", fg_color="#555555")
        self.status_label.configure(text="❌ 状态：出错")
        self.result_label.configure(text=f"错误：{error_msg[:50]}")

    def _on_close(self):
        """关闭窗口"""
        self.stop_event.set()
        self.destroy()


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    app = BidMonitorApp()
    app.mainloop()
