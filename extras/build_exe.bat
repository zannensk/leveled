@echo off
echo Building Leveled executable...
echo Make sure you have PyInstaller installed (pip install pyinstaller)

pyinstaller --noconfirm --onedir --windowed --add-data "ui/dashboard.html;ui" --name "Leveled" main.py

echo Build complete! Check the /dist directory.
pause
