import datetime
import time

from psycopg2.extras import execute_values

from modules.kafka.consumer import get_consumer
from modules.postgresql import get_connection


CHAT_COLUMNS = ("msg_id", "ts", "streamer", "msg_type", "nickname", "message", "pay_amount", "month", "tier_name", "tier_no")
STREAMING_COLUMNS = ("msg_id", "ts", "streamer", "msg_type", "category")

INSERT_CHAT = """
    INSERT INTO chat_messages (msg_id, ts, streamer, msg_type, nickname, message, pay_amount, month, tier_name, tier_no)
    VALUES %s
    ON CONFLICT (msg_id) DO NOTHING
"""

INSERT_STREAMING = """
    INSERT INTO streaming_events (msg_id, ts, streamer, msg_type, category)
    VALUES %s
    ON CONFLICT (msg_id) DO NOTHING
"""

BATCH_SIZE = 50
FLUSH_INTERVAL = 2  # 초


def _to_row(msg: dict) -> dict:
    payload = msg.get("payload", {})
    return {
        "msg_id": msg["msg_id"],
        "ts": datetime.datetime.fromtimestamp(msg["ts"]),
        "streamer": msg["streamer_name"],
        "msg_type": msg["msg_type"],
        "nickname": payload.get("nickname"),
        "message": payload.get("message"),
        "pay_amount": payload.get("payAmount"),
        "month": payload.get("month"),
        "tier_name": payload.get("tierName"),
        "tier_no": payload.get("tierNo"),
        "category": payload.get("category"),
    }


def run(topic: str):
    conn = get_connection()

    consumer = get_consumer(topic=topic)
    insert_sql = INSERT_CHAT if topic == "chat" else INSERT_STREAMING
    columns = CHAT_COLUMNS if topic == "chat" else STREAMING_COLUMNS

    print(f"[Consumer] Listening on topic: {topic}")

    batch = []
    last_flush = time.monotonic()

    for msg in consumer:
        content = msg.value
        batch.append(_to_row(content))

        now = time.monotonic()
        if len(batch) >= BATCH_SIZE or (now - last_flush) >= FLUSH_INTERVAL:
            values = [tuple(row[col] for col in columns) for row in batch]
            with conn.cursor() as cur:
                execute_values(cur, insert_sql, values)
                conn.commit()
            print(f"  [{topic}] flushed {len(batch)} rows")
            batch.clear()
            last_flush = now
