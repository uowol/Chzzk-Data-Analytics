import time

from pydantic import BaseModel

from classes.chzzk import CookiesType
from modules.chzzk.api import fetch_streamingCheck


class ComponentType(BaseModel):
    streamer_id: str
    cookies: CookiesType


class Component:
    def __init__(self, **config):
        self.config = ComponentType(**config)

    def __call__(self, **kwargs):
        while True:
            is_streaming = self.check_streaming(self.config.streamer_id, self.config.cookies)
            if is_streaming:
                print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Streaming is live!")
                break
            else:
                print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Streaming is offline.")
            time.sleep(10)

        return {
            **self.config.model_dump(),
            "result": "success",
        }

    def check_streaming(self, streamer_id: str, cookies: CookiesType) -> bool:
        try:
            return fetch_streamingCheck(streamer_id, cookies.model_dump())
        except Exception as e:
            print(f"Error checking streaming status for {streamer_id}: {e}")
            return False
