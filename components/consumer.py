import datetime
import time

from modules.kafka.consumer import get_consumer
from modules.postgresql import get_connection
from modules.postgresql.schema import init_schema


INSERT_CHAT = """
    INSERT INTO chat_messages (msg_id, ts, streamer, msg_type, nickname, message, pay_amount, month, tier_name, tier_no)
    VALUES (%(msg_id)s, %(ts)s, %(streamer)s, %(msg_type)s, %(nickname)s, %(message)s, %(pay_amount)s, %(month)s, %(tier_name)s, %(tier_no)s)
    ON CONFLICT (msg_id) DO NOTHING
"""

INSERT_STREAMING = """
    INSERT INTO streaming_events (msg_id, ts, streamer, msg_type, category)
    VALUES (%(msg_id)s, %(ts)s, %(streamer)s, %(msg_type)s, %(category)s)
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
    init_schema(conn)

    consumer = get_consumer(topic=topic)
    insert_sql = INSERT_CHAT if topic == "chat" else INSERT_STREAMING

    print(f"[Consumer] Listening on topic: {topic}")

    batch = []
    last_flush = time.monotonic()

    for msg in consumer:
        content = msg.value
        batch.append(_to_row(content))

        now = time.monotonic()
        if len(batch) >= BATCH_SIZE or (now - last_flush) >= FLUSH_INTERVAL:
            with conn.cursor() as cur:
                for row in batch:
                    cur.execute(insert_sql, row)
                conn.commit()
            print(f"  [{topic}] flushed {len(batch)} rows")
            batch.clear()
            last_flush = now
