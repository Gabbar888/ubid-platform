FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY src/ src/
COPY data/dictionaries/ data/dictionaries/
COPY migrations/ migrations/
COPY frontend/ frontend/

RUN pip install --no-cache-dir -e .

RUN mkdir -p data/parquet data/models

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000 8501

CMD ["uvicorn", "ubid.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
