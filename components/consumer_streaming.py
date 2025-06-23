import sys

sys.path.append("/home/dev/data-analysis")

from pydantic import BaseModel

from modules.kafka.consumer import get_consumer


class ComponentType(BaseModel):
    pass


class Component:
    def __init__(self, **config):
        self.config = ComponentType(**config)

    def __call__(self, **kwargs):
        consumer = get_consumer(topic="streaming")
        for msg in consumer:
            content = msg.value
            print(f"Received message: {content}")
            if content == 'STREAMING_END':
                print("Streaming ended.")
                break
        consumer.close()

        return {
            **self.config.model_dump(),
            "result": "success",
        }
        

if __name__ == "__main__":
    component = Component()
    res = component()
    print(res)