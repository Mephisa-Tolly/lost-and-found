"""为已存在的 lost_found.db 补齐 V3.0 新增字段（幂等，可重复执行）"""
import sqlite3, os

DB = "lost_found.db"

if not os.path.exists(DB):
    conn = sqlite3.connect(DB)
    conn.executescript(open("schema.sql", encoding="utf-8").read())
    conn.commit()
    print("[OK] 数据库已新建并初始化")
else:
    conn = sqlite3.connect(DB)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(matches)").fetchall()]
    if cols and "source" not in cols:
        conn.execute("ALTER TABLE matches ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'semantic'")
        conn.commit()
        print("[OK] 已为 matches 表补充 source 字段")
    else:
        print("[OK] 表结构已是最新，无需迁移")
    # 确保 items 表的敏感级别口径统一
    try:
        conn.execute("UPDATE items SET sensitive_level='normal' WHERE sensitive_level IN ('0', 0, '')")
        conn.commit()
    except Exception:
        pass
conn.close()
