# BitNet b1.58 2B-4T — Local Provider for CodeCrew

BitNet b1.58 is Microsoft's **1-bit Large Language Model** that runs efficiently on CPUs with minimal memory (~1 GB). It uses `bitnet.cpp` for inference and exposes an OpenAI-compatible API server.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Git | any | https://git-scm.com |
| Python | 3.9+ | https://python.org |
| CMake | 3.22+ | https://cmake.org |
| Clang | 18+ | https://releases.llvm.org |
| huggingface-cli | any | `pip install huggingface_hub` |

> **Windows**: Install Visual Studio 2022 Build Tools with the **C++ Desktop workload**, then install LLVM/Clang separately.

## Quick Start

### 1. Setup (one-time)

```powershell
cd bitnet
.\setup_bitnet.ps1
```

This will clone `microsoft/BitNet`, download the GGUF model (~500 MB), and build the inference engine.

### 2. Start the Server

```powershell
.\start_bitnet.ps1
```

The server starts at `http://127.0.0.1:8080` with an OpenAI-compatible API.

### 3. Configure CodeCrew

In your `.env` file:

```env
LLM_PROVIDER=bitnet
BITNET_BASE_URL=http://127.0.0.1:8080/v1
BITNET_MODEL=bitnet-b1.58-2B-4T
```

### 4. Run CodeCrew

```powershell
python -m codecrew "Build a calculator app"
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BITNET_BASE_URL` | `http://127.0.0.1:8080/v1` | Server endpoint |
| `BITNET_MODEL` | `bitnet-b1.58-2B-4T` | Model identifier |
| `BITNET_PORT` | `8080` | Server port |
| `BITNET_THREADS` | `4` | CPU threads for inference |
| `BITNET_CTX_SIZE` | `2048` | Context window size |

## Notes

- **All agent roles share the same 2B model.** Quality may be lower than larger Ollama/Groq models, but inference is extremely fast on CPU.
- **No API key required** — the server runs entirely locally.
- For best results, use on machines with AVX2 or newer instruction sets.
