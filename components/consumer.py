from pydantic import BaseModel

from modules.kafka.consumer import get_consumer


class ComponentType(BaseModel):
    topic: str


class Component:
    def __init__(self, **config):
        self.config = ComponentType(**config)

    def __call__(self, **kwargs):
        consumer = get_consumer(topic=self.config.topic)
        for msg in consumer:
            content = msg.value
            print(f"Received message: {content}")
            if content.get("msg_type") == "STREAMING_END":
                print("Streaming ended.")
                break
        consumer.close()

        return {
            **self.config.model_dump(),
            "result": "success",
        }
