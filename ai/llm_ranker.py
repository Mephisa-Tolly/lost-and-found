"""
阶段二：精排（大模型语义打分 + 生成解释）
------------------------------------------------
作用：粗筛送进来的 10 条候选，用大模型逐条判断"这两条信息是不是同一件东西"，
      并输出人类能读懂的理由。这是纯字面比对做不到的部分——
      字面比对只知道"黑色"+"保温杯"两个词重合，
      大模型能理解"杯底贴纸"这种细节级别的对应关系。

设计要点（对应任务书"输入-处理-输出-接口-异常处理"五要素）：
- 输入：源信息 + 候选列表（已结构化，字段固定）
- 处理：一次请求批量判定，temperature=0 保证可复现
- 输出：严格 JSON，字段 score(0-1) / level / reasons[]，用 Pydantic 兜底校验
- 异常：网络超时、Key 无效、返回非 JSON、返回漏项 —— 全部降级不崩服务
"""
import os
import json
import time
import re
import urllib.request
import urllib.error
from typing import List, Optional

# ---------- 等级映射 ----------
# 分数 -> 等级，阈值写死便于评测复现
LEVEL_HIGH = 0.75
LEVEL_MID = 0.45


def score_to_level(score: float) -> str:
    if score >= LEVEL_HIGH:
        return "高度疑似"
    if score >= LEVEL_MID:
        return "可能相关"
    return "低相关"


# ---------- Prompt ----------
SYSTEM_PROMPT = """你是校园失物招领平台的比对助手。你的任务是判断「失物信息」和「招领信息」是否在描述同一件物品。

判断原则：
1. 物品本体必须一致：类别、外观（颜色/品牌/型号）是主要依据。
2. 细节信息权重更高：「杯底有卡通贴纸」「左耳有裂痕」这类独特细节，一旦对上，可信度大幅提高。
3. 时空合理性：丢失时间和捡到时间应接近（捡到时间通常略晚于丢失时间）；地点应相同或相邻。时间和地点严重矛盾时要扣分。
4. 注意同义表达：「校园卡」和「一卡通」、「充电宝」和「移动电源」是同一个东西。
5. 不要因为描述风格不同（一个写"丢了"一个写"捡到"）就判为不相关，你比的是物品本身。
6. 如果候选信息实在无法判断（描述过于笼统），给中性分数 0.4-0.5，不要瞎猜高分。

打分标准：
- 0.85-1.00：几乎可以确定是同一件物品，关键细节高度吻合
- 0.65-0.84：很可能是同一件物品，主要特征吻合
- 0.40-0.64：有一定可能，但缺少决定性证据
- 0.00-0.39：基本不可能是同一件物品

你必须只输出 JSON，不要输出任何解释性文字、不要用 markdown 代码块包裹。"""


def _build_user_prompt(source: dict, candidates: List[dict]) -> str:
    def fmt(it):
        return (
            f"  - candidate_id: {it.get('item_id')}\n"
            f"    标题: {it.get('title') or '（未填）'}\n"
            f"    类别: {it.get('category') or '（未填）'}\n"
            f"    颜色: {it.get('color') or '（未填）'}\n"
            f"    品牌: {it.get('brand') or '（未填）'}\n"
            f"    地点: {it.get('location') or '（未填）'}\n"
            f"    时间: {it.get('time') or '（未填）'}\n"
            f"    详细描述: {it.get('description') or '（未填）'}"
        )

    cand_block = "\n".join(fmt(c) for c in candidates)
    src_type = "丢失" if source.get("type") == "lost" else "捡到"

    return f"""【待匹配的{src_type}信息】
  - item_id: {source.get('item_id')}
    标题: {source.get('title') or '（未填）'}
    类别: {source.get('category') or '（未填）'}
    颜色: {source.get('color') or '（未填）'}
    品牌: {source.get('brand') or '（未填）'}
    地点: {source.get('location') or '（未填）'}
    时间: {source.get('time') or '（未填）'}
    详细描述: {source.get('description') or '（未填）'}

【候选列表】（共 {len(candidates)} 条）
{cand_block}

请逐条判断上面的候选，输出如下格式的 JSON 数组（每个 candidate_id 都要有，不要遗漏）：
[
  {{
    "candidate_id": 123,
    "score": 0.82,
    "reasons": ["颜色品牌一致：都是黑色的保温杯", "独特细节吻合：都提到杯底有贴纸"]
  }}
]
reasons 每条不超过 30 字，说清楚"哪个字段对上了"或"哪里矛盾了"，2-3 条即可。"""


