# Building Windows Installers

This guide explains how to create Windows installers (`.exe`) for both applications:
1. **Smart Options Screener** - Options scanning and analysis tool
2. **Paper Trade App** - Paper trading simulator for options

## Prerequisites

### On Windows Machine:

1. **Python 3.10+** installed
2. **Git** (to clone the repository)

## Step-by-Step Build Process

### Step 1: Clone and Setup

```powershell
# Clone the repository
git clone https://github.com/yourusername/option_testing_qwen.git
cd option_testing_qwen

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r venv_requirements.txt

# Install PyInstaller
pip install pyinstaller
```

### Step 2: Build with PyInstaller

#### Option A: Build Both Applications (Recommended)

```powershell
# Run the all-in-one build script
.\build_all.bat
```

#### Option B: Build Individual Applications

```powershell
# Build Options Screener only
.\build_installer.bat

# OR Build Paper Trade App only
.\build_paper_trade.bat
```

#### Option C: Manual Build

```powershell
# Activate virtual environment
.\venv\Scripts\activate

# Build Options Screener
pyinstaller OptionsScreener.spec

# Build Paper Trade App
pyinstaller PaperTradeApp.spec
```

This creates:
- `dist\OptionsScreener\OptionsScreener.exe` - Options Screener
- `dist\PaperTradeApp\PaperTradeApp.exe` - Paper Trade App

### Step 3: Test the Builds

```powershell
# Test Options Screener
.\dist\OptionsScreener\OptionsScreener.exe

# Test Paper Trade App
.\dist\PaperTradeApp\PaperTradeApp.exe
```

### Step 4: Create Installers with Inno Setup

1. **Download Inno Setup**: https://jrsoftware.org/isdl.php
2. **Install Inno Setup** on your Windows machine

#### For Options Screener:
3. Open `installer\OptionsScreener_Setup.iss` in Inno Setup
4. Click Build > Compile (or Ctrl+F9)
5. Output: `installer\output\OptionsScreener_Setup_v3.3.exe`

#### For Paper Trade App:
3. Open `installer\PaperTradeApp_Setup.iss` in Inno Setup
4. Click Build > Compile (or Ctrl+F9)
5. Output: `installer\output\PaperTradeApp_Setup_v1.0.exe`

## Directory Structure After Build

```
option_testing_qwen/
├── dist/
│   ├── OptionsScreener/
│   │   ├── OptionsScreener.exe       # Options Screener executable
│   │   ├── *.dll                     # Required DLLs
│   │   ├── PyQt6/                    # Qt libraries
│   │   └── screener/                 # Application modules
│   └── PaperTradeApp/
│       ├── PaperTradeApp.exe         # Paper Trade App executable
│       ├── *.dll                     # Required DLLs
│       ├── PyQt6/                    # Qt libraries
│       └── paper_trade_app/          # Application modules
├── build/                            # Build artifacts (can be deleted)
├── installer/
│   ├── OptionsScreener_Setup.iss     # Inno Setup script
│   ├── PaperTradeApp_Setup.iss       # Inno Setup script
│   └── output/
│       ├── OptionsScreener_Setup_v3.3.exe  # Options Screener installer
│       └── PaperTradeApp_Setup_v1.0.exe    # Paper Trade App installer
├── OptionsScreener.spec              # PyInstaller spec file
├── PaperTradeApp.spec                # PyInstaller spec file
├── build_all.bat                     # Build both apps
├── build_installer.bat               # Build Options Screener only
└── build_paper_trade.bat             # Build Paper Trade App only
```

## Troubleshooting

### Issue: "Qt platform plugin could not be initialized"
**Solution**: Make sure PyQt6 is properly installed and the build includes Qt plugins.

```powershell
pip uninstall PyQt6 PyQt6-Qt6 PyQt6-sip
pip install PyQt6
```

### Issue: Missing DLLs
**Solution**: Install Visual C++ Redistributable:
- Download from: https://aka.ms/vs/17/release/vc_redist.x64.exe

### Issue: App crashes on startup
**Solution**: Build with console enabled to see errors:

Edit `OptionsScreener.spec`:
```python
exe = EXE(
    ...
    console=True,  # Change from False to True
    ...
)
```

### Issue: Module not found
**Solution**: Add the module to `hidden_imports` in `OptionsScreener.spec`:
```python
hidden_imports = [
    ...
    'missing_module_name',
]
```

## Quick Build Script

Create `build_installer.bat` for one-click building:

```batch
@echo off
echo Building Options Screener...

REM Activate virtual environment
call venv\Scripts\activate

REM Clean previous builds
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

REM Build with PyInstaller
pyinstaller OptionsScreener.spec

echo.
echo Build complete! 
echo Executable: dist\OptionsScreener\OptionsScreener.exe
echo.
echo Now open installer\OptionsScreener_Setup.iss in Inno Setup to create the installer.
pause
```

## Adding an Application Icon

1. Create a `.ico` file (256x256 pixels recommended)
2. Place it at `assets/icon.ico`
3. Update `OptionsScreener.spec`:
   ```python
   exe = EXE(
       ...
       icon='assets/icon.ico',
       ...
   )
   ```
4. Update `installer/OptionsScreener_Setup.iss`:
   ```ini
   SetupIconFile=..\assets\icon.ico
   UninstallDisplayIcon={app}\{#MyAppExeName}
   ```

## Distribution

After building, distribute the installers:
- `installer/output/OptionsScreener_Setup_v3.3.exe` - Options Screener
- `installer/output/PaperTradeApp_Setup_v1.0.exe` - Paper Trade App

Users can run these installers on any Windows 10/11 x64 machine.

## Application-Specific Notes

### Paper Trade App
The Paper Trade App requires additional setup after installation:
1. Copy `config_example.py` to `config.py` in the installation directory
2. Edit `config.py` with your API credentials (if using live data)
3. Place alert JSON files in the `alerts_inbox` folder

### Options Screener
No additional configuration needed - works out of the box.

