Set WshShell = CreateObject("WScript.Shell")
' Executa o main.py com o argumento --daemon e modo janela oculta (0)
WshShell.Run "pythonw.exe main.py --daemon", 0, False
