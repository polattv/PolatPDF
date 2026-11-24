# Polat PDF'i exe + kurulum dosyası olarak derler. "-Yayinla" verilirse GitHub'a yeni sürüm (Release) olarak yükler.
# Kullanım: önce surum.txt'yi artır, sonra:  powershell -ExecutionPolicy Bypass -File derle.ps1 -Yayinla
param([switch]$Yayinla)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$surum = (Get-Content surum.txt -Raw).Trim()
if ($Yayinla -and (git status --porcelain)) { throw "Kaydedilmemiş (commit edilmemiş) değişiklik var; önce commit edin" }

# her boyut ayrı çizilir: 40 px altı logo daha kalın/sade (büyükten küçültmek görev çubuğunda bulanık olurdu)
python -c "import tema; b=[256,128,64,48,32,24,16]; r=[tema.logo(s) for s in b]; r[0].save('polatpdf.ico', sizes=[(s,s) for s in b], append_images=r[1:])"
if ($LASTEXITCODE) { throw "Simge yapılamadı" }

python -m PyInstaller --noconfirm --clean --onedir --windowed --name PolatPDF --icon polatpdf.ico `
    --add-data "surum.txt;." --add-data "tessdata;tessdata" --collect-submodules fontTools pdf_duzenleyici.py
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
    foreach ($deneme in 1..3) {  # GitHub bağlantısı ara sıra kopuyor: birkaç kez dene
        gh release create "v$surum" $kurulum --target (git rev-parse HEAD) --title "Polat PDF $surum" --notes "Polat PDF $surum"
        if (-not $LASTEXITCODE) { break }
        Start-Sleep 5
    }
    if ($LASTEXITCODE) { throw "GitHub'a yüklenemedi" }
}
