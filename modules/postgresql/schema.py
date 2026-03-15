"""PostgreSQL 테이블 스키마 정의 및 초기화"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chat_messages (
    msg_id      TEXT PRIMARY KEY,
    ts          TIMESTAMP NOT NULL,
    streamer    TEXT NOT NULL,
    msg_type    TEXT NOT NULL,
    nickname    TEXT,
    message     TEXT,
    pay_amount  INTEGER,
    month       INTEGER,
    tier_name   TEXT,
    tier_no     INTEGER,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_streamer ON chat_messages (streamer);
CREATE INDEX IF NOT EXISTS idx_chat_messages_ts ON chat_messages (ts);
CREATE INDEX IF NOT EXISTS idx_chat_messages_msg_type ON chat_messages (msg_type);

CREATE TABLE IF NOT EXISTS streaming_events (
    msg_id      TEXT PRIMARY KEY,
    ts          TIMESTAMP NOT NULL,
    streamer    TEXT NOT NULL,
    msg_type    TEXT NOT NULL,
    category    TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_streaming_events_streamer ON streaming_events (streamer);
CREATE INDEX IF NOT EXISTS idx_streaming_events_ts ON streaming_events (ts);

CREATE TABLE IF NOT EXISTS streamers (
    streamer_id     TEXT PRIMARY KEY,
    streamer_name   TEXT NOT NULL,
    is_active       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW()
);
"""

def init_schema(connection):
    with connection.cursor() as cursor:
        cursor.execute(SCHEMA_SQL)
    connection.commit()
