from pydantic import BaseModel

from classes.chzzk import CookiesType
from modules.chzzk.chat import ChzzkChat
from modules.kafka.producer import get_producer


class ComponentType(BaseModel):
    streamer_id: str
    streamer_name: str
    cookies: CookiesType


class Component:
    def __init__(self, **config):
        self.config = ComponentType(**config)

    def __call__(self, **kwargs):
        producer = get_producer()
        chzzkchat = ChzzkChat(
            self.config.streamer_id,
            self.config.streamer_name,
            self.config.cookies.model_dump(),
            producer=producer,
        )
        chzzkchat.run()
        producer.close()

        return {
            **self.config.model_dump(),
            "result": "success",
        }
