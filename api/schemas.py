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

############### Personnages ####################

class PersonnageCreate(EmptyStringAsNone):
    name: str
    description: str | None = None
    image_url: str | None = None
    status: str | None = "vivant"           # vivant, mort ou disparu
    date_naissance: datetime.date | None = None
    date_deces: datetime.date | None = None
    civilisation_id: int | None = None
    ville_id: int | None = None
    quartier_id: int | None = None
    espece_id: int | None = None
    classe_id: int | None = None
    grade: str | None = None
    skin_source: str | None = "aucun"       # aucun, minecraft (compte lié du joueur) ou lien
    skin_url: str | None = None

class PersonnageUpdate(PersonnageCreate):
    # Seuls les champs envoyés sont modifiés ; un champ envoyé vide est effacé
    name: str | None = None
    status: str | None = None
    skin_source: str | None = None

class ReferentielItem(EmptyStringAsNone):
    # Espèce ou classe de personnage
    title: str | None = None
    description: str | None = None

class PersonnageMessageLink(BaseModel):
    journal_id: int
    message_id: str
    personnage_id: int

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

class GuerreEvenementCreate(EmptyStringAsNone):
    type: str | None = "bataille"           # bataille, siege, traite ou autre
    title: str
    description: str | None = None
    camp: str | None = None                 # attaquant, defenseur, ou vide pour les deux camps
    date_rp: datetime.date | None = None

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

############### Statistiques du monde ####################

# Envoyé par le générateur de cartes après lecture de la sauvegarde (scripts/map-generator/world_stats.py).
# Les totaux du relevé sont recalculés par l'API à partir des listes ci-dessous.

class MondeDimensionStat(BaseModel):
    source: str | None = None          # dossier du monde : "", "DIM-1", "dimensions/ns/nom"
    title: str | None = None
    dimension_id: int | None = None
    chunks: int | None = None
    chunks_actifs: int | None = None
    heures_presence: float | None = None
    lits: int | None = None
    lits_actifs: int | None = None
    villageois: int | None = None
    entites: int | None = None
    taille_octets: int | None = None

class MondeLieuStat(BaseModel):
    entity_type: str                   # civilisation, ville ou quartier
    entity_id: int
    title: str | None = None
    source: str | None = None
    dimension_id: int | None = None
    methode: str | None = None
    rayon: int | None = None
    x: int | None = None
    z: int | None = None
    population: int | None = None
    chunks: int | None = None
    chunks_actifs: int | None = None
    heures_presence: float | None = None
    lits: int | None = None
    lits_actifs: int | None = None
    villageois: int | None = None
    joueurs_presents: int | None = None
    joueurs_residents: int | None = None

class MondeZoneStat(BaseModel):
    rang: int | None = None
    source: str | None = None
    dimension_id: int | None = None
    x: int | None = None
    z: int | None = None
    taille: int | None = None
    heures_presence: float | None = None
    chunks: int | None = None
    lits: int | None = None
    lits_actifs: int | None = None
    villageois: int | None = None
    joueurs: int | None = None
    lieu_type: str | None = None
    lieu_id: int | None = None
    lieu_title: str | None = None
    lieu_distance: int | None = None

class MondeJoueurStat(BaseModel):
    uuid: str
    pseudo: str | None = None
    heures_jeu: float | None = None
    sessions: int | None = None
    morts: int | None = None
    joueurs_tues: int | None = None
    monstres_tues: int | None = None
    blocs_mines: int | None = None
    distance_km: float | None = None
    nuits_dormies: int | None = None
    niveau: int | None = None
    derniere_activite: datetime.datetime | None = None
    is_actif: bool | None = None
    dernier_x: int | None = None
    dernier_z: int | None = None
    derniere_dimension: str | None = None
    lit_x: int | None = None
    lit_z: int | None = None
    lit_dimension: str | None = None
    lieu_type: str | None = None
    lieu_id: int | None = None
    lieu_title: str | None = None

class MondeReleveCreate(BaseModel):
    source: str | None = "map-generator"
    releve_at: datetime.datetime | None = None
    world_name: str | None = None
    world_version: str | None = None
    data_version: int | None = None
    duration_seconds: float | None = None
    taille_octets: int | None = None
    seuil_heures_lit: float | None = None
    seuil_jours_actif: int | None = None
    seuil_heures_actif: float | None = None
    taille_tuile: int | None = None

    dimensions: List[MondeDimensionStat] = []
    lieux: List[MondeLieuStat] = []
    zones: List[MondeZoneStat] = []
    joueurs: List[MondeJoueurStat] = []


############### Templates ####################