FROM python:3.12-slim AS backend

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ src/
RUN pip install -e .[dev]

EXPOSE 8000
CMD ["codecrew-server"]
