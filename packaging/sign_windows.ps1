# rdpctl - Windows kod imzalama yardımcısı
# ---------------------------------------------------------------------------
# Kod imzalama, "virüs/bilinmeyen yayımcı" uyarılarının ASIL çözümüdür:
# dosyaya DOĞRULANABİLİR bir yayımcı kimliği ekler. Bir Authenticode kod
# imzalama sertifikası gerektirir (bir sertifika yetkilisinden alınır).
#
# Kullanım (yönetici PowerShell):
#   .\packaging\sign_windows.ps1 -Pfx "C:\yol\sertifika.pfx" -Password "***"
# veya mağazadaki bir sertifikayla:
#   .\packaging\sign_windows.ps1 -Thumbprint "AB12...EF"
#
# EV (Extended Validation) sertifikası, SmartScreen güvenini ANINDA sağlar.
# Standart (OV) sertifikada güven, indirme sayısı arttıkça birikir.
param(
    [string]$Pfx,
    [string]$Password,
    [string]$Thumbprint,
    [string]$TimestampUrl = "http://timestamp.digicert.com",
    [string[]]$Files = @("dist\rdpctl.exe", "dist\rdpctl-kaldir.exe")
)

$ErrorActionPreference = "Stop"

# signtool.exe'yi bul (Windows SDK ile gelir)
$signtool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" `
    -ErrorAction SilentlyContinue | Sort-Object FullName | Select-Object -Last 1
if (-not $signtool) {
    Write-Host "signtool.exe bulunamadi. Windows SDK kurun:" -ForegroundColor Red
    Write-Host "  https://developer.microsoft.com/windows/downloads/windows-sdk/"
    exit 1
}

foreach ($f in $Files) {
    if (-not (Test-Path $f)) { Write-Host "Atlandi (yok): $f" -ForegroundColor Yellow; continue }
    Write-Host "Imzalaniyor: $f" -ForegroundColor Cyan
    if ($Thumbprint) {
        & $signtool.FullName sign /sha1 $Thumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 $f
    } elseif ($Pfx) {
        & $signtool.FullName sign /f $Pfx /p $Password /fd SHA256 /tr $TimestampUrl /td SHA256 $f
    } else {
        Write-Host "Sertifika verilmedi (-Pfx veya -Thumbprint gerekli)." -ForegroundColor Red
        exit 1
    }
    & $signtool.FullName verify /pa /v $f
}
Write-Host "Imzalama tamam." -ForegroundColor Green
