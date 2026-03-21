# 🚀 CodeCrew — Multi-Agent AI Code Generator

CodeCrew is a **multi-agent system** powered by [CrewAI](https://crewai.com) that turns natural-language task descriptions into **complete, working codebases** — with README, tests, and a Git repo.

> *"build a todo app with auth"* → Full source code + tests + README + Git repo ✨

---

## 🏗️ Architecture

```
User Input ("build todo app with auth")
         │
         ▼
┌─────────────────┐
│  🔍 Researcher  │  Gathers specs, best practices, architecture patterns
└────────┬────────┘
         │ research output
         ▼
┌─────────────────┐
│  📐 Architect   │  Designs system structure, patterns, interfaces
└────────┬────────┘
         │ architecture blueprint
         ▼
┌─────────────────┐
│  💻 Coder       │  Writes complete production code following the blueprint
└────────┬────────┘
         │ full codebase
         ▼
┌─────────────────┐
│  🔎 Reviewer    │  Reviews, writes tests, bug reports, quality verdict
└────────┬────────┘
         │ reviewed & tested code
         ▼
┌─────────────────┐
│  🐳 DevOps      │  Dockerfile, CI/CD, Makefile, deployment configs
└────────┬────────┘
         │ deployment-ready project
         ▼
┌─────────────────┐
│  📝 Doc Writer  │  Polished README, API docs, CONTRIBUTING, CHANGELOG
└────────┬────────┘
         │
         ▼
   📦 Git Repo + Docs + Tests + CI/CD
```

**Agents run sequentially** with shared memory. Each agent can use tools (web search, file writer, code executor) and can optionally pause for human approval.


---

## ⚡ Quick Start

### 1. Prerequisites
- **Python 3.10+**
- **Ollama** running locally ([install guide](https://ollama.ai)) — or a Groq API key

### 2. Install

```bash
# Clone & enter project
cd CodeCrew

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

# Install
pip install -e .
```

### 3. Configure

```bash
copy .env.example .env    # Windows
# cp .env.example .env    # macOS/Linux
```

Edit `.env` with your preferred LLM and search provider.

### 4. Run

```bash
# Using Ollama (default, free)
codecrew --task "build a CLI calculator in Python"

# With human override (asks approval between agents)
codecrew --task "build a REST API with Flask" --human-override

# Custom output directory
codecrew --task "build a todo app" --output-dir ./my-project
```

---

## 🔧 Configuration

### LLM Providers

| Provider    | Cost  | Setup                                  | `LLM_PROVIDER` |
|------------|-------|----------------------------------------|-----------------|
| **Ollama** | Free  | Install Ollama, pull a model           | `ollama`        |
| **Free HA**| Free  | Zero-cost fallback (Groq+Cerebras+Gemini) | `free_ha`       |
| **Groq**   | Free  | Get API key at console.groq.com        | `groq`          |
| **Cerebras** | Free| Get API key at cloud.cerebras.ai       | `cerebras`      |
| **OpenAI** | Paid  | Get API key at platform.openai.com     | `openai`        |
| **Anthropic** | Paid | Get API key at console.anthropic.com | `anthropic`     |

### Search Providers

| Provider        | Cost  | Key Required | `SEARCH_PROVIDER` |
|----------------|-------|--------------|--------------------|
| **DuckDuckGo** | Free  | No           | `duckduckgo`       |
| **Serper**     | Free* | Yes          | `serper`           |
| **Tavily**     | Free* | Yes          | `tavily`           |
| **Exa**        | Free* | Yes          | `exa`              |

*Free tier available

---

## 🧪 Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## 📁 Project Structure

```
CodeCrew/
├── src/codecrew/
│   ├── config/
│   │   ├── agents.yaml      # Agent definitions
│   │   └── tasks.yaml       # Task definitions
│   ├── providers/
│   │   ├── llm_provider.py  # LLM factory (Ollama/Groq/OpenAI/Anthropic)
│   │   └── search_provider.py  # Search factory (DDG/Serper/Tavily/Exa)
│   ├── tools/
│   │   ├── file_writer.py   # Write files to output workspace
│   │   └── code_executor.py # Run shell commands with timeout
│   ├── crew.py              # Crew orchestration
│   └── main.py              # CLI entry point
├── tests/
├── .env.example
├── pyproject.toml
└── README.md
```

---

## 📄 License

MIT
