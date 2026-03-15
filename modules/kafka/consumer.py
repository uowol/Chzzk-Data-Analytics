import json

from kafka import KafkaConsumer

from modules.config import KAFKA_BOOTSTRAP_SERVERS


def get_consumer(topic: str, group_id: str = "chzzk") -> KafkaConsumer:
    return KafkaConsumer(
        topic,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id=group_id,
    )
