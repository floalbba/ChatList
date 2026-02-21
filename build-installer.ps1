# Сборка инсталлятора с помощью Inno Setup
# Использование: .\build-installer.ps1
# Требования: Inno Setup (https://jrsoftware.org/isinfo.php)

Set-Location $PSScriptRoot
$version = (python -c "from version import __version__; print(__version__)").Trim()

# Проверка наличия exe
$exePath = "dist\ChatList-$version.exe"
if (-not (Test-Path $exePath)) {
    Write-Host "Создание exe..." -ForegroundColor Yellow
    & .\build.ps1
}

# Создание папки для инсталлятора
New-Item -ItemType Directory -Force -Path "installer" | Out-Null

# Подстановка версии в installer.iss
$issContent = Get-Content "installer.iss" -Raw -Encoding UTF8
$issContent = $issContent -replace '\{\{VERSION\}\}', $version
$issPath = "installer.iss.generated"
$issContent | Set-Content $issPath -Encoding UTF8

# Запуск Inno Setup
$iscc = "iscc"
if (-not (Get-Command $iscc -ErrorAction SilentlyContinue)) {
    $isccPath = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    if (Test-Path $isccPath) {
        & $isccPath $issPath
    } else {
        Write-Host "Inno Setup не найден. Установите с https://jrsoftware.org/isinfo.php" -ForegroundColor Red
        exit 1
    }
} else {
    & $iscc $issPath
}

Remove-Item $issPath -ErrorAction SilentlyContinue

$installerPath = (Get-Location).Path + "\installer\ChatList-$version-Setup.exe"
if (Test-Path $installerPath) {
    Write-Host "`nГотово! Инсталлятор создан:" -ForegroundColor Green
    Write-Host $installerPath -ForegroundColor Cyan
} else {
    Write-Host "`nПроверьте вывод выше — возможно, Inno Setup не установлен." -ForegroundColor Yellow
}
