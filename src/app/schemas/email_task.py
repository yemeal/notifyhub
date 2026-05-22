from pydantic import BaseModel


class EmailTaskCreate(BaseModel):
    recipient: str
    subject: str
    body: str
