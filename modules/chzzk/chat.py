import hashlib
import json
import logging
import threading
import time

from kafka import KafkaProducer
from websocket import WebSocket

from . import api, enums
from .emoji import EmojiManager


def get_logger(streamer_name: str) -> logging.Logger:
    formatter = logging.Formatter("%(message)s")

    logger = logging.getLogger(name=f"{streamer_name}")
    logger.setLevel(logging.INFO)

    # 핸들러 중복 추가 방지
    if not logger.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger


def make_msg_id(cid: str, uid: str, msg: str, msg_time: str, idx: int = 0) -> str:
    """원본 메시지 기반 결정적 ID. 같은 메시지는 항상 같은 ID를 생성한다.

    cid(채팅 채널 ID) + uid + msg + msgTime + 배치 내 인덱스를 조합하여
    'ㅋ' 같은 짧은 메시지가 동시에 들어와도 충돌하지 않도록 한다.
    """
    raw = f"{cid}:{uid}:{msg}:{msg_time}:{idx}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


# API 호출 주기 (초)
STREAMING_CHECK_INTERVAL = 30
CATEGORY_CHECK_INTERVAL = 30


class ChzzkChat:
    def __init__(self, streamer_id: str, streamer_name: str,
                 cookies: dict,
                 producer: KafkaProducer,
                 shutdown_event: threading.Event | None = None):
        self.producer = producer
        self._shutdown_event = shutdown_event or threading.Event()
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

        self.emoji = EmojiManager(streamer_id, cookies)

        # 쿠키 만료 시 READ 모드로 전환
        if self.userIdHash is None:
            self.logger.info("쿠키가 만료되어 READ 모드로 연결합니다.")
            self.auth_mode = "READ"
        else:
            self.auth_mode = "SEND"

        # 주기적 체크용 타이머 (연결 직후 API 호출 방지)
        self._last_streaming_check = time.monotonic()
        self._last_category_check = time.monotonic()

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
        sock.settimeout(5)  # recv() 타임아웃 설정
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
                "auth": self.auth_mode,
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
            "bdy": {"recentMessageCount": 100},
        }

        sock.send(json.dumps(dict(send_dict, **default_dict)))
        recent_response = json.loads(sock.recv())
        self.logger.info(f"\r{self.channelName} 채팅창에 연결 중 ...")

        self.sock = sock
        if self.sock.connected:
            self.logger.info("연결 성공")
        else:
            raise ValueError("오류 발생")

        # 재연결 시 최근 메시지를 처리하여 갭 최소화
        self._process_raw_message(recent_response)

        # 재연결 후 타이머 리셋 (즉시 API 호출 방지)
        self._last_streaming_check = time.monotonic()
        self._last_category_check = time.monotonic()

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
                "msgTime": int(time.time()),
            },
        }

        self.sock.send(json.dumps(dict(send_dict, **default_dict)))

    def _publish(self, topic: str, msg_type: str, msg_id: str, payload: dict,
                 ts: float | None = None):
        self.producer.send(topic, {
            "msg_id": msg_id,
            "ts": ts or time.time(),
            "streamer_name": self.streamer_name,
            "msg_type": msg_type,
            "payload": payload,
        })

    def _process_raw_message(self, raw_message: dict):
        """수신된 WebSocket 메시지를 파싱하여 Kafka에 발행한다."""
        chat_cmd = raw_message.get("cmd")

        if chat_cmd == enums.ChzzkChatCommand.RECEIVE_CHAT:
            chat_type = enums.ChzzkChatType.CHAT
        elif chat_cmd == enums.ChzzkChatCommand.RECEIVE_SPECIAL:
            try:
                messageTypeCode = raw_message["bdy"][0]["msgTypeCode"]
                extras = json.loads(raw_message["bdy"][0]["extras"])
                chat_type = enums.ChzzkChatType.DONATION if messageTypeCode == 10 else enums.ChzzkChatType.SUBSCRIPTION
            except (KeyError, IndexError, json.JSONDecodeError):
                return
        else:
            # PING, 최근 채팅 응답 등 bdy가 리스트인 경우 처리
            if "bdy" in raw_message and isinstance(raw_message["bdy"], dict):
                # 최근 채팅 응답: bdy.messageList
                message_list = raw_message["bdy"].get("messageList", [])
                if message_list:
                    for idx, chat_data in enumerate(message_list):
                        self._process_chat_data(chat_data, enums.ChzzkChatType.CHAT, idx=idx)
            return

        for idx, chat_data in enumerate(raw_message.get("bdy", [])):
            if chat_type == enums.ChzzkChatType.CHAT and chat_data.get("msgStatusType") == "CBOTBLIND":
                current_type = enums.ChzzkChatType.DELETED_CHAT
            else:
                current_type = chat_type

            if current_type == enums.ChzzkChatType.DONATION:
                self._process_chat_data(chat_data, current_type, extras=extras, idx=idx)
            elif current_type == enums.ChzzkChatType.SUBSCRIPTION:
                self._process_chat_data(chat_data, current_type, extras=extras, idx=idx)
            else:
                self._process_chat_data(chat_data, current_type, idx=idx)

    def _process_chat_data(self, chat_data: dict, chat_type,
                           extras: dict | None = None, idx: int = 0):
        """개별 채팅 데이터를 처리하여 Kafka에 발행한다."""
        try:
            uid = chat_data.get("uid", "")
            if uid == "anonymous":
                nickname = "익명의 후원자"
            else:
                profile_data = json.loads(chat_data["profile"])
                nickname = profile_data["nickname"]
        except (KeyError, json.JSONDecodeError):
            return

        raw_msg = chat_data.get("msg") or ""
        msg = self.emoji.resolve(raw_msg) if raw_msg else ""
        msg_time = str(chat_data.get("msgTime", ""))

        # 결정적 msg_id: cid + uid + msg + msgTime + 배치인덱스 → 중복 방지
        msg_id = make_msg_id(self.chatChannelId, uid, raw_msg, msg_time, idx)

        # msgTime: 치지직 서버 타임스탬프 (밀리초) → 초 단위로 변환
        try:
            ts = int(msg_time) / 1000.0
        except (ValueError, TypeError):
            ts = time.time()

        if chat_type == enums.ChzzkChatType.DONATION:
            self._publish("chat", "DONATION", msg_id, {
                "nickname": nickname,
                "message": msg,
                "payAmount": extras.get("payAmount", 0) if extras else 0,
            }, ts=ts)
        elif chat_type == enums.ChzzkChatType.SUBSCRIPTION:
            self._publish("chat", "SUBSCRIPTION", msg_id, {
                "nickname": nickname,
                "message": msg,
                "month": extras["month"] if extras else 0,
                "tierName": extras["tierName"] if extras else "",
                "tierNo": extras["tierNo"] if extras else 0,
            }, ts=ts)
        elif chat_type == enums.ChzzkChatType.CHAT:
            self._publish("chat", "CHAT", msg_id, {
                "nickname": nickname,
                "message": msg,
            }, ts=ts)
        elif chat_type == enums.ChzzkChatType.DELETED_CHAT:
            self._publish("chat", "DELETED_CHAT", msg_id, {}, ts=ts)

    def _should_check_streaming(self) -> bool:
        now = time.monotonic()
        if now - self._last_streaming_check >= STREAMING_CHECK_INTERVAL:
            self._last_streaming_check = now
            return True
        return False

    def _should_check_category(self) -> bool:
        now = time.monotonic()
        if now - self._last_category_check >= CATEGORY_CHECK_INTERVAL:
            self._last_category_check = now
            return True
        return False

    def run(self):
        while not self._shutdown_event.is_set():
            try:
                # 방송 종료 체크 (주기적)
                if self._should_check_streaming():
                    try:
                        is_streaming = api.fetch_streamingCheck(self.streamer_id, self.cookies)
                        if not is_streaming:
                            self.logger.info(f"{self.channelName} 방송이 종료되었습니다.")
                            msg_id = make_msg_id(self.chatChannelId, "system", "STREAMING_END", str(time.time()))
                            self._publish("streaming", "STREAMING_END", msg_id, {})
                            self._publish("chat", "STREAMING_END", msg_id, {})
                            break
                    except Exception as e:
                        self.logger.error(f"Streaming check failed: {e}")

                # WebSocket 메시지 수신
                try:
                    raw_message = self.sock.recv()
                except TimeoutError:
                    continue  # 타임아웃이면 루프 재시작 (streaming check 수행)
                except KeyboardInterrupt:
                    break
                except Exception:
                    self.logger.info("WebSocket 연결 끊김, 재연결 중...")
                    self.connect()
                    continue

                if not raw_message:
                    self.logger.info("WebSocket 빈 응답, 재연결 중...")
                    self.connect()
                    continue

                raw_message = json.loads(raw_message)
                chat_cmd = raw_message["cmd"]

                # PING → PONG (즉시 응답, API 호출 없음)
                if chat_cmd == enums.ChzzkChatCommand.RECEIVE_PING:
                    self.sock.send(
                        json.dumps(
                            {"ver": "3", "cmd": enums.ChzzkChatCommand.REQUEST_PONG}
                        )
                    )
                    continue

                # 카테고리 변경 체크 (주기적)
                if self._should_check_category():
                    try:
                        _, live_category = self.get_streaming_info()
                        if self.category != live_category:
                            msg_id = make_msg_id(self.chatChannelId, "system", "CATEGORY_CHANGE", str(time.time()))
                            self._publish("streaming", "CATEGORY_CHANGE", msg_id, {
                                "category": live_category,
                            })
                            self.category = live_category
                    except Exception as e:
                        self.logger.error(f"Category check failed: {e}")

                self._process_raw_message(raw_message)

            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(f"Error in chat loop: {e}")
