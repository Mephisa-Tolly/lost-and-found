"""
AI 匹配服务 —— 流程编排层
================================================
这是 AI 模块的对外入口，把「粗筛」和「精排」串成一条完整流水线，
并把结果通过 HTTP 写回后端，前端就能在页面上看到 AI 的判断和理由。

整体链路（对应 EXP04 任务书要求的"集成进核心流程"）：

  新发布一条信息
      ↓
  ① 从后端拉取全库信息        GET  /api/v1/items
      ↓
  ② 结构化硬过滤（规则，FR05）  coarse_filter.hard_filter
      ↓
  ③ 字面相似度粗排（TF-IDF，FR06）coarse_filter.coarse_rank  → 取前 10
      ↓
  ④ 大模型语义精排（LLM，FR07）  llm_ranker.llm_rank         → 取前 3 + 理由
      ↓
  ⑤ 写回匹配结果              POST /api/v1/matches （upsert）
      ↓
  前端「待处理匹配」页展示

启动方式（在 ai 目录下）：
    python main.py                 # 常驻 HTTP 服务，端口 8100
    python main.py --once          # 只跑一次全库批处理然后退出
    python main.py --item-id 12    # 只对某一条信息跑匹配

为什么用标准库 http.server 而不是 FastAPI？
—— 为了让 AI 模块能独立运行、少装依赖。它和真正的后端服务解耦，
   任何组员都能单独启动它调试，不影响主后端。
"""
import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer


def load_dotenv(path=".env"):
    """
    极简 .env 读取（不依赖 python-dotenv）。
    已经存在的环境变量优先，不被文件覆盖 —— 这样才能用 set 临时改值。
    """
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception as e:
        print(f"[警告] 读取 {path} 失败：{e}")


# 必须在读取下面的模块级配置之前执行
load_dotenv()

from coarse_filter import hard_filter, coarse_rank  # noqa: E402
from llm_ranker import llm_rank, lexical_results, score_to_level  # noqa: E402

BACKEND = os.getenv("BACKEND_BASE", "http://localhost:8000/api/v1").rstrip("/")
TOP_K = int(os.getenv("TOP_K", "3"))
COARSE_LIMIT = int(os.getenv("COARSE_LIMIT", "10"))
RECALL_DAYS = int(os.getenv("RECALL_DAYS", "30"))
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.35"))


# ---------------- 后端 HTTP 客户端 ----------------
def _http(method: str, path: str, payload=None, timeout=20):
    url = f"{BACKEND}{path}"
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all_items():
    """
    拉全库信息。后端单页上限 100 条，这里循环翻页直到拿完。
    """
    out = []
    page = 1
    page_size = 100
    while True:
        body = _http("GET", f"/items?page={page}&size={page_size}")
        data = body.get("data") or {}
        batch = data.get("list") or []
        out.extend(batch)
        total = data.get("total") or 0
        if len(batch) < page_size or len(out) >= total:
            break
        page += 1
    return out


def fetch_item(item_id: int):
    body = _http("GET", f"/items/{item_id}")
    return body.get("data")


def push_matches(source_id: int, results):
    """把匹配结果写回后端。source_item_id 固定，后端按 (source,candidate) upsert。"""
    ok = 0
    for r in results:
        payload = {
            "source_item_id": source_id,
            "candidate_item_id": r["candidate_id"],
            "score": r["score"],
            "level": r["level"],
            "reasons": r["reasons"],
            "source": r["source"],
        }
        try:
            _http("POST", "/matches", payload)
            ok += 1
        except Exception as e:
            print(f"  [写入失败] candidate={r['candidate_id']} {e}")
    return ok


