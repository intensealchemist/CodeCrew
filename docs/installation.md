# Installation

## Prerequisites

- Python 3.10 to 3.13
- Node.js 18+
- Git
- One configured model provider

## 1) Clone Repository

```bash
git clone https://github.com/your-org/codecrew.git
cd codecrew
```

## 2) Create Virtual Environment

```bash
python -m venv .venv
.\.venv\Scripts\activate
```

## 3) Install Project Dependencies

```bash
pip install -e .[dev]
```

Install documentation dependencies:

```bash
pip install -e .[docs]
```

## 4) Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

## 5) Configure Environment

```bash
copy .env.example .env
```

Set provider and credentials in `.env`.

## 6) Start Backend API

```bash
.\.venv\Scripts\python.exe -m uvicorn codecrew.server:app --host 0.0.0.0 --port 8000
```

## 7) Start Frontend

```bash
cd frontend
npm run dev
```

Open:

- Frontend: `http://localhost:3000`
- Backend OpenAPI: `http://localhost:8000/docs`

## 8) Build Documentation

```bash
py -m mkdocs build --strict
```

Generate PDF bundle:

```bash
py -m mkdocs build -f mkdocs-pdf.yml
```
