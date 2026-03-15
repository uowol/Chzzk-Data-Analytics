from classes import base


class CookiesType(base.BaseModel):
    NID_SES: str
    NID_AUT: str


class RequestProducerMessage(base.RequestMessage):
    streamer_id: str | None = None
    streamer_name: str | None = None
    cookies: CookiesType | None = None


class RequestStreamingCheckMessage(base.RequestMessage):
    streamer_id: str | None = None
    cookies: CookiesType | None = None
