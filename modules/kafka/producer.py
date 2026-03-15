import json

from kafka import KafkaProducer

from modules.config import KAFKA_BOOTSTRAP_SERVERS


def get_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
