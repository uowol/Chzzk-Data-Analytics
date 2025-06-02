from typing import Dict, List, Optional, Union
from classes import base


class CookiesType(base.BaseModel):
    NID_SES: str
    NID_AUT: str


class RequestChzzkChatCrawlMessage(base.RequestMessage):
    streamer_id: Optional[str] = None
    streamer_name: Optional[str] = None
    cookies: Optional[CookiesType] = None


class ResponseChzzkChatCrawlMessage(RequestChzzkChatCrawlMessage):
    result: str  # "success" or "fail"


class RequestChzzkStreamingCheckMessage(base.RequestMessage):
    streamer_id: Optional[str] = None
    cookies: Optional[CookiesType] = None


class ResponseChzzkStreamingCheckMessage(RequestChzzkStreamingCheckMessage):
    result: str