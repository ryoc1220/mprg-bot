# ── ビルドステージ ──────────────────────────────────────────────────
FROM python:3.11-slim AS base

# タイムゾーン設定（ログの日時を日本時間に）と Python バッファリング無効化
ENV TZ=Asia/Tokyo
ENV PYTHONUNBUFFERED=1
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 作業ディレクトリ
WORKDIR /app

# 依存パッケージをインストール（キャッシュを活かすため先にコピー）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY main.py .

# ── 実行 ──────────────────────────────────────────────────────────────
CMD ["python", "main.py"]