# ---------- LLM 调用（只用标准库，不额外装包）----------
class LLMConfig:
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY", "").strip()
        self.base_url = os.getenv("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "glm-5.3-flash")
        # glm-5.3-flash 自带 thinking，响应比纯文本模型慢，超时给宽一些
        self.timeout = int(os.getenv("LLM_TIMEOUT", "60"))

    @property
    def ready(self) -> bool:
        return bool(self.api_key)


def _load_dotenv(path=".env"):
    """独立运行时也能读到 .env（被 main.py 导入时已加载过，这里幂等）"""
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


_load_dotenv()


def build_endpoint(base_url: str) -> str:
    """
    把各家的 base_url 拼成完整的 chat/completions 地址。

    各家 base_url 的写法差别很大，不能无脑拼 /v1：
      DeepSeek   https://api.deepseek.com                     -> 要补 /v1
      硅基流动    https://api.siliconflow.cn/v1                 -> 已带 /v1
      阿里百炼    https://dashscope.aliyuncs.com/compatible-mode/v1 -> 已带
      智谱 GLM   https://open.bigmodel.cn/api/paas/v4          -> 已带 /v4
      Ollama     http://localhost:11434/v1                     -> 已带 /v1
    """
    base = (base_url or "").strip().rstrip("/")
    if not base:
        base = "https://api.deepseek.com"
    # 已经写全了就别动
    if base.endswith("/chat/completions"):
        return base
    # 结尾是 /v1 /v4 这类版本号，直接接路径
    if re.search(r"/v\d+$", base):
        return base + "/chat/completions"
    # 其余情况补 /v1
    return base + "/v1/chat/completions"


def _chat(cfg: LLMConfig, system: str, user: str) -> str:
    """调用 OpenAI 兼容协议的 /chat/completions，返回纯文本"""
    url = build_endpoint(cfg.base_url)
    payload = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "max_tokens": 2000,
        "stream": False,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=cfg.timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def _extract_json(text: str) -> Optional[list]:
    """容错解析：模型偶尔会带代码块或前导说明，这里强行抠出 JSON 数组"""
    if not text:
        return None
    text = text.strip()
    # 去掉 ```json ... ```
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    # 截取第一个 [ 到最后一个 ]
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else None
    except Exception:
        return None


def _validate(raw_list: list, candidates: List[dict]) -> dict:
    """
    校验 + 归一，返回 {candidate_id: {score, reasons}}
    模型可能：给字符串分数、越界分数、漏项、item_id 不存在 —— 全部兜住
    """
    valid_ids = {c.get("item_id") for c in candidates}
    result = {}
    for row in raw_list:
        if not isinstance(row, dict):
            continue
        cid = row.get("candidate_id")
        try:
            cid = int(cid)
        except Exception:
            continue
        if cid not in valid_ids:
            continue  # 模型幻觉出来的 id，丢弃

        try:
            score = float(row.get("score", 0))
        except Exception:
            score = 0.0
        score = max(0.0, min(1.0, score))

        reasons = row.get("reasons") or []
        if isinstance(reasons, str):
            reasons = [reasons]
        reasons = [str(r).strip() for r in reasons if str(r).strip()][:3]
        if not reasons:
            reasons = ["模型未给出具体理由"]

        result[cid] = {"score": round(score, 4), "reasons": reasons}
    return result


def llm_rank(source: dict, candidates: List[dict], top_k: int = 3,
             retries: int = 2) -> dict:
    """
    精排主入口。

    返回:
      {
        "results": [{candidate_id, candidate, score, level, reasons, source}],
        "degraded": bool,          # 是否走了降级
        "note": str                # 给前端/日志看的状态说明
      }
    """
    if not candidates:
        return {"results": [], "degraded": False, "ok": None, "note": "无候选"}

    cfg = LLMConfig()
    if not cfg.ready:
        return {
            "results": [],
            "degraded": True,
            "ok": None,
            "note": "未配置 LLM_API_KEY，跳过精排（仅使用字面相似度结果）",
        }

    user_prompt = _build_user_prompt(source, candidates)
    last_err = ""
    for attempt in range(retries + 1):
        try:
            content = _chat(cfg, SYSTEM_PROMPT, user_prompt)
            parsed = _extract_json(content)
            if parsed is None:
                last_err = "模型返回内容不是合法 JSON"
                continue
            judged = _validate(parsed, candidates)
            if not judged:
                last_err = "模型返回的 candidate_id 全部非法"
                continue

            results = []
            for c in candidates:
                cid = c.get("item_id")
                if cid not in judged:
                    # 漏判的候选按字面分兜底，避免整批丢
                    continue
                j = judged[cid]
                base = j["score"]
                reasons = list(j["reasons"])

                # 品类互斥（充电器≠充电宝、长柄≠折叠）：模型看不出来时要兜住
                if category_mismatch(source, c):
                    base = min(base, 0.35)
                    reasons = ["品类不符：两者不是同一类物品"] + reasons[:2]

                # 细节信号：吻合加分、冲突扣分，并把细节写进理由
                sig = detail_signals(source, c)
                base = max(0.0, min(1.0, base + sig["delta"]))
                merged = sig["reasons"] + [r for r in reasons if r not in sig["reasons"]]
                results.append({
                    "candidate_id": cid,
                    "candidate": c,
                    "score": round(base, 4),
                    "level": score_to_level(base),
                    "reasons": merged[:3],
                    "source": "semantic",
                })
            results.sort(key=lambda x: -x["score"])
            missing = len(candidates) - len(results)
            note = "大模型精排完成"
            if missing > 0:
                note += f"（{missing} 条候选模型未返回，已剔除）"
            return {"results": results[:top_k], "degraded": False, "ok": True, "note": note}

        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.reason}"
            if e.code in (401, 403):
                break  # Key 有问题，重试无意义
        except urllib.error.URLError as e:
            last_err = f"网络不可达: {e.reason}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))

    return {
        "results": [],
        "degraded": True,
        "ok": False,
        "note": f"大模型调用失败，已降级为字面相似度结果。原因：{last_err}",
    }


