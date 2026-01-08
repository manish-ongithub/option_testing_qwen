# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Indian Options Paper Trading Application

Build command (run from project root):
    pyinstaller PaperTradeApp.spec

This will create:
    - dist/PaperTradeApp/  (folder with all files)
    - dist/PaperTradeApp.exe (main executable)
"""

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Get the absolute path of the project
project_root = os.path.abspath(SPECPATH)
paper_trade_path = os.path.join(project_root, 'paper_trade_app')

# Collect all paper_trade_app submodules
hidden_imports = [
    # Core modules
    'paper_trade_app',
    'paper_trade_app.core',
    'paper_trade_app.core.alert_normalizer',
    'paper_trade_app.core.alert_watcher',
    'paper_trade_app.core.alice_utils',
    'paper_trade_app.core.data_feed',
    'paper_trade_app.core.database',
    'paper_trade_app.core.fee_calculator',
    'paper_trade_app.core.instrument_mapper',
    'paper_trade_app.core.lot_sizes',
    'paper_trade_app.core.market_simulator',
    'paper_trade_app.core.report_generator',
    'paper_trade_app.core.session_manager',
    'paper_trade_app.core.simulator_worker',
    'paper_trade_app.core.trade_manager',
    'paper_trade_app.ui',
    'paper_trade_app.ui.dashboard',
    'paper_trade_app.main',
    # PyQt6 modules
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtWebEngineCore',
    'PyQt6.sip',
    # Third-party dependencies
    'pandas',
    'numpy',
    'requests',
    'websocket',
    'watchdog',
    'watchdog.observers',
    'watchdog.events',
    'fpdf',
    'xlsxwriter',
    'reportlab',
    'reportlab.lib',
    'reportlab.lib.pagesizes',
    'reportlab.lib.styles',
    'reportlab.lib.units',
    'reportlab.platypus',
    'reportlab.pdfgen',
    # Database (optional - for PostgreSQL support)
    'psycopg2',
    # Peewee ORM (used in database.py)
    'peewee',
]

# Data files to include
datas = [
    # Include paper_trade_app package
    (os.path.join(project_root, 'paper_trade_app'), 'paper_trade_app'),
    # Include CSV data files
    (os.path.join(paper_trade_path, 'NSE.csv'), 'paper_trade_app'),
    (os.path.join(paper_trade_path, 'NFO.csv'), 'paper_trade_app'),
    (os.path.join(paper_trade_path, 'INDICES.csv'), 'paper_trade_app'),
]

# Binaries (Qt plugins will be auto-collected by PyInstaller for PyQt6)
binaries = []

a = Analysis(
    [os.path.join(paper_trade_path, 'main.py')],
    pathex=[project_root, paper_trade_path],
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
    name='PaperTradeApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to True if you want to see console output for debugging
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add path to .ico file if you have one: 'assets/paper_trade_icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PaperTradeApp',
)

