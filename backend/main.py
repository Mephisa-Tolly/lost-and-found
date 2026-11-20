# main.py
from fastapi import FastAPI, HTTPException, Query, Request, Header
import html
import base64
import hashlib
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from typing import Optional, List
import sqlite3
import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta

from fastapi.middleware.cors import CORSMiddleware

import socket

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIST = os.path.normpath(os.path.join(BASE_DIR, "..", "frontend", "dist"))
AI_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "ai"))

app = FastAPI(
    title="校园智能失物招领匹配系统 API",
    swagger_ui_parameters={
        "swagger_js_url": "https://cdn.bootcdn.net/ajax/libs/swagger-ui/4.15.5/swagger-ui-bundle.js",
        "swagger_css_url": "https://cdn.bootcdn.net/ajax/libs/swagger-ui/4.15.5/swagger-ui.css",
    }
)
# 数据库位置：本地默认在 backend 目录下；
# 云平台挂载了持久磁盘时，用 DB_PATH 环境变量指过去（否则容器重启数据会丢）
DB_PATH = os.getenv("DB_PATH") or os.path.join(BASE_DIR, "lost_found.db")

# 图片落盘目录：与数据库同级，挂持久磁盘（DB_PATH=/app/data/xx.db）时图片一起保留。
# 数据库里只存 /api/v1/media/xxx.jpg 这样的短路径，列表接口不再返回几 MB 的 base64。
UPLOAD_DIR = os.getenv("UPLOAD_DIR") or os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/api/v1/media", StaticFiles(directory=UPLOAD_DIR), name="media")

# 允许的图片类型：mime -> 落盘扩展名（不接受 svg，避免脚本注入）
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 单张 5MB
MAX_IMAGE_COUNT = 3


def save_data_url_image(data_url: str) -> str:
    """把 data:image/...;base64,... 解码落盘，返回可访问的相对路径。"""
    header, _, b64 = data_url.partition(",")
    mime = header[5:].split(";")[0].lower()  # 去掉 "data:"
    raw = base64.b64decode(b64, validate=True)
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("单张图片不能超过 5MB")
    ext = ALLOWED_IMAGE_TYPES[mime]
    name = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
        f.write(raw)
    return f"/api/v1/media/{name}"


def remove_item_images(images_json):
    """删除某条记录关联的图片文件（忽略异常，避免删记录时被文件问题阻断）"""
    try:
        names = json.loads(images_json or "[]")
    except Exception:
        return
    for u in names if isinstance(names, list) else []:
        if isinstance(u, str) and u.startswith("/api/v1/media/"):
            path = os.path.join(UPLOAD_DIR, os.path.basename(u))
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except OSError:
                pass

# 允许前端(Vite/5173)跨域访问本服务
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 简易登录与权限（V3.0 新增） ====================
# 课程 Demo 的定位：不做注册、不做密码找回，只提供「用户 / 管理员」两个演示账号，
# 用来演示两种角色看到的界面和能做的操作不同。
# 口令不写死在代码里：可用环境变量 AUTH_USER_PASS / AUTH_ADMIN_PASS 覆盖，
# 默认值仅用于课堂演示，真实部署请改掉。
_ADMIN_USER = os.getenv("AUTH_ADMIN_USER", "admin")
_ADMIN_PASS = os.getenv("AUTH_ADMIN_PASS", "admin123")
_USER_USER = os.getenv("AUTH_USER_USER", "user")
_USER_PASS = os.getenv("AUTH_USER_PASS", "user123")

# token 无状态签名（不落库），进程重启后旧 token 失效——课堂上重新登录即可
_SECRET = os.getenv("AUTH_SECRET", "campus-lostfound-v3-demo-secret")


def _make_token(username: str, role: str) -> str:
    raw = f"{username}:{role}"
    sig = hashlib.sha256((raw + _SECRET).encode("utf-8")).hexdigest()[:32]
    return base64.urlsafe_b64encode(f"{raw}:{sig}".encode("utf-8")).decode("ascii")


def _parse_token(token: str):
    """返回 {username, role} 或 None（签名不对/格式不对都算无效）"""
    if not token:
        return None
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        username, role, sig = raw.split(":")
    except Exception:
        return None
    want = hashlib.sha256(f"{username}:{role}".encode("utf-8") + _SECRET.encode("utf-8")).hexdigest()[:32]
    if sig != want:
        return None
    return {"username": username, "role": role}


def _current_user(authorization: Optional[str]) -> Optional[dict]:
    if not authorization:
        return None
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return _parse_token(parts[1])


def _require_admin(authorization: Optional[str]):
    """管理员操作校验：不是管理员就抛 403，由调用方转成统一响应"""
    u = _current_user(authorization)
    if not u or u.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return u


class LoginReq(BaseModel):
    username: str
    password: str


@app.post("/api/v1/auth/login")
def auth_login(req: LoginReq, authorization: Optional[str] = Header(None)):
    """登录。前端拿到 token 存在 localStorage，后续请求带 Authorization: Bearer <token>"""
    u = (req.username or "").strip()
    p = (req.password or "").strip()
    if u == _ADMIN_USER and p == _ADMIN_PASS:
        return api_response(200, "登录成功", {
            "token": _make_token(u, "admin"), "username": u, "role": "admin",
            "role_name": "管理员",
        })
    if u == _USER_USER and p == _USER_PASS:
        return api_response(200, "登录成功", {
            "token": _make_token(u, "user"), "username": u, "role": "user",
            "role_name": "普通用户",
        })
    return api_response(401, "账号或密码不正确")


@app.get("/api/v1/auth/me")
def auth_me(authorization: Optional[str] = Header(None)):
    """校验 token 是否仍然有效，前端启动时调用一次"""
    u = _current_user(authorization)
    if not u:
        return api_response(401, "登录状态已失效，请重新登录")
    return api_response(200, "success", u)


def get_db():
    """
    统一连接入口。

    测试阶段多人同时发布时，SQLite 默认会报 database is locked。
    这里做三件事让它扛住并发：
      1. timeout=30        —— 拿不到锁最多等 30 秒，而不是立刻失败
      2. WAL 模式          —— 读不阻塞写、写不阻塞读（默认的 rollback 模式做不到）
      3. busy_timeout      —— 底层再兜一层，避免驱动层提前放弃
    """
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")   # 幂等，重复设置返回当前模式
        conn.execute("PRAGMA synchronous = NORMAL")
    except Exception:
        pass
    return conn


