# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Smart Options Screener v3.3

Build command (run from project root):
    pyinstaller OptionsScreener.spec

This will create:
    - dist/OptionsScreener/  (folder with all files)
    - dist/OptionsScreener.exe (main executable)
"""

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Get the absolute path of the project
project_root = os.path.abspath(SPECPATH)

# Collect all screener submodules
hidden_imports = [
    'screener',
    'screener.api',
    'screener.api.market_status',
    'screener.api.nse_session',
    'screener.api.option_chain',
    'screener.iv',
    'screener.iv.historical',
    'screener.iv.opstra',
    'screener.iv.opstra_login',
    'screener.iv.provider',
    'screener.output',
    'screener.output.csv_logger',
    'screener.output.json_logger',
    'screener.scanners',
    'screener.scanners.index',
    'screener.scanners.stock',
    'screener.strategies',
    'screener.strategies.bear_put_spread',
    'screener.strategies.bull_call_spread',
    'screener.strategies.helpers',
    'screener.strategies.long_straddle',
    'screener.strategies.long_strangle',
    'screener.utils',
    'screener.utils.helpers',
    'screener.utils.logging_setup',
    'screener.config',
    'screener.main',
    'screener.ui',
    'screener.ui.screener_gui',
    # PyQt6 modules
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.sip',
    # Third-party dependencies
    'pandas',
    'numpy',
    'scipy',
    'requests',
    'httpx',
    'beautifulsoup4',
    'nsepython',
    'yfinance',
    'schedule',
    'watchdog',
]

# Data files to include
datas = [
    # Include screener package
    (os.path.join(project_root, 'screener'), 'screener'),
]

# Binaries (Qt plugins will be auto-collected by PyInstaller for PyQt6)
binaries = []

a = Analysis(
    [os.path.join(project_root, 'screener', 'ui', 'screener_gui.py')],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OptionsScreener',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to True if you want to see console output for debugging
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add path to .ico file if you have one: 'assets/icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='OptionsScreener',
)

