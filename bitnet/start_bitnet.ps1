<#
.SYNOPSIS
    Launches the bitnet.cpp inference server for BitNet b1.58 2B-4T.

.DESCRIPTION
    Reads configuration from environment / .env and starts the bitnet.cpp
    server with an OpenAI-compatible API on the configured port.

.PARAMETER Port
    Listening port (default: 8080)

.PARAMETER Threads
    Number of CPU threads to use (default: 4)

.EXAMPLE
    .\start_bitnet.ps1
    .\start_bitnet.ps1 -Port 8081 -Threads 8
#>

param(
    [string]$Port = "",
    [string]$Threads = "",
    [string]$CtxSize = "",
    [string]$ModelPath = ""
)

# Load .env variables
$envPath = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..\.env"
if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
        $line = $_.Trim()
        if (![string]::IsNullOrEmpty($line) -and !$line.StartsWith("#")) {
            $parts = $line.Split('=', 2)
            if ($parts.Length -eq 2) {
                [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim())
            }
        }
    }
}

if ($Port -eq "") { $Port = if ($env:BITNET_PORT) { $env:BITNET_PORT } else { "8080" } }
if ($Threads -eq "") { $Threads = if ($env:BITNET_THREADS) { $env:BITNET_THREADS } else { "4" } }
if ($CtxSize -eq "") { $CtxSize = if ($env:BITNET_CTX_SIZE) { $env:BITNET_CTX_SIZE } else { "2048" } }

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# ── Locate the model file ──────────────────────────────────────────────────
if ($ModelPath -eq "") {
    # Auto-detect GGUF file in models/BitNet-b1.58-2B-4T/
    $modelSearchDir = Join-Path (Join-Path $scriptDir "models") "BitNet-b1.58-2B-4T"
    if (Test-Path $modelSearchDir) {
        $ggufFile = Get-ChildItem -Path $modelSearchDir -Filter "*.gguf" -File | Select-Object -First 1
        if ($ggufFile) {
            $ModelPath = $ggufFile.FullName
        }
    }
    # Also check the engine's build output
    if ($ModelPath -eq "") {
        $engineModels = Join-Path $scriptDir "engine" | Join-Path -ChildPath "models"
        if (Test-Path $engineModels) {
            $ggufFile = Get-ChildItem -Path $engineModels -Recurse -Filter "*.gguf" -File | Select-Object -First 1
            if ($ggufFile) {
                $ModelPath = $ggufFile.FullName
            }
        }
    }
    if ($ModelPath -eq "") {
        Write-Host "  X No GGUF model file found. Run setup_bitnet.ps1 first." -ForegroundColor Red
        exit 1
    }
}

# ── Locate the server executable ───────────────────────────────────────────
$serverExe = ""
# Check engine build output for the server binary
$engineBinDir = Join-Path (Join-Path $scriptDir "engine") "build" | Join-Path -ChildPath "bin"
if (Test-Path $engineBinDir) {
    $candidate = Get-ChildItem -Path $engineBinDir -Recurse -Filter "llama-server*" -File | Select-Object -First 1
    if ($candidate) { $serverExe = $candidate.FullName }
}
# Fallback: check if a server binary exists in the engine root
if ($serverExe -eq "") {
    $candidate = Join-Path (Join-Path (Join-Path (Join-Path (Join-Path $scriptDir "engine") "3rdparty") "llama.cpp") "build") "bin" | Join-Path -ChildPath "llama-server.exe"
    if (Test-Path $candidate) { $serverExe = $candidate }
}
if ($serverExe -eq "") {
    Write-Host "  X bitnet.cpp server executable not found. Run setup_bitnet.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  BitNet b1.58 2B-4T - Inference Server" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Model    : $ModelPath" -ForegroundColor White
Write-Host "  Port     : $Port" -ForegroundColor White
Write-Host "  Threads  : $Threads" -ForegroundColor White
Write-Host "  Ctx Size : $CtxSize" -ForegroundColor White
Write-Host "  Server   : $serverExe" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ── Build arguments ────────────────────────────────────────────────────────
$args_list = @(
    "-m",    $ModelPath,
    "--port", $Port,
    "-c",    $CtxSize,
    "-t",    $Threads,
    "--chat-template", "chatml"
)

$cmdArgs = $args_list -join " "
Write-Host "Starting server..." -ForegroundColor DarkGray
Write-Host ""

& $serverExe @args_list