def ensure_db():
    """启动时自动建库建表，重复运行不会丢数据。用户不需要手动跑 migrate.py。"""
    schema = os.path.join(BASE_DIR, "schema.sql")
    fresh = not os.path.exists(DB_PATH)
    if not os.path.exists(schema):
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        # 无论新旧都执行一遍：CREATE ... IF NOT EXISTS 是幂等的，能补齐新增的索引
        with open(schema, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
        print(f"[DB] 数据库就绪 {DB_PATH}" + ("（新建）" if fresh else ""))

        # 老库补字段：matches.source / sensitive_level 归一
        cols = [r[1] for r in conn.execute("PRAGMA table_info(matches)")]
        if cols and "source" not in cols:
            conn.execute("ALTER TABLE matches ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'semantic'")
            conn.commit()
            print("[DB] 已补充 matches.source 字段")

        # V3.0 老库补字段：claims 表补申请人用户名 / 审核意见 / 审核时间
        ccols = [r[1] for r in conn.execute("PRAGMA table_info(claims)")]
        if ccols:
            for name, ddl in (
                ("applicant_name", "ALTER TABLE claims ADD COLUMN applicant_name VARCHAR(50) DEFAULT 'user'"),
                ("review_note", "ALTER TABLE claims ADD COLUMN review_note TEXT"),
                ("reviewed_at", "ALTER TABLE claims ADD COLUMN reviewed_at DATETIME"),
            ):
                if name not in ccols:
                    conn.execute(ddl)
                    print(f"[DB] 已补充 claims.{name} 字段")
            conn.commit()
        try:
            conn.execute("UPDATE items SET sensitive_level='normal' WHERE sensitive_level IN ('0','','0.0')")
            conn.execute("UPDATE items SET sensitive_level='sensitive' WHERE sensitive_level IN ('1','1.0')")
            conn.commit()
        except Exception:
            pass

        # 历史库可能已经存在重复配对：先去重（保留分数最高的那条），否则唯一索引建不上
        try:
            dup = conn.execute("""SELECT source_item_id, candidate_item_id, COUNT(*) c
                                  FROM matches GROUP BY 1, 2 HAVING c > 1""").fetchall()
            if dup:
                for sid, cid, _ in dup:
                    conn.execute("""DELETE FROM matches WHERE match_id NOT IN (
                                        SELECT match_id FROM matches
                                        WHERE source_item_id=? AND candidate_item_id=?
                                        ORDER BY score DESC, match_id ASC LIMIT 1)
                                    AND source_item_id=? AND candidate_item_id=?""",
                                 (sid, cid, sid, cid))
                conn.commit()
                print(f"[DB] 清理历史重复匹配 {len(dup)} 组")
        except Exception:
            pass
        # 索引可能因上面的清理顺序没建上，这里再兜一次
        conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS ux_matches_pair
                        ON matches(source_item_id, candidate_item_id)""")
        conn.commit()
    finally:
        conn.close()

def api_response(code: int, msg: str, data: dict = None):
    return {"code": code, "msg": msg, "data": data or {}}


@app.exception_handler(RequestValidationError)
async def _validation_handler(request, exc):
    """把 FastAPI 的校验错误翻成前端认识的统一结构，前端直接显示 msg 即可。"""
    errs = exc.errors()
    msg = "参数错误"
    if errs:
        first = errs[0]
        raw = str(first.get("msg", "")).replace("Value error, ", "")
        loc = first.get("loc") or []
        field = loc[-1] if loc else ""
        type_ = first.get("type", "")
        if type_ == "missing":
            msg = f"缺少必填项：{field}"
        elif not raw or raw == "Field required":
            msg = f"{field} 参数不合法"
        else:
            msg = raw
    return JSONResponse(status_code=400, content=api_response(400, msg))


# ============================================================
# AI 匹配集成：发布后自动触发，无需单独启动 AI 服务
# ============================================================
# 把 ai 目录加进模块搜索路径，直接复用 coarse_filter / llm_ranker
if AI_DIR not in sys.path:
    sys.path.insert(0, AI_DIR)

try:
    from coarse_filter import hard_filter, coarse_rank
    from llm_ranker import llm_rank, lexical_results, score_to_level, LLMConfig
    _AI_READY = True
except Exception as _e:
    print(f"[AI] 模块加载失败（ai 目录缺失或文件损坏）：{_e}")
    _AI_READY = False


def _read_ai_config():
    """从 ai/.env 读配置（如果存在），同时把 LLM_API_KEY 等注入环境变量"""
    cfg = {"TOP_K": 3, "COARSE_LIMIT": 10, "RECALL_DAYS": 30, "MIN_SCORE": 0.35}
    env_path = os.path.join(AI_DIR, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k in cfg:
                        cfg[k] = float(v) if k == "MIN_SCORE" else int(v)
                    # 大模型 Key 等配置注入环境，供 llm_ranker 读取
                    if k and v and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass
    return cfg


# 最近一次大模型调用结果：ok=None 未调用 / True 成功 / False 失败
_AI_LAST = {"ok": None, "note": "", "at": ""}

_read_ai_config()  # 启动时加载一次，让 LLM_API_KEY 尽早生效
ensure_db()        # 启动时自动建库/补字段，用户无需手动跑 migrate.py


def auto_seed_if_empty():
    """
    库是空的就写入演示数据。
    云端容器每次重启文件系统都是新的，没有这一步，测试组打开只会看到一个空页面。
    本地已有数据时不会执行；想强制关掉就设环境变量 AUTO_SEED=0。
    """
    if os.getenv("AUTO_SEED", "1").strip() == "0":
        return
    conn = get_db()
    try:
        n = conn.execute("SELECT COUNT(*) c FROM items").fetchone()["c"]
        if n > 0:
            return

        from demo_data import ITEMS
        cur = conn.cursor()
        for it in ITEMS:
            sensitive = detect_sensitive(it.get("category", ""), it.get("title", ""),
                                         it.get("description", ""))
            cur.execute("""INSERT INTO items
                           (type, title, category, location, time, description, color, brand,
                            anonymous, status, sensitive_level, created_by)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, '待匹配', ?, 1)""",
                        (it["type"], it["title"], it["category"], it["location"], it["time"],
                         it["description"], it.get("color", ""), it.get("brand", ""), sensitive))
        conn.commit()
        print(f"[DEMO] 空库，已自动写入演示数据 {len(ITEMS)} 条")
        ids = [r["item_id"] for r in conn.execute("SELECT item_id FROM items").fetchall()]

    except Exception as e:
        conn.rollback()
        print(f"[DEMO] 演示数据写入失败：{e}")
        ids = []
    finally:
        conn.close()

    # 匹配放到后台线程跑，不拖慢启动；线程内自己开连接，不复用上面已关闭的
    if ids:
        def _warm():
            time.sleep(1)          # 让服务先起完整
            for i in ids:
                run_matching(i)
            print(f"[DEMO] 演示数据预匹配完成")
        threading.Thread(target=_warm, daemon=True).start()



def run_matching(source_id: int):
    """
    对一条信息执行完整匹配流水线（硬过滤 → 粗排 → 精排），结果写库。
    由发布接口在后台线程调用，用户无感知。
    """
    if not _AI_READY:
        return
    cfg = _read_ai_config()
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM items WHERE item_id = ?", (source_id,))
        row = cur.fetchone()
        if not row:
            return
        source = dict(row)
        cur.execute("SELECT * FROM items")
        pool = [dict(r) for r in cur.fetchall()]

        filtered = hard_filter(source, pool, recall_days=cfg["RECALL_DAYS"])
        ranked = coarse_rank(source, filtered, limit=cfg["COARSE_LIMIT"])
        if not ranked:
            return
        candidates = [it for it, _ in ranked]

        out = llm_rank(source, candidates, top_k=cfg["TOP_K"])
        # 记录最近一次大模型调用结果，供 /ai/status 展示（区分"Key 填对了"和"Key 是错的"）
        _AI_LAST["ok"] = out.get("ok")
        _AI_LAST["note"] = out.get("note") or ""
        _AI_LAST["at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if out["degraded"] or not out["results"]:
            results = lexical_results(source, ranked, top_k=cfg["TOP_K"])
        else:
            results = out["results"]

        # 本次达到阈值的候选（Top-K），用来清理上一轮遗留的推荐
        keep_ids = [r["candidate_id"] for r in results if r["score"] >= cfg["MIN_SCORE"]]
        if keep_ids:
            ph = ",".join("?" * len(keep_ids))
            cur.execute(f"""DELETE FROM matches
                            WHERE source_item_id = ? AND status = '推荐'
                              AND candidate_item_id NOT IN ({ph})""",
                        [source_id] + keep_ids)
        else:
            # 这一轮没有候选了（比如时间窗变了），旧的推荐也应作废
            cur.execute("DELETE FROM matches WHERE source_item_id = ? AND status = '推荐'",
                        (source_id,))

        for r in results:
            if r["score"] < cfg["MIN_SCORE"]:
                continue
            lvl = norm_level(r["level"], r["score"])
            reasons_json = json.dumps(r["reasons"], ensure_ascii=False)
            # 并发保护：多个后台线程可能同时对同一对记录写库。
            # 唯一索引 + upsert 保证「一对记录只有一条匹配」，不会出现重复候选。
            # 已确认/已拒绝的结果不被覆盖，避免把人工判断冲掉。
            cur.execute("""INSERT INTO matches
                           (source_item_id, candidate_item_id, score, level, matched_fields, source, status)
                           VALUES (?, ?, ?, ?, ?, ?, '推荐')
                           ON CONFLICT(source_item_id, candidate_item_id) DO UPDATE SET
                                score = excluded.score,
                                level = excluded.level,
                                matched_fields = excluded.matched_fields,
                                source = excluded.source
                           WHERE matches.status = '推荐'""",
                        (source_id, r["candidate_id"], r["score"], lvl, reasons_json, r["source"]))
        conn.commit()
        print(f"[AI] item {source_id} 匹配完成，写入 {len(results)} 条")
    except sqlite3.IntegrityError as e:
        # 并发下偶发的唯一键冲突：说明别的线程已经写过这条，直接放弃不报错
        conn.rollback()
        print(f"[AI] item {source_id} 并发冲突已忽略：{e}")
    except Exception as e:
        conn.rollback()
        print(f"[AI] item {source_id} 匹配失败：{e}")
    finally:
        conn.close()


def trigger_matching_async(source_id: int):
    """
    后台线程触发，不阻塞发布接口的响应。
    双向匹配：新发布的条目要去找候选；库里已有的对向条目也要把它纳入候选。
    """
    def _work():
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT item_id, type FROM items WHERE item_id = ?", (source_id,))
            row = cur.fetchone()
            if not row:
                return
            new_type = row["type"]
            # 新条目自己跑一遍
            run_matching(source_id)
            # 对向的"待匹配"条目也重跑一遍，让新条目有机会成为它们的候选
            opposite = "found" if new_type == "lost" else "lost"
            cur.execute("""SELECT item_id FROM items
                           WHERE type = ? AND status = '待匹配' AND item_id != ?""",
                        (opposite, source_id))
            for r in cur.fetchall():
                run_matching(r["item_id"])
        finally:
            conn.close()

    t = threading.Thread(target=_work, daemon=True)
    t.start()

# --- Pydantic 模型 (入参校验) ---
# 字段约束放在模型层，非法输入在进入业务逻辑前就被拦住并返回 400，
# 而不是让数据库 CHECK 约束报 500（那会把数据库错误暴露给前端）。
VALID_TYPES = ("lost", "found")

class ItemCreate(BaseModel):
    type: str
    title: str
    category: str
    location: str
    time: str
    description: str
    color: Optional[str] = None
    brand: Optional[str] = None
    images: Optional[List[str]] = None   # data:image/...;base64 字符串数组，最多 3 张
    anonymous: bool = False
    created_by: int = 1 # 默认测试用户ID

    @field_validator("type")
    @classmethod
    def _check_type(cls, v):
        v = (v or "").strip().lower()
        if v not in VALID_TYPES:
            raise ValueError("type 只能是 lost（丢失）或 found（招领）")
        return v

    @field_validator("title", "category", "location")
    @classmethod
    def _check_required_text(cls, v, info):
        v = (v or "").strip()
        if not v:
            raise ValueError(f"{info.field_name} 不能为空")
        limit = 100 if info.field_name != "category" else 30
        if len(v) > limit:
            raise ValueError(f"{info.field_name} 超过 {limit} 字")
        # 入库前 HTML 转义：<script> 之类会在库中变成纯文本，前端即使用 v-html 也不会执行
        return html.escape(v, quote=True)

    @field_validator("description")
    @classmethod
    def _check_description(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("description 不能为空")
        if len(v) > 2000:
            raise ValueError("描述最多 2000 字，请精简后重新提交")
        return html.escape(v, quote=True)

    @field_validator("time")
    @classmethod
    def _check_time(cls, v):
        v = (v or "").strip()
        parsed = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(v, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            raise ValueError("时间格式必须为 YYYY-MM-DD HH:MM（例：2026-11-03 14:30）")
        # 失物/招领的时间不可能在未来：允许多留 10 分钟时区误差
        if parsed > datetime.now() + timedelta(minutes=10):
            raise ValueError("时间不能晚于当前时间（失物不可能在未来丢失）")
        return v

    @field_validator("color", "brand")
    @classmethod
    def _check_opt_text(cls, v):
        v = (v or "").strip()
        if not v:
            return ""
        if len(v) > 30:
            raise ValueError("颜色/品牌最多 30 字")
        return html.escape(v, quote=True)

    @field_validator("images")
    @classmethod
    def _check_images(cls, v):
        """图片只接受 data:image/(jpeg|png|webp|gif|bmp);base64, 格式，最多 3 张，单张 5MB。
        非图片文件（pdf/exe/txt 等）即使绕过前端，也会在这里被拦下。"""
        if not v:
            return []
        if not isinstance(v, list):
            raise ValueError("images 必须是数组")
        if len(v) > MAX_IMAGE_COUNT:
            raise ValueError(f"图片最多上传 {MAX_IMAGE_COUNT} 张")
        cleaned = []
        for img in v:
            s = (img or "").strip()
            if not s:
                continue
            if not s.startswith("data:"):
                raise ValueError("图片格式不合法，请重新选择图片")
            header, _, b64 = s.partition(",")
            mime = header[5:].split(";")[0].lower()
            if mime not in ALLOWED_IMAGE_TYPES:
                raise ValueError("只能上传图片文件（jpg/png/webp/gif/bmp）")
            try:
                raw = base64.b64decode(b64, validate=True)
            except Exception:
                raise ValueError("图片数据损坏，请重新选择")
            if len(raw) > MAX_IMAGE_BYTES:
                raise ValueError("单张图片不能超过 5MB")
            cleaned.append(s)
        return cleaned

class StatusUpdate(BaseModel):
    target_status: str

class MatchCreate(BaseModel):
    source_item_id: int
    candidate_item_id: int
    score: float
    level: str
    reasons: Optional[List[str]] = None      # 新字段：匹配理由
    matched_fields: Optional[List[str]] = None  # 旧字段，保留兼容
    source: Optional[str] = "semantic"        # semantic=语义匹配 / lexical=字面匹配

    @field_validator("score")
    @classmethod
    def _check_score(cls, v):
        # 分数必须落在 0—1，越界直接拒绝，避免脏数据进库
        if v is None or not (0.0 <= float(v) <= 1.0):
            raise ValueError("score 必须在 0 到 1 之间")
        return float(v)

    @field_validator("source")
    @classmethod
    def _check_source(cls, v):
        v = (v or "semantic").strip().lower()
        if v not in ("semantic", "lexical", "fusion"):
            raise ValueError("source 只能是 semantic / lexical / fusion")
        return v

    @field_validator("source_item_id", "candidate_item_id")
    @classmethod
    def _check_id(cls, v):
        if int(v) <= 0:
            raise ValueError("物品 ID 必须为正整数")
        return int(v)

class MatchConfirm(BaseModel):
    status: str # 已确认 / 已拒绝

# --- 等级归一 ---
# 数据库里只存单字（高/中/低），前端要展示完整中文，
# AI 模块也可能传"高度疑似"这类长字符串，这里统一收口。
LEVEL_MAP = {
    "高": "高", "高度疑似": "高", "高相关": "高", "high": "高",
    "中": "中", "可能相关": "中", "中相关": "中", "medium": "中", "mid": "中",
    "低": "低", "低相关": "低", "low": "低",
}

def norm_level(level, score: float = 0.0) -> str:
    """把任意写法的等级归一到 高/中/低；认不出来就按分数兜底"""
    if level is not None:
        key = str(level).strip().lower()
        if key in LEVEL_MAP:
            return LEVEL_MAP[key]
    # 兜底：按分数划档（与 AI 模块阈值保持一致）
    if score >= 0.75:
        return "高"
    if score >= 0.45:
        return "中"
    return "低"

# --- 敏感物品识别 ---
# FR10：校园卡/学生证、银行卡、钥匙属于敏感物品，
# 这类信息需要遮挡关键细节、且认领时必须人工核验。
SENSITIVE_CATEGORIES = {"校园卡/学生证", "银行卡", "钥匙"}
# 描述里出现这些词，即使分类写的是"其他"也算敏感
SENSITIVE_WORDS = ("校园卡", "学生证", "一卡通", "银行卡", "身份证", "钥匙")

def detect_sensitive(category: str, title: str = "", description: str = "") -> str:
    """返回数据库用的敏感级别：'sensitive' / 'normal'"""
    if (category or "").strip() in SENSITIVE_CATEGORIES:
        return "sensitive"
    text = f"{title or ''}{description or ''}"
    if any(w in text for w in SENSITIVE_WORDS):
        return "sensitive"
    return "normal"


# --- 接口实现 ---

@app.post("/api/v1/items")
def create_item(item: ItemCreate):
    """发布失物招领信息"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # 自动识别敏感物品（校园卡/银行卡/钥匙）
        sensitive = detect_sensitive(item.category, item.title, item.description)
        # 图片落盘，库里只存短路径；库表保持轻量，列表接口不会因为图片变成几 MB
        saved_urls = []
        for data_url in (item.images or []):
            try:
                saved_urls.append(save_data_url_image(data_url))
            except ValueError:
                raise
        images_json = json.dumps(saved_urls, ensure_ascii=False)
        # 校验状态机：默认初始状态为"待匹配"
        cursor.execute("""
            INSERT INTO items (type, title, category, location, time, description, color, brand, images, anonymous, status, sensitive_level, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '待匹配', ?, ?)
        """, (item.type, item.title, item.category, item.location, item.time, 
              item.description, item.color, item.brand, images_json, item.anonymous, sensitive, item.created_by))
        conn.commit()
        item_id = cursor.lastrowid

        # 发布成功后自动触发 AI 匹配（后台线程，不影响发布响应速度）
        # 用户发布完，过几秒去「待确认匹配」页就能看到结果
        trigger_matching_async(item_id)
        return api_response(200, "发布成功", {"item_id": item_id})
    except Exception as e:
        conn.rollback()
        return api_response(500, f"系统异常: {str(e)}")
    finally:
        conn.close()

