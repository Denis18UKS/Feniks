$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (Get-Command dotnet -ErrorAction SilentlyContinue) {
    dotnet publish windows-bridge/Feniks.WindowsBridge.csproj -c Release -r win-x64 --self-contained false -o feniks/bin
} else {
    Write-Warning ".NET SDK not found: Windows bridge will not be included."
}

python -m pip install -r requirements.txt
python -m PyInstaller FeniksAIStudio.spec --noconfirm --clean
Write-Host "Built: dist/FeniksAIStudio.exe" -ForegroundColor Green
