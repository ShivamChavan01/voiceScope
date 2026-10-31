FROM python:3.11-slim AS builder

WORKDIR /app

RUN python -m pip install --no-cache-dir --upgrade pip==26.2.2 setuptools==84.1.0

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

RUN python -m pip install --no-cache-dir --upgrade pip==26.2.2 setuptools==84.1.0

RUN groupadd -r voicescope && useradd -r -m -g voicescope voicescope
ENV DATA_DIR=/app/data

COPY --from=builder /install /usr/local

COPY . .

RUN mkdir -p /app/data /app/chroma_db /app/logs && \
    chown -R voicescope:voicescope /app

USER voicescope

EXPOSE 8000

CMD ["sh", "-c", "umask 077; exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