@app.get("/api/v1/items")
def list_items(
    page: int = Query(1, ge=1), 
    size: int = Query(10, ge=1, le=100),
    type: Optional[str] = None,
    category: Optional[str] = None,
    categories: Optional[str] = None,
    locations: Optional[str] = None,
    order: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None
):
    """信息池列表查询（分页/筛选）

    V3.0 新增广场所需的筛选：
    - categories=水杯,雨伞   多选类别（逗号分隔）
    - locations=图书馆,一食堂 多选地点（按名称包含匹配）
    - order=asc|desc         按发布时间排序，默认 desc（最新在最上面）
    """
    conn = get_db()
    cursor = conn.cursor()
    offset = (page - 1) * size
    query = "SELECT * FROM items WHERE 1=1"
    params = []
    
    if type:
        query += " AND type = ?"
        params.append(type)
    if category:
        query += " AND category = ?"
        params.append(category)
    if categories:
        cats = [c.strip() for c in categories.split(",") if c.strip()]
        if cats:
            query += " AND category IN (%s)" % ",".join("?" * len(cats))
            params.extend(cats)
    if locations:
        locs = [l.strip() for l in locations.split(",") if l.strip()]
        if locs:
            query += " AND (" + " OR ".join(["location LIKE ?"] * len(locs)) + ")"
            params.extend([f"%{l}%" for l in locs])
    if status:
        query += " AND status = ?"
        params.append(status)
    if keyword:
        query += " AND (title LIKE ? OR description LIKE ?)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])
        
    # 查询总数
    count_query = query.replace("SELECT *", "SELECT COUNT(*) as count")
    cursor.execute(count_query, params)
    total = cursor.fetchone()["count"]
    
    # 查询分页数据：默认最新在最上面；order=asc 时旧帖在前
    direction = "ASC" if str(order or "").lower() == "asc" else "DESC"
    query += f" ORDER BY datetime(created_at) {direction}, item_id {direction} LIMIT ? OFFSET ?"
    params.extend([size, offset])
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    data_list = [dict(row) for row in rows]
    # 公开列表不带私密特征与联系方式（敏感物品的核验答案不能随手可查）
    for row in data_list:
        row.pop("private_features", None)
        row.pop("contact_encrypted", None)
    return api_response(200, "success", {"total": total, "page": page, "size": size, "list": data_list})

