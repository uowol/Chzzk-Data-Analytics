import datetime
import json
import logging
import uuid

from kafka import KafkaProducer
from websocket import WebSocket

from . import api, enums


def get_logger(streamer_name: str) -> logging.Logger:
    formatter = logging.Formatter("%(message)s")

    logger = logging.getLogger(name=f"{streamer_name}")
    logger.setLevel(logging.INFO)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def get_ts() -> float:
    return datetime.datetime.now().timestamp()


def get_uid() -> str:
    return uuid.uuid4().hex[:8]


def make_msg_id(streamer_name: str, ts: float, uid: str) -> str:
    now = datetime.datetime.fromtimestamp(ts).strftime("%Y%m%d%H%M%S")
    return f"{streamer_name}_{now}_{uid}"


class ChzzkChat:
    def __init__(self, streamer_id: str, streamer_name: str,
                 cookies: dict,
                 producer: KafkaProducer):
        self.producer = producer
        self.logger = get_logger(streamer_name)

        self.streamer_id = streamer_id
        self.streamer_name = streamer_name
        self.cookies = cookies
        self.category = None

        self.sid = None
        self.userIdHash = api.fetch_userIdHash(self.cookies)
        self.chatChannelId, _ = api.fetch_chatChannelId(self.streamer_id, self.cookies)
        self.channelName = api.fetch_channelName(self.streamer_id)
        self.accessToken, self.extraToken = api.fetch_accessToken(
            self.chatChannelId, self.cookies
        )
        self.emojiPacks, self.subEmojiPacks = api.fetch_channelEmojiPacks(
            self.streamer_id, self.cookies
        )

        self.connect()

    def get_streaming_info(self):
        return api.fetch_chatChannelId(self.streamer_id, self.cookies)

    def connect(self):
        self.chatChannelId, _ = self.get_streaming_info()
        self.accessToken, self.extraToken = api.fetch_accessToken(
            self.chatChannelId, self.cookies
        )

        sock = WebSocket()
        sock.connect("wss://kr-ss3.chat.naver.com/chat")
        self.logger.info(f"{self.channelName} 채팅창에 연결 중 .")

        default_dict = {
            "ver": "3",
            "svcid": "game",
            "cid": self.chatChannelId,
        }

        send_dict = {
            "cmd": enums.ChzzkChatCommand.REQUEST_CONNECT,
            "tid": 1,
            "bdy": {
                "uid": self.userIdHash,
                "devType": 2001,
                "accTkn": self.accessToken,
                "auth": "SEND",
            },
        }

        sock.send(json.dumps(dict(send_dict, **default_dict)))
        sock_response = json.loads(sock.recv())
        self.sid = sock_response["bdy"]["sid"]
        self.logger.info(f"\r{self.channelName} 채팅창에 연결 중 ..")

        send_dict = {
            "cmd": enums.ChzzkChatCommand.REQUEST_RECENT_CHAT,
            "tid": 2,
            "sid": self.sid,
            "bdy": {"recentMessageCount": 50},
        }

        sock.send(json.dumps(dict(send_dict, **default_dict)))
        sock.recv()
        self.logger.info(f"\r{self.channelName} 채팅창에 연결 중 ...")

        self.sock = sock
        if self.sock.connected:
            self.logger.info("연결 성공")
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

    def _publish(self, topic: str, msg_type: str, payload: dict):
        ts = get_ts()
        uid = get_uid()
        self.producer.send(topic, {
            "msg_id": make_msg_id(self.streamer_name, ts, uid),
            "ts": ts,
            "streamer_name": self.streamer_name,
            "msg_type": msg_type,
            "payload": payload,
        })

    def run(self):
        while True:
            try:
                is_streaming = api.fetch_streamingCheck(self.streamer_id, self.cookies)
                if not is_streaming:
                    self.logger.info(f"{self.channelName} 방송이 종료되었습니다.")
                    self._publish("streaming", "STREAMING_END", {})
                    self._publish("chat", "STREAMING_END", {})
                    break

                try:
                    raw_message = self.sock.recv()
                except KeyboardInterrupt:
                    break
                except Exception:
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
                        self.streamer_id, self.cookies
                    )[0]:
                        self.connect()
                    continue

                _, self.liveCategory = self.get_streaming_info()
                if self.category != self.liveCategory:
                    self._publish("streaming", "CATEGORY_CHANGE", {
                        "category": self.liveCategory,
                    })
                    self.category = self.liveCategory

                if chat_cmd == enums.ChzzkChatCommand.RECEIVE_CHAT:
                    chat_type = enums.ChzzkChatType.CHAT
                elif chat_cmd == enums.ChzzkChatCommand.RECEIVE_SPECIAL:
                    messageTypeCode = raw_message["bdy"][0]["msgTypeCode"]
                    extras = json.loads(raw_message["bdy"][0]["extras"])
                    chat_type = enums.ChzzkChatType.DONATION if messageTypeCode == 10 else enums.ChzzkChatType.SUBSCRIPTION
                else:
                    continue

                for chat_data in raw_message["bdy"]:
                    if chat_type == enums.ChzzkChatType.CHAT and chat_data.get("msgStatusType") == "CBOTBLIND":
                        current_type = enums.ChzzkChatType.DELETED_CHAT
                    else:
                        current_type = chat_type

                    try:
                        if chat_data["uid"] == "anonymous":
                            nickname = "익명의 후원자"
                        else:
                            profile_data = json.loads(chat_data["profile"])
                            nickname = profile_data["nickname"]
                    except (KeyError, json.JSONDecodeError):
                        continue

                    ts = chat_data["msgTime"] / 1000
                    msg = chat_data["msg"]

                    if current_type == enums.ChzzkChatType.DONATION:
                        self._publish("chat", "DONATION", {
                            "nickname": nickname,
                            "message": msg,
                            "payAmount": extras.get("payAmount", 0),
                        })
                    elif current_type == enums.ChzzkChatType.SUBSCRIPTION:
                        self._publish("chat", "SUBSCRIPTION", {
                            "nickname": nickname,
                            "message": msg,
                            "month": extras["month"],
                            "tierName": extras["tierName"],
                            "tierNo": extras["tierNo"],
                        })
                    elif current_type == enums.ChzzkChatType.CHAT:
                        self._publish("chat", "CHAT", {
                            "nickname": nickname,
                            "message": msg,
                        })
                    elif current_type == enums.ChzzkChatType.DELETED_CHAT:
                        self._publish("chat", "DELETED_CHAT", {})
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(f"Error in chat loop: {e}")
