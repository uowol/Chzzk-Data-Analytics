from modules.chzzk.chat import ChzzkChat
from modules.config import NID_SES, NID_AUT
from modules.kafka.producer import get_producer


def run(streamer_id: str, streamer_name: str):
    cookies = {"NID_SES": NID_SES, "NID_AUT": NID_AUT}

    producer = get_producer()
    chzzkchat = ChzzkChat(
        streamer_id,
        streamer_name,
        cookies,
        producer=producer,
    )
    chzzkchat.run()
    producer.close()