# ==================== V3.0：描述细节提取与冲突判定 ====================
# 问题来源：EXP05 评价发现「45 条候选 0 条引用描述细节」，理由只复述字段相等，
# 用户无法据此判断「是不是我的东西」。这里的做法是：
#   ① 只抽取「判别性」细节（贴纸、绳结、划痕、挂件、容量…），颜色/品牌不在此列（另有字段比对）
#   ② 一方提到、另一方明确否认（"没有绳结"）→ 判冲突，大幅扣分
#   ③ 双方都提到同一细节 → 判吻合，加分并写进理由
# 全部为规则实现，不依赖大模型，因此在降级（429/断网）时同样生效。

# 不含颜色的判别性细节（颜色在下面单独处理，避免「都写了黑色」被当成细节吻合）
_DETAIL_PATTERNS = [
    r"卡通[^，。、\s]{0,3}贴纸", r"贴纸", r"贴画", r"姓名贴",
    r"红色绳结", r"绳结", r"红绳", r"挂件", r"挂饰", r"钥匙扣", r"吊坠", r"小玩偶", r"玩偶",
    r"划痕", r"刮痕", r"磕碰", r"凹陷", r"裂痕", r"裂纹", r"破损", r"缺口", r"缺角",
    r"刻字", r"签名", r"标签", r"二维码", r"记号笔", r"涂鸦",
    r"格子花纹", r"格子", r"条纹", r"波点", r"图案", r"刺绣", r"补丁", r"破洞",
    r"木柄", r"弯钩", r"长柄", r"折叠伞", r"三折伞", r"自动伞", r"透明伞",
    r"\d{3,6}\s*毫安", r"\d+\s*W", r"Type-?C", r"快充", r"USB[^，。\s]{0,4}",
    r"小熊", r"小猫", r"小狗", r"兔子", r"星星", r"爱心",
]
_COLOR_WORDS = ("粉色", "黄色", "红色", "蓝色", "绿色", "紫色", "橙色", "白色", "黑色", "灰色", "银色", "金色")

# 否定词：出现在细节词前后 8 字内，视为"明确否认该细节"
_NEG_WORDS = ("没有", "没带", "无", "不带", "缺少", "少了", "没挂", "没贴", "不是")

# 句子切分：细节上下文不跨句，避免「黑色折叠伞，伞柄系着红色绳结」被拼成一条
_SEP = "，。、；;,.!?！？\n\s"


def _sentences(text: str):
    return [x for x in re.split(f"[{_SEP}]+", str(text or "")) if x.strip()]


def extract_details(text: str) -> list:
    """从描述中抽取判别性细节短语（按句切分，去重保序）"""
    if not text:
        return []
    found = []
    for sent in _sentences(text):
        for pat in _DETAIL_PATTERNS:
            for m in re.finditer(pat, sent):
                phrase = sent.strip()
                if 1 < len(phrase) <= 18 and phrase not in found:
                    found.append(phrase)
    return found[:6]


