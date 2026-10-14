@echo off
echo Building TaskVoice...
pip install -r requirements.txt
pyinstaller --onefile --windowed --name TaskVoice --icon=assets/icon.ico main.py
echo Done! Check dist/TaskVoice.exe
pause
