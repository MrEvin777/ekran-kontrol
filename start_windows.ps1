# Jarvis baslatici (PowerShell surumu). launch.py'nin yaptigi ayni sey:
# Ollama'yi hazirlar, kurulum kontrolunu loglar, uygulamayi acar.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Jarvis baslatiliyor..." -ForegroundColor Cyan
try {
    py "$root\launch.py"
} catch {
    Write-Host "HATA: $_" -ForegroundColor Red
    Write-Host "Once .\install_windows.ps1 calistirdiniz mi?" -ForegroundColor Yellow
    exit 1
}
