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
        "NID_SES": "AAABj37B90J5E7LwTt5exVNeNqzXoLPJtC9z0ENTk8xy72DglOyOVzRmMGFMv8TwNYGPkOYZmF9QKyzUEz1JgB/etmMuWG17RSc7FuNgHJUGKRUfTOgdUkDSVSMi/jCi09rnVYh6p6Qy8UoSicZXbeu2EkfsDqnB36EoGD8hwXQyIFiOJ0MyrzwKYpfWxFhGNxVffhDjkyy7DJ1jZIVodzzOmzy0jP+BTF4EgL9ijnq8kIjL+Ntm7hMiYRDORXcOOU21TIOOAeeXr6kO2FEaUGAi2YKp6JYP5a4yYGju3RQKsOAlzwHvlGpKG+SOZhrHV/7zvfQnOsxJJpt/E+UK6O5C1g2l0MGWo6mYkDhtCDNcTMDFtH0DjzePRxZol7KQV3TwH1oNMlN0RqIKHr9lBVJPkl4cZKtaB7Go6KpU/XnpXVxxrotLThiX/BE8sahhHvrfUz48pZ4Q5+gQ8MQY3urC2cNF4cd0D8GpXriTVfscWPUy5HrwJ0gC44QbHhbAgqGbp7q2co2eL3lAh+lbEvLwfP4=",
        "NID_AUT": "MaQPZAaBpPwjGER/3MoOBBmkeUVh7P/NZ1saKtb708Zi47t4x4X8zv86cccxOnO3",
    }

    # 채팅창으로 메세지 보내기
    # mesaage = ' '
    # chzzkchat.send(message=mesaage)

    config = {"streamer_id": streamer_id, "cookies": cookies, "streamer_name": streamer_name}
    component = Component(**config)
    res = component()
    # print(res)
