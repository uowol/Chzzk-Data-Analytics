import sys

sys.path.append("/home/dev/data-analysis")

from pydantic import BaseModel

from classes.chzzk import CookiesType
from modules.chzzk.chat import ChzzkChat, get_logger


class ComponentType(BaseModel):
    streamer_id: str
    streamer_name: str
    cookies: CookiesType


class Component:
    def __init__(self, **config):
        self.config = ComponentType(**config)

    def __call__(self, **kwargs):
        chzzkchat = ChzzkChat(self.config.streamer_id, self.config.cookies.model_dump(), get_logger(self.config.streamer_name))
        chzzkchat.run()

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

    # 채팅창으로 메세지 보내기
    # mesaage = ' '
    # chzzkchat.send(message=mesaage)

    config = {"streamer_id": streamer_id, "cookies": cookies, "streamer_name": streamer_name}
    component = Component(**config)
    res = component()
    # print(res)
