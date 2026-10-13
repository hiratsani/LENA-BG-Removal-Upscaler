param(
    [string]$Python = "$PSScriptRoot/.venv/Scripts/python.exe",
    [string]$Compiler = '',
    [switch]$AppOnly,
    [string]$InstallerName = 'LENA'
)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (!(Test-Path -LiteralPath $Python)) { throw 'Create .venv and install requirements-build.txt first. See README.md.' }
    & $Python prepare_models.py --verify-only
    if ($LASTEXITCODE -ne 0) { throw 'Run prepare_models.py before building.' }
    & $Python make_notices.py
    if ($LASTEXITCODE -ne 0) { throw 'Third-party notice generation failed.' }
    & $Python -m PyInstaller --clean --noconfirm --windowed --name LENA --distpath .build/dist --workpath .build/work --specpath .build --icon "$PSScriptRoot/assets/LENA.ico" --version-file "$PSScriptRoot/version.txt" --add-data "$PSScriptRoot/assets;assets" --add-data "$PSScriptRoot/licenses;licenses" --add-data "$PSScriptRoot/THIRD-PARTY-NOTICES.txt;." --add-data "$PSScriptRoot/../LICENSE;." --additional-hooks-dir . --collect-all customtkinter --collect-all PIL --hidden-import PIL._imaging --hidden-import PIL._imagingtk --collect-binaries onnxruntime --exclude-module openvino --exclude-module torch --exclude-module torchvision --exclude-module timm --exclude-module transformers --exclude-module kornia --exclude-module pandas --exclude-module matplotlib --exclude-module sympy --exclude-module onnx.reference --exclude-module onnx.backend.test --exclude-module pymupdf --exclude-module fitz --exclude-module fontTools --exclude-module resvg_py --exclude-module huggingface_hub lena_app.py
    if ($LASTEXITCODE -ne 0) { throw 'Application build failed.' }
    $pillowImaging = Get-ChildItem -LiteralPath '.build/dist/LENA/_internal/PIL' -Filter '_imaging*.pyd' -ErrorAction SilentlyContinue
    if (!$pillowImaging) { throw 'Pillow native extension was not bundled.' }
    & $Python trim_bundle.py
    if ($LASTEXITCODE -ne 0) { throw 'Bundle optimization failed.' }
    Copy-Item -LiteralPath README.md,MODEL-GUIDE.md,GPU-AUDIT.md,THIRD-PARTY-NOTICES.txt -Destination .build/dist/LENA/
    if ($AppOnly) { return }
    if (!$Compiler) {
        $Compiler = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
            "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
        ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
    if (!$Compiler -or !(Test-Path -LiteralPath $Compiler)) { throw 'Install Inno Setup 6 or pass -Compiler with its ISCC.exe path.' }
    & $Compiler /Q "/F$InstallerName" installer.iss
    if ($LASTEXITCODE -ne 0) { throw 'Installer build failed.' }
    Write-Host "Installer ready: $(Join-Path (Split-Path $PSScriptRoot -Parent) "Installer/$InstallerName.exe")"
}
finally { Pop-Location }
