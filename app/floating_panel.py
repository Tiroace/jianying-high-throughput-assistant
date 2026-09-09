from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from core import ROOT, create_task_from_text, generate_drafts, load_settings, scan_assets
from jianying_window import find_jianying_window, snap_panel


class FloatingPanel(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("剪映 · 高产剪辑助手")
        self.geometry("390x740")
        self.minsize(350, 560)
        self.attributes("-topmost", True)
        self.settings_data = load_settings()
        self.project_var = tk.StringVar(value="黄精批量素材")
        self.persona_var = tk.StringVar(value="家庭关怀型")
        self.auto_attach = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="正在寻找剪映……")
        self.count_var = tk.StringVar(value="预计生成 2 条草稿")
        self.action_var = tk.StringVar(value="准备就绪")
        self.last_target_rect: tuple[int, int, int, int] | None = None
        self.busy = False
        self._build_ui()
        self.after(80, self._ensure_visible)
        self.after(300, self._watch_jianying)

    def _ensure_visible(self) -> None:
        self.deiconify()
        self.state("normal")
        self.attributes("-topmost", True)
        self.lift()
        self.update_idletasks()

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.configure("Primary.TButton", font=("Microsoft YaHei UI", 11, "bold"), padding=8)
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text="高产剪辑助手", font=("Microsoft YaHei UI", 16, "bold")).pack(side="left")
        ttk.Button(header, text="使用说明" if getattr(sys, "frozen", False) else "完整工作台", command=self.open_full).pack(side="right")
        ttk.Label(outer, textvariable=self.status_var, foreground="#147d3f").pack(anchor="w", pady=(2, 7))

        line = ttk.Frame(outer)
        line.pack(fill="x", pady=2)
        ttk.Label(line, text="项目", width=7).pack(side="left")
        ttk.Entry(line, textvariable=self.project_var).pack(side="left", fill="x", expand=True)
        ttk.Combobox(line, textvariable=self.persona_var, state="readonly", values=["口播讲解型", "家庭关怀型", "工厂纪实型", "主播问答型", "对比测评型"], width=12).pack(side="left", padx=(6, 0))

        ttk.Label(outer, text="钩子｜每行一个", font=("Microsoft YaHei UI", 9, "bold")).pack(anchor="w", pady=(7, 2))
        self.hooks = tk.Text(outer, height=4, wrap="word", undo=True)
        self.hooks.pack(fill="x")
        self.hooks.insert("1.0", "很多人挑滋补产品，只看价格，却忽略了原料信息。\n黄精怎么选？先别急着听夸张宣传。")

        ttk.Label(outer, text="正文｜系统按句号自动拆镜头", font=("Microsoft YaHei UI", 9, "bold")).pack(anchor="w", pady=(7, 2))
        self.body = tk.Text(outer, height=7, wrap="word", undo=True)
        self.body.pack(fill="both", expand=True)
        self.body.insert("1.0", "先看原料来源、配料表和真实的产品信息。再看食用方法是否简单，能不能放进日常生活。")

        ttk.Label(outer, text="结尾｜每行一个", font=("Microsoft YaHei UI", 9, "bold")).pack(anchor="w", pady=(7, 2))
        self.ctas = tk.Text(outer, height=3, wrap="word", undo=True)
        self.ctas.pack(fill="x")
        self.ctas.insert("1.0", "看清楚产品信息，再决定适不适合自己。")
        for widget in (self.hooks, self.body, self.ctas):
            widget.bind("<KeyRelease>", lambda _event: self._update_count())

        info = ttk.Frame(outer)
        info.pack(fill="x", pady=(7, 4))
        ttk.Label(info, textvariable=self.count_var, foreground="#315ca8").pack(side="left")
        ttk.Checkbutton(info, text="自动吸附剪映", variable=self.auto_attach, command=self._force_attach).pack(side="right")

        self.generate_button = ttk.Button(outer, text="批量生成剪映草稿", style="Primary.TButton", command=self.generate)
        self.generate_button.pack(fill="x", pady=4)

        tools = ttk.Frame(outer)
        tools.pack(fill="x", pady=3)
        ttk.Button(tools, text="扫描素材", command=self.index_assets).pack(side="left", fill="x", expand=True, padx=(0, 3))
        ttk.Button(tools, text="素材库", command=lambda: os.startfile(self.settings_data["asset_folder"])).pack(side="left", fill="x", expand=True, padx=3)
        ttk.Button(tools, text="草稿目录", command=lambda: os.startfile(self.settings_data["draft_folder"])).pack(side="left", fill="x", expand=True, padx=3)
        ttk.Button(tools, text="启动剪映", command=self.launch_jianying).pack(side="left", fill="x", expand=True, padx=(3, 0))

        ttk.Separator(outer).pack(fill="x", pady=(7, 4))
        ttk.Label(outer, textvariable=self.action_var, foreground="#555", wraplength=350).pack(anchor="w")

    @staticmethod
    def _lines(widget: tk.Text) -> list[str]:
        return [line.strip() for line in widget.get("1.0", "end").splitlines() if line.strip()]

    def _update_count(self) -> None:
        hooks = max(1, len(self._lines(self.hooks)))
        ctas = max(1, len(self._lines(self.ctas)))
        limit = int(self.settings_data.get("max_variants", 12))
        count = min(limit, hooks * ctas)
        self.count_var.set(f"预计生成 {count} 条草稿（钩子 {hooks} × 结尾 {ctas}）")

    def _watch_jianying(self) -> None:
        target = find_jianying_window()
        if target:
            self.status_var.set(f"● 已连接剪映  PID {target['pid']}")
            rect = (target["left"], target["top"], target["right"], target["bottom"])
            if self.auto_attach.get() and rect != self.last_target_rect:
                self.update_idletasks()
                snap_panel(self.winfo_id(), target)
                self.last_target_rect = rect
        else:
            self.status_var.set("○ 剪映未启动，仍可先编辑任务")
            self.last_target_rect = None
        self.after(1000, self._watch_jianying)

    def _force_attach(self) -> None:
        self.last_target_rect = None

    def _set_busy(self, busy: bool, message: str) -> None:
        self.busy = busy
        self.action_var.set(message)
        self.generate_button.configure(state="disabled" if busy else "normal")

    def index_assets(self) -> None:
        if self.busy:
            return
        self._set_busy(True, "正在增量扫描素材库……")

        def work() -> None:
            try:
                assets = scan_assets(self.settings_data)
                self.after(0, lambda: self._finish_ok(f"素材索引完成：{len(assets)} 个文件"))
            except Exception as exc:
                self.after(0, lambda error=exc: self._finish_error("扫描失败", error))

        threading.Thread(target=work, daemon=True).start()

    def generate(self) -> None:
        if self.busy:
            return
        project = self.project_var.get().strip()
        body = self.body.get("1.0", "end").strip()
        if not project or not body:
            messagebox.showwarning("内容不完整", "项目名称和正文不能为空。")
            return
        hooks = self.hooks.get("1.0", "end")
        ctas = self.ctas.get("1.0", "end")
        persona = self.persona_var.get()
        self._set_busy(True, "正在增量索引素材并批量生成草稿……")

        def work() -> None:
            try:
                task_path = create_task_from_text(project, body, hooks, ctas, persona)
                task_data = json.loads(task_path.read_text(encoding="utf-8-sig"))
                results = generate_drafts(task_path, self.settings_data, refresh_assets=True)
                warnings = task_data.get("compliance_warnings", [])
                text = f"完成：生成 {len(results)} 条草稿"
                if warnings:
                    text += "；合规预警：" + "、".join(warnings)
                self.after(0, lambda: self._finish_ok(text, show=True))
            except Exception as exc:
                self.after(0, lambda error=exc: self._finish_error("生成失败", error))

        threading.Thread(target=work, daemon=True).start()

    def _finish_ok(self, text: str, show: bool = False) -> None:
        self._set_busy(False, text)
        if show:
            messagebox.showinfo("剪映草稿已生成", text + "\n\n请回到剪映刷新草稿列表并终审。")

    def _finish_error(self, title: str, exc: Exception) -> None:
        self._set_busy(False, f"{title}：{exc}")
        traceback.print_exception(exc)
        messagebox.showerror(title, str(exc))

    def launch_jianying(self) -> None:
        exe_value = self.settings_data.get("jianying_exe", "")
        exe = Path(exe_value) if exe_value else Path("__missing_jianying__")
        if not exe_value or not exe.exists():
            messagebox.showerror("无法启动", f"没有找到剪映：{exe}")
            return
        subprocess.Popen([str(exe)], cwd=str(exe.parent))

    def open_full(self) -> None:
        if getattr(sys, "frozen", False):
            readme = ROOT / "使用说明.txt"
            if readme.exists():
                os.startfile(readme)
            else:
                messagebox.showinfo("使用说明", "把素材放进程序旁边的“素材库”，再粘贴文案并点击批量生成。")
            return
        pythonw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
        subprocess.Popen([str(pythonw), str(ROOT / "app" / "gui.py")], cwd=str(ROOT))


if __name__ == "__main__":
    FloatingPanel().mainloop()
