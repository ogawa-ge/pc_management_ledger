FROM python:3.11-slim

WORKDIR /app

# 依存ライブラリのコピーとインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ソースコードのコピー
COPY . .

# FastAPIを起動 (ポート80)
# 本番環境では uvicorn を使用
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "80"]