@app.get("/api/v1/items/{item_id}")
def get_item(item_id: int, authorization: Optional[str] = Header(None)):
    """获取物品详情。私密特征与联系方式只对管理员返回，避免公开接口泄露答案。"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items WHERE item_id = ?", (item_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return api_response(404, "物品不存在")
    data = dict(row)
    data.setdefault("images", "")
    data["contact"] = ""
    data["sensitive_level"] = 1 if data.get("sensitive_level") in ("sensitive", 1, "1") else 0
    me = _current_user(authorization)
    if not me or me.get("role") != "admin":
        data["private_features"] = ""
        data["contact_encrypted"] = ""
    return api_response(200, "success", data)

@app.patch("/api/v1/items/{item_id}/status")
def update_item_status(item_id: int, req: StatusUpdate):
    """状态流转校验与更新"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 获取当前状态
    cursor.execute("SELECT status FROM items WHERE item_id = ?", (item_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return api_response(404, "物品不存在")
    
    current_status = row["status"]
    target_status = req.target_status
    
    # 状态机校验规则 (严格按数据字典)
    valid_transitions = {
        "待匹配": ["已匹配", "已关闭"],
        "已匹配": ["认领中", "已关闭", "无人认领"],
        "认领中": ["已确认", "已匹配"], # 认领失败退回已匹配
        "已确认": ["已关闭"],
        "无人认领": ["已关闭"]
    }
    
    if target_status not in valid_transitions.get(current_status, []):
        conn.close()
        return api_response(400, f"状态流转异常：不允许从 '{current_status}' 跳转到 '{target_status}'")
        
    try:
        cursor.execute("UPDATE items SET status = ? WHERE item_id = ?", (target_status, item_id))
        conn.commit()
        return api_response(200, "状态更新成功", {"item_id": item_id, "old_status": current_status, "new_status": target_status})
    except Exception as e:
        conn.rollback()
        return api_response(500, f"系统异常: {str(e)}")
    finally:
        conn.close()

def _item_brief(conn, item_id):
    """取候选物品的简要信息，供前端候选卡片展示"""
    cur = conn.cursor()
    cur.execute("""SELECT item_id, type, title, category, location, time, color, brand,
                          description, images, status FROM items WHERE item_id = ?""", (item_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def _load_matches(conn, source_item_id):
    """读取某条记录的全部匹配候选（按分数降序）"""
    cur = conn.cursor()
    cur.execute("""SELECT match_id, source_item_id, candidate_item_id, score, level,
                          matched_fields, source, status, created_at
                   FROM matches WHERE source_item_id = ? ORDER BY score DESC""", (source_item_id,))
    rows = [dict(r) for r in cur.fetchall()]
    result = []
    for r in rows:
        try:
            reasons = json.loads(r["matched_fields"]) if r["matched_fields"] else []
        except Exception:
            reasons = []
        cand = _item_brief(conn, r["candidate_item_id"])
        result.append({
            "match_id": r["match_id"],
            "candidate_id": r["candidate_item_id"],
            "candidate": cand,
            "score": r["score"],
            "level": r["level"],
            "reasons": reasons,
            "source": r["source"] or "semantic",
            "review": {"已确认": "confirmed", "已拒绝": "ignored"}.get(r["status"]),
            "status": r["status"],
        })
    return result


@app.get("/api/v1/items/{item_id}/matches")
def get_item_matches(item_id: int):
    """某条记录的人工确认候选列表（对应前端匹配结果页）"""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT item_id FROM items WHERE item_id = ?", (item_id,))
        if not cur.fetchone():
            return api_response(404, "物品不存在")
        item = _item_brief(conn, item_id)
        matches_list = _load_matches(conn, item_id)
        return api_response(200, "success", {"item": item, "item_id": item_id,
                                             "total": len(matches_list), "list": matches_list})
    finally:
        conn.close()


@app.get("/api/v1/matches/pending")
def pending_matches():
    """待人工确认的匹配总览（收件箱）"""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""SELECT DISTINCT source_item_id FROM matches
                       WHERE status = '推荐' ORDER BY source_item_id DESC""")
        ids = [r["source_item_id"] for r in cur.fetchall()]
        out = []
        for sid in ids:
            cands = _load_matches(conn, sid)
            pending = len([c for c in cands if not c["review"]])
            if not cands:
                continue
            out.append({"item": _item_brief(conn, sid), "candidates": cands, "pending": pending})
        out.sort(key=lambda x: -x["pending"])
        return api_response(200, "success", {"total": len(out), "list": out})
    finally:
        conn.close()


@app.get("/api/v1/ai/status")
def ai_status():
    """AI 模块当前状态，前端右上角据此显示是否已接入大模型"""
    from llm_ranker import LLMConfig
    cfg = LLMConfig()
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) c FROM matches WHERE source='semantic'")
        semantic = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) c FROM matches WHERE source='lexical'")
        lexical = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) c FROM matches")
        total = cur.fetchone()["c"]
    finally:
        conn.close()
    return api_response(200, "success", {
        "enabled": bool(_AI_READY and cfg.ready),
        "ai_ready": _AI_READY,
        "model": cfg.model if cfg.ready else "",
        "provider": cfg.base_url if cfg.ready else "",
        "mode": "语义匹配" if (cfg.ready and _AI_READY) else "字面相似匹配",
        "match_total": total,
        "by_source": {"semantic": semantic, "lexical": lexical},
        # 最近一次真实调用结果，用来区分"Key 填对了"和"Key 是错的"
        "last_call": dict(_AI_LAST),
    })


@app.get("/api/v1/stats")
def stats():
    """首页统计卡"""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) c FROM items")
        total = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) c FROM items WHERE type='lost'")
        lost = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) c FROM items WHERE type='found'")
        found = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) c FROM matches")
        matched = cur.fetchone()["c"]
        return api_response(200, "success", {"total": total, "lost": lost,
                                             "found": found, "matched": matched})
    finally:
        conn.close()


@app.post("/api/v1/matches")
def create_match(match: MatchCreate):
    """AI 匹配结果写入接口（由 AI 模块调用）"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        reasons = match.reasons if match.reasons else (match.matched_fields or [])
        lvl = norm_level(match.level, match.score)
        cursor.execute("""SELECT match_id FROM matches
                          WHERE source_item_id = ? AND candidate_item_id = ?""",
                       (match.source_item_id, match.candidate_item_id))
        exist = cursor.fetchone()
        if exist:
            cursor.execute("""UPDATE matches SET score=?, level=?, matched_fields=?, source=?
                              WHERE match_id=?""",
                           (match.score, lvl,
                            json.dumps(reasons, ensure_ascii=False),
                            match.source or "semantic", exist["match_id"]))
            conn.commit()
            return api_response(200, "匹配记录已更新", {"match_id": exist["match_id"]})
        cursor.execute("""INSERT INTO matches
                          (source_item_id, candidate_item_id, score, level, matched_fields, source, status)
                          VALUES (?, ?, ?, ?, ?, ?, '推荐')""",
                       (match.source_item_id, match.candidate_item_id, match.score,
                        lvl, json.dumps(reasons, ensure_ascii=False),
                        match.source or "semantic"))
        conn.commit()
        return api_response(200, "匹配记录写入成功", {"match_id": cursor.lastrowid})
    except Exception as e:
        conn.rollback()
        return api_response(500, f"系统异常: {str(e)}")
    finally:
        conn.close()


# ==================== 管理端接口（V3.0 新增，需管理员 token） ====================
@app.get("/api/v1/admin/items")
def admin_list_items(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    type: Optional[str] = None,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """管理端信息列表：比广场多返回敏感级别、创建时间等管理所需字段"""
    _require_admin(authorization)
    conn = get_db()
    try:
        cur = conn.cursor()
        query = "SELECT * FROM items WHERE 1=1"
        params = []
        if type:
            query += " AND type = ?"
            params.append(type)
        if category:
            query += " AND category = ?"
            params.append(category)
        if keyword:
            query += " AND (title LIKE ? OR description LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        count_q = query.replace("SELECT *", "SELECT COUNT(*) as count")
        cur.execute(count_q, params)
        total = cur.fetchone()["count"]
        query += " ORDER BY datetime(created_at) DESC, item_id DESC LIMIT ? OFFSET ?"
        params.extend([size, (page - 1) * size])
        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]
        return api_response(200, "success", {"total": total, "page": page, "size": size, "list": rows})
    finally:
        conn.close()


def _delete_items_by_ids(conn, ids):
    """删除信息及其关联的匹配、认领记录（外键/孤儿数据一并清理）"""
    cur = conn.cursor()
    deleted_claims = 0
    deleted_matches = 0
    for iid in ids:
        # 先把图片文件清掉，避免删记录后留下孤儿文件
        cur.execute("SELECT images FROM items WHERE item_id = ?", (iid,))
        row = cur.fetchone()
        if row:
            remove_item_images(row["images"])
        cur.execute("DELETE FROM matches WHERE source_item_id = ? OR candidate_item_id = ?", (iid, iid))
        deleted_matches += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        cur.execute("DELETE FROM claims WHERE item_id = ?", (iid,))
        deleted_claims += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        cur.execute("DELETE FROM items WHERE item_id = ?", (iid,))
    return deleted_matches, deleted_claims


@app.delete("/api/v1/admin/items/{item_id}")
def admin_delete_item(item_id: int, authorization: Optional[str] = Header(None)):
    """管理员删除单条信息（其匹配与认领记录一并删除）"""
    _require_admin(authorization)
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT title FROM items WHERE item_id = ?", (item_id,))
        row = cur.fetchone()
        if not row:
            return api_response(404, "该信息不存在或已被删除")
        m, c = _delete_items_by_ids(conn, [item_id])
        conn.commit()
        return api_response(200, "已删除", {"item_id": item_id, "title": row["title"],
                                            "matches_deleted": m, "claims_deleted": c})
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        return api_response(500, f"删除失败: {str(e)}")
    finally:
        conn.close()


class BulkDeleteReq(BaseModel):
    item_ids: List[int]


@app.post("/api/v1/admin/items/bulk-delete")
def admin_bulk_delete(req: BulkDeleteReq, authorization: Optional[str] = Header(None)):
    """管理员批量删除信息"""
    _require_admin(authorization)
    ids = [int(i) for i in (req.item_ids or []) if int(i) > 0]
    if not ids:
        return api_response(400, "请先选择要删除的信息")
    if len(ids) > 200:
        return api_response(400, "单次最多删除 200 条")
    conn = get_db()
    try:
        cur = conn.cursor()
        ph = ",".join("?" * len(ids))
        cur.execute(f"SELECT item_id FROM items WHERE item_id IN ({ph})", ids)
        exist = [r["item_id"] for r in cur.fetchall()]
        if not exist:
            return api_response(404, "所选信息均不存在")
        m, c = _delete_items_by_ids(conn, exist)
        conn.commit()
        return api_response(200, f"已删除 {len(exist)} 条", {
            "deleted": len(exist), "item_ids": exist,
            "matches_deleted": m, "claims_deleted": c,
        })
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        return api_response(500, f"批量删除失败: {str(e)}")
    finally:
        conn.close()


@app.get("/api/v1/admin/overview")
def admin_overview(authorization: Optional[str] = Header(None)):
    """管理端概览：各类数据总量，用于控制台卡片"""
    _require_admin(authorization)
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) c FROM items")
        items = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) c FROM items WHERE type='lost'")
        lost = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) c FROM items WHERE type='found'")
        found = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) c FROM items WHERE sensitive_level IN ('sensitive', '1', 1)")
        sensitive = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) c FROM matches")
        matches = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) c FROM matches WHERE status='推荐'")
        pending = cur.fetchone()["c"]
        return api_response(200, "success", {
            "items": items, "lost": lost, "found": found,
            "sensitive": sensitive, "matches": matches, "pending": pending,
        })
    finally:
        conn.close()


