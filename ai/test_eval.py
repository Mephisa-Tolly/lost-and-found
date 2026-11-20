"""
AI 匹配模块评测脚本
================================================
对应 EXP04 任务书「验证」要求：代表性输入 / 边界输入 / 异常输入 三类必须都覆盖。

运行（在 ai 目录下，需先在 backend 目录启动后端）：
    python test_eval.py                # 跑全部用例（不写库）
    python test_eval.py --verbose      # 打印每条候选详情

说明：
- 本脚本**不依赖真实 API Key**。没配 Key 时走字面相似度降级路径，
  也能完整验证「硬过滤 → 粗排 → 阈值 → 输出结构」这一整条链路是否正确。
- 配了 Key 时会走大模型，脚本会额外报告精排是否生效。
- 每条用例写明"期望第 1 名是谁"和"期望排第几"，直接给出命中/未命中。
"""
import os
import sys
import json
import argparse
from datetime import datetime, timedelta

from coarse_filter import hard_filter, coarse_rank, normalize_text
from llm_ranker import llm_rank, lexical_results, LLMConfig

MIN_SCORE = float(os.getenv("MIN_SCORE", "0.35"))
TOP_K = int(os.getenv("TOP_K", "3"))
COARSE_LIMIT = int(os.getenv("COARSE_LIMIT", "10"))
RECALL_DAYS = int(os.getenv("RECALL_DAYS", "30"))

NOW = datetime(2026, 10, 26, 12, 0)


def t(hours_offset: float) -> str:
    """相对 NOW 的时间字符串"""
    return (NOW + timedelta(hours=hours_offset)).strftime("%Y-%m-%d %H:%M:00")


def mk(iid, typ, title, category, desc, color="", brand="", loc="", hours=0, status="待匹配"):
    return {
        "item_id": iid, "type": typ, "title": title, "category": category,
        "description": desc, "color": color, "brand": brand, "location": loc,
        "time": t(hours), "status": status,
    }


# ============================================================
# 一、代表性输入（正常业务场景，应当匹配成功）
# ============================================================
REPRESENTATIVE = [
    {
        "name": "R1 保温杯-细节吻合",
        "source": mk(101, "lost", "黑色保温杯丢了", "水杯",
                     "膳魔师保温杯，杯底贴了一张卡通贴纸", "黑色", "膳魔师", "图书馆三楼", 0),
        "pool": [
            mk(201, "found", "拾到一个黑色保温杯", "水杯",
               "黑色保温杯，杯身有磨损，底部贴了卡通贴纸", "黑色", "膳魔师", "图书馆三楼自习区", 2),
            mk(202, "found", "捡到蓝色雨伞", "雨伞", "蓝色长柄雨伞", "蓝色", "", "一食堂门口", -20),
            mk(203, "found", "捡到一副眼镜", "眼镜", "黑框眼镜", "黑色", "", "教学楼A", -5),
        ],
        "expect_rank": 1, "expect_id": 201,
        "why": "类别+颜色+品牌+独特细节（贴纸）全对上，应排第 1",
    },
    {
        "name": "R2 校园卡-同义词",
        "source": mk(102, "lost", "一卡通不见了", "校园卡",
                     "学生校园卡，卡套是蓝色的", "蓝色", "", "二食堂", -3),
        "pool": [
            mk(204, "found", "拾到一张校园卡", "校园卡",
               "在二食堂捡到一张校园卡，蓝色卡套", "蓝色", "", "二食堂", -2),
            mk(205, "found", "捡到身份证", "身份证", "身份证一张", "", "", "图书馆", -1),
        ],
        "expect_rank": 1, "expect_id": 204,
        "why": "「一卡通」与「校园卡」是同义词，需归一后才能匹配上",
    },
    {
        "name": "R3 耳机-品牌型号",
        "source": mk(103, "lost", "AirPods 丢了", "耳机",
                     "白色 AirPods 三代，左耳有轻微划痕", "白色", "Apple", "体育馆", -6),
        "pool": [
            mk(206, "found", "体育馆捡到白色蓝牙耳机", "耳机",
               "白色无线耳机，充电盒没有保护套", "白色", "Apple", "体育馆器材室", -4),
            mk(207, "found", "捡到充电宝", "充电宝", "黑色充电宝", "黑色", "", "体育馆", -5),
        ],
        "expect_rank": 1, "expect_id": 206,
        "why": "同类别+同颜色+同地点，品牌也一致",
    },
    {
        "name": "R4 反向匹配（招领找失物）",
        "source": mk(104, "found", "捡到一把伞", "雨伞",
                     "黑色折叠伞，伞柄有挂绳", "黑色", "", "实验楼B座", 1),
        "pool": [
            mk(208, "lost", "实验楼丢了一把黑色折叠伞", "雨伞",
               "黑色折叠伞，伞柄上有个小挂绳", "黑色", "", "实验楼B座", -1),
            mk(209, "lost", "丢了个水杯", "水杯", "白色保温杯", "白色", "", "实验楼", 0),
        ],
        "expect_rank": 1, "expect_id": 208,
        "why": "招领信息应向失物列表反查，方向不能反",
    },
]

