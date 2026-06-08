"""
WordPress カスタムエンドポイント疎通確認スクリプト
/wp-json/mprg/v1/publication へダミーデータを送信し、
Toolset カスタムフィールドへの書き込みが成功するかを確認する。

使い方:
    cd /Users/ryo/Desktop/mprg-bot
    python test_wp_endpoint.py

確認手順:
    1. このスクリプトを実行してステータス 201 が返ることを確認
    2. 出力された edit_link を開いて編集画面を確認
    3. 各カスタムフィールドに値が入っているか目視確認
    4. 確認後、作成された下書きを WordPress 管理画面から削除
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

WP_SITE_URL   = os.environ["WP_SITE_URL"]
WP_USERNAME   = os.environ["WP_USERNAME"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]

# ─── JWT トークン取得 ────────────────────────────────────────────────────────
print("▶ JWT トークン取得中...")

token_resp = requests.post(
    f"{WP_SITE_URL}/wp-json/jwt-auth/v1/token",
    json={"username": WP_USERNAME, "password": WP_APP_PASSWORD},
    timeout=15
)

if token_resp.status_code != 200:
    print(f"✗ JWT 認証失敗 ({token_resp.status_code})")
    print(token_resp.text)
    exit(1)

token = token_resp.json()["token"]
print(f"✓ トークン取得成功")

# ─── テストペイロード ────────────────────────────────────────────────────────
# 実際の論文データに近い形のダミーデータ
test_payload = {
    "title":                 "【テスト】顔認識を用いた自動論文登録システムの開発と評価",
    "abstract":              "本論文では，深層学習を用いた顔認識技術とSlackボットを組み合わせた論文自動登録システムを提案する．提案システムはGeminiによる自動解析とWordPress REST APIを統合することで，登録作業を効率化する．実験により，提案手法の有効性を示した．",
    "slug":                  "T20260502_test",
    "publication_date":      "2026-05-02 00:00:00",
    "wpcf-author":           "テスト太郎, テスト花子, テスト次郎",
    "wpcf-publication":      "情報処理学会全国大会（テスト）",
    "wpcf-tex_ref":          r"テスト太郎, ``顔認識を用いた自動論文登録システム,'' 情報処理学会, 2026.",
    "wpcf-bibtex_ref":       "@inproceedings{test2026,\n  author={テスト太郎},\n  title={顔認識を用いた自動論文登録システム},\n  booktitle={情報処理学会全国大会},\n  year={2026}\n}",
    "wpcf-dlfile1":          "http://mprg.jp/data/MPRG/T_group/T20260529_test.pdf",
    "wpcf-linktxt1":         "PDF",
    "wpcf-subtxt1":          "Japanese",
    "wpcf-lang-ja":          "1",   # 日本語論文: lang-ja=1, lang-en=0
    "wpcf-lang-en":          "0",   # 英語論文なら "1" に変える
    "wpcf-category_type":    "T",   # スラッグ先頭1文字
    "wpcf-paper_type":       "テスト種別（国内学会等に変更してください）",
}

# ─── エンドポイント呼び出し ──────────────────────────────────────────────────
print("\n▶ /wp-json/mprg/v1/publication へ POST 中...")

resp = requests.post(
    f"{WP_SITE_URL}/wp-json/mprg/v1/publication",
    json=test_payload,
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    },
    timeout=30
)

print(f"\nHTTP Status: {resp.status_code}")

if resp.status_code == 201:
    result = resp.json()
    print(f"\n✅ 成功！")
    print(f"   post_id   : {result['post_id']}")
    print(f"   slug      : {result['slug']}")
    print(f"   edit_link : {result['edit_link']}")
    print(f"\n👆 上記リンクを開いて各フィールドが入力されているか確認してください。")
    print(f"   確認後、この下書きは WordPress 管理画面から削除してください。")
else:
    print(f"\n❌ 失敗")
    try:
        print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
    except Exception:
        print(resp.text)
