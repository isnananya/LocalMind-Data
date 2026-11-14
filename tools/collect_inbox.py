#!/usr/bin/env python3
"""把 App 端推来的消息（设备画像 / 崩溃 / 留言 / 内测选择）收进 data/inbox.json。

链路：
    App ──POST──> ntfy.sh/<topic>  ──拉取──> 本脚本 ──> data/inbox.json ──> 后台页面

为什么绕这一圈：站点是 GitHub Pages（纯静态，写不了），而崩溃日志和用户留言
是**文本**，没有计数器服务能存。用 ntfy 当收件箱 + 定时任务落库，好处是
**APK 里不需要内置任何 GitHub 令牌**（否则谁都能反编译拿去改仓库）。

注意：ntfy 的公开主题没有鉴权，任何人都能往里写。所以这里只当"用户来信"看，
不当可信数据源 —— 展示时原样呈现、不做自动决策。

消息格式（App 端 TelemetryService.publish 发出来的 body 就是一段 JSON）：
  kind=device   机型/系统/运存/CPU/版本
  kind=crash    堆栈 + 用户补充说明（用户点了"上传"才发）
  kind=idea     功能建议正文 + 可选联系方式
  kind=update   更新弹窗的选择（accept / reject）
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

TOPIC = "lm-inbox-7f3a91c4e5b2d8a6"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
INBOX = os.path.join(DATA, "inbox.json")
UA = {"User-Agent": "LocalMind-inbox/1.0"}

# 保留条数上限：只留最近的，免得仓库越滚越大（每条几 KB，500 条约 1~2 MB）
MAX_ITEMS = 500


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_inbox():
    if not os.path.isfile(INBOX):
        return {"version": 1, "updatedAt": "", "items": [], "seen": []}
    try:
        with open(INBOX, encoding="utf-8") as f:
            j = json.load(f)
        if not isinstance(j.get("items"), list):
            j["items"] = []
        if not isinstance(j.get("seen"), list):
            j["seen"] = []
        return j
    except Exception as e:
        print("inbox.json 读取失败，重建：%s" % e, file=sys.stderr)
        return {"version": 1, "updatedAt": "", "items": [], "seen": []}


def fetch_messages():
    """拉主题里还留着的消息。ntfy 免费版默认只留 12 小时，所以 15 分钟一跑很安全。"""
    url = "https://ntfy.sh/%s/json?poll=1" % TOPIC
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        print("拉取 ntfy 失败（本轮跳过）：%s" % e, file=sys.stderr)
        return []

    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get("event") != "message":
            continue
        body = ev.get("message", "")
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                continue
        except Exception:
            continue
        payload["nid"] = ev.get("id", "")
        payload["recvAt"] = ev.get("time", 0)
        out.append(payload)
    return out


def main():
    inbox = load_inbox()
    # 去重靠 seen（永久保留），不靠 items —— items 会被 MAX_ITEMS 截断，
    # 早先的 id 一旦掉出 items 就会被重新收进来（这个 bug 实际发生过）。
    seen = set(inbox.get("seen") or [])
    seen |= {it.get("nid") for it in inbox["items"] if it.get("nid")}
    incoming = fetch_messages()

    added = 0
    for m in incoming:
        nid = m.get("nid")
        if not nid or nid in seen:
            continue
        seen.add(nid)
        inbox["items"].append(m)
        added += 1

    if added == 0:
        print("没有新消息")
        # 仍然写一次，保证文件存在（首次部署时 Pages 才有东西可读）
        if not os.path.isfile(INBOX):
            write(inbox)
        return

    # 只留最近 MAX_ITEMS 条：按客户端时间 ts 排序，没有 ts 的用接收时间
    inbox["items"].sort(key=lambda it: it.get("ts") or it.get("recvAt") or 0)
    if len(inbox["items"]) > MAX_ITEMS:
        inbox["items"] = inbox["items"][-MAX_ITEMS:]

    # seen 也要封顶，否则长期会无限增长（2000 个 id ≈ 30KB，够用）
    inbox["seen"] = list(seen)[-2000:]

    by_kind = {}
    for it in inbox["items"]:
        k = it.get("kind", "?")
        by_kind[k] = by_kind.get(k, 0) + 1
    inbox["updatedAt"] = now_iso()
    write(inbox)
    print("新增 %d 条；累计 %s" % (added, json.dumps(by_kind, ensure_ascii=False)))


def write(inbox):
    os.makedirs(DATA, exist_ok=True)
    with open(INBOX, "w", encoding="utf-8") as f:
        json.dump(inbox, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