def _has_neg(text: str, core: str) -> bool:
    """
    该细节在同一条记录里是否被「明确否认」。
    判定范围放宽到整句：句中出现否定词（没有/无/不是…）且句中提到该核心细节 → 视为否认。
    例：「黑色折叠伞，伞柄没有绳结」→ 绳结被否认；「红色绳结」→ 未否认。
    """
    for sent in _sentences(text):
        if core not in sent:
            continue
        if any(neg in sent for neg in _NEG_WORDS):
            return True
    return False


def _detail_core(phrase: str) -> str:
    """取细节短语的判别核心词（去掉'我的是''一方写了'这类叙述成分）"""
    m = re.search(
        r"(贴纸|贴画|姓名贴|绳结|红绳|挂件|挂饰|钥匙扣|吊坠|玩偶|划痕|刮痕|磕碰|凹陷|裂痕|裂纹|破损|缺口|缺角|"
        r"刻字|签名|标签|二维码|记号笔|涂鸦|格子|条纹|波点|图案|刺绣|补丁|破洞|木柄|弯钩|长柄|折叠|透明|"
        r"\d+\s*毫安|\d+\s*W|Type-?C|快充)", phrase)
    return m.group(0) if m else phrase[:4]


def _detail_polarity(text: str, core: str):
    """
    该记录对某个细节的**表态**：
      True  → 明确否认（"伞柄没有绳结"）
      False → 明确肯定（"伞柄有个绳结"）
      None  → 没提到这个细节
    只看包含该核心词的那一句，避免跨句误判。
    """
    for sent in _sentences(text):
        if core not in sent:
            continue
        return any(neg in sent for neg in _NEG_WORDS)
    return None


def detail_signals(source: dict, cand: dict) -> dict:
    """
    比对双方描述里的细节，返回
      { hit, conflict, only_src, only_cand, delta, reasons }
    hit 为空且 conflict 为空时，只给出「细节待核对」提示，不加不减分。

    判定表（核心在于「一方肯定、另一方否认」才叫冲突，两边都否认反而是吻合）：
      源肯定 + 候选肯定 → 吻合
      源肯定 + 候选否认 → 冲突
      源否认 + 候选肯定 → 冲突
      源否认 + 候选否认 → 吻合（都说了"没有"，特征一致）
      只有一方提到      → 待核对，不加不减
    """
    src_text = f"{source.get('description') or ''} {source.get('title') or ''}"
    cand_text = f"{cand.get('description') or ''} {cand.get('title') or ''}"
    src_d = extract_details(src_text)
    cand_d = extract_details(cand_text)

    hit, conflict, only_src, only_cand = [], [], [], []
    used_cand = set()
    for d in src_d:
        core = _detail_core(d)
        src_neg = _detail_polarity(src_text, core)
        match = next((c for c in cand_d if core in c), None)
        cand_neg = _detail_polarity(cand_text, core)
        if cand_neg is None:
            # 对方没提这个细节，谈不上吻合也谈不上冲突
            only_src.append(d)
            continue
        if match:
            used_cand.add(match)
        # 表态相反 → 冲突；表态相同 → 吻合（含双方都否认）
        if src_neg != cand_neg:
            conflict.append(f"{core}（一方描述该特征，另一方明确否认）")
        else:
            hit.append(core)
    for c in cand_d:
        if c in used_cand:
            continue
        core = _detail_core(c)
        cand_neg = _detail_polarity(cand_text, core)
        src_neg = _detail_polarity(src_text, core)
        if src_neg is None:
            only_cand.append(c)
        elif src_neg != cand_neg:
            conflict.append(f"{core}（一方描述该特征，另一方明确否认）")
        else:
            hit.append(core)

    # 颜色单独比对（不进细节命中，但冲突要计）
    src_color = (source.get("color") or "").strip()
    cand_color = (cand.get("color") or "").strip()
    color_note = ""
    if src_color and cand_color and src_color != cand_color:
        color_note = f"颜色冲突：{src_color} ↔ {cand_color}"
    elif src_color and cand_color:
        color_note = f"颜色一致：{src_color}"

    hit = list(dict.fromkeys(hit))
    delta = 0.0
    reasons = []
    if hit:
        delta += min(0.05 * len(hit), 0.10)
        reasons.append("细节吻合：" + "、".join(hit[:2]))
    if conflict:
        # 细节相反是强证据：双方描述互相矛盾，说明不是同一件东西
        # 细节相反 = 几乎可以排除同一物，扣分要够狠（EXP05 案例：细节相反仍给 1.000）
        delta -= min(0.35 * len(conflict), 0.55)
        reasons.insert(0, "细节冲突：" + conflict[0].split("（")[0])
    if not hit and not conflict:
        # 界面是给管理员看的，称谓用「失物帖 / 招领帖」而不是「你 / 对方」
        src_label = "失物帖" if source.get("type") == "lost" else "招领帖"
        cand_label = "招领帖" if src_label == "失物帖" else "失物帖"
        if only_src and only_cand:
            reasons.append(f"细节待核对：{src_label}写了「{_detail_core(only_src[0])}」，{cand_label}写了「{_detail_core(only_cand[0])}」")
        elif only_src:
            reasons.append(f"细节待核对：{src_label}写了「{_detail_core(only_src[0])}」，{cand_label}未提及")
        elif only_cand:
            reasons.append(f"细节待核对：{cand_label}写了「{_detail_core(only_cand[0])}」，{src_label}未提及")
    if color_note:
        reasons.append(color_note)

    return {"hit": hit, "conflict": conflict, "only_src": only_src,
            "only_cand": only_cand, "delta": round(delta, 4), "reasons": reasons}