# ---------------- 核心流程 ----------------
def match_one(source: dict, pool=None, dry_run=False) -> dict:
    """
    对一条信息执行完整匹配流程，返回结构化结果（方便单测和 HTTP 接口复用）
    """
    t0 = __import__("time").time()
    if pool is None:
        pool = fetch_all_items()

    # ② 硬过滤
    filtered = hard_filter(source, pool, recall_days=RECALL_DAYS)
    # ③ 粗排
    ranked = coarse_rank(source, filtered, limit=COARSE_LIMIT)

    trace = {
        "source_item_id": source.get("item_id"),
        "stage": {},
    }
    trace["stage"]["pull"] = {"pool_size": len(pool)}
    trace["stage"]["hard_filter"] = {
        "count": len(filtered),
        "ids": [c.get("item_id") for c in filtered],
    }
    trace["stage"]["coarse_rank"] = {
        "count": len(ranked),
        "top": [{"id": it.get("item_id"), "lexical": sc} for it, sc in ranked[:5]],
    }

    candidates = [it for it, _ in ranked]

    # ④ 精排
    if candidates:
        out = llm_rank(source, candidates, top_k=TOP_K)
        if out["degraded"] or not out["results"]:
            results = lexical_results(source, ranked, top_k=TOP_K)
            degraded = True
            note = out.get("note") or "精排无结果，已降级"
        else:
            results = out["results"]
            degraded = False
            note = out["note"]
    else:
        results = []
        degraded = False
        note = "硬过滤后无候选，无需匹配"

    # 低于阈值的丢弃（避免给用户推一堆"低相关"噪音）
    kept = [r for r in results if r["score"] >= MIN_SCORE]
    dropped = len(results) - len(kept)

    trace["stage"]["llm_rank"] = {
        "degraded": degraded,
        "note": note,
        "returned": len(results),
        "kept": len(kept),
        "dropped_below_min_score": dropped,
    }
    trace["note"] = note
    trace["degraded"] = degraded
    trace["results"] = kept
    trace["elapsed_ms"] = int((__import__("time").time() - t0) * 1000)

    # ⑤ 写回
    if not dry_run and kept:
        trace["written"] = push_matches(source["item_id"], kept)
    else:
        trace["written"] = 0

    return trace


def run_all(dry_run=False):
    """全库批处理：对每条信息都跑一遍匹配（用于初始化或定时重算）"""
    items = fetch_all_items()
    print(f"全库 {len(items)} 条，开始批量匹配…")
    summary = []
    for i, it in enumerate(items, 1):
        try:
            r = match_one(it, pool=items, dry_run=dry_run)
            summary.append(r)
            print(f"[{i}/{len(items)}] item {it.get('item_id')} → 候选 {len(r['results'])} 条"
                  f"（{r['note']}，{r['elapsed_ms']}ms）")
        except Exception as e:
            print(f"[{i}/{len(items)}] item {it.get('item_id')} 失败：{e}")
    total = sum(len(s["results"]) for s in summary)
    print(f"完成：处理 {len(summary)} 条信息，产出 {total} 条匹配")
    return summary


