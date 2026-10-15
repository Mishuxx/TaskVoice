@echo off
echo Building Taskmaster...
pip install -r requirements.txt
pyinstaller --onefile --windowed --name Taskmaster --icon=assets/icon.ico main.py
echo Done! Check dist/Taskmaster.exe
pause
