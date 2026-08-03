"""
Modèles bruts miroir des tables des anciennes bases MariaDB, importées depuis les dumps SQL :
- mbu-s1      -> tables préfixées "s1-"
- mbu-tetrago -> tables préfixées "s2-"

Ces modèles reflètent fidèlement les colonnes des dumps (pas de relations/foreign_key
ajoutées) et servent uniquement de support à l'import des données historiques.
Les noms de colonnes contenant un tiret dans les dumps (ex: `card-desc`) sont
retranscrits en snake_case (ex: `card_desc`) car un tiret n'est pas valide dans un
identifiant Python.
"""
import datetime as dt
from sqlmodel import SQLModel, Field

############### mbu-s1 (préfixe s1-) ####################

class S1Civilisations(SQLModel, table=True):
    __tablename__ = "s1-civilisations"
    civid: int | None = Field(default=None, primary_key=True)
    ownerid: int
    affichage: bool = Field(default=False)
    visibilite: bool = Field(default=True)
    date_creation: dt.date | None = Field(default=None)
    name: str
    flag_link: str | None = Field(default=None)
    short_desc: str | None = Field(default=None)
    long_desc: str | None = Field(default=None)
    gouvernement: str = Field(default="Démocratie")
    devise: str | None = Field(default=None)
    hymne: str | None = Field(default=None)
    capital_name: str
    capital_desc: str | None = Field(default=None)
    capital_coord_x: int = Field(default=0)
    capital_coord_z: int = Field(default=0)

class S1Commerces(SQLModel, table=True):
    __tablename__ = "s1-commerces"
    commerceid: int | None = Field(default=None, primary_key=True)
    ownerid: int
    civid: int | None = Field(default=None)
    visibilite: bool = Field(default=True)
    zcid: int | None = Field(default=0)
    name: str
    flag_link: str | None = Field(default=None)
    coord_x: int = Field(default=0)
    coord_z: int = Field(default=0)
    short_desc: str | None = Field(default=None)
    long_desc: str | None = Field(default=None)

class S1Personnages(SQLModel, table=True):
    __tablename__ = "s1-personnages"
    persoid: int | None = Field(default=None, primary_key=True)
    ownerid: int
    civid: int | None = Field(default=0)
    grade: str | None = Field(default=None)
    name: str
    skin_link: str | None = Field(default=None)
    perso_lock: bool = Field(default=True)
    long_desc: str | None = Field(default=None)

class S1Presses(SQLModel, table=True):
    __tablename__ = "s1-presses"
    presseid: int | None = Field(default=None, primary_key=True)
    ownerid: int
    channelid: int
    affichage: bool = Field(default=True)
    flag_link: str | None = Field(default=None)
    name: str
    short_desc: str | None = Field(default=None)
    tag: bool = Field(default=False)

class S1Structures(SQLModel, table=True):
    __tablename__ = "s1-structures"
    structid: int | None = Field(default=None, primary_key=True)
    ownerid: int
    name: str
    link: str | None = Field(default=None)
    link_name: str | None = Field(default=None)
    category: str | None = Field(default="Autres")

class S1Villes(SQLModel, table=True):
    __tablename__ = "s1-villes"
    villeid: int | None = Field(default=None, primary_key=True)
    ownerid: int
    civid: int
    name: str
    flag_link: str | None = Field(default=None)
    short_desc: str | None = Field(default=None)
    coord_x: int = Field(default=0)
    coord_z: int = Field(default=0)

class S1ZonesCommerciale(SQLModel, table=True):
    __tablename__ = "s1-zones_commerciale"
    zcid: int | None = Field(default=None, primary_key=True)
    ownerid: int
    name: str
    short_desc: str | None = Field(default=None)
    coord_x: int = Field(default=0)
    coord_z: int = Field(default=0)

############### mbu-tetrago (préfixe s2-) ####################

