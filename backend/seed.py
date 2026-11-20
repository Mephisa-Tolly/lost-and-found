"""
填充虚拟数据（招领启事 + 寻物启事），用于演示和功能验证。

用法：在 lost-and-found-v2.0 目录下打开 cmd，输入

    python seed.py

数据写入 backend/lost_found.db，会自动触发 AI 匹配。
重复运行会先清空原有数据，保持每次演示都是干净的同一份。
（云端首次启动会自动写入同样的数据，不需要手动执行本脚本。）
"""
import os
import sys
import json
import time
import sqlite3
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "lost_found.db")
BASE = os.getenv("BACKEND_BASE", "http://localhost:8000/api/v1")

# 演示数据集中放在 demo_data.py，供本脚本和后端自动初始化共用
from demo_data import ITEMS


def post_item(it):
    payload = {k: v for k, v in it.items() if k != "note"}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/items", data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print("  HTTP", e.code, e.read().decode("utf-8", "ignore")[:200])
        return None
    except Exception as e:
        print("  失败：", e)
        return None


def main():
    if not os.path.exists(DB):
        print("找不到数据库：" + DB)
        print("请先启动一次服务（在 backend 目录下运行 python main.py），它会自动建库。")
        sys.exit(1)

    # 清空旧数据，保证每次演示都是同一份干净的，且 id 重新从 1 开始
    conn = sqlite3.connect(DB)
    for t in ("matches", "claims", "notifications", "items"):
        try:
            conn.execute("DELETE FROM " + t)
        except Exception:
            pass
    # 重置自增序列，否则 id 会一直往上累加（演示时链接 id 会看着像错的）
    try:
        conn.execute("DELETE FROM sqlite_sequence")
    except Exception:
        pass
    conn.commit()
    conn.close()
    print("已清空旧数据\n")

    print("正在写入 %d 条虚拟数据……\n" % len(ITEMS))
    ok = 0
    for it in ITEMS:
        r = post_item(it)
        if r and r.get("code") == 200:
            ok += 1
            print("  [OK] %-6s %s" % (it["type"], it["title"]))
        else:
            print("  [失败] %s" % it["title"])
    print("\n写入完成：%d / %d 条" % (ok, len(ITEMS)))

    # 每条发布都会在后台线程触发匹配，连续写入时多个线程会同时跑。
    # 等它们跑完再报告结果，避免"看起来少了一条"或重复候选。
    print("\n等待 AI 后台匹配完成……", end="", flush=True)
    deadline = time.time() + 30
    last = -1
    stable = 0
    while time.time() < deadline:
        time.sleep(2)
        print(".", end="", flush=True)
        try:
            with urllib.request.urlopen(BASE + "/stats", timeout=5) as r:
                matched = json.loads(r.read().decode("utf-8"))["data"]["matched"]
        except Exception:
            continue
        if matched == last:
            stable += 1
            if stable >= 2:      # 连续两次不变，认为跑完了
                break
        else:
            stable = 0
            last = matched
    print()

    try:
        with urllib.request.urlopen(BASE + "/stats", timeout=5) as r:
            s = json.loads(r.read().decode("utf-8"))["data"]
        print("当前数据：信息 %d 条（丢失 %d / 招领 %d），匹配候选 %d 条"
              % (s["total"], s["lost"], s["found"], s["matched"]))
        print("浏览器打开 " + BASE.replace("/api/v1", "") + "  即可查看「待确认匹配」页。")
    except Exception:
        pass


if __name__ == "__main__":
    main()
