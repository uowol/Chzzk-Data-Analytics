import sys

sys.path.append("/home/dev/data-analysis")

from pydantic import BaseModel

from classes.chzzk import CookiesType
from modules.chzzk.chat import ChzzkChat
from modules.kafka.producer import get_producer, close_producer


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
        close_producer(producer=producer)

        return {
            **self.config.model_dump(),
            "result": "success",
        }


if __name__ == "__main__":
    streamer_id = "6e06f5e1907f17eff543abd06cb62891"
    streamer_name = 'nokduro'
    cookies = {
        "NID_SES": "",
        "NID_AUT": "",
    }

    config = {"streamer_id": streamer_id, "cookies": cookies, "streamer_name": streamer_name}
    component = Component(**config)
    res = component()
    # print(res)
