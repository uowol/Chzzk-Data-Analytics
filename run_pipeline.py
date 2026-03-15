import argparse
import threading
from pathlib import Path

import yaml
from pydantic import BaseModel

from components import streaming_check, producer, consumer


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

    # Consumer를 백그라운드 스레드로 실행
    consumer_threads = []
    for topic in ("chat", "streaming"):
        t = threading.Thread(target=consumer.run, args=(topic,), daemon=True)
        t.start()
        consumer_threads.append(t)

    # Producer 실행 (방송 종료 시 반환)
    print(f"# ===== producer: {config.streamer_name} =====")
    producer.run(config.streamer_id, config.streamer_name)

    # Producer 종료 후 Consumer가 STREAMING_END를 소비할 때까지 대기
    for t in consumer_threads:
        t.join(timeout=10)

    print("# ===== pipeline finished =====")


if __name__ == "__main__":
    main()
