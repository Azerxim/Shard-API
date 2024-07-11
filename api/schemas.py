from typing import List, Optional
from pydantic import BaseModel
import datetime


class TableAuth(BaseModel):
    idAuth: int
    platform: str
    pseudo: str
    password: str
    mail: str
    statut: str
    image_url: str
    arrival: str

    # platform_discord_id: str
    # platform_discord_name: str
    # platform_discord_mail: str
    # platform_discord_image_url: str

    # platform_github_id: str
    # platform_github_name: str
    # platform_github_mail: str
    # platform_github_image_url: str
    
    # platform_microsoft_id: str
    # platform_microsoft_name: str
    # platform_microsoft_mail: str
    # platform_microsoft_image_url: str

    class Config:
        from_attributes = False


################# Users ########################
# Utilisateur dans la base de données
class Users(BaseModel):
    id: int
    username: str
    full_name: str
    email: str | None = None
    hashed_password: str
    platform: str
    arrival: datetime.datetime
    disabled: bool | None = None

# Interface pour les requetes utilisateur
class iUsers(BaseModel):
    username: str
    full_name: str
    email: str | None = None
    password: str

# Retour données utilisateur
class rUsers(BaseModel):
    id: int
    username: str
    full_name: str
    email: str
    arrival: datetime.datetime
    disabled: bool | None = None


################# Security #####################

class SecurityUsers(BaseModel):
    username: str
    full_name: str
    email: str | None = None
    hashed_password: str
    disabled: bool | None = None


class ActiveSession(BaseModel):
    username: str
    access_token: str
    expiry_time: datetime.datetime