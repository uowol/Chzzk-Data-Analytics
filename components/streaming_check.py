import threading
import time

from modules.chzzk.api import fetch_streamingCheck
from modules.config import NID_SES, NID_AUT


def run(streamer_id: str, shutdown_event: threading.Event | None = None):
    """방송 시작을 대기한다. 방송 시작 시 True, shutdown 요청 시 False 반환."""
    cookies = {"NID_SES": NID_SES, "NID_AUT": NID_AUT}

    while True:
        if shutdown_event and shutdown_event.is_set():
            return False

        try:
            is_streaming = fetch_streamingCheck(streamer_id, cookies)
        except Exception as e:
            print(f"Error checking streaming status for {streamer_id}: {e}")
            is_streaming = False

        if is_streaming:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Streaming is live!")
            return True
        else:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Streaming is offline.")

        if shutdown_event:
            shutdown_event.wait(timeout=10)
        else:
            time.sleep(10)
