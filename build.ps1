# Скрипт сборки исполняемого файла
# Использование: .\build.ps1

pip install pyinstaller --quiet
python -m PyInstaller --onefile --windowed --name ChatList main.py
Write-Host "`nГотово! Исполняемый файл: dist\ChatList.exe" -ForegroundColor Green
