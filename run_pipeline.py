import argparse
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel

from classes.chzzk import (
    RequestChzzkChatCrawlMessage,
    RequestChzzkStreamingCheckMessage
)
from components.chzzk_chat_crawl import Component as ChzzkChatCrawlComponent
from components.chzzk_streaming_check import Component as ChzzkStreamingCheckComponent


class PipelineType(BaseModel):
    chzzk_streaming_check: Optional[RequestChzzkStreamingCheckMessage] = None
    chzzk_chat_crawl: Optional[RequestChzzkChatCrawlMessage] = None


class Pipeline:
    def __init__(self, **config):
        self.config = PipelineType(**config)    # Validate the config against PipelineType

    def __call__(self):
        def exec_component(
            Component, request_message: dict
        ):
            print(f"# ===== exec_component: {Component} =====")
            # print("# [INFO] request_message: ", request_message)
            component = Component(**request_message)
            response_message = component()
            # print("# [INFO] response_message: ", response_message)
            assert (
                response_message["result"] == "success"
            ), f"exec_component failed: {response_message}"
            return response_message

        if self.config.chzzk_streaming_check is not None:
            request_message = self.config.chzzk_streaming_check
            response_message = exec_component(
                ChzzkStreamingCheckComponent, request_message.model_dump()
            )
            self.config.chzzk_chat_crawl = RequestChzzkChatCrawlMessage(
                streamer_id=request_message.streamer_id,
                streamer_name=self.config.chzzk_chat_crawl.streamer_name if self.config.chzzk_chat_crawl is not None else request_message.streamer_id,
                cookies=request_message.cookies
            )
        if self.config.chzzk_chat_crawl is not None:
            request_message = self.config.chzzk_chat_crawl
            response_message = exec_component(ChzzkChatCrawlComponent, request_message.model_dump())


def init():
    parser = argparse.ArgumentParser(description="Run a pipeline")
    parser.add_argument("--pipeline", type=str, metavar="PIPELINE", required=True)
    args = parser.parse_args()

    return args


def main():
    args = init()
    with open(Path("pipelines") / args.pipeline, "r") as fp:
        config = yaml.safe_load(fp)
        config = config if config is not None else {}

    pipeline = Pipeline(**config)
    pipeline()


if __name__ == "__main__":
    main()
