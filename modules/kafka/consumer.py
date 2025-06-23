from kafka import KafkaConsumer
import json 


def get_consumer(topic: str) -> KafkaConsumer:
    """
    Create and return a Kafka consumer.
    """
    return KafkaConsumer(
        topic,
        bootstrap_servers='broker:29092',
        value_deserializer=lambda v: json.loads(v.decode('utf-8')),
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        group_id='chzzk',
    )