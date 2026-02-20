# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Warehouse Activity Tracker.
Produces a single windowed (no-console) exe.
"""

block_cipher = None

a = Analysis(
    ['tracker.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # pynput backend hooks
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        # pystray backend
        'pystray._win32',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='WarehouseTracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # disabled to reduce AV false-positives
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Use a 1-pixel icon so Windows gives the process a proper taskbar identity
    # Replace with a real .ico path if you have one
    # icon='icon.ico',
)
