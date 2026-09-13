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
    # Modérateur RP : valide, refuse et clôt les guerres (les administrateurs le peuvent aussi)
    is_moderateur: bool | None = Field(default=False)
    is_visible: bool = Field(default=True)
    created_at: dt.datetime = Field(default_factory=dt.datetime.now)

    platforms: list["UserPlatforms"] = Relationship(back_populates="user")

class UserPlatforms(SQLModel, table=True):
    # Compte externe lié (Discord, Microsoft…) : un par plateforme et par utilisateur, un utilisateur par compte externe
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id")
    platform: str
    uid: str
    username: str | None = Field(default=None)
    avatar_url: str | None = Field(default=None)
    linked_at: dt.datetime | None = Field(default=None)

    user: Users = Relationship(back_populates="platforms")

class OAuthStates(SQLModel, table=True):
    # Jeton "state" d'une autorisation OAuth en cours : usage unique, courte durée
    id: int | None = Field(default=None, primary_key=True)
    state: str = Field(index=True, unique=True)
    provider: str
    mode: str  # "login" ou "link"
    user_id: int | None = Field(default=None, foreign_key="users.id")  # utilisateur qui lie son compte
    expires_at: dt.datetime

class ActiveSession(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    access_token: str = Field(index=True, unique=True)
    expiry_time: dt.datetime = Field()


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

    is_public: bool | None = Field(default=None)

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
    civilisation_id: int | None = Field(default=None, foreign_key="civilisations.id")
    
    published_date: dt.date | None = Field(default=None)
    created_at: dt.datetime = Field(default_factory=dt.datetime.now)

    is_public: bool | None = Field(default=None)

class LivresContenus(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    livre_id: int | None = Field(default=None, foreign_key="livres.id")
    chapitre: str | None = Field(default=None)
    sous_chapitre: str | None = Field(default=None)
    ordre: int = Field(default=0)
    indent: int | None = Field(default=None)
    content: str | None = Field(default=None)
    page_number: int | None = Field(default=None)

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
    type: str | None = Field(default=None)
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

    is_civilisation_dirigeante: bool | None = Field(default=True)
    dirigeante_civilisation_id: int | None = Field(default=0)

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


############### Commerces ####################
class Commerces(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str | None = Field(default=None)
    date_founded: dt.date | None = Field(default=None)

    is_public: bool | None = Field(default=None)
    created_at: dt.datetime | None = Field(default=None)

    # Comme les civilisations : un commerce dirigeant (défaut) ou dirigé par dirigeant_commerce_id
    is_commerce_dirigeant: bool | None = Field(default=True)
    dirigeant_commerce_id: int | None = Field(default=0)

class CommerceMembers(SQLModel, table=True):
    # Comme les religions : rôles "Fondateur" (un seul, changé par transfert), "Admin" ou "Membre"
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id")
    commerce_id: int | None = Field(default=None, foreign_key="commerces.id")
    role: str | None = Field(default=None)
    joined_at: dt.datetime = Field(default_factory=dt.datetime.now)

class CommerceMagasins(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    commerce_id: int | None = Field(default=None, foreign_key="commerces.id")
    title: str
    description: str | None = Field(default=None)

    founded_date: dt.date | None = Field(default=None)

    dimension_id: int | None = Field(default=None, foreign_key="dimensions.id")
    x: int | None = Field(default=None)
    z: int | None = Field(default=None)

    is_siege: bool | None = Field(default=None)
    is_public: bool | None = Field(default=None)
    created_at: dt.datetime | None = Field(default=None)
    
    ville_id: int | None = Field(default=None, foreign_key="villes.id")


############### Religions ####################

class Religions(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str | None = Field(default=None)
    date_founded: dt.date | None = Field(default=None)
    color: str | None = Field(default=None)
    icon: str | None = Field(default=None)

    is_public: bool | None = Field(default=None)
    created_at: dt.datetime | None = Field(default=None)

class ReligionMembers(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id")
    religion_id: int | None = Field(default=None, foreign_key="religions.id")
    role: str | None = Field(default=None)
    joined_at: dt.datetime = Field(default_factory=dt.datetime.now)

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

############### Alliances ####################

class Alliances(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str | None = Field(default=None)
    type: str = Field(default="Militaire")  # "Militaire" ou "Diplomatique"
    color: str | None = Field(default=None)
    icon: str | None = Field(default=None)
    flag_url: str | None = Field(default=None)
    date_founded: dt.date | None = Field(default=None)
    is_public: bool | None = Field(default=True)
    created_at: dt.datetime | None = Field(default=None)

class AllianceMembres(SQLModel, table=True):
    # Les membres d'une alliance sont des civilisations : "Chef de file" (un seul), "Membre" ou "Observateur"
    id: int | None = Field(default=None, primary_key=True)
    alliance_id: int | None = Field(default=None, foreign_key="alliances.id")
    civilisation_id: int | None = Field(default=None, foreign_key="civilisations.id")
    role: str = Field(default="Membre")
    joined_at: dt.datetime = Field(default_factory=dt.datetime.now)

class AllianceInvitations(SQLModel, table=True):
    # direction "invitation" : l'alliance invite une civilisation ; "demande" : la civilisation demande à entrer
    id: int | None = Field(default=None, primary_key=True)
    alliance_id: int | None = Field(default=None, foreign_key="alliances.id")
    civilisation_id: int | None = Field(default=None, foreign_key="civilisations.id")
    direction: str = Field(default="invitation")
    status: str = Field(default="en_attente")  # en_attente, acceptee, refusee, annulee
    created_by: int | None = Field(default=None, foreign_key="users.id")
    created_at: dt.datetime = Field(default_factory=dt.datetime.now)
    answered_at: dt.datetime | None = Field(default=None)

############### Guerres ####################

class Guerres(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    type: str = Field(default="Militaire")  # "Militaire" (entre civilisations) ou "Religion" (entre religions)
    casus_belli: str | None = Field(default=None)
    description: str | None = Field(default=None)
    status: str = Field(default="en_attente")  # en_attente, en_cours, terminee, refusee
    issue: str | None = Field(default=None)
    moderation_note: str | None = Field(default=None)
    date_debut: dt.date | None = Field(default=None)  # Dates RP
    date_fin: dt.date | None = Field(default=None)
    declared_by: int | None = Field(default=None, foreign_key="users.id")
    declared_at: dt.datetime = Field(default_factory=dt.datetime.now)
    moderator_id: int | None = Field(default=None, foreign_key="users.id")
    validated_at: dt.datetime | None = Field(default=None)
    ended_at: dt.datetime | None = Field(default=None)

class GuerreBelligerants(SQLModel, table=True):
    # Une civilisation ou une religion dans un camp ; "appele" tant qu'elle n'a pas accepté l'appel aux armes
    id: int | None = Field(default=None, primary_key=True)
    guerre_id: int | None = Field(default=None, foreign_key="guerres.id")
    camp: str = Field(default="attaquant")  # attaquant ou defenseur
    entity_type: str = Field(default="civilisation")  # civilisation ou religion
    entity_id: int
    is_leader: bool | None = Field(default=False)
    status: str = Field(default="engage")  # engage ou appele
    alliance_id: int | None = Field(default=None, foreign_key="alliances.id")
    joined_at: dt.datetime = Field(default_factory=dt.datetime.now)

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