# 品类互斥：这些词对指向不同的东西，出现即视为品类不符（同义词表合并过度的补丁）
_CATEGORY_EXCLUSIVE = [
    (("充电宝", "移动电源"), ("充电器", "充电头", "电源适配器")),
    (("长柄", "直柄", "木柄"), ("折叠", "三折")),
]


def category_mismatch(source: dict, cand: dict) -> bool:
    """
    强品类互斥判定。注意「不是充电宝」这类否定表述要排除：
    如果某条记录里出现 "不是A" 或 "A以外的"，说明它本身就不是 A。
    """
    def profile(it):
        text = f"{it.get('title') or ''} {it.get('description') or ''}"
        out = {}
        for ga, gb in _CATEGORY_EXCLUSIVE:
            for tag, group in (("a", ga), ("b", gb)):
                present = False
                for w in group:
                    for m in re.finditer(w, text):
                        before = text[max(0, m.start() - 4): m.start()]
                        if not any(neg in before for neg in ("不是", "非", "不属于", "而非")):
                            present = True
                out[(ga[0], tag)] = present
        return out

    ps, pc = profile(source), profile(cand)
    for ga, gb in _CATEGORY_EXCLUSIVE:
        ka, kb = (ga[0], "a"), (ga[0], "b")
        if (ps.get(ka) and pc.get(kb) and not pc.get(ka)) or \
           (ps.get(kb) and pc.get(ka) and not ps.get(ka)):
            return True
    return False


# ---------- 降级路径 ----------
def lexical_results(source: dict, ranked: List[tuple], top_k: int = 3) -> List[dict]:
    """
    只有当大模型不可用时才用这条路径：把 TF-IDF 分数当最终分数。
    source 标为 lexical，让用户/老师一眼看出这条结果是"廉价算法"给的。
    """
    out = []
    for item, sc in ranked[:top_k]:
        base = sc
        # 品类互斥直接压到阈值以下，让误召（充电宝↔充电器）不再出现在候选里
        if category_mismatch(source, item):
            base = min(base, 0.30)

        # 细节信号：这是 EXP05「理由不落地细节」的直接修复
        sig = detail_signals(source, item)
        base = max(0.0, min(1.0, base + sig["delta"]))

        reasons = list(sig["reasons"])
        if item.get("category") and item.get("category") == source.get("category"):
            reasons.append(f"类别一致：{item['category']}")
        if item.get("color") and item.get("color") == source.get("color"):
            reasons.append(f"颜色一致：{item['color']}")
        if item.get("brand") and item.get("brand") == source.get("brand"):
            reasons.append(f"品牌一致：{item['brand']}")
        if not reasons:
            reasons.append(f"文本字面相似度 {sc}")

        out.append({
            "candidate_id": item.get("item_id"),
            "candidate": item,
            "score": round(base, 4),
            "level": score_to_level(base),
            "reasons": reasons[:3],
            "source": "lexical",
        })
    # 细节冲突把分数压下去后，可能跌破阈值——重新排序，把最可信的排前面
    out.sort(key=lambda x: -x["score"])
    return out


if __name__ == "__main__":
    # 无 Key 时应当走降级，不抛异常
    src = {"item_id": 1, "type": "lost", "title": "黑色保温杯", "category": "水杯",
           "description": "杯底有贴纸", "color": "黑色", "brand": "膳魔师",
           "location": "图书馆三楼", "time": "2026-10-26 14:00:00"}
    cands = [{"item_id": 2, "type": "found", "title": "拾到黑色保温杯", "category": "水杯",
              "description": "底部有卡通贴纸", "color": "黑色", "brand": "膳魔师",
              "location": "图书馆三楼", "time": "2026-10-26 16:00:00"}]
    print(json.dumps(llm_rank(src, cands), ensure_ascii=False, indent=2))
