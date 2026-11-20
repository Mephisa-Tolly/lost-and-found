# demo_data.py
"""
演示数据（15 条：6 组配对 + 3 条干扰项）。

放在这里是为了两处共用：
  1. backend/seed.py    —— 本地手动执行，清空后重写
  2. backend/main.py    —— 云端首次启动自动写入，避免测试组打开看到空页面

字段与发布接口 POST /api/v1/items 保持一致。
"""

ITEMS = [
    # --- 第 1 组：黑色保温杯（信息齐全，典型正例）---
    dict(type="lost", title="黑色保温杯丢了", category="水杯",
         location="图书馆三楼自习区", time="2026-10-26 14:00:00",
         color="黑色", brand="膳魔师",
         description="黑色膳魔师保温杯，杯底贴了一张卡通猫贴纸，杯身有点磕碰",
         note="正例A-寻物"),
    dict(type="found", title="拾到一个黑色保温杯", category="水杯",
         location="图书馆三楼", time="2026-10-26 16:20:00",
         color="黑色", brand="膳魔师",
         description="黑色保温杯，杯底有卡通贴纸，杯身有磨损",
         note="正例A-招领，应与上条匹配"),

    # --- 第 2 组：校园卡（敏感物品，信息做了遮挡）---
    dict(type="lost", title="校园卡不见了", category="校园卡/学生证",
         location="一食堂", time="2026-10-27 12:10:00",
         color="白色", brand="",
         description="白色校园卡，卡套是卡通兔子图案，姓名首字母L*Y",
         note="正例B-敏感物品"),
    dict(type="found", title="捡到一张校园卡", category="校园卡/学生证",
         location="一食堂二楼", time="2026-10-27 12:40:00",
         color="白色", brand="",
         description="白色校园卡，外面套着卡通兔子卡套，已交至失物招领处",
         note="正例B-招领，应与上条匹配"),

    # --- 第 3 组：耳机（描述细节不同，靠语义理解）---
    dict(type="lost", title="AirPods 耳机丢了", category="耳机",
         location="体育馆", time="2026-10-28 18:00:00",
         color="白色", brand="苹果",
         description="白色 AirPods Pro，右耳耳机有轻微划痕，充电盒上贴了名字缩写",
         note="正例C-寻物"),
    dict(type="found", title="体育馆看台捡到白色耳机", category="耳机",
         location="体育馆看台", time="2026-10-28 19:30:00",
         color="白色", brand="苹果",
         description="白色无线耳机一副，带充电盒，盒上有字迹",
         note="正例C-招领，应与上条匹配"),

    # --- 第 4 组：雨伞（同款多把，考验区分能力）---
    dict(type="lost", title="丢了一把黑色长柄伞", category="雨伞",
         location="教学楼A201", time="2026-10-28 09:00:00",
         color="黑色", brand="",
         description="黑色长柄雨伞，伞柄是木质弯钩的，伞面内侧有格子花纹",
         note="边界D-寻物，同款多把"),
    dict(type="found", title="教室捡到两把伞", category="雨伞",
         location="教学楼A201", time="2026-10-28 11:00:00",
         color="黑色", brand="",
         description="教室后排留下两把伞，一把黑色长柄伞，一把蓝色折叠伞",
         note="边界D-招领，只能匹配其中一把"),

    # --- 第 5 组：充电宝（时间跨度大，考验时间窗）---
    dict(type="lost", title="罗马仕充电宝没了", category="充电宝",
         location="二食堂", time="2026-10-24 13:00:00",
         color="白色", brand="罗马仕",
         description="白色罗马仕充电宝，20000毫安，顶部有一个小裂口",
         note="正例E-寻物"),
    dict(type="found", title="食堂桌上捡到充电宝", category="充电宝",
         location="二食堂", time="2026-10-24 14:30:00",
         color="白色", brand="罗马仕",
         description="白色充电宝，容量较大，外壳顶部有裂口",
         note="正例E-招领，应与上条匹配"),

    # --- 第 6 组：钥匙（敏感物品，两侧都有）---
    dict(type="lost", title="宿舍钥匙丢了", category="钥匙",
         location="操场", time="2026-10-29 06:50:00",
         color="", brand="",
         description="一串钥匙大概四把，有宿舍门钥匙和自行车钥匙，挂着一个棕色小熊挂件",
         note="正例F-寻物（敏感物品）"),
    dict(type="found", title="操场捡到一串钥匙", category="钥匙",
         location="操场东侧看台", time="2026-10-29 07:30:00",
         color="", brand="",
         description="一串钥匙，约四把，挂着一个小熊挂件，已交辅导员",
         note="正例F-招领，应与上条匹配（敏感物品）"),

    # --- 干扰项：没有对应记录 ---
    dict(type="lost", title="一本高数教材丢了", category="书本/文具",
         location="教学楼B103", time="2026-10-27 16:00:00",
         color="", brand="",
         description="《高等数学》上册，扉页写了学号后四位 3721",
         note="干扰G-寻物，无对应招领"),
    dict(type="found", title="快递站捡到一张银行卡", category="银行卡",
         location="快递站", time="2026-10-29 15:00:00",
         color="", brand="",
         description="某银行储蓄卡，卡号末四位 6688，已上交",
         note="干扰H-招领，无对应寻物"),
    dict(type="found", title="捡到一副黑框眼镜", category="其他",
         location="图书馆一楼", time="2026-10-29 16:30:00",
         color="黑色", brand="",
         description="黑色镜框近视眼镜，装在一个灰色眼镜盒里",
         note="干扰I-招领，无对应寻物"),
]
