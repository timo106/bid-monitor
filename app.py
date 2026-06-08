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
# 配置文件路径
# ============================================================

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schedule_config.json")


def load_schedule_config() -> dict:
    """加载定时配置"""
    default = {"enabled": False, "hour": 9, "minute": 0, "repeat": True}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def save_schedule_config(config: dict):
    """保存定时配置"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ============================================================
# 日志 Handler
# ============================================================

class TextHandler(logging.Handler):
    """自定义日志处理器，将日志写入 CTkTextbox"""

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

        # 窗口配置
        self.title("📋 招标信息监控")
        self.geometry("780x650")
        self.minsize(650, 520)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # 状态变量
        self.running = False
        self.stop_event = threading.Event()
        self.worker_thread = None

        # 定时配置
        self.schedule_config = load_schedule_config()
        self.scheduler_running = False
        self._scheduler_check_id = None

        # 构建界面
        self._build_ui()

        # 配置日志
        self._setup_logging()

        # 启动定时检查器
        self._start_scheduler()

        # 关闭时保存配置
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        """构建界面布局"""

        # ---------- 顶部标题栏 ----------
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

        # 第一行：标题和开关
        row1 = ctk.CTkFrame(schedule_frame, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(10, 5))

        ctk.CTkLabel(
            row1, text="⏰ 定时执行", font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left")

        self.schedule_switch = ctk.CTkSwitch(
            row1, text="启用", font=ctk.CTkFont(size=12),
            command=self._on_schedule_toggle, onvalue=True, offvalue=False,
        )
        self.schedule_switch.pack(side="right")
        if self.schedule_config.get("enabled"):
            self.schedule_switch.select()

        # 第二行：时间选择
        row2 = ctk.CTkFrame(schedule_frame, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkLabel(row2, text="执行时间：", font=ctk.CTkFont(size=12)).pack(side="left")

        # 小时下拉框
        self.hour_var = ctk.StringVar(value=str(self.schedule_config.get("hour", 9)).zfill(2))
        self.hour_menu = ctk.CTkOptionMenu(
            row2, variable=self.hour_var,
            values=[str(i).zfill(2) for i in range(24)],
            width=60, font=ctk.CTkFont(size=13),
            command=self._on_time_change,
        )
        self.hour_menu.pack(side="left", padx=(8, 2))

        ctk.CTkLabel(row2, text="时", font=ctk.CTkFont(size=12)).pack(side="left")

        # 分钟下拉框
        self.minute_var = ctk.StringVar(value=str(self.schedule_config.get("minute", 0)).zfill(2))
        self.minute_menu = ctk.CTkOptionMenu(
            row2, variable=self.minute_var,
            values=[str(i).zfill(2) for i in range(0, 60, 5)],
            width=60, font=ctk.CTkFont(size=13),
            command=self._on_time_change,
        )
        self.minute_menu.pack(side="left", padx=(8, 2))

        ctk.CTkLabel(row2, text="分", font=ctk.CTkFont(size=12)).pack(side="left")

        # 重复选项
        self.repeat_switch = ctk.CTkSwitch(
            row2, text="每天重复", font=ctk.CTkFont(size=12),
            command=self._on_time_change, onvalue=True, offvalue=False,
        )
        self.repeat_switch.pack(side="left", padx=(20, 0))
        if self.schedule_config.get("repeat", True):
            self.repeat_switch.select()

        # 下次执行时间
        self.next_run_label = ctk.CTkLabel(
            row2, text="", font=ctk.CTkFont(size=11), text_color="#85c1e9",
        )
        self.next_run_label.pack(side="right")
        self._update_next_run_label()

        # ---------- 按钮区域 ----------
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(10, 5))

        self.btn_start = ctk.CTkButton(
            btn_frame, text="▶  开始监控", font=ctk.CTkFont(size=14, weight="bold"),
            width=160, height=40, fg_color="#27ae60", hover_color="#219a52",
            command=self._on_start,
        )
        self.btn_start.pack(side="left", padx=(0, 10))

        self.btn_stop = ctk.CTkButton(
            btn_frame, text="⏹  停止", font=ctk.CTkFont(size=14, weight="bold"),
            width=120, height=40, fg_color="#e74c3c", hover_color="#c0392b",
            command=self._on_stop, state="disabled",
        )
        self.btn_stop.pack(side="left", padx=(0, 10))

        self.btn_clear = ctk.CTkButton(
            btn_frame, text="🗑 清空日志", font=ctk.CTkFont(size=13),
            width=100, height=40, fg_color="#7f8c8d", hover_color="#6c7a7d",
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

        # ---------- 底部结果栏 ----------
        footer = ctk.CTkFrame(self, fg_color="#1a252f", corner_radius=0, height=40)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        self.result_label = ctk.CTkLabel(
            footer, text="今日结果：-  |  邮件：-", font=ctk.CTkFont(size=12), text_color="#85c1e9",
        )
        self.result_label.pack(side="left", padx=20)

    # ============================================================
    # 定时调度
    # ============================================================

    def _on_schedule_toggle(self):
        """开关定时功能"""
        enabled = self.schedule_switch.get()
        self.schedule_config["enabled"] = enabled
        save_schedule_config(self.schedule_config)
        self._update_next_run_label()
        if enabled:
            logging.info(f"定时任务已启用：每天 {self.hour_var.get()}:{self.minute_var.get()} 执行")
        else:
            logging.info("定时任务已关闭")

    def _on_time_change(self, *args):
        """时间改变"""
        self.schedule_config["hour"] = int(self.hour_var.get())
        self.schedule_config["minute"] = int(self.minute_var.get())
        self.schedule_config["repeat"] = self.repeat_switch.get()
        save_schedule_config(self.schedule_config)
        self._update_next_run_label()

    def _get_next_run_time(self) -> datetime | None:
        """计算下次执行时间"""
        if not self.schedule_config.get("enabled"):
            return None

        now = datetime.now()
        target = now.replace(
            hour=self.schedule_config.get("hour", 9),
            minute=self.schedule_config.get("minute", 0),
            second=0, microsecond=0,
        )

        if target <= now:
            if self.schedule_config.get("repeat", True):
                target += timedelta(days=1)
            else:
                return None

        return target

    def _update_next_run_label(self):
        """更新下次执行时间标签"""
        next_run = self._get_next_run_time()
        if next_run:
            self.next_run_label.configure(text=f"下次执行：{next_run.strftime('%m月%d日 %H:%M')}")
        else:
            self.next_run_label.configure(text="")

    def _start_scheduler(self):
        """启动定时检查器（每 30 秒检查一次）"""
        self._check_schedule()
        self._scheduler_check_id = self.after(30000, self._start_scheduler)

    def _check_schedule(self):
        """检查是否到了执行时间"""
        if not self.schedule_config.get("enabled"):
            return
        if self.running:
            return

        now = datetime.now()
        target_hour = self.schedule_config.get("hour", 9)
        target_minute = self.schedule_config.get("minute", 0)

        if now.hour == target_hour and now.minute == target_minute:
            logging.info(f"⏰ 定时触发：{target_hour:02d}:{target_minute:02d}")
            self._on_start()

            # 如果不重复，执行一次后关闭
            if not self.schedule_config.get("repeat", True):
                self.schedule_config["enabled"] = False
                self.schedule_switch.deselect()
                save_schedule_config(self.schedule_config)
                logging.info("一次性任务已执行，定时已关闭")

    # ============================================================
    # 任务控制
    # ============================================================

    def _setup_logging(self):
        """配置日志系统"""
        handler = TextHandler(self.log_text)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S",
        ))
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.handlers.clear()
        root_logger.addHandler(handler)

    def _on_start(self):
        """点击开始按钮"""
        if self.running:
            return
        self.running = True
        self.stop_event.clear()

        self.btn_start.configure(state="disabled", fg_color="#555555")
        self.btn_stop.configure(state="normal", fg_color="#e74c3c")
        self.status_label.configure(text="🔄 状态：正在运行...")
        self.progress_bar.set(0)
        self.result_label.configure(text="今日结果：运行中...  |  邮件：-")

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
            from main import main as run_main
            result = run_main(stop_event=self.stop_event)
            self.after(0, self._on_task_complete, result)
        except Exception as e:
            logging.error(f"程序异常: {e}")
            self.after(0, self._on_task_error, str(e))

    def _on_task_complete(self, result):
        """任务完成回调"""
        self.running = False
        self.btn_start.configure(state="normal", fg_color="#27ae60")
        self.btn_stop.configure(state="disabled", fg_color="#555555")
        self.progress_bar.set(1.0)
        self._update_next_run_label()

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

    def _on_close(self):
        """关闭窗口"""
        if self._scheduler_check_id:
            self.after_cancel(self._scheduler_check_id)
        self.stop_event.set()
        self.destroy()


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    app = BidMonitorApp()
    app.mainloop()
