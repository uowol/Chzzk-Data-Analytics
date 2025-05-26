import sys

sys.path.append("/home/dev/data-analysis")

from pydantic import BaseModel

from classes.chzzk import CookiesType
from modules.chzzk.chat import ChzzkChat, get_logger


class ComponentType(BaseModel):
    streamer_id: str
    cookies: CookiesType


class Component:
    def __init__(self, **config):
        self.config = ComponentType(**config)

    def __call__(self, **kwargs):
        chzzkchat = ChzzkChat(self.config.streamer_id, self.config.cookies.model_dump(), get_logger())
        chzzkchat.run()

        return {
            **self.config.model_dump(),
            "result": "success",
        }


if __name__ == "__main__":
    logger = get_logger()
    streamer_id = ""
    cookies = {
        "NID_SES": "",
        "NID_AUT": "",
    }

    # 채팅창으로 메세지 보내기
    # mesaage = ' '
    # chzzkchat.send(message=mesaage)

    config = {"streamer_id": streamer_id, "cookies": cookies}
    component = Component(**config)
    res = component()
    print(res)
