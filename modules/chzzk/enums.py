from enum import IntEnum


class ChzzkChatCommand(IntEnum):
    RECEIVE_PING: int = 0
    REQUEST_PONG: int = 10000
    REQUEST_CONNECT: int = 100
    REQUEST_SEND_CHAT: int = 3101
    REQUEST_RECENT_CHAT: int = 5101
    RECEIVE_CHAT: int = 93101
    RECEIVE_SPECIAL: int = 93102
