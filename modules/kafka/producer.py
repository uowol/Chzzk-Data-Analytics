import json

from kafka import KafkaProducer


def get_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers='broker:29092',
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    )
