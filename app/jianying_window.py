from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import Any


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
GA_ROOT = 2
HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SPI_GETWORKAREA = 0x0030
SW_RESTORE = 9

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL


def _process_path(pid: int) -> str:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value
        return ""
    finally:
        kernel32.CloseHandle(handle)


def find_jianying_window() -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width < 500 or height < 350:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process_path = _process_path(pid.value)
        title_len = user32.GetWindowTextLengthW(hwnd)
        title_buffer = ctypes.create_unicode_buffer(title_len + 1)
        user32.GetWindowTextW(hwnd, title_buffer, title_len + 1)
        title = title_buffer.value
        exe = Path(process_path).name.lower() if process_path else ""
        title_fallback = not exe and ("剪映" in title or "jianying" in title.lower())
        if exe == "jianyingpro.exe" or title_fallback:
            candidates.append({
                "hwnd": int(hwnd), "pid": int(pid.value), "title": title, "process_path": process_path,
                "left": rect.left, "top": rect.top, "right": rect.right, "bottom": rect.bottom,
                "width": width, "height": height,
            })
        return True

    user32.EnumWindows(callback, 0)
    if not candidates:
        return None
    candidates.sort(key=lambda item: item["width"] * item["height"], reverse=True)
    return candidates[0]


def snap_panel(panel_hwnd: int, target: dict[str, Any], width: int = 390, height: int = 740) -> tuple[int, int, int, int]:
    root_hwnd = user32.GetAncestor(panel_hwnd, GA_ROOT) or panel_hwnd
    work = wintypes.RECT()
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(work), 0)
    gap = 8
    if work.right - target["right"] >= width + gap:
        x = target["right"] + gap
    elif target["left"] - work.left >= width + gap:
        x = target["left"] - width - gap
    else:
        x = max(work.left, target["right"] - width - 18)
    y = max(work.top, target["top"] + 38)
    panel_height = min(height, max(480, work.bottom - y))
    user32.ShowWindow(root_hwnd, SW_RESTORE)
    moved = user32.SetWindowPos(root_hwnd, wintypes.HWND(HWND_TOPMOST), x, y, width, panel_height, SWP_NOACTIVATE)
    if not moved:
        raise ctypes.WinError()
    return x, y, width, panel_height


if __name__ == "__main__":
    print(find_jianying_window())