class S2Datapacks(SQLModel, table=True):
    __tablename__ = "s2-_datapacks"
    dpid: int | None = Field(default=None, primary_key=True)
    visibilite: bool = Field(default=False)
    nom: str
    card_desc: str | None = Field(default=None)
    lien: str | None = Field(default=None)

class S2Mods(SQLModel, table=True):
    __tablename__ = "s2-_mods"
    modid: int | None = Field(default=None, primary_key=True)
    visibilite: bool = Field(default=False)
    nom: str
    card_desc: str | None = Field(default=None)
    lien: str | None = Field(default=None)

class S2Params(SQLModel, table=True):
    __tablename__ = "s2-_params"
    paramid: int | None = Field(default=None, primary_key=True)
    etat: int = Field(default=0)
    nom: str
    valeur: str | None = Field(default=None)

class S2Plugins(SQLModel, table=True):
    __tablename__ = "s2-_plugins"
    pluginid: int | None = Field(default=None, primary_key=True)
    visibilite: bool = Field(default=False)
    nom: str
    card_desc: str | None = Field(default=None)
    lien: str | None = Field(default=None)

class S2Regles(SQLModel, table=True):
    __tablename__ = "s2-_regles"
    regleid: int | None = Field(default=None, primary_key=True)
    titre: str
    card_desc: str | None = Field(default=None)
    visibilite: bool = Field(default=False)
    ordre: int = Field(default=999)

class S2Saves(SQLModel, table=True):
    __tablename__ = "s2-_saves"
    saveid: int | None = Field(default=None, primary_key=True)
    visibilite: bool = Field(default=False)
    map: str
    date_save: dt.date
    card_desc: str | None = Field(default=None)
    lien: str | None = Field(default=None)
    mc_version: str | None = Field(default=None)
    taille: str | None = Field(default=None)
    unite: str = Field(default="Go")  # Go, Mo ou Ko

class S2Structures(SQLModel, table=True):
    __tablename__ = "s2-_structures"
    structid: int | None = Field(default=None, primary_key=True)
    ownerid: int
    name: str
    link: str | None = Field(default=None)
    link_name: str | None = Field(default=None)
    category: str | None = Field(default="Autres")

class S2AllianceCommerces(SQLModel, table=True):
    __tablename__ = "s2-alliance_commerces"
    partisantid: int | None = Field(default=None, primary_key=True)
    guildid: int
    commerceid: int

class S2AlliancePartisants(SQLModel, table=True):
    __tablename__ = "s2-alliance_partisants"
    partisantid: int | None = Field(default=None, primary_key=True)
    guildid: int
    civid: int

class S2Alliances(SQLModel, table=True):
    __tablename__ = "s2-alliances"
    guildid: int | None = Field(default=None, primary_key=True)
    name: str
    icon: str = Field(default="cubes")
    color: str = Field(default="black")
    visibilite: int = Field(default=1)
    flag_link: str | None = Field(default=None)
    short_desc: str | None = Field(default=None)
    long_desc: str | None = Field(default=None)
    type: str = Field(default="Militaire")

class S2Auth(SQLModel, table=True):
    __tablename__ = "s2-auth"
    idAuth: int | None = Field(default=None, primary_key=True)
    Platform: str | None = Field(default="TopazDevAuth")
    Pseudo: str
    MDP: str | None = Field(default=None)
    Email: str | None = Field(default=None)
    Statut: str | None = Field(default="Standard")
    Image: str | None = Field(default=None)
    Visible: int = Field(default=1)
    DiscordID: int | None = Field(default=None)
    DiscordEmail: str | None = Field(default=None)
    DiscordName: str | None = Field(default=None)
    MicrosoftID: str | None = Field(default=None)
    MicrosoftEmail: str | None = Field(default=None)
    media_instagram: str | None = Field(default=None)
    media_threads: str | None = Field(default=None)
    media_x_twitter: str | None = Field(default=None)
    media_youtube: str | None = Field(default=None)
    media_twitch: str | None = Field(default=None)

