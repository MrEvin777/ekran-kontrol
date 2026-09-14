# Jarvis (Evin's AI OS) - Windows kurulum. launch.py + mevcut arkana_v2.py'yi
# degistirmez, sadece bagimliliklari kurar.
$ErrorActionPreference = "Continue"  # native araclarin stderr'i (uyarilar) PS 5.1'de Stop ile fatal sayiliyor
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "1) Python kontrolu..." -ForegroundColor Cyan
$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) { Write-Host "HATA: Python bulunamadi. python.org'dan kurun." -ForegroundColor Red; exit 1 }
py --version

Write-Host "2) Bagimliliklar kuruluyor..." -ForegroundColor Cyan
py -m pip install --upgrade pip --quiet
py -m pip install -r "$root\requirements.txt"

Write-Host "3) Gerekli klasorler..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.omniai" | Out-Null
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.omniai\tessdata" | Out-Null

Write-Host "4) config.json kontrolu..." -ForegroundColor Cyan
$cfg = "$env:USERPROFILE\.omniai\config.json"
if (-not (Test-Path $cfg)) {
    "{}" | Out-File -FilePath $cfg -Encoding utf8
    Write-Host "   Bos config.json olusturuldu. API anahtarlarini uygulama icinden 'Ayarlar'dan girin." -ForegroundColor Yellow
} else {
    Write-Host "   Mevcut config.json korunuyor (uzerine yazilmadi)." -ForegroundColor Green
}

Write-Host "5) Kurulum kontrolu calistiriliyor..." -ForegroundColor Cyan
py "$root\setup_check.py" 2>&1 | Out-Null
py -c "import sys; sys.path.insert(0,r'$root'); import setup_check, json; [print(('[OK] ' if r['ok'] else '[HATA] ') + r['name'] + ': ' + r['detail']) for r in setup_check.run_all()]"

Write-Host "`nKurulum tamamlandi. Baslatmak icin: .\start_windows.ps1 veya masaustundeki Jarvis kisayolu." -ForegroundColor Green
