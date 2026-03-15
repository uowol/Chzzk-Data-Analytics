import argparse
from pathlib import Path

import yaml
from pydantic import BaseModel

from components import streaming_check, producer


class PipelineConfig(BaseModel):
    streamer_id: str
    streamer_name: str


def main():
    parser = argparse.ArgumentParser(description="Run a pipeline")
    parser.add_argument("--pipeline", type=str, metavar="PIPELINE", required=True)
    args = parser.parse_args()

    with open(Path("pipelines") / args.pipeline, "r") as fp:
        raw = yaml.safe_load(fp) or {}

    config = PipelineConfig(**raw)

    print(f"# ===== streaming_check: {config.streamer_id} =====")
    streaming_check.run(config.streamer_id)

    print(f"# ===== producer: {config.streamer_name} =====")
    producer.run(config.streamer_id, config.streamer_name)


if __name__ == "__main__":
    main()
