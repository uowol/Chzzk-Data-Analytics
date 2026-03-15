import time

from modules.chzzk.api import fetch_streamingCheck
from modules.config import NID_SES, NID_AUT


def run(streamer_id: str):
    cookies = {"NID_SES": NID_SES, "NID_AUT": NID_AUT}

    while True:
        try:
            is_streaming = fetch_streamingCheck(streamer_id, cookies)
        except Exception as e:
            print(f"Error checking streaming status for {streamer_id}: {e}")
            is_streaming = False

        if is_streaming:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Streaming is live!")
            return
        else:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Streaming is offline.")
        time.sleep(10)
