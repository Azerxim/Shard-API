from typing import Optional, List
from pydantic import BaseModel, field_validator
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
    is_moderateur: bool | None = None
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
    image_url: Optional[str] = None
    is_disabled: Optional[bool] = None
    is_visible: Optional[bool] = None
    # Rôles : modifiables uniquement par un administrateur (vérifié par la route)
    is_admin: Optional[bool] = None
    is_moderateur: Optional[bool] = None

class UserRead(BaseModel):
    id: int
    username: str
    full_name: str | None = None
    email: str | None = None
    image_url: str | None = None
    arrival: datetime.datetime | None = None
    is_disabled: bool | None = None
    is_admin: bool | None = None
    is_moderateur: bool | None = None
    is_visible: bool | None = None
    created_at: datetime.datetime | None = None

class UserLogin(BaseModel):
    username: str | None = None
    email: str | None = None
    password: str
    full_name: str | None = None  # Pseudo affiché, saisi à l'inscription


############### Bibliothèque ####################

class EmptyDatesAsNone(BaseModel):
    # Les formulaires envoient "" pour une date non renseignée : on la traite comme absente
    @field_validator("date_founded", "founded_date", "published_date", mode="before", check_fields=False)
    @classmethod
    def empty_date_as_none(cls, value):
        return None if value == "" else value

class Journal(EmptyDatesAsNone):
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
    is_public: bool | None = None


class Livre(EmptyDatesAsNone):
    id: int | None = None
    user_id: int
    author: str
    title: str
    description: str | None = None
    cover_url: str | None = None
    cover_icon: str | None = "fas fa-book"
    cover_color: str | None = "#4CAF50"
    pages: int | None = None
    language: str | None = "Français"
    link: str | None = None
    civilisation_id: int | None = None
    published_date: datetime.datetime | None = None
    created_at: datetime.datetime | None = None
    is_public: bool | None = None

class LivreContenu(BaseModel):
    id: int | None = None
    livre_id: int
    chapitre: str | None = None
    sous_chapitre: str | None = None
    ordre: int = 0
    indent: int | None = None
    content: str | None = None
    page_number: int | None = None
    
############### Civilisations ####################

class CivilisationMember(BaseModel):
    id: int
    user_id: int
    civilisation_id: int
    role: str
    joined_at: datetime.datetime

    class Config:
        from_attributes = True

class CivilisationMemberAdd(BaseModel):
    user_id: int
    role: str
    
class CivilisationMemberUpdate(BaseModel):
    role: str

class CivilisationFounderTransfer(BaseModel):
    user_id: int                      # Nouveau fondateur
    former_role: str = "Admin"        # Rôle de l'ancien fondateur : "Admin" ou "Membre"

class ReligionFounderTransfer(CivilisationFounderTransfer):
    pass

# Religions et commerces : mêmes formulaires que les membres de civilisation
class ReligionMemberAdd(CivilisationMemberAdd):
    pass

class ReligionMemberUpdate(CivilisationMemberUpdate):
    pass

class CommerceMemberAdd(CivilisationMemberAdd):
    pass

class CommerceMemberUpdate(CivilisationMemberUpdate):
    pass

class CommerceFounderTransfer(CivilisationFounderTransfer):
    pass

class Gouvernement(BaseModel):
    id: int
    civilisation_id: int
    title: str
    type: str
    description: str | None = None
    devise: str | None = None
    hymne: str | None = None
    created_at: datetime.datetime | None = None

    class Config:
        from_attributes = True

class GouvernementCreate(BaseModel):
    civilisation_id: int
    title: str
    type: str
    description: str | None = None
    devise: str | None = None
    hymne: str | None = None

class Civilisation(EmptyDatesAsNone):
    id: int
    title: str
    description: str | None = None
    date_founded: datetime.datetime | None = None
    gouvernement_id: int | None = None
    
    is_public: bool | None = None
    created_at: datetime.datetime | None = None

    is_civilisation_dirigeante: bool | None = True
    dirigeante_civilisation_id: int | None = 0

    class Config:
        from_attributes = True

class CivilisationCreate(EmptyDatesAsNone):
    title: str
    description: str | None = None
    date_founded: datetime.datetime | None = None
    gouvernement_id: int | None = None
    is_public: bool | None = None
    is_civilisation_dirigeante: bool | None = True
    dirigeante_civilisation_id: int | None = 0

class Ville(EmptyDatesAsNone):
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

class VilleCreate(EmptyDatesAsNone):
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

class Quartier(EmptyDatesAsNone):
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

class QuartierCreate(EmptyDatesAsNone):
    # Sans x / z, le quartier est placé au centre de sa ville
    title: str
    description: str | None = None
    population: int | None = 0
    founded_date: datetime.datetime | None = None
    x: int | None = None
    z: int | None = None
    is_public: bool | None = None
    ville_id: int

    @field_validator("population", "x", "z", mode="before")
    @classmethod
    def empty_number_as_none(cls, value):
        return None if value == "" else value

class QuartierUpdate(QuartierCreate):
    # Seuls les champs renseignés sont modifiés
    title: str | None = None
    population: int | None = None
    ville_id: int | None = None

############### Commerces ####################

class Commerce(BaseModel):
    id: int
    title: str
    description: str | None = None

    is_public: bool | None = None
    created_at: datetime.datetime | None = None