@app.patch("/api/v1/matches/{match_id}/confirm")
def confirm_match(match_id: int, req: MatchConfirm, authorization: Optional[str] = Header(None)):
    """人工确认 / 拒绝匹配结果（仅管理员可操作）。
    确认后：两条信息都流转为「已确认」，实现双向状态闭环（FR08）。"""
    _require_admin(authorization)
    if req.status not in ["已确认", "已拒绝"]:
        return api_response(400, "参数错误：status 必须为'已确认'或'已拒绝'")
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT source_item_id, candidate_item_id, status FROM matches WHERE match_id = ?",
            (match_id,))
        row = cursor.fetchone()
        if not row:
            return api_response(404, "匹配记录不存在")

        # 幂等：同一结论重复提交，直接返回原结果，不重复改状态
        if row["status"] == req.status:
            return api_response(200, f"该匹配已是「{req.status}」状态，无需重复操作", {
                "match_id": match_id, "status": req.status,
                "items": [row["source_item_id"], row["candidate_item_id"]],
                "idempotent": True,
            })
        # 已确认的操作不可撤销，避免把人工结论改回去
        if row["status"] == "已确认" and req.status != "已确认":
            return api_response(400, "该匹配已确认，不能撤销；如需退回请联系管理员")

        # 防重复占用：确认前校验双方是否已被别的匹配占用
        if req.status == "已确认":
            for iid in (row["source_item_id"], row["candidate_item_id"]):
                cursor.execute("SELECT status FROM items WHERE item_id = ?", (iid,))
                it = cursor.fetchone()
                if it and it["status"] == "已确认":
                    return api_response(409, f"物品 {iid} 已被其他匹配确认，不能重复占用该候选")

        cursor.execute("UPDATE matches SET status = ? WHERE match_id = ?", (req.status, match_id))

        # 确认：两条信息都进入「已确认」，同一条信息的其它待定匹配自动作废
        if req.status == "已确认":
            for iid in (row["source_item_id"], row["candidate_item_id"]):
                cursor.execute("UPDATE items SET status = '已确认' WHERE item_id = ?", (iid,))
            cursor.execute("""UPDATE matches SET status = '已拒绝'
                              WHERE status = '推荐'
                                AND match_id != ?
                                AND (source_item_id IN (?, ?) OR candidate_item_id IN (?, ?))""",
                           (match_id, row["source_item_id"], row["candidate_item_id"],
                            row["source_item_id"], row["candidate_item_id"]))
        # 拒绝：条目回到「待匹配」，方便继续尝试下一个候选
        else:
            for iid in (row["source_item_id"], row["candidate_item_id"]):
                cursor.execute("UPDATE items SET status = '待匹配' WHERE item_id = ? AND status = '已匹配'", (iid,))

        conn.commit()
        return api_response(200, "人工确认完成", {
            "match_id": match_id,
            "status": req.status,
            "items": [row["source_item_id"], row["candidate_item_id"]],
        })
    except Exception as e:
        conn.rollback()
        return api_response(500, f"系统异常: {str(e)}")
    finally:
        conn.close()


