from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys
import traceback
from datetime import datetime
from pathlib import Path


ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "日志"
LOG_PATH = LOG_DIR / "启动错误.log"
ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9


def focus_existing_panel() -> None:
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def callback(hwnd: int, _lparam: int) -> bool:
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, title, length + 1)
        if title.value == "剪映 · 高产剪辑助手":
            ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            return False
        return True

    ctypes.windll.user32.EnumWindows(callback, 0)


def show_error(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(None, message, "剪映高产剪辑助手 - 启动失败", 0x10)


try:
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "JianYingHighThroughputAssistant")
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        focus_existing_panel()
        raise SystemExit(0)
    from floating_panel import FloatingPanel

    FloatingPanel().mainloop()
except Exception:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    detail = traceback.format_exc()
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[{datetime.now().isoformat(timespec='seconds')}]\n{detail}\n")
    show_error(f"程序启动失败，错误已经写入：\n{LOG_PATH}\n\n{detail[-1000:]}")