class CommerceCreate(BaseModel):
    # L'utilisateur connecté devient Fondateur du commerce
    title: str
    description: str | None = None
    date_founded: datetime.date | None = None
    is_public: bool | None = None
    is_commerce_dirigeant: bool | None = True
    dirigeant_commerce_id: int | None = 0

    @field_validator("dirigeant_commerce_id", mode="before")
    @classmethod
    def empty_dirigeant_as_zero(cls, value):
        return 0 if value in ("", None) else value

    @field_validator("date_founded", mode="before")
    @classmethod
    def empty_date_as_none(cls, value):
        return None if value == "" else value

class EmptyStringAsNone(BaseModel):
    # Les formulaires envoient "" pour un champ vide (select sans choix, nombre effacé)
    @field_validator("*", mode="before")
    @classmethod
    def empty_string_as_none(cls, value):
        return None if value == "" else value

class CommerceUpdate(EmptyStringAsNone):
    title: str | None = None
    description: str | None = None
    date_founded: datetime.date | None = None
    is_public: bool | None = None
    is_commerce_dirigeant: bool | None = None
    dirigeant_commerce_id: int | None = None

class MagasinCreate(EmptyStringAsNone):
    commerce_id: int
    title: str
    description: str | None = None
    founded_date: datetime.date | None = None

    dimension_id: int | None = None
    x: int | None = None
    z: int | None = None

    is_siege: bool | None = None
    is_public: bool | None = None
    ville_id: int | None = None

class MagasinUpdate(EmptyStringAsNone):
    title: str | None = None
    description: str | None = None
    founded_date: datetime.date | None = None

    dimension_id: int | None = None
    x: int | None = None
    z: int | None = None

    is_siege: bool | None = None
    is_public: bool | None = None
    ville_id: int | None = None

class CommerceMagasin(EmptyDatesAsNone):
    id: int
    commerce_id: int
    title: str
    description: str | None = None
    founded_date: datetime.datetime | None = None

    dimension_id: int
    x: int
    z: int

    is_siege: bool | None = None
    is_public: bool | None = None
    created_at: datetime.datetime | None = None

    ville_id: int

class CommerceMagasinCreate(EmptyDatesAsNone):
    commerce_id: int
    title: str
    description: str | None = None
    founded_date: datetime.datetime | None = None

    dimension_id: int
    x: int
    z: int

    is_siege: bool | None = None
    is_public: bool | None = None
    
    ville_id: int


############### Religions ####################

class Religions(EmptyDatesAsNone):
    id: int
    title: str
    description: str | None = None
    date_founded: datetime.datetime | None = None
    color: str | None = None
    icon: str | None = None

    is_public: bool | None = None
    created_at: datetime.datetime | None = None

class ReligionCreate(EmptyDatesAsNone):
    title: str
    description: str | None = None
    date_founded: datetime.datetime | None = None
    color: str | None = None
    icon: str | None = None
    is_public: bool | None = None

class ReligionMember(BaseModel):
    id: int
    user_id: int
    religion_id: int
    role: str
    joined_at: datetime.datetime

    class Config:
        from_attributes = True

class VillesReligions(BaseModel):
    id: int
    ville_id: int
    religion_id: int
    influence: float | None = 0.0

class VillesReligionsCreate(BaseModel):
    ville_id: int
    religion_id: int
    influence: float | None = 0.0

class VillesReligionsUpdate(BaseModel):
    ReligionID: int
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

############### Alliances ####################

class AllianceCreate(EmptyStringAsNone):
    title: str
    description: str | None = None
    type: str | None = "Militaire"          # "Militaire" ou "Diplomatique"
    color: str | None = None
    icon: str | None = None
    flag_url: str | None = None
    date_founded: datetime.date | None = None
    is_public: bool | None = True
    civilisation_id: int                    # Civilisation fondatrice, chef de file

class AllianceUpdate(EmptyStringAsNone):
    title: str | None = None
    description: str | None = None
    type: str | None = None
    color: str | None = None
    icon: str | None = None
    flag_url: str | None = None
    date_founded: datetime.date | None = None
    is_public: bool | None = None

class AllianceCivilisation(BaseModel):
    civilisation_id: int

class AllianceMembreUpdate(BaseModel):
    role: str                               # "Membre" ou "Observateur" (le chef de file change par transfert)

class ReponseInvitation(BaseModel):
    accepter: bool

############### Guerres ####################

class GuerreDeclaration(EmptyStringAsNone):
    title: str
    type: str | None = "Militaire"          # "Militaire" (civilisations) ou "Religion" (religions)
    casus_belli: str | None = None
    description: str | None = None
    attaquant_id: int
    defenseur_id: int

class GuerreUpdate(EmptyStringAsNone):
    title: str | None = None
    casus_belli: str | None = None
    description: str | None = None

class GuerreValidation(EmptyStringAsNone):
    date_debut: datetime.date | None = None
    note: str | None = None

class GuerreRefus(EmptyStringAsNone):
    note: str | None = None

class GuerreFin(EmptyStringAsNone):
    issue: str
    date_fin: datetime.date | None = None

class GuerreAppel(EmptyStringAsNone):
    camp: str                               # "attaquant" ou "defenseur"
    civilisation_id: int | None = None
    alliance_id: int | None = None          # Appelle toutes les civilisations de l'alliance

class ReponseAppel(BaseModel):
    accepter: bool

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

class CartographieUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    text: str | None = None
    color: str | None = None
    type: str | None = None
    type_id: int | None = None
    dimension_id: int | None = None
    shape_type: str | None = None
    coordinates: str | None = None

############### Templates ####################