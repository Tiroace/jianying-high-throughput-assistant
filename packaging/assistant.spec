# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_all


project_root = Path(SPECPATH).resolve().parent
datas = []
binaries = []
hiddenimports = []
for package in ("pyJianYingDraft", "pymediainfo", "imageio", "PIL", "uiautomation", "comtypes"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

a = Analysis(
    [str(project_root / "app" / "start_panel.py")],
    pathex=[str(project_root / "app")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "IPython", "matplotlib", "pandas"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="剪映高产剪辑助手",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="剪映高产剪辑助手",
)
