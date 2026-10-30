@echo off
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt pyinstaller
py -3 -m PyInstaller --noconfirm --onefile --windowed --name NUT65-Control run.py
echo.
echo Done: dist\NUT65-Control.exe
pause
