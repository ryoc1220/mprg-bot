import os
import json
import shutil
import requests

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from google import genai
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

SLACK_BOT_TOKEN  = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN  = os.environ.get("SLACK_APP_TOKEN")

GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY")

WP_SITE_URL      = os.environ.get("WP_SITE_URL")
WP_USERNAME      = os.environ.get("WP_USERNAME")
WP_APP_PASSWORD  = os.environ.get("WP_APP_PASSWORD")

WEB_KAHO_SLACK_ID = os.environ.get("WEB_KAHO_SLACK_ID")


slack_app = App(token=SLACK_BOT_TOKEN)

gemini_client = genai.Client(
    api_key=GEMINI_API_KEY
)

class DetailedPaperInfo(BaseModel):

    title: str = Field(
        description="論文タイトル"
    )

    publication_date: str = Field(
        description="YYYY-MM-DD"
    )

    authors: str = Field(
        description="著者一覧（カンマ区切り）"
    )

    author_slug: str = Field(
        description=(
            "第一著者の苗字を小文字ローマ字で表記．"
            "例: 羽濂 → hazumi．"
            "同姓者がいる場合は名の頭文字も付加: 鈴木裕 → suzukih"
        )
    )

    publication: str = Field(
        description="掃載誌・学会名"
    )

    abstract: str = Field(
        description="概要"
    )

    tex_reference: str = Field(
        description="Tex Reference"
    )

    bibtex_reference: str = Field(
        description="BibTeX"
    )

    paper_type: str = Field(
        description="論文種別（詳細名、例: IEICE Transactions on Information and Systems）"
    )

    category: str = Field(
        description=(
            "論文の区分．必ず以下のいずれかを選択: "
            "'論文誌' (ジャーナルの論文）， "
            "'国際学会' (国際会議・シンポジウム）， "
            "'国内学会' (国内学会・全国大会・研究会）"
        )
    )

    language: str = Field(
        description="English または Japanese"
    )

    official_url: str = Field(
        description="公式URL（IEEE・CVF等）"
    )

def handle_error(say, thread_ts, error_msg):

    print(f"【ERROR】{error_msg}")

    say(
        text=f"❌ エラーが発生しました: {error_msg}",
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "❌ エラーが発生しました",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```{error_msg}```"
                }
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<@{WEB_KAHO_SLACK_ID}> さん，確認をお願いします 🙏"
                }
            }
        ],
        thread_ts=thread_ts
    )

