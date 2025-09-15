import sqlite3

# 데이터베이스 연결
conn = sqlite3.connect('database.sqlite')
print("Database connected successfully")


# users 테이블 생성 (사용자 정보 및 API 토큰 저장)
conn.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT UNIQUE NOT NULL,
    api_token TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
''')
print("users table is ready")

# phq9 테이블 생성 (이미 있다면 실행되지 않음)
conn.execute('''
CREATE TABLE IF NOT EXISTS phq9 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_score INTEGER NOT NULL
);
''')
print("phq9 table is ready")

# --- [새로 추가된 부분] ---
# events_raw 테이블 생성 (사용자 활동 원본 데이터)
conn.execute('''
CREATE TABLE IF NOT EXISTS events_raw (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    url TEXT NOT NULL,
    duration_seconds INTEGER,
    event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
''')
print("events_raw table is ready")
# -------------------------
conn.execute('''
CREATE TABLE IF NOT EXISTS features_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    analysis_date DATE NOT NULL,
    total_usage_daily REAL,
    late_night_ratio REAL,
    sns_ent_ratio REAL,
    UNIQUE(user_id, analysis_date)
);
''')
print("features_daily table is ready")

# 연결 종료
conn.close()