class ClaimCreate(BaseModel):
    applicant: Optional[str] = "匿名用户"
    answers: Optional[str] = ""


class ClaimReview(BaseModel):
    action: str  # approve | reject
    note: Optional[str] = ""


@app.post("/api/v1/items/{item_id}/claims")
def create_claim(item_id: int, claim: ClaimCreate, authorization: Optional[str] = Header(None)):
    """提交认领申请（需填写私密特征核验答案）"""
    if not claim.answers or not str(claim.answers).strip():
        return api_response(400, "必须填写私密特征核验答案")
    me = _current_user(authorization) or {}
    if me.get("role") == "admin":
        return api_response(400, "管理员账号不参与认领申请")
    applicant_name = me.get("username") or "user"
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT item_id, status FROM items WHERE item_id = ?", (item_id,))
        row = cursor.fetchone()
        if not row:
            return api_response(404, "物品不存在")
        # 同一用户对同一物品只保留一条待核验申请，避免连点提交出多条
        cursor.execute("""SELECT claim_id FROM claims
                          WHERE item_id = ? AND applicant_name = ? AND status = '待核验'""",
                       (item_id, applicant_name))
        dup = cursor.fetchone()
        if dup:
            return api_response(200, "你已提交过申请，请等待管理员审核",
                                {"claim_id": dup["claim_id"], "status": "待核验", "duplicated": True})
        cursor.execute("""INSERT INTO claims (item_id, applicant_id, applicant_name, answers, status)
                          VALUES (?, 1, ?, ?, '待核验')""",
                       (item_id, applicant_name, claim.answers))
        conn.commit()
        return api_response(200, "认领申请已提交", {"claim_id": cursor.lastrowid, "status": "待核验"})
    except Exception as e:
        conn.rollback()
        return api_response(500, f"系统异常: {str(e)}")
    finally:
        conn.close()


