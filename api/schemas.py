from typing import List, Optional
from pydantic import BaseModel


class TableAuth(BaseModel):
    idAuth: int
    platform: str
    pseudo: str
    password: str
    mail: str
    statut: str
    image_url: str
    arrival: str

    platform_discord_id: str
    platform_discord_mail: str
    platform_discord_image_url: str

    platform_github_id: str
    platform_github_mail: str
    platform_github_image_url: str
    
    platform_microsoft_id: str
    platform_microsoft_mail: str
    platform_microsoft_image_url: str

    param_visible: int
    param_maillist: int
    param_beta: int


    class Config:
        orm_mode = False
