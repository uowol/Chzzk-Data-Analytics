from enum import IntEnum


class ChzzkChatCommand(IntEnum):
    RECEIVE_PING: int = 0
    REQUEST_PONG: int = 10000
    REQUEST_CONNECT: int = 100
    REQUEST_SEND_CHAT: int = 3101
    REQUEST_RECENT_CHAT: int = 5101
    RECEIVE_CHAT: int = 93101
    RECEIVE_SPECIAL: int = 93102

class ChzzkChatType(IntEnum):
    CHAT: int = 100
    DELETED_CHAT: int = 101
    DONATION: int = 102
    SUBSCRIPTION: int = 103

class ChzzkStreamingType(IntEnum):
    CHANGE_CATEGORY: int = 200