class S2Bibliotheque(SQLModel, table=True):
    __tablename__ = "s2-bibliotheque"
    livreid: int | None = Field(default=None, primary_key=True)
    ownerid: int
    parentid: int = Field(default=0)
    tag: str
    name: str
    visibilite: bool = Field(default=False)
    short_desc: str | None = Field(default=None)
    introduction: str | None = Field(default=None)
    infos: str | None = Field(default=None)
    long_desc: str | None = Field(default=None)

class S2Cartographie(SQLModel, table=True):
    __tablename__ = "s2-cartographie"
    cartoid: int | None = Field(default=None, primary_key=True)
    civid: int
    villeid: int
    dim: str  # dimension
    shape: str  # type de figure
    coords: str  # coordonnées de la figure
    color: str = Field(default="#008ed7")
    text: str | None = Field(default=None)

class S2CartographieQuartiers(SQLModel, table=True):
    __tablename__ = "s2-cartographie_quartiers"
    cartoid: int | None = Field(default=None, primary_key=True)
    villeid: int
    quartierid: int
    dim: str  # dimension
    shape: str  # type de figure
    coords: str  # coordonnées de la figure
    color: str = Field(default="#008ed7")
    text: str | None = Field(default=None)

class S2CivMembres(SQLModel, table=True):
    __tablename__ = "s2-civ_membres"
    membreid: int | None = Field(default=None, primary_key=True)
    id: int
    civid: int

class S2Civilisations(SQLModel, table=True):
    __tablename__ = "s2-civilisations"
    civid: int | None = Field(default=None, primary_key=True)
    ownerid: int
    affichage: bool = Field(default=False)
    visibilite: bool = Field(default=True)
    inactif: int = Field(default=0)
    date_creation: dt.date | None = Field(default=None)
    name: str
    flag_link: str | None = Field(default=None)
    short_desc: str | None = Field(default=None)
    long_desc: str | None = Field(default=None)
    gouvernement: str = Field(default="Démocratie")
    devise: str | None = Field(default=None)
    hymne: str | None = Field(default=None)

class S2Commerces(SQLModel, table=True):
    __tablename__ = "s2-commerces"
    commerceid: int | None = Field(default=None, primary_key=True)
    ownerid: int
    civid: int | None = Field(default=None)
    visibilite: bool = Field(default=True)
    name: str
    flag_link: str | None = Field(default=None)
    short_desc: str | None = Field(default=None)
    long_desc: str | None = Field(default=None)

class S2GuerreOpposants(SQLModel, table=True):
    __tablename__ = "s2-guerre_opposants"
    opposantid: int | None = Field(default=None, primary_key=True)
    guerreid: int
    id: int  # civid ou guildid
    idtype: str  # civ ou guild
    role: str = Field(default="att")  # Attaquant (att) ou Défenseur (def)

class S2Guerres(SQLModel, table=True):
    __tablename__ = "s2-guerres"
    guerreid: int | None = Field(default=None, primary_key=True)
    name: str
    type: str = Field(default="Militaire")  # type de guerre
    date: dt.date | None = Field(default=None)
    date_end: dt.date | None = Field(default=None)
    visibilite: int = Field(default=0)
    short_desc: str | None = Field(default=None)

class S2Journaux(SQLModel, table=True):
    __tablename__ = "s2-journaux"
    journalid: int | None = Field(default=None, primary_key=True)
    ownerid: int
    channelid: int
    affichage: bool = Field(default=True)
    flag_link: str | None = Field(default=None)
    name: str
    short_desc: str | None = Field(default=None)
    tag: bool = Field(default=False)

class S2Magasins(SQLModel, table=True):
    __tablename__ = "s2-magasins"
    magasinid: int | None = Field(default=None, primary_key=True)
    ownerid: int
    commerceid: int
    siege: int = Field(default=0)
    name: str
    short_desc: str | None = Field(default=None)
    coord_x: int = Field(default=0)
    coord_z: int = Field(default=0)
    world: str = Field(default="tetrago")

