"""DB 기반 크롤러 오케스트레이터.

streamers 테이블의 is_active 플래그를 폴링하여
크롤러 스레드를 자동으로 시작/중지한다.
"""

import threading
import time

from components import streaming_check, producer, consumer
from modules.postgresql import get_connection
from modules.postgresql.schema import init_schema

POLL_INTERVAL = 5  # DB 폴링 주기 (초)


def _crawler_loop(streamer_id: str, streamer_name: str,
                  shutdown_event: threading.Event):
    """하나의 스트리머에 대한 크롤링 루프.

    is_active=TRUE인 동안 반복:
      1) 방송 시작 대기 (streaming_check)
      2) 방송 시작 → producer 실행 (WebSocket 크롤)
      3) 방송 종료 → 다시 1로 (is_active가 여전히 TRUE이면)
    """
    while not shutdown_event.is_set():
        # Phase 1: 방송 대기
        print(f"[Orchestrator] {streamer_name}: 방송 대기 중...")
        is_live = streaming_check.run(streamer_id, shutdown_event)

        if not is_live:
            # shutdown 요청으로 대기 취소됨
            break

        # Phase 2: 크롤링 시작
        print(f"[Orchestrator] {streamer_name}: 크롤링 시작")
        try:
            producer.run(streamer_id, streamer_name, shutdown_event)
        except Exception as e:
            print(f"[Orchestrator] {streamer_name}: 크롤링 오류 - {e}")

        # Phase 3: 방송 종료 → 잠시 대기 후 다시 루프
        print(f"[Orchestrator] {streamer_name}: 방송 종료, 대기 루프로 복귀")
        shutdown_event.wait(timeout=5)


def main():
    # DB 초기화
    init_conn = get_connection()
    init_schema(init_conn)
    init_conn.close()

    # Consumer 스레드 (장기 실행, 전체 토픽 공유)
    for topic in ("chat", "streaming"):
        t = threading.Thread(target=consumer.run, args=(topic,), daemon=True)
        t.start()
        print(f"[Orchestrator] Consumer 시작: {topic}")

    active_crawlers: dict[str, threading.Thread] = {}
    shutdown_events: dict[str, threading.Event] = {}

    print("[Orchestrator] 시작됨. DB 폴링 중...")

    conn = get_connection()
    conn.autocommit = True

    try:
        while True:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT streamer_id, streamer_name FROM streamers WHERE is_active = TRUE"
                    )
                    active_streamers = {row[0]: row[1] for row in cur.fetchall()}
            except Exception:
                # 연결 끊김 시 재연결
                try:
                    conn.close()
                except Exception:
                    pass
                conn = get_connection()
                conn.autocommit = True
                continue

            # 새로 활성화된 스트리머 → 크롤러 시작
            for s_id, s_name in active_streamers.items():
                if s_id not in active_crawlers or not active_crawlers[s_id].is_alive():
                    event = threading.Event()
                    t = threading.Thread(
                        target=_crawler_loop,
                        args=(s_id, s_name, event),
                        daemon=True,
                    )
                    t.start()
                    active_crawlers[s_id] = t
                    shutdown_events[s_id] = event
                    print(f"[Orchestrator] 크롤러 스레드 시작: {s_name}")

            # 비활성화된 스트리머 → 크롤러 중지
            for s_id in list(active_crawlers.keys()):
                if s_id not in active_streamers:
                    if not shutdown_events[s_id].is_set():
                        shutdown_events[s_id].set()
                        print(f"[Orchestrator] 크롤러 중지 요청: {s_id[:8]}")

            # 종료된 스레드 정리
            for s_id in list(active_crawlers.keys()):
                if not active_crawlers[s_id].is_alive():
                    del active_crawlers[s_id]
                    del shutdown_events[s_id]

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("[Orchestrator] 종료 중...")
        for event in shutdown_events.values():
            event.set()
        for t in active_crawlers.values():
            t.join(timeout=10)
        conn.close()
        print("[Orchestrator] 종료 완료")


if __name__ == "__main__":
    main()
