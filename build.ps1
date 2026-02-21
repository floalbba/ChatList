# Скрипт сборки исполняемого файла
# Использование: .\build.ps1

$version = (python -c "from version import __version__; print(__version__)").Trim()
$name = "ChatList-$version"

pip install pyinstaller --quiet
python -m PyInstaller --onefile --windowed --name $name main.py
Write-Host ""
Write-Host ("Ready: dist\" + $name + ".exe") -ForegroundColor Green