# ============================================================
# 二、边界输入（容易误判的情形，重点看"不该匹配的有没有被挡住"）
# ============================================================
BOUNDARY = [
    {
        "name": "B1 同类不同物-应低分/被阈值拦",
        "source": mk(105, "lost", "黑色保温杯", "水杯",
                     "黑色保温杯，没有其他特征", "黑色", "", "图书馆", 0),
        "pool": [
            mk(210, "found", "捡到一个白色保温杯", "水杯",
               "白色保温杯，带茶隔", "白色", "", "图书馆", 1),
            mk(211, "found", "捡到一个蓝色保温杯", "水杯",
               "蓝色保温杯，有点旧", "蓝色", "", "图书馆", 2),
        ],
        "expect_ids": [],  # 期望全部被过滤掉
        "why": "同类别但颜色全不一致，不应推荐（防止'是杯子就推'的误报）",
    },
    {
        "name": "B2 时间超窗-应被硬过滤",
        "source": mk(106, "lost", "丢失手机", "手机",
                     "黑色 iPhone，屏幕有裂痕", "黑色", "Apple", "图书馆", 0),
        "pool": [
            # 90 天前的招领，超出 RECALL_DAYS=30 窗口
            mk(212, "found", "捡到黑色手机", "手机",
               "黑色 iPhone，屏幕有裂痕", "黑色", "Apple", "图书馆", -24 * 90),
        ],
        "expect_ids": [],
        "why": "时间差 90 天 > 30 天窗口，应被硬过滤排除",
    },
    {
        "name": "B3 已关闭记录-应被硬过滤",
        "source": mk(107, "lost", "丢失钥匙", "钥匙",
                     "一串钥匙，挂了小熊挂件", "", "", "宿舍楼下", 0),
        "pool": [
            mk(213, "found", "捡到钥匙", "钥匙", "一串钥匙，有小熊挂件",
               "", "", "宿舍楼下", 1, status="已确认"),
            mk(214, "found", "捡到钥匙串", "钥匙", "钥匙一串", "",
               "", "宿舍楼下", 2, status="已关闭"),
        ],
        "expect_ids": [],
        "why": "已确认/已关闭的记录不应再参与匹配",
    },
    {
        "name": "B4 描述极简-应给中性分而非高分",
        "source": mk(108, "lost", "丢东西了", "", "", "", "", "", 0),
        "pool": [
            mk(215, "found", "捡到东西", "", "", "", "", "", 1),
        ],
        "expect_max_score": 0.75,
        "why": "双方描述都几乎没有信息，不应给出'高度疑似'，避免瞎猜",
    },
    {
        "name": "B5 同地点不同类别-不应串类",
        "source": mk(109, "lost", "丢了充电宝", "充电宝",
                     "白色小米充电宝", "白色", "小米", "图书馆", 0),
        "pool": [
            mk(216, "found", "图书馆捡到白色耳机", "耳机",
               "白色耳机", "白色", "小米", "图书馆", 1),
        ],
        "expect_ids": [],
        "why": "颜色品牌地点都对，但类别不同（充电宝 vs 耳机），不应匹配",
    },
]

# ============================================================
# 三、异常输入（脏数据/空值/类型错乱，服务不能崩）
# ============================================================
ABNORMAL = [
    {
        "name": "A1 空候选池",
        "source": mk(110, "lost", "丢了个东西", "水杯", "黑色", "黑色", "", "", 0),
        "pool": [],
        "expect_ids": [],
        "why": "空库时不应报错，应返回空结果",
    },
    {
        "name": "A2 字段缺失（None / 空串）",
        "source": {"item_id": 111, "type": "lost", "title": "丢了个杯子",
                   "category": None, "description": None, "color": "", "brand": None,
                   "location": None, "time": None, "status": "待匹配"},
        "pool": [
            {"item_id": 217, "type": "found", "title": "捡到杯子", "category": None,
             "description": None, "color": None, "brand": None, "location": None,
             "time": t(1), "status": "待匹配"},
        ],
        "expect_ids": None,  # 不校验内容，只要求不抛异常
        "why": "字段大量为 None 时不能抛 TypeError",
    },
    {
        "name": "A3 时间格式非法",
        "source": mk(112, "lost", "丢掉雨伞", "雨伞", "黑色雨伞", "黑色", "", "食堂", 0),
        "pool": [
            {"item_id": 218, "type": "found", "title": "捡到雨伞", "category": "雨伞",
             "description": "黑色雨伞", "color": "黑色", "brand": "", "location": "食堂",
             "time": "不是时间", "status": "待匹配"},
            {"item_id": 219, "type": "found", "title": "捡到雨伞伞", "category": "雨伞",
             "description": "黑色雨伞一把", "color": "黑色", "brand": "", "location": "食堂",
             "time": "", "status": "待匹配"},
        ],
        "expect_ids": None,
        "why": "时间解析失败时应回退到当前时间，不能崩",
    },
    {
        "name": "A4 超长文本",
        "source": mk(113, "lost", "丢失钱包", "钱包", "黑色钱包" + "很着急" * 500,
                     "黑色", "", "操场", 0),
        "pool": [
            mk(220, "found", "捡到钱包", "钱包", "黑色钱包" + "无" * 500, "黑色", "", "操场", 1),
        ],
        "expect_ids": None,
        "why": "超长描述（2000+ 字）不能拖垮程序或超时",
    },
    {
        "name": "A5 未知类型值",
        "source": mk(114, "unknown", "随便", "", "测试", "", "", "", 0),
        "pool": [mk(221, "found", "随便2", "", "测试2", "", "", "", 1)],
        "expect_ids": [],
        "why": "type 是未知值时不应匹配任何东西，也不应崩",
    },
]


