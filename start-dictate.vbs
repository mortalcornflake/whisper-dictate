' Launch Whisper Dictate quietly on Windows (no console window) by running
' start-dictate.bat hidden. Used by the Startup shortcut (auto-start at login)
' and the Desktop shortcut (manual start).
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
bat = fso.GetParentFolderName(WScript.ScriptFullName) & "\start-dictate.bat"
sh.Run Chr(34) & bat & Chr(34), 0, False
