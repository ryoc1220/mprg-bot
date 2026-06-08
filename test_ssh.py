"""
SSH/SFTP接続 単体テストスクリプト
さくらサーバーへの接続を検証する

使い方:
    python3 test_ssh.py
"""

import os
import paramiko
from dotenv import load_dotenv

load_dotenv()

SSH_HOST = os.environ["WP_SSH_HOST"]
SSH_USER = os.environ["WP_SSH_USER"]
SSH_PASS = os.environ["WP_SSH_PASS"]

print(f"接続先: {SSH_USER}@{SSH_HOST}:22")
print(f"パスワード: {'*' * len(SSH_PASS)}\n")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(
        hostname=SSH_HOST,
        username=SSH_USER,
        password=SSH_PASS,
        port=22,
        timeout=15,
        look_for_keys=False,   # ローカルの秘密鍵を探さない
        allow_agent=False,     # SSHエージェントを使わない
    )
    print("✅ SSH接続成功！")

    # ホームディレクトリを確認
    stdin, stdout, stderr = ssh.exec_command("echo $HOME && ls ~")
    output = stdout.read().decode()
    print(f"ホームディレクトリ:\n{output}")

    # webrootの存在確認
    stdin, stdout, stderr = ssh.exec_command("ls ~/www/data/MPRG/ 2>/dev/null || echo '（data/MPRGディレクトリなし）'")
    output = stdout.read().decode()
    print(f"~/www/data/MPRG/:\n{output}")

    ssh.close()

except paramiko.AuthenticationException as e:
    print(f"❌ 認証失敗: {e}")
    print("\n試してみること:")
    print("  1. .envのWP_SSH_USERを確認（さくらのコントロールパネルのSSHユーザー名）")
    print("  2. .envのWP_SSH_PASSを確認（さくらのコントロールパネルのSSHパスワード）")
    print("  3. さくらのコントロールパネルでSSHが有効になっているか確認")

except paramiko.SSHException as e:
    print(f"❌ SSH接続エラー: {e}")

except Exception as e:
    print(f"❌ その他のエラー: {e}")