# ---------------- HTTP 服务 ----------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # 静音默认日志，避免刷屏

    def _send(self, code: int, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(200, {"ok": True})

    def do_GET(self):
        if self.path.startswith("/health"):
            return self._send(200, {
                "status": "ok",
                "backend": BACKEND,
                "llm_key_configured": bool(os.getenv("LLM_API_KEY", "").strip()),
                "config": {"TOP_K": TOP_K, "COARSE_LIMIT": COARSE_LIMIT,
                           "RECALL_DAYS": RECALL_DAYS, "MIN_SCORE": MIN_SCORE},
            })
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception:
            return self._send(400, {"error": "请求体不是合法 JSON"})

        # POST /match          body: {item_id: 12}  → 对指定条目跑匹配
        if self.path.startswith("/match"):
            item_id = payload.get("item_id")
            if item_id is None:
                return self._send(400, {"error": "缺少 item_id"})
            try:
                item = fetch_item(int(item_id))
            except Exception as e:
                return self._send(502, {"error": f"拉取 item 失败: {e}"})
            if not item:
                return self._send(404, {"error": f"item {item_id} 不存在"})
            try:
                result = match_one(item)
            except Exception as e:
                return self._send(500, {"error": f"匹配失败: {e}"})
            return self._send(200, {"code": 200, "msg": "ok", "data": result})

        # POST /batch         body: {}            → 全库批处理
        if self.path.startswith("/batch"):
            try:
                summary = run_all()
            except Exception as e:
                return self._send(500, {"error": f"批处理失败: {e}"})
            return self._send(200, {"code": 200, "msg": "ok",
                                    "data": {"processed": len(summary)}})

        return self._send(404, {"error": "not found"})


def doctor():
    """
    自检：告诉用户"页面为什么是空的"。
    按顺序检查：后端通不通 → 有没有物品 → 有没有匹配记录 → 大模型配没配
    """
    print("=" * 66)
    print("AI 模块自检")
    print("=" * 66)

    problems = []

    # ① 后端连通性
    try:
        body = _http("GET", "/stats", timeout=5)
        st = body.get("data") or {}
        print(f"[1] 后端连接    OK   {BACKEND}")
        print(f"                物品 {st.get('total')} 条（寻物 {st.get('lost')} / 招领 {st.get('found')}）")
        print(f"                匹配记录 {st.get('matched')} 条")
    except Exception as e:
        print(f"[1] 后端连接    失败  {BACKEND}")
        print(f"                原因：{type(e).__name__}: {e}")
        print("                → 后端没启动，或 BACKEND_BASE 地址不对")
        print("                → 在 backend 目录运行：python -m uvicorn main:app --reload --port 8000")
        return

    total_items = st.get("total") or 0
    total_matches = st.get("matched") or 0

    # ② 有没有物品
    if total_items == 0:
        print("[2] 物品数据    空   数据库里一条信息都没有")
        problems.append("数据库里没有物品 —— 先去页面上发布几条失物/招领信息")
    else:
        print(f"[2] 物品数据    OK   {total_items} 条")

    # ③ 有没有匹配
    if total_items > 0 and total_matches == 0:
        print("[3] 匹配记录    空   还没跑过匹配")
        problems.append("从没跑过匹配 —— 在 ai 目录运行：python main.py --once")
    elif total_matches > 0:
        print(f"[3] 匹配记录    OK   {total_matches} 条")
    else:
        print("[3] 匹配记录    -    无物品，跳过")

    # ④ 待确认数量
    try:
        body = _http("GET", "/matches/pending", timeout=5)
        pend = (body.get("data") or {})
        n_rows = pend.get("total") or 0
        n_cands = sum(len(r.get("candidates") or []) for r in (pend.get("list") or []))
        print(f"[4] 待确认页    {n_rows} 个条目 / {n_cands} 个候选")
        if n_rows == 0 and total_matches > 0:
            print("                → 有匹配记录但都已被确认或忽略了，属正常")
        if n_rows == 0 and total_matches == 0 and total_items > 0:
            problems.append("待确认为空是因为还没跑匹配（同上）")
    except Exception as e:
        print(f"[4] 待确认页    读取失败  {e}")

    # ⑤ 大模型配置
    key = os.getenv("LLM_API_KEY", "").strip()
    if key:
        from llm_ranker import LLMConfig, build_endpoint
        cfg = LLMConfig()
        print(f"[5] 大模型      已配置  {cfg.model}")
        print(f"                地址 {build_endpoint(cfg.base_url)}")
        print(f"                Key  {key[:8]}...{key[-4:] if len(key) > 12 else ''}")
    else:
        print("[5] 大模型      未配置  将走字面相似度降级（功能可用，理由没那么准）")
        print("                → 复制 .env.example 为 .env，填入 LLM_API_KEY")

    print("-" * 66)
    if problems:
        print("需要处理：")
        for i, p in enumerate(problems, 1):
            print(f"  {i}. {p}")
    else:
        print("一切正常。如果页面还是空的，按 Ctrl+F5 强制刷新一次浏览器。")
    print("=" * 66)


def main():
    ap = argparse.ArgumentParser(description="失物招领 AI 匹配服务")
    ap.add_argument("--port", type=int, default=int(os.getenv("AI_PORT", "8100")))
    ap.add_argument("--once", action="store_true", help="只跑一次全库批处理")
    ap.add_argument("--item-id", type=int, help="只对指定 item 跑匹配")
    ap.add_argument("--dry-run", action="store_true", help="只计算不写回后端")
    ap.add_argument("--status", action="store_true", help="自检：页面为什么是空的")
    args = ap.parse_args()

    if args.status:
        doctor()
        return

    if args.item_id:
        item = fetch_item(args.item_id)
        if not item:
            print(f"item {args.item_id} 不存在")
            sys.exit(1)
        r = match_one(item, dry_run=args.dry_run)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return

    if args.once:
        run_all(dry_run=args.dry_run)
        return

    print(f"AI 匹配服务启动：http://localhost:{args.port}")
    print(f"  后端地址 {BACKEND}")
    print(f"  大模型   {'已配置' if os.getenv('LLM_API_KEY', '').strip() else '未配置（将走字面相似度降级）'}")
    HTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
