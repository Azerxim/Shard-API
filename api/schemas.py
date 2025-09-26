from typing import List, Optional
from pydantic import BaseModel
import datetime


################# Users ########################
# Plateforme de connexion externe de l'utilisateur
class UserPlatforms(BaseModel):
    id: int
    user_id: int
    platform: str
    uid: str

    class Config:
        from_attributes = True

# Utilisateur dans la base de données
class Users(BaseModel):
    id: int
    username: str
    email: str | None = None
    hashed_password: str
    pseudo: str
    image_url: str | None = None
    arrival: datetime.datetime
    is_disabled: bool | None = None
    is_admin: bool | None = None

    platforms: List[UserPlatforms] = []

# Interface pour la creation d'un utilisateur
class createUser(BaseModel):
    username: str
    email: str | None = None
    password: str
    pseudo: str

# Interface pour le login d'un utilisateur
class loginUser(BaseModel):
    username: str | None = None
    email: str | None = None
    password: str

# Interface pour la mise à jour d'un utilisateur
class updateUser(BaseModel):
    id: int
    username: str | None = None
    email: str | None = None
    password: str | None = None
    pseudo: str | None = None
    image_url: str | None = None
    is_disabled: bool | None = None
    is_admin: bool | None = None

# Interface de retour d'un utilisateur
class readUser(BaseModel):
    id: int
    username: str
    email: str | None = None
    pseudo: str
    image_url: str | None = None
    arrival: datetime.datetime
    is_disabled: bool | None = None
    is_admin: bool | None = None

    platforms: List[UserPlatforms] = []

    class Config:
        from_attributes = True


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