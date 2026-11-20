"""
阶段一：粗筛（结构化过滤 + 字面相似度）
------------------------------------------------
作用：从全库几百上千条记录里，用零成本的方式挑出一小批候选，
      再交给大模型做语义精排。这样既控制 API 成本，又避免大模型"看太多分心"。

实现：
1. 结构化硬过滤（FR05）：反向类型、时间窗口、排除已关闭
2. 字面相似（FR06）：TF-IDF + 余弦相似度，中文按字级 2-gram 切分
3. 同义词归一（第三周设计的同义词表）：校园卡/一卡通 → 视为同一词
"""
import re
import json
import math
from datetime import datetime, timedelta
from collections import Counter

# 同义词表（与后端 synonyms 表口径一致，覆盖校园常见失物）
SYNONYM_GROUPS = [
    ["校园卡", "一卡通", "学生卡", "饭卡"],
    ["耳机", "蓝牙耳机", "airpods", "airpod", "耳麦"],
    ["充电宝", "移动电源", "充电宝电池"],
    # 注意：充电器（插头）不是充电宝。两者经常在同一个包里丢，
    # 但它们是两件东西，不能归成同义词，否则会把充电器误配到充电宝上。
    ["充电器", "充电头", "电源适配器", "数据线插头"],
    ["保温杯", "水杯", "杯子", "茶杯", "水瓶"],
    ["雨伞", "雨具", "遮阳伞", "伞"],
    ["钥匙", "钥匙串", "门钥匙"],
    ["书包", "背包", "双肩包", "挎包"],
    ["手机", "电话", "智能机"],
    ["学生证", "证件", "校园卡套"],
    ["眼镜", "框架眼镜", "近视镜"],
    ["身份证", "身份证件"],
    ["钱包", "皮夹", "钱夹"],
]

# 词 -> 归一后的代表词
_SYN_MAP = {}
for group in SYNONYM_GROUPS:
    rep = group[0]
    for w in group:
        _SYN_MAP[w] = rep


def normalize_text(text: str) -> str:
    """同义词归一 + 小写 + 去标点"""
    if not text:
        return ""
    t = str(text).lower()
    for word in sorted(_SYN_MAP.keys(), key=len, reverse=True):
        if word in t:
            t = t.replace(word, _SYN_MAP[word])
    t = re.sub(r"[\s，。、,.!！?？;；:：\"'“”‘’()（）\[\]【】~·\-—_/\\]+", " ", t)
    return t.strip()


def _grams(text: str, n: int = 2):
    """中文字级 n-gram（无需分词库，对短文本鲁棒）"""
    t = text.replace(" ", "")
    if len(t) < n:
        return [t] if t else []
    return [t[i:i + n] for i in range(len(t) - n + 1)]


def _tfidf_vectors(docs):
    """极简 TF-IDF：返回每个文档的稀疏向量"""
    grams_list = [_grams(d) for d in docs]
    df = Counter()
    for g in grams_list:
        for w in set(g):
            df[w] += 1
    n = len(docs)
    vectors = []
    for g in grams_list:
        tf = Counter(g)
        vec = {}
        for w, c in tf.items():
            idf = math.log((n + 1) / (df[w] + 1)) + 1
            vec[w] = (c / len(g)) * idf
        vectors.append(vec)
    return vectors


def _cosine(v1, v2):
    if not v1 or not v2:
        return 0.0
    common = set(v1) & set(v2)
    num = sum(v1[w] * v2[w] for w in common)
    d1 = math.sqrt(sum(x * x for x in v1.values()))
    d2 = math.sqrt(sum(x * x for x in v2.values()))
    if d1 == 0 or d2 == 0:
        return 0.0
    return num / (d1 * d2)


def item_text(item: dict) -> str:
    """把一条记录拼成用于比对的文本"""
    parts = [
        item.get("title") or "",
        item.get("category") or "",
        item.get("description") or "",
        item.get("color") or "",
        item.get("brand") or "",
        item.get("location") or "",
    ]
    return normalize_text(" ".join(p for p in parts if p))


def hard_filter(source: dict, pool: list, recall_days: int = 30) -> list:
    """
    结构化硬过滤：这一步不涉及 AI，纯规则，成本为零
    - 必须是对向信息（lost 找 found，found 找 lost）
    - 排除自己
    - 时间窗口内
    - 排除已确认/已关闭的记录
    """
    out = []
    opposite = "found" if source.get("type") == "lost" else "lost"
    try:
        base_time = datetime.strptime(str(source.get("time"))[:16], "%Y-%m-%d %H:%M")
    except Exception:
        base_time = datetime.now()
    window = timedelta(days=recall_days)

    for it in pool:
        if it.get("item_id") == source.get("item_id"):
            continue
        if it.get("type") != opposite:
            continue
        if it.get("status") in ("已确认", "已关闭", "无人认领"):
            continue
        try:
            t = datetime.strptime(str(it.get("time"))[:16], "%Y-%m-%d %H:%M")
        except Exception:
            t = base_time
        if abs(t - base_time) > window:
            continue
        out.append(it)
    return out


