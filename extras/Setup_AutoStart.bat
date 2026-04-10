@echo off
echo Setting up Leveled to run on Windows startup...
echo.

set "startup_folder=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "target_vbs=%~dp0Leveled_Start.vbs"
set "shortcut_vbs=%startup_folder%\Leveled_Start.vbs"

:: Create a small VBS wrapper in the startup folder that explicitly uses wscript.exe
:: This guarantees it runs silently and bypasses any broken .vbs file associations
echo Set WshShell = CreateObject("WScript.Shell") > "%shortcut_vbs%"
echo WshShell.Run "wscript.exe """ ^& "%target_vbs%" ^& """", 0 >> "%shortcut_vbs%"
echo Set WshShell = Nothing >> "%shortcut_vbs%"

echo Startup script successfully created at:
echo %shortcut_vbs%
echo.
echo Leveled will now start automatically when you log in.
echo You can close this window now.
pause
