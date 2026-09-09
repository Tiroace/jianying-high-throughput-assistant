from __future__ import annotations

import os
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core import ROOT, create_task_from_text, diagnose, generate_drafts, load_settings, save_settings, scan_assets


class EditingAssistant(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("剪辑系统 · 剪映旁路助手 v0.1")
        self.geometry("940x760")
        self.minsize(820, 640)
        self.settings_data = load_settings()
        self.task_var = tk.StringVar(value=str(ROOT / "文案" / "示例任务.json"))
        self.asset_var = tk.StringVar(value=self.settings_data["asset_folder"])
        self.draft_var = tk.StringVar(value=self.settings_data["draft_folder"])
        self.project_var = tk.StringVar(value="黄精内容测试")
        self.persona_var = tk.StringVar(value="家庭关怀型")
        self._build_ui()
        self.after(200, self.run_diagnose)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="剪映旁路助手", font=("Microsoft YaHei UI", 20, "bold")).pack(anchor="w")
        ttk.Label(outer, text="自动装配时间线，剪映负责预览、精修和导出。", foreground="#555").pack(anchor="w", pady=(3, 10))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="x")
        quick = ttk.Frame(notebook, padding=12)
        advanced = ttk.Frame(notebook, padding=12)
        notebook.add(quick, text="快速生成")
        notebook.add(advanced, text="高级任务 JSON")
        self._build_quick(quick)
        self._build_advanced(advanced)

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=10)
        ttk.Button(actions, text="扫描素材库", command=self.run_index).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="环境诊断", command=self.run_diagnose).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="打开素材库", command=lambda: os.startfile(self.asset_var.get())).pack(side="right")

        ttk.Label(outer, text="运行记录", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", pady=(2, 5))
        self.log = tk.Text(outer, height=16, wrap="word", font=("Consolas", 10), bg="#10151c", fg="#d6e2ef", insertbackground="white")
        self.log.pack(fill="both", expand=True)
        self.log.insert("end", "先把自有或已授权素材放入素材库。文件名建议：黄精_原料_特写_01.mp4。\n")

    def _build_quick(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="项目名称").grid(row=0, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.project_var).grid(row=0, column=1, sticky="ew", padx=(8, 18))
        ttk.Label(parent, text="内容类型").grid(row=0, column=2, sticky="w")
        ttk.Combobox(parent, textvariable=self.persona_var, state="readonly", values=["口播讲解型", "家庭关怀型", "工厂纪实型", "主播问答型", "对比测评型"], width=16).grid(row=0, column=3, sticky="ew", padx=(8, 0))

        ttk.Label(parent, text="钩子（每行一个）").grid(row=1, column=0, sticky="nw", pady=(9, 0))
        self.hooks_text = tk.Text(parent, height=3, wrap="word")
        self.hooks_text.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=(9, 0))
        self.hooks_text.insert("1.0", "很多人挑滋补产品，只看价格，却忽略了原料信息。\n黄精怎么选？先别急着听夸张宣传。")

        ttk.Label(parent, text="正文").grid(row=2, column=0, sticky="nw", pady=(9, 0))
        self.body_text = tk.Text(parent, height=5, wrap="word")
        self.body_text.grid(row=2, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=(9, 0))
        self.body_text.insert("1.0", "先看原料来源、配料表和真实的产品信息。再看食用方法是否简单，能不能放进日常生活。")

        ttk.Label(parent, text="结尾（每行一个）").grid(row=3, column=0, sticky="nw", pady=(9, 0))
        self.ctas_text = tk.Text(parent, height=2, wrap="word")
        self.ctas_text.grid(row=3, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=(9, 0))
        self.ctas_text.insert("1.0", "看清楚产品信息，再决定适不适合自己。")

        buttons = ttk.Frame(parent)
        buttons.grid(row=4, column=1, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="保存任务", command=lambda: self.run_quick(False)).pack(side="left", padx=4)
        ttk.Button(buttons, text="保存并生成剪映草稿", command=lambda: self.run_quick(True)).pack(side="left", padx=4)
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(3, weight=1)

    def _build_advanced(self, parent: ttk.Frame) -> None:
        self._row(parent, 0, "任务 JSON", self.task_var, self.choose_task)
        self._row(parent, 1, "素材库", self.asset_var, self.choose_asset_folder)
        self._row(parent, 2, "剪映草稿目录", self.draft_var, self.choose_draft_folder)
        ttk.Button(parent, text="根据 JSON 生成剪映草稿", command=self.run_build).grid(row=3, column=2, sticky="e", pady=(10, 0))

    def _row(self, parent: ttk.Widget, row: int, label: str, variable: tk.StringVar, command) -> None:
        ttk.Label(parent, text=label, width=14).grid(row=row, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(parent, text="选择", command=command).grid(row=row, column=2, pady=5)
        parent.columnconfigure(1, weight=1)

    def choose_task(self) -> None:
        value = filedialog.askopenfilename(initialdir=str(ROOT / "文案"), filetypes=[("JSON 任务", "*.json")])
        if value:
            self.task_var.set(value)

    def choose_asset_folder(self) -> None:
        value = filedialog.askdirectory(initialdir=self.asset_var.get())
        if value:
            self.asset_var.set(value)

    def choose_draft_folder(self) -> None:
        value = filedialog.askdirectory(initialdir=self.draft_var.get())
        if value:
            self.draft_var.set(value)

    def _sync_settings(self) -> dict:
        self.settings_data["asset_folder"] = self.asset_var.get()
        self.settings_data["draft_folder"] = self.draft_var.get()
        save_settings(self.settings_data)
        return self.settings_data

    def write(self, value: str) -> None:
        self.log.insert("end", value.rstrip() + "\n")
        self.log.see("end")
        self.update_idletasks()

    def run_diagnose(self) -> None:
        try:
            self.write("\n=== 环境诊断 ===")
            for name, ok, detail in diagnose(self._sync_settings()):
                self.write(f"[{'OK' if ok else 'FAIL'}] {name}: {detail}")
        except Exception:
            self.write(traceback.format_exc())

    def run_index(self) -> None:
        try:
            self.write("\n=== 扫描素材库 ===")
            assets = scan_assets(self._sync_settings())
            self.write(f"完成：共索引 {len(assets)} 个素材。")
        except Exception as exc:
            self.write(traceback.format_exc())
            messagebox.showerror("扫描失败", str(exc))

    def run_quick(self, build: bool) -> None:
        try:
            task = create_task_from_text(
                self.project_var.get(),
                self.body_text.get("1.0", "end"),
                self.hooks_text.get("1.0", "end"),
                self.ctas_text.get("1.0", "end"),
                self.persona_var.get(),
            )
            self.task_var.set(str(task))
            self.write(f"已保存任务：{task}")
            if build:
                self._build_task(task)
        except Exception as exc:
            self.write(traceback.format_exc())
            messagebox.showerror("任务失败", str(exc))

    def _build_task(self, task: Path) -> None:
        results = generate_drafts(task, self._sync_settings(), refresh_assets=True)
        for result in results:
            self.write(f"已生成 {result['draft']}，时长 {result['duration']} 秒")
        self.write("请重启剪映或进出一次已有草稿，刷新草稿列表。")
        messagebox.showinfo("生成完成", f"已生成 {len(results)} 个可编辑剪映草稿。")

    def run_build(self) -> None:
        try:
            self.write("\n=== 生成剪映草稿 ===")
            task = Path(self.task_var.get())
            if not task.exists():
                raise FileNotFoundError(f"任务文件不存在：{task}")
            self._build_task(task)
        except FileExistsError as exc:
            self.write(str(exc))
            messagebox.showwarning("草稿已存在", "为保护已有草稿，系统没有覆盖。请修改项目名称后再试。")
        except Exception as exc:
            self.write(traceback.format_exc())
            messagebox.showerror("生成失败", str(exc))


if __name__ == "__main__":
    EditingAssistant().mainloop()
