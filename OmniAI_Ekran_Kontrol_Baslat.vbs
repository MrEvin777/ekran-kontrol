' Tek baslatici: Ollama'yi hazirlar, kurulum kontrolunu loglar, sonra Jarvis'i acar.
' pyw.exe (Python Launcher for Windows) her Python kurulumunda PATH'te olur -- belirli
' bir surume sabit yol vermekten daha tasinabilir (bkz. launch.py).
Set WshShell = CreateObject("WScript.Shell")
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "pyw """ & scriptDir & "\launch.py""", 0, False
