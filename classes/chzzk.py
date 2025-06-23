from typing import Dict, List, Optional, Union
from classes import base


class CookiesType(base.BaseModel):
    NID_SES: str
    NID_AUT: str


class RequestProducerMessage(base.RequestMessage):
    streamer_id: Optional[str] = None
    streamer_name: Optional[str] = None
    cookies: Optional[CookiesType] = None


class ResponseProducerMessage(RequestProducerMessage):
    result: str  # "success" or "fail"


class RequestStreamingCheckMessage(base.RequestMessage):
    streamer_id: Optional[str] = None
    cookies: Optional[CookiesType] = None


class ResponseStreamingCheckMessage(RequestStreamingCheckMessage):
    result: str