<#
.SYNOPSIS
    Sets up bitnet.cpp and downloads the BitNet b1.58 2B-4T GGUF model.

.DESCRIPTION
    One-time setup script that:
    1. Clones the microsoft/BitNet repository
    2. Installs Python dependencies
    3. Downloads the GGUF model from Hugging Face
    4. Builds the bitnet.cpp inference engine

.NOTES
    Prerequisites: Git, Python 3.9+, CMake 3.22+, Clang 18+
    On Windows: install Visual Studio 2022 Build Tools with C++ workload,
    and LLVM/Clang from https://releases.llvm.org/

.EXAMPLE
    .\setup_bitnet.ps1
#>

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  BitNet b1.58 2B-4T — Setup Script" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Clone the BitNet repository ────────────────────────────────────
$engineDir = Join-Path $scriptDir "engine"
if (Test-Path $engineDir) {
    Write-Host "  ✅ BitNet engine directory already exists, skipping clone." -ForegroundColor Green
} else {
    Write-Host "  📥 Cloning microsoft/BitNet repository..." -ForegroundColor Yellow
    git clone --recursive https://github.com/microsoft/BitNet.git $engineDir
    if ($LASTEXITCODE -ne 0) { throw "Failed to clone BitNet repository." }
    Write-Host "  ✅ Repository cloned." -ForegroundColor Green
}

# ── Step 2: Install Python dependencies ────────────────────────────────────
Write-Host "  📦 Installing Python dependencies (this might take a few minutes)..." -ForegroundColor Yellow
$reqFile = Join-Path $engineDir "requirements.txt"
if (Test-Path $reqFile) {
    python -m pip install -v -r $reqFile
    if ($LASTEXITCODE -ne 0) { throw "Failed to install Python dependencies." }
    Write-Host "  ✅ Python dependencies installed." -ForegroundColor Green
} else {
    Write-Host "  ⚠️  No requirements.txt found, skipping pip install." -ForegroundColor Yellow
}

# ── Step 3: Download the GGUF model ────────────────────────────────────────
$modelDir = Join-Path $scriptDir "models"
$modelSubDir = Join-Path $modelDir "BitNet-b1.58-2B-4T"
if (Test-Path $modelSubDir) {
    Write-Host "  ✅ Model directory already exists, skipping download." -ForegroundColor Green
} else {
    Write-Host "  📥 Downloading BitNet b1.58 2B-4T GGUF model..." -ForegroundColor Yellow
    Write-Host "     (This may take a few minutes depending on your connection)" -ForegroundColor DarkGray
    New-Item -ItemType Directory -Force -Path $modelDir | Out-Null
    huggingface-cli download microsoft/BitNet-b1.58-2B-4T-gguf --local-dir $modelSubDir
    if ($LASTEXITCODE -ne 0) { throw "Failed to download model. Make sure huggingface-cli is installed: pip install huggingface_hub" }
    Write-Host "  ✅ Model downloaded." -ForegroundColor Green
}

# ── Step 4: Build bitnet.cpp ───────────────────────────────────────────────
Write-Host "  🔨 Building bitnet.cpp inference engine..." -ForegroundColor Yellow
Push-Location $engineDir
try {
    python setup_env.py -md (Join-Path $scriptDir "models" "BitNet-b1.58-2B-4T")
    if ($LASTEXITCODE -ne 0) { throw "bitnet.cpp build failed." }
    Write-Host "  ✅ bitnet.cpp built successfully." -ForegroundColor Green
} finally {
    Pop-Location
}

# ── Done ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ✨ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "    1. Run: .\start_bitnet.ps1" -ForegroundColor White
Write-Host "    2. Set LLM_PROVIDER=bitnet in your .env" -ForegroundColor White
Write-Host "    3. Run CodeCrew as usual" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
