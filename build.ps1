# Gera em dist\:
#   clak820\                              executáveis (clak820.exe + clak820-cli.exe)
#   clak820-<versão>-setup.exe            instalador
#   clak820-<versão>-windows-x64.zip      versão portátil
$ErrorActionPreference = 'Continue'  # erros checados via $LASTEXITCODE
Set-Location $PSScriptRoot

python -m pip install -e ".[build]" --quiet --no-warn-script-location
if ($LASTEXITCODE) { throw "pip falhou" }
python -m pytest -q
if ($LASTEXITCODE) { throw "testes falharam" }
python packaging/make_icon.py
python -m PyInstaller packaging/clak820.spec --noconfirm --clean --distpath dist --workpath build
if ($LASTEXITCODE) { throw "PyInstaller falhou" }

$version = python -c "import clak820; print(clak820.__version__)"

$zip = "dist\clak820-$version-windows-x64.zip"
Remove-Item $zip -ErrorAction SilentlyContinue
Compress-Archive -Path dist\clak820 -DestinationPath $zip

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 não encontrado (winget install JRSoftware.InnoSetup)" }
& $iscc /Q "/DAppVersion=$version" packaging\clak820.iss
if ($LASTEXITCODE) { throw "Inno Setup falhou" }

Write-Host "Pronto:"
Get-ChildItem dist -File | ForEach-Object { Write-Host ("  {0}  ({1:N1} MB)" -f $_.Name, ($_.Length / 1MB)) }
