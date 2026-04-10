Set WshShell = CreateObject("WScript.Shell")

' Start the consolidated TaskOverlay process
' If you built the executable, you can change this to:
' WshShell.Run "dist\TaskOverlay\TaskOverlay.exe", 0

WshShell.Run "pythonw main.py", 0

Set WshShell = Nothing
