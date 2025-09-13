from typing import List, Optional
from pydantic import BaseModel
import datetime


################# Users ########################
# Utilisateur dans la base de données
class Users(BaseModel):
    id: int
    username: str
    full_name: str
    email: str | None = None
    image_url: str | None = None
    hashed_password: str
    platform: str
    arrival: datetime.datetime
    disabled: bool | None = None

# Utilisateur full dans la base de données
class FullUser(BaseModel):
    username: str
    full_name: str
    email: str | None = None

# Interface pour les requetes utilisateur
class iUser(FullUser):
    password: str

# Update utilisateur
class uUser(FullUser):
    disabled: bool | None = None
    image_url: str | None = None

# Retour données utilisateur
class rUser(uUser):
    id: int
    platform: str
    arrival: datetime.datetime


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