from pydantic import BaseModel, Field


class AdminCredentials(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128, repr=False)


class AdminSessionRead(BaseModel):
    token: str = Field(repr=False)
