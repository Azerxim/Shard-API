import datetime as dt
from sqlmodel import SQLModel, Field, Relationship

################# Users ########################

class Users(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    full_name: str | None = Field(default=None)
    email: str = Field(index=True, unique=True)
    hashed_password: str = Field()
    image_url: str | None = Field(default=None)
    arrival: dt.datetime | None = Field(default=None)
    is_disabled: bool = Field(default=False)
    is_admin: bool = Field(default=False)
    is_visible: bool = Field(default=True)
    created_at: dt.datetime = Field(default_factory=dt.datetime.now)

    platforms: list["UserPlatforms"] = Relationship(back_populates="user")

class UserPlatforms(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id")
    platform: str
    uid: str

    user: Users = Relationship(back_populates="platforms")

# class ActiveSession(SQLModel, table=True):
#     id: int | None = Field(default=None, primary_key=True)
#     username: str = Field(index=True)
#     access_token: str = Field()
#     expiry_time: dt.datetime = Field()


############### Bibliothèque ####################

class Journaux(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id")
    author: str
    title: str
    description: str | None = Field(default=None)
    
    cover_url: str | None = Field(default=None)
    cover_icon: str | None = Field(default=None)
    cover_color: str | None = Field(default=None)

    link: str | None = Field(default=None)
    uid: str | None = Field(default=None)

    published_date: dt.date | None = Field(default=None)
    created_at: dt.datetime = Field(default_factory=dt.datetime.now)


class Livres(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id")
    author: str
    title: str
    description: str | None = Field(default=None)
    
    cover_url: str | None = Field(default=None)
    cover_icon: str | None = Field(default=None)
    cover_color: str | None = Field(default=None)
    pages: int | None = Field(default=None)
    language: str | None = Field(default=None)

    link: str | None = Field(default=None)
    published_date: dt.date | None = Field(default=None)
    created_at: dt.datetime = Field(default_factory=dt.datetime.now)

############### Civilisations ####################

class CivilisationMembers(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id")
    civilisation_id: int | None = Field(default=None, foreign_key="civilisations.id")
    role: str | None = Field(default=None)
    joined_at: dt.datetime = Field(default_factory=dt.datetime.now)

class Gouvernements(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    civilisation_id: int | None = Field(default=None, foreign_key="civilisations.id")
    title: str
    description: str | None = Field(default=None)
    devise: str | None = Field(default=None)
    hymne: str | None = Field(default=None)
    created_at: dt.datetime = Field(default_factory=dt.datetime.now)

class Civilisations(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str | None = Field(default=None)
    date_founded: dt.date | None = Field(default=None)
    gouvernement_id: int | None = Field(default=None, foreign_key="gouvernements.id")

    is_public: bool | None = Field(default=None)
    created_at: dt.datetime | None = Field(default=None)

class Villes(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str | None = Field(default=None)

    population: int | None = Field(default=None)
    founded_date: dt.date | None = Field(default=None)
    
    dimension_id: int | None = Field(default=None, foreign_key="dimensions.id")
    x: int | None = Field(default=None)
    z: int | None = Field(default=None)

    is_public: bool | None = Field(default=None)
    is_capital: bool | None = Field(default=None)
    created_at: dt.datetime | None = Field(default=None)
    
    civilisation_id: int | None = Field(default=None, foreign_key="civilisations.id")

class Quartiers(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str | None = Field(default=None)

    population: int | None = Field(default=None)
    founded_date: dt.date | None = Field(default=None)

    x: int | None = Field(default=None)
    z: int | None = Field(default=None)

    is_public: bool | None = Field(default=None)
    created_at: dt.datetime | None = Field(default=None)
    
    ville_id: int | None = Field(default=None, foreign_key="villes.id")
    

############### Religions ####################

class Religions(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str | None = Field(default=None)
    founder: str | None = Field(default=None)
    date_founded: dt.date | None = Field(default=None)

    is_public: bool | None = Field(default=None)
    created_at: dt.datetime | None = Field(default=None)

class VillesReligions(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ville_id: int | None = Field(default=None, foreign_key="villes.id")
    religion_id: int | None = Field(default=None, foreign_key="religions.id")
    influence: float | None = Field(default=None)

class QuartiersReligions(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    quartier_id: int | None = Field(default=None, foreign_key="quartiers.id")
    religion_id: int | None = Field(default=None, foreign_key="religions.id")
    influence: float | None = Field(default=None)

############### Cartographie ####################

class Dimensions(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str 
    link: str | None = Field(default=None)
    description: str | None = Field(default=None)

class Cartographie(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str | None = Field(default=None)
    text: str | None = Field(default=None)
    color: str | None = Field(default=None)
    type: str | None = Field(default=None)      # e.g., "civilisation", "ville", "quartier"
    type_id: int | None = Field(default=None)   # ID of the associated entity
    
    dimension_id: int = Field(foreign_key="dimensions.id")
    shape_type: str | None = Field(default=None)  # e.g., "point", "line", "polygon"
    coordinates: str | None = Field(default=None)  # Stored as JSON string

############### Templates ####################


