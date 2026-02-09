from typing import Optional, List
from pydantic import BaseModel
import datetime

################# Users ########################

# Utilisateur dans la base de données
class UserPlatforms(BaseModel):
    id: int
    user_id: int
    platform: str
    uid: str

class Users(BaseModel):
    id: int
    username: str
    full_name: str | None = None
    email: str | None = None
    hashed_password: str
    image_url: str | None = None
    arrival: datetime.datetime | None = None
    is_disabled: bool | None = None
    is_admin: bool | None = None
    is_visible: bool | None = None
    created_at: datetime.datetime | None = None

class ActiveSession(BaseModel):
    id: int
    username: str
    access_token: str
    expiry_time: datetime.datetime

class UserUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    is_disabled: Optional[bool] = None
    is_admin: Optional[bool] = None
    is_visible: Optional[bool] = None

class UserRead(BaseModel):
    id: int
    username: str
    full_name: str | None = None
    email: str | None = None
    image_url: str | None = None
    arrival: datetime.datetime | None = None
    is_disabled: bool | None = None
    is_admin: bool | None = None
    is_visible: bool | None = None
    created_at: datetime.datetime | None = None

class UserLogin(BaseModel):
    username: str | None = None
    email: str | None = None
    password: str


############### Bibliothèque ####################

class Journal(BaseModel):
    id: int | None = None
    user_id: int
    author: str
    title: str
    description: str | None = None
    cover_url: str | None = None
    cover_icon: str | None = "fab fa-discord"
    cover_color: str | None = "#5865F2"
    link: str | None = None
    uid: str | None = None
    published_date: datetime.datetime | None = None
    created_at: datetime.datetime | None = None


class Livre(BaseModel):
    id: int | None = None
    user_id: int
    author: str
    title: str
    description: str | None = None
    cover_url: str | None = None
    cover_icon: str | None = "fas fa-book"
    cover_color: str | None = "#4CAF50"
    pages: int | None = 0
    language: str | None = "Français"
    link: str | None = None
    published_date: datetime.datetime | None = None
    created_at: datetime.datetime | None = None
    
############### Civilisations ####################

class CivilisationMember(BaseModel):
    id: int
    user_id: int
    civilisation_id: int
    role: str
    joined_at: datetime.datetime

    class Config:
        from_attributes = True

class Gouvernement(BaseModel):
    id: int
    civilisation_id: int
    type: str
    description: str | None = None
    devise: str | None = None
    hymne: str | None = None
    created_at: datetime.datetime | None = None

    class Config:
        from_attributes = True

class GouvernementCreate(BaseModel):
    civilisation_id: int
    type: str
    description: str | None = None
    devise: str | None = None
    hymne: str | None = None

class Civilisation(BaseModel):
    id: int
    title: str
    description: str | None = None
    date_founded: datetime.datetime | None = None
    gouvernement_id: int | None = None

    is_public: bool | None = None
    created_at: datetime.datetime | None = None

    class Config:
        from_attributes = True

class CivilisationCreate(BaseModel):
    title: str
    description: str | None = None
    date_founded: datetime.datetime | None = None
    gouvernement_id: int | None = None
    is_public: bool | None = None

class Ville(BaseModel):
    id: int
    title: str
    description: str | None = None
    population: int | None = 0
    founded_date: datetime.datetime | None = None

    dimension_id: int
    x: int
    z: int

    is_public: bool | None = None
    is_capital: bool | None = None
    created_at: datetime.datetime | None = None
    
    civilisation_id: int

class VilleCreate(BaseModel):
    title: str
    description: str | None = None
    population: int | None = 0
    founded_date: datetime.datetime | None = None
    
    dimension_id: int
    x: int
    z: int

    is_capital: bool | None = None
    is_public: bool | None = None
    civilisation_id: int

class Quartier(BaseModel):
    id: int
    title: str
    description: str | None = None
    population: int | None = 0
    founded_date: datetime.datetime | None = None

    x: int
    z: int
    
    is_public: bool | None = None
    created_at: datetime.datetime | None = None

    ville_id: int

class QuartierCreate(BaseModel):
    title: str
    description: str | None = None
    population: int | None = 0
    founded_date: datetime.datetime | None = None
    
    is_public: bool | None = None
    ville_id: int

############### Religions ####################

class Religions(BaseModel):
    id: int
    title: str
    description: str | None = None
    founder: str | None = None
    date_founded: datetime.datetime | None = None

    is_public: bool | None = None
    created_at: datetime.datetime | None = None

class ReligionCreate(BaseModel):
    title: str
    description: str | None = None
    founder: str | None = None
    date_founded: datetime.datetime | None = None
    is_public: bool | None = None

class VillesReligions(BaseModel):
    id: int
    ville_id: int
    religion_id: int
    influence: float | None = 0.0

class VillesReligionsCreate(BaseModel):
    ville_id: int
    religion_id: int
    influence: float | None = 0.0

class QuartiersReligions(BaseModel):
    id: int
    quartier_id: int
    religion_id: int
    influence: float | None = 0.0

class QuartiersReligionsCreate(BaseModel):
    quartier_id: int
    religion_id: int
    influence: float | None = 0.0

############### Cartographie ####################

class Dimension(BaseModel):
    id: int
    title: str
    link: str | None = None
    description: str | None = None

class DimensionCreate(BaseModel):
    title: str
    link: str | None = None
    description: str | None = None

class Cartographie(BaseModel):
    id: int
    title: str | None = None
    description: str | None = None
    text: str | None = None
    color: str | None = None
    type: str | None = None
    type_id: int | None = None
    dimension_id: int
    shape_type: str
    coordinates: str

class CartographieCreate(BaseModel):
    title: str | None = None
    description: str | None = None
    text: str | None = None
    color: str | None = None
    type: str | None = None
    type_id: int | None = None
    dimension_id: int
    shape_type: str
    coordinates: str

############### Templates ####################