import argparse
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel

from classes.chzzk import (
    RequestProducerMessage,
    RequestStreamingCheckMessage
)
from components.producer import Component as ProducerComponent
from components.streaming_check import Component as StreamingCheckComponent


class PipelineType(BaseModel):
    streaming_check: Optional[RequestStreamingCheckMessage] = None
    producer: Optional[RequestProducerMessage] = None


class Pipeline:
    def __init__(self, **config):
        self.config = PipelineType(**config)    # Validate the config against PipelineType

    def __call__(self):
        def exec_component(
            Component, request_message: dict
        ):
            print(f"# ===== exec_component: {Component} =====")
            component = Component(**request_message)
            response_message = component()
            assert (
                response_message["result"] == "success"
            ), f"exec_component failed: {response_message}"
            return response_message

        if self.config.streaming_check is not None:
            request_message = self.config.streaming_check
            response_message = exec_component(
                StreamingCheckComponent, request_message.model_dump()
            )
            self.config.producer = RequestProducerMessage(
                streamer_id=request_message.streamer_id,
                streamer_name=self.config.producer.streamer_name if self.config.producer is not None else request_message.streamer_id,
                cookies=request_message.cookies
            )
        if self.config.producer is not None:
            request_message = self.config.producer
            response_message = exec_component(ProducerComponent, request_message.model_dump())


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