# ============================================================
# 执行引擎
# ============================================================
def run_one(case):
    """跑单条用例，返回 (结果列表, 追踪信息)"""
    src = case["source"]
    pool = case["pool"]

    filtered = hard_filter(src, pool, recall_days=RECALL_DAYS)
    ranked = coarse_rank(src, filtered, limit=COARSE_LIMIT)
    candidates = [it for it, _ in ranked]

    degraded = False
    note = ""
    if candidates:
        out = llm_rank(src, candidates, top_k=TOP_K)
        if out["degraded"] or not out["results"]:
            results = lexical_results(src, ranked, top_k=TOP_K)
            degraded = True
            note = out.get("note", "")
        else:
            results = out["results"]
    else:
        results = []

    kept = [r for r in results if r["score"] >= MIN_SCORE]
    return kept, {
        "filtered": len(filtered),
        "coarse": len(ranked),
        "degraded": degraded,
        "note": note,
    }


def judge(case, results, trace):
    """判定用例是否通过，返回 (pass, 说明)"""
    ids = [r["candidate_id"] for r in results]

    if "expect_rank" in case:
        want = case["expect_id"]
        if want in ids and ids.index(want) + 1 <= case["expect_rank"]:
            return True, f"命中：{want} 排第 {ids.index(want) + 1}"
        if want in ids:
            return False, f"未达标：{want} 排第 {ids.index(want) + 1}，期望第 {case['expect_rank']}"
        return False, f"漏召回：{want} 未出现在结果里（实际 {ids}）"

    if "expect_max_score" in case:
        top = results[0]["score"] if results else 0
        if top <= case["expect_max_score"]:
            return True, f"最高分 {top} ≤ 阈值 {case['expect_max_score']}，未过度自信"
        return False, f"最高分 {top} 超过上限 {case['expect_max_score']}，过于自信"

    if case.get("expect_ids") == []:
        if not ids:
            return True, "已正确过滤（无推荐）" if trace["filtered"] == 0 or not ids else "无推荐"
        return False, f"误报：不该推荐却给出了 {ids}"

    return True, "已执行未崩溃"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    cfg = LLMConfig()
    print("=" * 78)
    print("AI 匹配模块评测")
    print("=" * 78)
    print(f"配置：TOP_K={TOP_K} COARSE_LIMIT={COARSE_LIMIT} RECALL_DAYS={RECALL_DAYS} MIN_SCORE={MIN_SCORE}")
    print(f"大模型：{'已配置 ' + cfg.model if cfg.ready else '未配置 → 本次走字面相似度降级路径'}")
    print()

    groups = [
        ("一、代表性输入（正常场景，应召回）", REPRESENTATIVE),
        ("二、边界输入（易误判，应挡住）", BOUNDARY),
        ("三、异常输入（脏数据，不能崩）", ABNORMAL),
    ]

    total = passed = 0
    failures = []

    for title, cases in groups:
        print(f"\n【{title}】")
        print("-" * 78)
        for case in cases:
            total += 1
            try:
                results, trace = run_one(case)
                ok, msg = judge(case, results, trace)
            except Exception as e:
                ok, msg = False, f"抛出异常：{type(e).__name__}: {e}"
                results, trace = [], {}

            if ok:
                passed += 1
            else:
                failures.append((case["name"], msg))

            flag = "✓" if ok else "✗"
            print(f"  {flag} {case['name']}")
            print(f"      意图：{case['why']}")
            print(f"      结果：{msg}")
            if trace:
                print(f"      链路：硬过滤后 {trace['filtered']} 条 → 粗排 {trace['coarse']} 条"
                      f" → 阈值后 {len(results)} 条"
                      + ("（降级：字面相似度）" if trace["degraded"] else "（大模型精排）"))
            if args.verbose and results:
                for i, r in enumerate(results, 1):
                    print(f"        {i}. [{r['candidate_id']}] {r['candidate'].get('title')} "
                          f"score={r['score']} level={r['level']} src={r['source']}")
                    print(f"           理由：{r['reasons']}")
            print()

    print("=" * 78)
    print(f"总览：{passed}/{total} 通过  （通过率 {passed / total * 100:.1f}%）")
    if failures:
        print("\n未通过用例：")
        for name, msg in failures:
            print(f"  - {name}：{msg}")
    print("=" * 78)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
