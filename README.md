# MPRG 論文自動登録ボット

Slackに論文データ（`txt` + 任意で `pdf`）を含む `zip` ファイルを投稿すると、ボットが自動で研究室サイト（WordPress）へ **下書き** として登録するシステムです。

```
Slack (zip投稿)
    ↓ Slack Bolt (Socket Mode)
Gemini 2.5 Flash (論文情報のパース)
    ↓
WordPress REST API (下書き作成 + カスタムフィールド書き込み)
    ↓ PDFがある場合
WordPress カスタムエンドポイント (PDFをサーバーへ保存)
    ↓
Slack (登録完了通知 + X投稿用下書きテキスト)
```

---

## 必要なもの

| 項目 | 説明 |
|------|------|
| **Slack App** | Bot Token (`xoxb-...`) + App-Level Token (`xapp-...`) |
| **Google Gemini API Key** | [Google AI Studio](https://aistudio.google.com/) で取得 |
| **WordPress** | JWT Authentication プラグイン + Code Snippets プラグイン必須 |
| **Docker** | ローカル実行でも可（Python 3.9以上） |

---

## セットアップ

### 1. リポジトリをクローン

```bash
git clone https://github.com/<your-org>/mprg-bot.git
cd mprg-bot
```

### 2. 環境変数ファイルを作成

`.env.example` をコピーして `.env` を作成し、各値を入力してください。

```bash
cp .env.example .env
```

`.env` の内容：

```env
# Slack
SLACK_BOT_TOKEN="xoxb-..."
SLACK_APP_TOKEN="xapp-..."

# Google Gemini
GEMINI_API_KEY="..."

# WordPress
WP_SITE_URL="https://mprg.jp/wp"
WP_USERNAME="wp-admin-user"
WP_APP_PASSWORD="xxxx xxxx xxxx xxxx xxxx xxxx"

# Slack通知先（Webサイト管理者のSlack ID）
WEB_KAHO_SLACK_ID="U0XXXXXXXXX"
```

> [!CAUTION]
> `.env` は絶対に Git にコミットしないでください。`.gitignore` に含まれています。

### 3. Slack App の設定

1. [api.slack.com/apps](https://api.slack.com/apps) でアプリを作成
2. **OAuth & Permissions** → Bot Token Scopes に以下を追加：
   - `app_mentions:read`
   - `chat:write`
   - `files:read`
3. **Event Subscriptions** → Socket Mode を有効化
4. **Subscribe to bot events** に `app_mention` を追加
5. アプリをワークスペースにインストール → **Bot User OAuth Token** をコピー
6. **Basic Information** → **App-Level Tokens** → `connections:write` スコープで生成 → コピー

### 4. WordPress の設定

#### 4-1. プラグインのインストール

WordPress管理画面でインストール・有効化：

- **JWT Authentication for WP REST API**  
  `wp-config.php` に以下を追加：
  ```php
  define('JWT_AUTH_SECRET_KEY', 'ランダムな秘密鍵');
  define('JWT_AUTH_CORS_ENABLE', true);
  ```

- **Code Snippets**

#### 4-2. カスタムエンドポイントの登録

1. WordPress管理画面 → **Code Snippets** → 新規追加
2. **実行タイミング**: 「フロントエンドとバックエンド」
3. `wp_snippet.php` の内容を貼り付けて保存・有効化
4. **設定 → パーマリンク設定 → 変更を保存**（ルートをフラッシュ）

---

## 起動方法

### A. ローカル（Python直接実行）

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# 起動
python main.py
```

起動成功時:
```
⚡️ Bolt app is running!
```

### B. Docker（推奨）

```bash
# ビルド
docker compose build

# バックグラウンドで起動
docker compose up -d

# ログ確認
docker compose logs -f

# 停止
docker compose down
```

> [!TIP]
> `restart: unless-stopped` が設定されているため、サーバー再起動後も自動復旧します。

---

## 使い方

### 論文の登録

1. 以下を含む `zip` ファイルを作成：
   - `論文情報.txt` — 論文の全テキスト（タイトル・著者・アブスト等）
   - `論文.pdf` — 任意（PDFがある場合）

2. **SlackのMPRG論文登録チャンネル**で、ボットを **@メンション** しながら `zip` を添付：
   ```
   @mprg-bot
   [zipファイルを添付]
   ```

3. ボットが自動で：
   - Gemini で論文情報をパース
   - WordPress に下書きを作成
   - PDFをサーバーにアップロード（`/data/MPRG/{区分}_group/{slug}.pdf`）
   - Slack に登録完了通知 + **X投稿用下書きテキスト** を送信

4. WordPress管理画面で内容を確認・編集後、**公開（Publish）**

5. SlackのX下書きテキストをコピーし、**論文ページのURLを追記**してX（旧Twitter）に手動投稿

### 識別子（スラッグ）のルール

| 区分 | 接頭辞 | 例 |
|------|--------|-----|
| 論文誌 | `B` | `B20261201_yamada` |
| 国際学会 | `C` | `C20261005_tanakak` |
| 国内学会 | `F` | `F20260513_hazumi` |

PDFの保存パス：`http://mprg.jp/data/MPRG/{接頭辞}_group/{slug}.pdf`

---

## プロジェクト構成

```
mprg-bot/
├── main.py              # ボット本体
├── wp_snippet.php       # WordPress カスタムエンドポイント（Code Snippetsへ貼り付け）
├── requirements.txt     # Python依存パッケージ
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example         # 環境変数テンプレート（実際の値は.envに）
├── .gitignore
└── README.md
```

---

## トラブルシューティング

### `rest_no_route` (404) が返ってくる

→ Code Snippets が無効化されている可能性があります。  
WordPress管理画面 → Code Snippets でスニペットが **Active** か確認し、**設定 → パーマリンク設定 → 変更を保存** を実行してください。

### `Authentication failed` (WordPress)

→ `WP_APP_PASSWORD` はWordPressのアプリケーションパスワードです（ログインパスワードとは別）。  
WordPress管理画面 → ユーザー → プロフィール → **アプリケーションパスワード** で新規生成してください。

### 二重応答が発生する

→ 複数の `main.py` プロセスが起動しています。以下で全プロセスを終了してから再起動：
```bash
pkill -f "main.py"
python main.py
```

### タイムアウトエラー（WordPress API）

→ サーバーの応答が遅い場合、自動で1回リトライします（最大90秒 × 2回）。  
頻発する場合は、さくらサーバーのコントロールパネルで `max_execution_time` を延長してください。

---

## 開発者向け

### ボットの再起動（コード変更後）

```bash
# Dockerの場合
docker compose restart

# ローカルの場合
pkill -f "main.py" && python main.py
```

### Dockerイメージの再ビルド（依存パッケージ変更後）

```bash
docker compose up -d --build
```

### ログのリアルタイム確認

```bash
docker compose logs -f mprg-bot
```
