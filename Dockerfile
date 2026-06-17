FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

RUN groupadd -r voicescope && useradd -r -g voicescope voicescope

COPY --from=builder /install /usr/local

COPY . .

RUN mkdir -p /app/chroma_db /app/logs && \
    chown -R voicescope:voicescope /app

USER voicescope

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8000/api/v1/health').raise_for_status()"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
