import datetime
import json
import logging
import re
import os

from websocket import WebSocket
from logging.handlers import TimedRotatingFileHandler

from . import api, enums


class ChzzkChat:

    def __init__(self, streamer: str, cookies: dict, logger: logging.Logger):

        self.streamer = streamer
        self.cookies = cookies
        self.logger = logger
        self.category = None

        self.sid = None
        self.userIdHash = api.fetch_userIdHash(self.cookies)
        self.chatChannelId, self.liveCategory = api.fetch_chatChannelId(self.streamer, self.cookies)
        self.channelName = api.fetch_channelName(self.streamer)
        self.accessToken, self.extraToken = api.fetch_accessToken(
            self.chatChannelId, self.cookies
        )
        self.emojiPacks, self.subEmojiPacks = api.fetch_channelEmojiPacks(
            self.streamer, self.cookies
        )
        
        self.connect()

    def get_emoji_url(self, emoji_id: str) -> str:
        if emoji_id.startswith("dp_") or emoji_id.startswith("lck_"):
            emojipacks = self.emojiPacks
        else:
            emojipacks = self.subEmojiPacks
        for pack in emojipacks:
            for emoji in pack["emojis"]:
                if emoji["emojiId"] == emoji_id:
                    return emoji["imageUrl"]
        return emoji_id

    def connect(self):

        self.chatChannelId, self.liveCategory  = api.fetch_chatChannelId(self.streamer, self.cookies)
        self.accessToken, self.extraToken = api.fetch_accessToken(
            self.chatChannelId, self.cookies
        )
        
        if self.category != self.liveCategory:
            self.logger.info(f"방송 카테고리가 변경되었습니다. {self.category} -> {self.liveCategory}")
            self.category = self.liveCategory

        sock = WebSocket()
        sock.connect("wss://kr-ss3.chat.naver.com/chat")
        print(f"{self.channelName} 채팅창에 연결 중 .", end="")

        default_dict = {
            "ver": "3",  # 2025-03
            "svcid": "game",
            "cid": self.chatChannelId,
        }

        send_dict = {
            "cmd": enums.ChzzkChatCommand.REQUEST_CONNECT,
            "tid": 1,
            "bdy": {
                "uid": self.userIdHash,
                "devType": 2001,  # 2001: Browser, 2002: Mobile
                "accTkn": self.accessToken,
                "auth": "SEND",
            },
        }

        sock.send(json.dumps(dict(send_dict, **default_dict)))
        sock_response = json.loads(sock.recv())
        self.sid = sock_response["bdy"]["sid"]
        print(f"\r{self.channelName} 채팅창에 연결 중 ..", end="")

        send_dict = {
            "cmd": enums.ChzzkChatCommand.REQUEST_RECENT_CHAT,
            "tid": 2,
            "sid": self.sid,
            "bdy": {"recentMessageCount": 50},
        }

        sock.send(json.dumps(dict(send_dict, **default_dict)))
        sock.recv()
        print(f"\r{self.channelName} 채팅창에 연결 중 ...")

        self.sock = sock
        if self.sock.connected:
            print("연결 완료")
        else:
            raise ValueError("오류 발생")

    def send(self, message: str):

        default_dict = {
            "ver": "3",
            "svcid": "game",
            "cid": self.chatChannelId,
        }

        extras = {
            "chatType": "STREAMING",
            "emojis": "",
            "osType": "PC",
            "extraToken": self.extraToken,
            "streamingChannelId": self.chatChannelId,
        }

        send_dict = {
            "tid": 3,
            "cmd": enums.ChzzkChatCommand.REQUEST_SEND_CHAT,
            "retry": False,
            "sid": self.sid,
            "bdy": {
                "msg": message,
                "msgTypeCode": 1,
                "extras": json.dumps(extras),
                "msgTime": int(datetime.datetime.now().timestamp()),
            },
        }

        self.sock.send(json.dumps(dict(send_dict, **default_dict)))

    def run(self):

        while True:

            try:

                try:
                    raw_message = self.sock.recv()

                except KeyboardInterrupt:
                    break

                except:
                    self.connect()
                    raw_message = self.sock.recv()

                raw_message = json.loads(raw_message)
                chat_cmd = raw_message["cmd"]

                if chat_cmd == enums.ChzzkChatCommand.RECEIVE_PING:

                    self.sock.send(
                        json.dumps(
                            {"ver": "3", "cmd": enums.ChzzkChatCommand.REQUEST_PONG}
                        )
                    )

                    if self.chatChannelId != api.fetch_chatChannelId(
                        self.streamer, self.cookies
                    )[0]:  # 방송 시작시 chatChannelId가 달라지는 문제
                        self.connect()

                    continue

                if chat_cmd == enums.ChzzkChatCommand.RECEIVE_CHAT:
                    chat_type = "채팅"

                elif chat_cmd == enums.ChzzkChatCommand.RECEIVE_SPECIAL:
                    messageTypeCode = raw_message["bdy"][0]["msgTypeCode"]
                    extras = json.loads(raw_message["bdy"][0]["extras"])
                    chat_type = "후원" if messageTypeCode == 10 else "구독"

                else:
                    continue

                for chat_data in raw_message["bdy"]:

                    try:
                        if chat_data["uid"] == "anonymous":
                            nickname = "익명의 후원자"

                        else:
                            profile_data = json.loads(chat_data["profile"])
                            nickname = profile_data["nickname"]

                        if chat_data["msgStatusType"] == "CBOTBLIND":
                            chat_data["msg"] = "클린봇에 의해 삭제된 메시지입니다."

                    except:
                        continue

                    now = datetime.datetime.fromtimestamp(chat_data["msgTime"] / 1000)
                    now = datetime.datetime.strftime(now, "%Y-%m-%d %H:%M:%S")

                    msg = re.sub(
                        r":.*?:",
                        lambda x: self.get_emoji_url(x.group(0)[1:-1]),
                        chat_data["msg"],
                    )
                    if chat_type == "후원":
                        self.logger.info(
                            f"[{now}][{chat_type}] {extras['payAmount']} - {nickname} : {msg}"
                        )
                    elif chat_type == "구독":
                        self.logger.info(
                            f'[{now}][{chat_type}] {extras["month"]}/{extras["tierName"]}/{extras["tierNo"]} - {nickname} : {msg}'
                        )
                    elif chat_type == "채팅":
                        self.logger.info(f"[{now}][{chat_type}] {nickname} : {msg}")

            except:
                pass


def get_logger(streamer_name: str) -> logging.Logger:
    
    class JsonFormatter(logging.Formatter):
        def format(self, record):
            return json.dumps(record.msg, ensure_ascii=False)

    formatter = logging.Formatter("%(message)s")

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    os.makedirs(f"logs/{streamer_name}", exist_ok=True)
    json_handler = TimedRotatingFileHandler(
        f"logs/{streamer_name}/chat",
        when="M",      # M = minutes, H = hours
        interval=1,    # 1분마다 회전
        encoding="utf-8",
        backupCount=0  # 개수 제한 없음
    )
    json_handler.suffix = "%Y%m%d_%H%M.jsonl"
    json_handler.setFormatter(JsonFormatter())
    logger.addHandler(json_handler)
    
    # file_handler = logging.FileHandler("logs/chat.log", mode="w")
    # file_handler.setFormatter(formatter)
    # logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger
