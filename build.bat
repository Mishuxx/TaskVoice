@echo off
echo Building BountyHunter...
pip install -r requirements.txt
pyinstaller --onefile --windowed --name BountyHunter --icon=assets/icon.ico main.py
echo Done! Check dist/BountyHunter.exe
pause