def coarse_rank(source: dict, candidates: list, limit: int = 10) -> list:
    """
    字面相似度排序，返回 [(item, lexical_score)]

    打分 = TF-IDF 余弦 + 结构化加分 - 结构化惩罚
    惩罚项很重要：只加不减会让"同类别不同物"（白杯子 vs 黑杯子）拿到虚高分，
    也会让"颜色品牌地点全对但根本不是一类东西"（充电宝 vs 耳机）漏过去。
    """
    if not candidates:
        return []
    src_text = item_text(source)
    docs = [src_text] + [item_text(c) for c in candidates]
    vecs = _tfidf_vectors(docs)
    src_vec = vecs[0]
    scored = []
    for i, cand in enumerate(candidates):
        score = _cosine(src_vec, vecs[i + 1])

        src_cat = (source.get("category") or "").strip()
        cand_cat = (cand.get("category") or "").strip()
        # 类别冲突：双方都填了类别且不一致 —— 视为硬矛盾，直接判死
        if src_cat and cand_cat and src_cat != cand_cat:
            scored.append((cand, 0.0))
            continue

        bonus, penalty = 0.0, 0.0
        # --- 加分 ---
        if src_cat and cand_cat and src_cat == cand_cat:
            bonus += 0.12
        src_color = (source.get("color") or "").strip()
        cand_color = (cand.get("color") or "").strip()
        src_brand = (source.get("brand") or "").strip()
        cand_brand = (cand.get("brand") or "").strip()
        if src_color and cand_color and src_color == cand_color:
            bonus += 0.06
        if src_brand and cand_brand and src_brand == cand_brand:
            bonus += 0.06
        src_loc = (source.get("location") or "").strip()
        cand_loc = (cand.get("location") or "").strip()
        if src_loc and cand_loc and (cand_loc in src_loc or src_loc in cand_loc):
            bonus += 0.05

        # --- 惩罚 ---
        # 颜色明确冲突（都填了且不同）：外观对不上，大幅扣分
        if src_color and cand_color and src_color != cand_color:
            penalty += 0.30
        # 品牌明确冲突：同类别里品牌不同，可信度下降
        if src_brand and cand_brand and src_brand != cand_brand:
            penalty += 0.15
        # 地点不同（都填了且互不包含）：可能只是巧合
        if src_loc and cand_loc and not (cand_loc in src_loc or src_loc in cand_loc):
            penalty += 0.08

        final = min(max(score + bonus - penalty, 0.0), 1.0)
        scored.append((cand, round(final, 4)))

    scored.sort(key=lambda x: -x[1])
    return scored[:limit]


if __name__ == "__main__":
    # 自测
    src = {"item_id": 1, "type": "lost", "title": "黑色保温杯", "category": "水杯",
           "description": "黑色膳魔师保温杯，杯底有贴纸", "color": "黑色",
           "brand": "膳魔师", "location": "图书馆三楼", "time": "2026-10-26 14:00:00"}
    pool = [
        {"item_id": 2, "type": "found", "title": "拾到一个黑色保温杯", "category": "水杯",
         "description": "黑色保温杯，杯身有磨损，底部贴了卡通贴纸", "color": "黑色",
         "brand": "膳魔师", "location": "图书馆三楼自习区", "time": "2026-10-26 16:00:00"},
        {"item_id": 3, "type": "found", "title": "捡到一把雨伞", "category": "雨伞",
         "description": "蓝色长柄雨伞", "color": "蓝色", "brand": "",
         "location": "一食堂门口", "time": "2026-10-25 12:00:00"},
        {"item_id": 4, "type": "lost", "title": "丢了个杯子", "category": "水杯",
         "description": "黑色杯子", "color": "黑色", "brand": "",
         "location": "教学楼", "time": "2026-10-26 10:00:00"},
    ]
    filtered = hard_filter(src, pool)
    print("硬过滤后候选数:", len(filtered), [f["item_id"] for f in filtered])
    for it, sc in coarse_rank(src, filtered):
        print(f"  候选 {it['item_id']} 《{it['title']}》 字面相似度 {sc}")
