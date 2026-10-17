# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包設定檔 - GameScript Pro
打包為單一 EXE 執行檔，內嵌 assets 與驅動程式
"""

import sys
import os
from pathlib import Path

block_cipher = None

project_dir = os.path.abspath(SPECPATH)

datas = [
    (os.path.join(project_dir, 'assets'), 'assets'),
]

hidden_imports = [
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'win32gui',
    'win32process',
    'win32con',
    'win32api',
    'pynput',
    'pynput.keyboard',
    'pynput.mouse',
    'keyboard',
    'vgamepad',
    'PIL',
    'cv2',
]

a = Analysis(
    ['main.py'],
    pathex=[project_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'numpy.tests'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GameScriptPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,             # 無控制台黑視窗 (GUI 模式)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,            # 請求管理員權限以支援底層驅動與全域鍵鼠監聽
    icon=None,
)
