from typing import Dict, List, Optional, Union

from pydantic import BaseModel


class RequestMessage(BaseModel):
    pass


class ResponseMessage(RequestMessage):
    result: str  # "success" or "fail"
