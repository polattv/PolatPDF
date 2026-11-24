# Polat PDF'i exe + kurulum dosyası olarak derler. "-Yayinla" verilirse GitHub'a yeni sürüm (Release) olarak yükler.
# Kullanım: önce surum.txt'yi artır, sonra:  powershell -ExecutionPolicy Bypass -File derle.ps1 -Yayinla
param([switch]$Yayinla)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$surum = (Get-Content surum.txt -Raw).Trim()
if ($Yayinla -and (git status --porcelain)) { throw "Kaydedilmemiş (commit edilmemiş) değişiklik var; önce commit edin" }

python -c "import tema; tema.logo(256).save('polatpdf.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
if ($LASTEXITCODE) { throw "Simge yapılamadı" }

python -m PyInstaller --noconfirm --clean --onedir --windowed --name PolatPDF --icon polatpdf.ico `
    --add-data "surum.txt;." --collect-submodules fontTools pdf_duzenleyici.py
if ($LASTEXITCODE) { throw "PyInstaller başarısız" }

$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 bulunamadı" }
& $iscc /Q "/DSurum=$surum" kurulum.iss
if ($LASTEXITCODE) { throw "Inno Setup başarısız" }
$kurulum = "Output\PolatPDF-Kurulum-$surum.exe"
Write-Host "Hazır: $kurulum"

if ($Yayinla) {
    git push
    if ($LASTEXITCODE) { throw "git push başarısız" }
    gh release create "v$surum" $kurulum --target (git rev-parse HEAD) --title "Polat PDF $surum" --notes "Polat PDF $surum"
    if ($LASTEXITCODE) { throw "GitHub'a yüklenemedi" }
}
