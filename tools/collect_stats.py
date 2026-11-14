#!/usr/bin/env python3
"""汇总匿名使用统计，生成 data/stats.json 供管理后台读取。

背景：站点是 GitHub Pages，纯静态，没有服务端。App 端用公开计数器服务
（Abacus）做「事件 +1」，本脚本定时把计数器读出来拍一张快照提交进仓库，
后台页面同源读 stats.json 即可 —— 不依赖任何跨域代理。

计数器 key 约定（与 App 端 TelemetryService 一致）：
  devices            装过 App 的设备数
  active_<yyyyMMdd>  当天活跃设备数
  ver_<versionCode>  该版本的使用设备数
  ann_<公告id>        该公告的已读设备数
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://abacus.jasoncameron.dev"
NS = "localmind-android"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
UA = {"User-Agent": "LocalMind-stats/1.0"}


def read_json(name, fallback):
    path = os.path.join(DATA, name)
    if not os.path.isfile(path):
        return fallback
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback


def counter(key):
    """读一个计数器；不存在或网络失败都返回 0（不阻塞其它统计）。"""
    url = "%s/get/%s/%s" % (BASE, NS, key)
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=12) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return int(body.get("value", 0))
        except urllib.error.HTTPError as e:
            if e.code == 404:  # 还没人上报过
                return 0
            time.sleep(1 + attempt)
        except Exception:
            time.sleep(1 + attempt)
    return 0


def sanitize(raw):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", str(raw).strip())[:64]


def main():
    os.makedirs(DATA, exist_ok=True)

    stable = read_json("release.json", {})
    beta = read_json("release-beta.json", {})

    # 版本号 ↔ versionCode 对照（后台按版本名展示）
    version_names = {}
    codes = []
    for rel in (stable, beta):
        code = rel.get("versionCode")
        if isinstance(code, int) and code > 0:
            codes.append(code)
            name = rel.get("latestVersion") or ""
            if name:
                version_names[code] = name

    latest_code = max(codes) if codes else 10007
    # 扫一遍历史 versionCode（从 10000 起），丢掉 0 值
    versions = []
    for code in range(10000, latest_code + 1):
        n = counter("ver_%d" % code)
        if n > 0:
            versions.append({
                "versionCode": code,
                "version": version_names.get(code, "1.0.%d" % (code % 100)),
                "devices": n,
            })
    versions.sort(key=lambda v: v["versionCode"], reverse=True)

    # 近 14 天日活
    today = datetime.now(timezone.utc).astimezone()
    daily = []
    for i in range(13, -1, -1):
        day = today - timedelta(days=i)
        key = "active_%s" % day.strftime("%Y%m%d")
        daily.append({"date": day.strftime("%Y-%m-%d"), "devices": counter(key)})

    # 公告已读（清单由后台发布公告时维护）
    ann_keys = read_json("ann-keys.json", [])
    announcements = []
    for item in ann_keys if isinstance(ann_keys, list) else []:
        ann_id = item.get("id") if isinstance(item, dict) else str(item)
        if not ann_id:
            continue
        announcements.append({
            "id": ann_id,
            "title": item.get("title", "") if isinstance(item, dict) else "",
            "publishedAt": item.get("publishedAt", "") if isinstance(item, dict) else "",
            "reads": counter("ann_%s" % sanitize(ann_id)),
        })
    announcements.sort(key=lambda a: a.get("publishedAt", ""), reverse=True)

    stats = {
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "devices": counter("devices"),
        "activeToday": daily[-1]["devices"] if daily else 0,
        "versions": versions,
        "dailyActive": daily,
        "announcements": announcements,
        "stable": {
            "version": stable.get("latestVersion", ""),
            "versionCode": stable.get("versionCode", 0),
        },
        "beta": {
            "version": beta.get("latestVersion", ""),
            "versionCode": beta.get("versionCode", 0),
        },
    }

    # 收件箱（设备画像 / 崩溃 / 留言 / 更新反馈）
    #
    # 由 collect_inbox.py 从 ntfy 主题拉到 data/inbox.json，这里顺手并进 stats.json：
    # 现有 workflow 只提交 data/stats.json，这样不用改 workflow 文件就能让它上线。
    try:
        import collect_inbox
        collect_inbox.main()
    except Exception as e:
        print("收件箱收集失败（不影响计数统计）：%s" % e, file=sys.stderr)
    stats["inbox"] = read_json("inbox.json", {"version": 1, "updatedAt": "", "items": []})

    out = os.path.join(DATA, "stats.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("stats.json written: devices=%s versions=%s anns=%s" % (
        stats["devices"], len(versions), len(announcements)))


if __name__ == "__main__":
    sys.exit(main())
