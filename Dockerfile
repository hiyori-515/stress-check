FROM python:3.11-slim

# 日本語フォント（PDF生成用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-ipafont-gothic \
    fonts-wqy-zenhei \
    fonts-dejavu-core \
    && fc-cache -f \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# PDF出力先・ログ用ディレクトリ
RUN mkdir -p /tmp/pdfs logs/audit

ENV PORT=8080
ENV MOCK_MODE=false
ENV PDF_OUT_DIR=/tmp/pdfs
ENV LOG_DIR=/app/logs/audit

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120", "app:app"]
