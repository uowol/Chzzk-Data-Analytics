import datetime

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

    for msg in consumer:
        content = msg.value
        row = _to_row(content)

        with conn.cursor() as cur:
            cur.execute(insert_sql, row)
            conn.commit()

        print(f"  [{topic}] {row['msg_type']}: {row['msg_id']}")

        if content.get("msg_type") == "STREAMING_END":
            print(f"[Consumer] Streaming ended on topic: {topic}")
            break

    consumer.close()
    conn.close()
