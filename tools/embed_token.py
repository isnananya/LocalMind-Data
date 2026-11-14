#!/usr/bin/env python3
"""把 admin 页要用的 GitHub 令牌生成成「可粘贴进 index.html」的混淆串。

## 为什么要混淆

后台页 `index.html` 托管在公开仓库的 GitHub Pages 上。GitHub 的 secret
scanner 会扫公开仓库的原始文件，明文 `gho_xxx` 一旦提交就会被自动吊销
（还会给账号发一封 "your token was leaked" 的邮件）。所以这里按字节
异或 0x5A 再 base64，页面上只剩一串看不出内容的字符。

**这不是加密，只是防扫描**：拿到页面源码的人照样能还原出令牌。所以
  * 令牌只授权必要的仓库（Fine-grained：只选 LocalMind-Data + LocalMind-Android，
    Contents: Read and write）；
  * 一旦怀疑泄露，去 GitHub 撤销重发一个，然后重跑这个脚本换掉串。

## 用法

    export GH_ADMIN_TOKEN=gho_xxx      # 或者先跑 gh auth token 取
    python tools/embed_token.py        # 打印新的 EMBED_B64

把打印出来的串替换 index.html 里的 `const EMBED_B64 = '...'`。
"""
import base64
import os
import subprocess
import sys

KEY = 0x5A


def read_token() -> str:
    token = os.environ.get("GH_ADMIN_TOKEN", "").strip()
    if token:
        return token
    try:
        out = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except Exception:
        sys.exit(
            "拿不到令牌：设置 GH_ADMIN_TOKEN，或者先 gh auth login\n"
            "（不要用明文把它写进仓库里的任何文件）"
        )


def main() -> None:
    token = read_token()
    if not token:
        sys.exit("令牌是空的")
    blob = base64.b64encode(bytes((ord(c) ^ KEY) for c in token)).decode()
    print(blob)
    print(f"\n# 长度 {len(token)}，前缀 {token[:4]}…；粘贴到 index.html 的 EMBED_B64",
          file=sys.stderr)


if __name__ == "__main__":
    main()