def _claim_rows(conn, where: str = "", args: tuple = ()):
    """认领申请 + 物品摘要，用户端/管理端共用"""
    cur = conn.cursor()
    cur.execute(f"""SELECT c.claim_id, c.item_id, c.applicant_name, c.answers, c.status,
                           c.review_note, c.reviewed_at, c.created_at,
                           i.title, i.type, i.category, i.location, i.private_features
                    FROM claims c LEFT JOIN items i ON i.item_id = c.item_id
                    {where}
                    ORDER BY CASE c.status WHEN '待核验' THEN 0 ELSE 1 END,
                             datetime(c.created_at) DESC""", args)
    out = []
    for r in cur.fetchall():
        out.append({
            "claim_id": r["claim_id"],
            "item_id": r["item_id"],
            "applicant": r["applicant_name"] or "user",
            "answers": r["answers"],
            "status": r["status"],
            "passed": r["status"] in ("已通过", "已完成"),
            "review_note": r["review_note"] or "",
            "reviewed_at": r["reviewed_at"] or "",
            "created_at": r["created_at"],
            "item": {
                "item_id": r["item_id"],
                "title": r["title"] or "（该信息已删除）",
                "type": r["type"] or "",
                "category": r["category"] or "",
                "location": r["location"] or "",
                "private_features": r["private_features"] or "",
            },
        })
    return out


