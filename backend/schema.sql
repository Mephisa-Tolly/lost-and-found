PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(128) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK(role IN ('owner', 'finder', 'admin', 'security')),
    anonymous_flag BOOLEAN NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    type VARCHAR(10) NOT NULL CHECK(type IN ('lost', 'found')),
    title VARCHAR(100) NOT NULL,
    category VARCHAR(30) NOT NULL,
    location VARCHAR(100) NOT NULL,
    time DATETIME NOT NULL,
    description TEXT NOT NULL,
    color VARCHAR(20),
    brand VARCHAR(50),
    images TEXT,
    contact_encrypted VARCHAR(255),
    anonymous BOOLEAN DEFAULT 0,
    sensitive_level VARCHAR(10) DEFAULT 'normal' CHECK(sensitive_level IN ('normal', 'sensitive')),
    private_features TEXT,
    status VARCHAR(20) NOT NULL DEFAULT '待匹配',
    created_by INTEGER NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS matches (
    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_item_id INTEGER NOT NULL,
    candidate_item_id INTEGER NOT NULL,
    score FLOAT NOT NULL,
    level VARCHAR(10) NOT NULL CHECK(level IN ('高', '中', '低')),
    matched_fields TEXT NOT NULL,
    source VARCHAR(20) NOT NULL DEFAULT 'semantic' CHECK(source IN ('semantic', 'lexical', 'fusion')),
    status VARCHAR(20) NOT NULL DEFAULT '推荐' CHECK(status IN ('推荐', '已确认', '已拒绝')),
    confirmed_by INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_item_id) REFERENCES items(item_id),
    FOREIGN KEY (candidate_item_id) REFERENCES items(item_id),
    FOREIGN KEY (confirmed_by) REFERENCES users(user_id)
);

-- 同一对「源→候选」只允许一条匹配记录。
-- 发布时会开多个后台线程并行匹配，没有这个约束就会插出重复候选（分数还不同）。
CREATE UNIQUE INDEX IF NOT EXISTS ux_matches_pair
    ON matches(source_item_id, candidate_item_id);

CREATE INDEX IF NOT EXISTS ix_matches_source ON matches(source_item_id);
CREATE INDEX IF NOT EXISTS ix_items_type_status ON items(type, status);

CREATE TABLE IF NOT EXISTS claims (
    claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    applicant_id INTEGER NOT NULL,
    applicant_name VARCHAR(50) DEFAULT 'user',
    answers TEXT NOT NULL,
    -- claim=失主对招领帖提交认领申请 / clue=知情人对寻物帖提交线索
    kind VARCHAR(10) NOT NULL DEFAULT 'claim' CHECK(kind IN ('claim', 'clue')),
    status VARCHAR(20) NOT NULL DEFAULT '待核验' CHECK(status IN ('待核验', '已通过', '已拒绝', '已完成')),
    review_note TEXT,
    reviewed_at DATETIME,
    finder_confirm BOOLEAN DEFAULT 0,
    admin_confirm BOOLEAN DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(item_id),
    FOREIGN KEY (applicant_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    read_flag BOOLEAN DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS locations (
    location_id INTEGER PRIMARY KEY AUTOINCREMENT,
    shelf VARCHAR(20) NOT NULL,
    cabinet VARCHAR(20) NOT NULL,
    grid VARCHAR(20) NOT NULL,
    item_id INTEGER NOT NULL UNIQUE,
    FOREIGN KEY (item_id) REFERENCES items(item_id)
);

CREATE TABLE IF NOT EXISTS synonyms (
    word VARCHAR(50) NOT NULL,
    synonym_group VARCHAR(50) NOT NULL,
    PRIMARY KEY (word, synonym_group)
);

INSERT OR IGNORE INTO synonyms (word, synonym_group) VALUES 
('校园卡', 'G1'), ('一卡通', 'G1'), ('学生证', 'G1'),
('耳机', 'G2'), ('蓝牙耳机', 'G2'), ('AirPods', 'G2'),
('充电宝', 'G3'), ('移动电源', 'G3');