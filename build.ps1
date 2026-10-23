# Gera dist\clak820\ (executáveis) e dist\clak820-<versão>-windows-x64.zip
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

python -m pip install -e ".[build]" --quiet
python -m pytest -q
python packaging/make_icon.py
python -m PyInstaller packaging/clak820.spec --noconfirm --clean --distpath dist --workpath build

$version = python -c "import clak820; print(clak820.__version__)"
$zip = "dist\clak820-$version-windows-x64.zip"
Remove-Item $zip -ErrorAction SilentlyContinue
Compress-Archive -Path dist\clak820 -DestinationPath $zip
Write-Host "Pronto: $zip"
