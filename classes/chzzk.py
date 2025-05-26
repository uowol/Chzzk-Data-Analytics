from typing import Dict, List, Optional, Union
from classes import base


class CookiesType(base.BaseModel):
    NID_SES: str
    NID_AUT: str


class RequestChzzkChatCrawlMessage(base.RequestMessage):
    streamer_id: str
    cookies: CookiesType


class ResponseChzzkChatCrawlMessage(RequestChzzkChatCrawlMessage):
    result: str  # "success" or "fail"