@app.get("/api/v1/claims/mine")
def my_claims(authorization: Optional[str] = Header(None)):
    """当前用户的认领申请记录（含管理员审核结果）"""
    me = _current_user(authorization)
    if not me:
        return api_response(401, "请先登录")
    conn = get_db()
    try:
        rows = _claim_rows(conn, "WHERE c.applicant_name = ?", (me.get("username"),))
        # 申请人自己不能看到物品的「私密特征」标准答案，否则核验形同虚设
        for r in rows:
            r.pop("private_features", None)
        stat = {"total": len(rows),
                "pending": len([r for r in rows if r["status"] == "待核验"]),
                "passed": len([r for r in rows if r["passed"]]),
                "rejected": len([r for r in rows if r["status"] == "已拒绝"])}
        return api_response(200, "success", {"total": len(rows), "list": rows, "stat": stat})
    finally:
        conn.close()


@app.get("/api/v1/admin/claims")
def admin_claims(status: Optional[str] = None,
                 keyword: Optional[str] = None,
                 authorization: Optional[str] = Header(None)):
    """管理端：所有用户的认领申请"""
    _require_admin(authorization)
    where, args = [], []
    if status and status != "all":
        where.append("c.status = ?")
        args.append(status)
    if keyword:
        where.append("(i.title LIKE ? OR c.applicant_name LIKE ? OR c.answers LIKE ?)")
        kw = f"%{keyword}%"
        args.extend([kw, kw, kw])
    sql = ("WHERE " + " AND ".join(where)) if where else ""
    conn = get_db()
    try:
        rows = _claim_rows(conn, sql, tuple(args))
        stat = {"total": len(rows),
                "pending": len([r for r in rows if r["status"] == "待核验"]),
                "passed": len([r for r in rows if r["passed"]]),
                "rejected": len([r for r in rows if r["status"] == "已拒绝"])}
        return api_response(200, "success", {"total": len(rows), "list": rows, "stat": stat})
    finally:
        conn.close()


@app.post("/api/v1/admin/claims/{claim_id}/review")
def review_claim(claim_id: int, body: ClaimReview,
                 authorization: Optional[str] = Header(None)):
    """管理端审核认领申请：通过 / 不通过"""
    _require_admin(authorization)
    action = (body.action or "").lower()
    if action not in ("approve", "reject"):
        return api_response(400, "action 只能是 approve 或 reject")
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT claim_id, item_id, status FROM claims WHERE claim_id = ?", (claim_id,))
        row = cur.fetchone()
        if not row:
            return api_response(404, "申请不存在")
        if row["status"] in ("已通过", "已拒绝", "已完成"):
            return api_response(409, f"该申请已审核过（当前状态：{row['status']}），不能重复审核")
        new_status = "已通过" if action == "approve" else "已拒绝"
        cur.execute("""UPDATE claims
                       SET status = ?, review_note = ?, reviewed_at = ?,
                           admin_confirm = ?
                       WHERE claim_id = ?""",
                    (new_status, (body.note or "").strip(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                     1 if action == "approve" else 0, claim_id))
        # 通过后把物品标记为已认领，双向闭环
        if action == "approve":
            cur.execute("UPDATE items SET status = '已确认' WHERE item_id = ?", (row["item_id"],))
            # 同一物品的其他待核验申请自动作废，避免一物多认
            cur.execute("""UPDATE claims SET status = '已拒绝', review_note = '该物品已由其他申请人认领'
                           WHERE item_id = ? AND claim_id != ? AND status = '待核验'""",
                        (row["item_id"], claim_id))
        conn.commit()
        return api_response(200, f"已{'通过' if action == 'approve' else '驳回'}该申请",
                            {"claim_id": claim_id, "status": new_status})
    except Exception as e:
        conn.rollback()
        return api_response(500, f"系统异常: {str(e)}")
    finally:
        conn.close()


# ============================================================
# 前端静态页面托管：打开 http://localhost:8000 就能用系统
# 前端是 hash 路由（/#/xxx），所以只需把 / 指向 index.html
# ============================================================
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

    @app.get("/favicon.ico")
    def serve_favicon():
        ico = os.path.join(FRONTEND_DIST, "favicon.ico")
        if os.path.exists(ico):
            return FileResponse(ico)
        return api_response(404, "no favicon")
else:
    @app.get("/")
    def no_frontend():
        return api_response(200, "后端运行中。前端静态文件未找到（frontend/dist 不存在），请先用 npm run build 构建前端，或用 npm run dev 单独启动前端。")


# 空库自动填充演示数据（云端容器重启后数据库为空，靠这一步保证有内容可看）
auto_seed_if_empty()


if __name__ == "__main__":
    import uvicorn

    def _lan_ip():
        """取本机在局域网里的 IP，方便别人访问；失败就回 127.0.0.1"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect(("223.5.5.5", 80))   # 不会真的发包，只是让系统选出口网卡
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    port = int(os.getenv("PORT", "8000"))
    ip = _lan_ip()

    # 启动横幅：把"能不能用 AI""别人怎么访问"直接打在屏幕上，省得反复问
    cfg0 = _read_ai_config()
    key_ok = bool(os.getenv("LLM_API_KEY", "").strip())
    print("")
    print("=" * 60)
    print("  校园智能失物招领匹配系统  v3.0")
    print("=" * 60)
    print(f"  本机访问    http://localhost:{port}")
    print(f"  局域网访问  http://{ip}:{port}   （同一 WiFi 下其他人用这个）")
    print("-" * 60)
    if key_ok:
        print(f"  AI 状态     已配置  {os.getenv('LLM_MODEL','')}")
    else:
        print("  AI 状态     未配置 Key")
        print("              目前走「字面相似匹配」，系统能正常用，但不是大模型判定")
        print("              要启用请在 ai/.env 填入 LLM_API_KEY，或设环境变量后重启")
    print("-" * 60)
    if not os.path.exists(DB_PATH):
        print("  数据       空库，可执行 python seed.py 写入演示数据")
    print("=" * 60)
    print("")

    uvicorn.run(app, host="0.0.0.0", port=port)
