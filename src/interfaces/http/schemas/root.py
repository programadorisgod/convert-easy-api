from pydantic import BaseModel


class RootResponse(BaseModel):
    message: str
    version: str
    docs: str
    health: str
    api: str
