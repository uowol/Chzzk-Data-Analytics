from kafka import KafkaProducer
import json 


def get_producer() -> KafkaProducer:
    """
    Create and return a Kafka producer.
    """
    producer = KafkaProducer(
        bootstrap_servers='broker:29092',
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    )
    return producer

def send_message(producer:KafkaProducer, topic: str, message: dict) -> None:
    """
    Send a message to the specified Kafka topic.
    """
    producer.send(topic, message)
    
def close_producer(producer: KafkaProducer) -> None:
    """
    Close the Kafka producer.
    """
    producer.close()