@slack_app.event("app_mention")
def handle_mentions(event, say, client):

    thread_ts = event.get("ts")

    files = event.get("files", [])

    if not files:

        say(
            text="📎 zipファイルを添付してください",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "📎 *論文 zip ファイルを添付してください*\n"
                            "txtファイル（＋任意でPDF）を zip にまとめて，もう一度メンションしてください．"
                        )
                    }
                }
            ],
            thread_ts=thread_ts
        )

        return

    zip_file_info = files[0]

    if not zip_file_info.get("name", "").endswith(".zip"):

        say(
            text="⚠️ zipファイルのみ対応しています",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "⚠️ *zip ファイルのみ対応しています*\n"
                            "添付ファイルを `.zip` 形式にまとめて再送してください．"
                        )
                    }
                }
            ],
            thread_ts=thread_ts
        )

        return

    say(
        text="📥 zipファイルを受信しました．解析中です…",
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "📥 *zip ファイルを受信しました*\n"
                        "🔍 Gemini で解析中です．少々お待ちください…"
                    )
                }
            }
        ],
        thread_ts=thread_ts
    )

    tmp_dir = "./tmp_paper_process"

    os.makedirs(tmp_dir, exist_ok=True)

    zip_path = os.path.join(
        tmp_dir,
        "uploaded.zip"
    )

    try:

        """
        Slack download
        """
        file_id = zip_file_info.get("id")

        file_info = client.files_info(
            file=file_id
        )

        url_private = file_info["file"]["url_private_download"]

        headers = {
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}"
        }

        response = requests.get(
            url_private,
            headers=headers,
            stream=True
        )

        if response.status_code != 200:

            handle_error(
                say,
                thread_ts,
                "Slackダウンロード失敗"
            )

            return

        with open(zip_path, "wb") as f:

            for chunk in response.iter_content(8192):

                f.write(chunk)

        """
        unzip
        """
        extract_dir = os.path.join(
            tmp_dir,
            "extracted"
        )

        os.makedirs(
            extract_dir,
            exist_ok=True
        )

        shutil.unpack_archive(
            zip_path,
            extract_dir,
            "zip"
        )

        txt_content = ""

        has_pdf = False

        for root, dirs, filenames in os.walk(extract_dir):

            for filename in filenames:

                if filename.startswith("._"):
                    continue

                if filename.startswith(".DS_Store"):
                    continue

                full_path = os.path.join(
                    root,
                    filename
                )

                if filename.endswith(".txt"):

                    with open(
                        full_path,
                        "r",
                        encoding="utf-8",
                        errors="ignore"
                    ) as f:

                        txt_content = f.read()

                elif filename.endswith(".pdf"):

                    has_pdf = True
                    pdf_local_path = full_path  # SFTPアップロード用にパスを保存

        if not txt_content:

            handle_error(
                say,
                thread_ts,
                "txtファイルが見つかりません"
            )

            return

        """
        Gemini
        """
        system_prompt = (
            "研究室論文登録用JSONを生成してください．\n"
            "句読点は「，」「．」に統一してください．\n\n"
            "【categoryフィールド】必ず次の3候補のいずれかのみを選択．\n"
            "  '論文誌'  : ジャーナル・論文誌への掲載\n"
            "  '国際学会': 国際会議・シンポジウムでの発表（ポスター・口頭等発表形式は問わない）\n"
            "  '国内学会': 国内学会・全国大会・研究会での発表（ポスター・口頭等発表形式は問わない）\n"
            "  《poster, oral, workshopなど発表形式は category に含めない》\n\n"
            "【author_slugフィールド】第一著者の苗字を小文字ローマ字で記述．\n"
            "  例: 羽濂→hazumi， 鈴木裕→suzukih（同姓者がいる場合は名の頭文字も付加）\n"
            "  《poster, oral, journalなど発表形式・論文種別の小文字を入れてはいけない》"
        )

        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=txt_content,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=DetailedPaperInfo
            )
        )

        data = json.loads(
            response.text
        )

        # ── スラッグをPython側で確定的に生成（Geminiの区分文字誤りを完全防止） ──
        CATEGORY_MAP = {
            "論文誌":   "B",
            "国際学会": "C",
            "国内学会": "F",
        }

        category_raw = data.get("category", "")
        category_letter = CATEGORY_MAP.get(category_raw)

        if category_letter is None:
            # CATEGORY_MAPにヒットしない場合のキーワードフォールバック
            raw_lower = category_raw.lower()
            if any(k in raw_lower for k in ["journal", "transaction", "論文誌", "ジャーナル"]):
                category_letter = "B"
            elif any(k in raw_lower for k in ["international", "国際", "ieee", "cvf", "eccv", "iccv", "cvpr", "iclr", "nips", "neurips"]):
                category_letter = "C"
            else:
                # poster/oral等発表形式は国内学会または国際学会に属するのでデフォルトF
                category_letter = "F"
            print(f"【WARN】category '{category_raw}' が未知 → '{category_letter}' にフォールバック")

        date_compact = data["publication_date"].replace("-", "")  # "2026-05-13" → "20260513"
        author_slug  = data.get("author_slug", "unknown").lower().strip()
        slug_fixed   = f"{category_letter}{date_compact}_{author_slug}"
        print(f"【INFO】category='{category_raw}' → letter='{category_letter}', slug='{slug_fixed}'")

        """
        PDF URL
        """
        if has_pdf:

            group_folder = f"{category_letter}_group"  # CATEGORY_MAPで確定済みの文字を再利用

            final_download_url = (
                f"http://mprg.jp/data/MPRG/"
                f"{group_folder}/"
                f"{slug_fixed}.pdf"
            )

        else:

            final_download_url = data.get(
                "official_url",
                ""
            )

        """
        JWT auth
        """
        token_url = (
            f"{WP_SITE_URL}"
            f"/wp-json/jwt-auth/v1/token"
        )

        token_response = requests.post(
            token_url,
            json={
                "username": WP_USERNAME,
                "password": WP_APP_PASSWORD
            }
        )

        if token_response.status_code != 200:

            handle_error(
                say,
                thread_ts,
                "JWT認証失敗"
            )

            return

        token = token_response.json()["token"]

        """
        Custom REST API
        """
        wp_api_url = (
            f"{WP_SITE_URL}"
            f"/wp-json/mprg/v1/publication"
        )

        wp_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # 公開日時は発表日の 12:00 AM（午前0時）= 00:00:00
        formatted_date = (
            f"{data['publication_date']} 00:00:00"
        )

        # 言語チェックボックス: 英語論文は日本語・英語の両方にチェック
        lang_ja_value = "1"
        lang_en_value = "1" if data["language"] == "English" else "0"

        wp_payload = {
            "title":              data["title"],
            "abstract":           data["abstract"],
            "slug":               slug_fixed,
            "publication_date":   formatted_date,
            "wpcf-author":        data["authors"],
            "wpcf-publication":   data["publication"],
            "wpcf-tex_ref":       data["tex_reference"],
            "wpcf-bibtex_ref":    data["bibtex_reference"],
            "wpcf-dlfile1":       final_download_url,
            "wpcf-linktxt1":      "PDF" if final_download_url else "",
            "wpcf-subtxt1":       data["language"],
            "wpcf-lang-ja":       lang_ja_value,
            "wpcf-lang-en":       lang_en_value,
            "wpcf-category_type": category_letter,  # CATEGORY_MAPで確定済み
            "wpcf-paper_type":    data["paper_type"],
        }

        # タイムアウトを90秒に設定（さくらサーバーのCGI遅延を考慮）
        # タイムアウト時は1回だけリトライする
        wp_response = None
        for attempt in range(2):
            try:
                wp_response = requests.post(
                    wp_api_url,
                    json=wp_payload,
                    headers=wp_headers,
                    timeout=90
                )
                break  # 成功したらループを抜ける
            except requests.exceptions.Timeout:
                if attempt == 0:
                    print(f"【WARN】WordPress API タイムアウト（試行{attempt+1}回目）。リトライします…")
                    say(
                        text="⏳ サーバーの応答が遅れています。リトライ中です…",
                        blocks=[
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "⏳ WordPress サーバーの応答が遅れています．リトライ中です…"
                                }
                            }
                        ],
                        thread_ts=thread_ts
                    )
                else:
                    handle_error(
                        say,
                        thread_ts,
                        "WordPress APIがタイムアウトしました（2回試行）．サーバーの状態を確認してください．"
                    )
                    return

        print(wp_response.text)

        if wp_response.status_code not in [200, 201]:

            handle_error(
                say,
                thread_ts,
                (
                    f"WordPress投稿失敗\n"
                    f"{wp_response.text}"
                )
            )

            return


        response_json = wp_response.json()

        post_id = response_json["post_id"]

        # PHP の admin_url() が返す正確なパスをそのまま使う
        # （WP のサブディレクトリ構成に依存しないため）
        admin_link = response_json.get(
            "edit_link",
            f"{WP_SITE_URL}/wp-admin/post.php?post={post_id}&action=edit"
        )

        lang_label = (
            "日本語・英語（両方チェック）"
            if data["language"] == "English"
            else "日本語のみ"
        )

        # ── PDF を WordPress カスタムエンドポイント経由でアップロード ──────
        # SSH/SFTP の代わりに JWT 認証済み HTTP POST で送信する
        pdf_upload_status = ""
        if has_pdf:
            pdf_api_url = f"{WP_SITE_URL}/wp-json/mprg/v1/upload-pdf"
            try:
                with open(pdf_local_path, "rb") as pdf_file:
                    pdf_response = requests.post(
                        pdf_api_url,
                        headers={"Authorization": f"Bearer {token}"},
                        files={"pdf": (f"{slug_fixed}.pdf", pdf_file, "application/pdf")},
                        data={
                            "slug":  slug_fixed,
                            "group": group_folder,
                        },
                        timeout=90
                    )
                if pdf_response.status_code == 200:
                    pdf_upload_status = f"✅ PDFアップロード成功: `{final_download_url}`"
                    print(f"【INFO】PDF upload OK: {final_download_url}")
                else:
                    pdf_upload_status = f"⚠️ PDFアップロード失敗\n`{pdf_response.text}`"
                    print(f"【WARN】PDF upload failed ({pdf_response.status_code}): {pdf_response.text}")
            except Exception as pdf_err:
                pdf_upload_status = f"⚠️ PDFアップロードエラー\n`{str(pdf_err)}`"
                print(f"【WARN】PDF upload error: {pdf_err}")


        dl_label = (
            final_download_url
            if final_download_url
            else "（PDFなし → 公式URLを使用）"
        )

        # ── X (旧Twitter) 投稿用ツイート下書きを生成 ────────────────────
        # 公開URLは発表後に確定するためプレースホルダーを入れる
        title_short   = data["title"][:60] + "…" if len(data["title"]) > 60 else data["title"]
        authors_short = data["authors"][:40] + "…" if len(data["authors"]) > 40 else data["authors"]
        tweet_draft = (
            f"📚 新着論文\n"
            f"「{title_short}」\n"
            f"\u270d️ {authors_short}\n"
            f"📌 {data['publication']} ({data['publication_date']})\n\n"
            f"🔗 論文ページ: [公開後にURLを追記]\n"
            + (f"📥 PDF: {final_download_url}\n" if final_download_url else "")
            + "\n#MPRG"
        )

        say(
            text=f"🎉 論文下書き登録完了: {slug_fixed}",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🎉 論文下書きを登録しました",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{data['title']}*"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*👤 著者*\n{data['authors']}"},
                        {"type": "mrkdwn", "text": f"*📅 発表日*\n{data['publication_date']}"},
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*🏛️ 学会・論文誌*\n{data['publication']}"},
                        {"type": "mrkdwn", "text": f"*📂 区分*\n{data['category']}（{category_letter}）"},
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*🌐 言語*\n{lang_label}"},
                        {"type": "mrkdwn", "text": f"*🔑 識別子*\n`{slug_fixed}`"},
                    ]
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"✅ *自動入力済み*\n"
                            f"・言語チェックボックス: {lang_label}\n"
                            f"・ダウンロードURL: `{dl_label}`\n"
                            + (f"・{pdf_upload_status}\n" if pdf_upload_status else "")
                            + f"\n⚠️ *要確認* カテゴリー・論文の種類が正しいか確認してください"
                        )
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"<{admin_link}|✏️ *WordPress 編集画面を開く →*>"
                    }
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "🐦 *X (旧Twitter) 投稿用下書き*\n公開後に《論文ページURL》を入れてこちらを手動投稿してください:"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"```{tweet_draft}```"
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Post ID: `{post_id}`  |  Slug: `{slug_fixed}`"
                        }
                    ]
                }
            ],
            thread_ts=thread_ts
        )

    except Exception as e:

        handle_error(
            say,
            thread_ts,
            str(e)
        )

    finally:

        if os.path.exists(tmp_dir):

            shutil.rmtree(tmp_dir)

if __name__ == "__main__":

    SocketModeHandler(
        slack_app,
        SLACK_APP_TOKEN
    ).start()