class S2NiveauType(SQLModel, table=True):
    __tablename__ = "s2-niveau_type"
    nivid: int | None = Field(default=None, primary_key=True)
    type: str  # militaire, civil ou religieux
    name: str
    points: int

class S2NiveauVilles(SQLModel, table=True):
    __tablename__ = "s2-niveau_villes"
    niv_villeid: int | None = Field(default=None, primary_key=True)
    civid: int
    villeid: int  # villeid ou 0 pour la capitale
    nivid: int

class S2PersoClasses(SQLModel, table=True):
    __tablename__ = "s2-perso_classes"
    classeid: int | None = Field(default=None, primary_key=True)
    name: str

class S2PersoEspeces(SQLModel, table=True):
    __tablename__ = "s2-perso_especes"
    especeid: int | None = Field(default=None, primary_key=True)
    name: str

class S2Personnages(SQLModel, table=True):
    __tablename__ = "s2-personnages"
    persoid: int | None = Field(default=None, primary_key=True)
    ownerid: int
    civid: int | None = Field(default=0)
    grade: str | None = Field(default=None)
    name: str
    skin_link: str | None = Field(default=None)
    type_link: str = Field(default="link")
    type_skin: str = Field(default="default")
    perso_lock: bool = Field(default=True)
    long_desc: str | None = Field(default=None)
    date_death: dt.date | None = Field(default=None)
    date_naissance: dt.date | None = Field(default=None)
    especeid: int = Field(default=0)
    classeid: int = Field(default=0)
    vie: int | None = Field(default=0)
    vie_max: int | None = Field(default=0)
    inventaire: str | None = Field(default=None)
    equipements: str | None = Field(default=None)
    caracteristiques: str | None = Field(default=None)

class S2Religions(SQLModel, table=True):
    __tablename__ = "s2-religions"
    religionid: int | None = Field(default=None, primary_key=True)
    ownerid: int
    name: str
    icon: str = Field(default="cubes")
    color: str = Field(default="black")
    visibilite: int = Field(default=1)
    flag_link: str | None = Field(default=None)
    short_desc: str | None = Field(default=None)
    long_desc: str | None = Field(default=None)

class S2Salons(SQLModel, table=True):
    __tablename__ = "s2-salons"
    salonid: int | None = Field(default=None, primary_key=True)
    ownerid: int
    name: str
    visibilite: bool
    short_desc: str
    channelid: int

class S2Villes(SQLModel, table=True):
    __tablename__ = "s2-villes"
    villeid: int | None = Field(default=None, primary_key=True)
    ownerid: int
    civid: int
    capitale: int = Field(default=0)
    name: str
    flag_link: str | None = Field(default=None)
    short_desc: str | None = Field(default=None)
    coord_x: int = Field(default=0)
    coord_z: int = Field(default=0)
    world: str = Field(default="tetrago")
    religion: int = Field(default=0)
    parc: int = Field(default=0)

class S2VillesQuartiers(SQLModel, table=True):
    __tablename__ = "s2-villes_quartiers"
    quartierid: int | None = Field(default=None, primary_key=True)
    villeid: int
    name: str
    short_desc: str | None = Field(default=None)
    coord_x: int = Field(default=0)
    coord_z: int = Field(default=0)
    flag_link: str | None = Field(default=None)
    religion: int = Field(default=0)
    parc: int = Field(default=0)

class S2ZonesCommerciale(SQLModel, table=True):
    __tablename__ = "s2-zones_commerciale"
    zcid: int | None = Field(default=None, primary_key=True)
    ownerid: int
    name: str
    short_desc: str | None = Field(default=None)
    coord_x: int = Field(default=0)
    coord_z: int = Field(default=0)
