"""Statistiques du monde Minecraft : relevés envoyés par le générateur de cartes.

Un relevé correspond à une lecture de la sauvegarde (scripts/map-generator/world_stats.py de ShardUI-2-Maps) :
totaux par dimension, mesures rapportées aux villes et quartiers, zones les plus fréquentées et joueurs.
L'API se contente de recevoir, de compléter avec les données du site (comptes liés, populations déclarées,
personnages domiciliés) et de conserver l'historique ; tout le calcul se fait à la lecture du monde.
"""
import datetime as dt
import json
import os
import threading
import urllib.error
import urllib.request

from fastapi import HTTPException
from sqlmodel import Session, select

from ..core import utils
from ..db import models, schemas
from . import crud, crud_personnages
from ..db.database import engine

# Relevés conservés : un par semaine, soit deux ans d'historique
MAX_RELEVES = 104

# Pseudos Minecraft : la sauvegarde ne contient que des UUID, playerdb.co donne le nom et la tête du joueur.
# SHARD_PLAYERDB_URL permet de viser un autre service (tests).
PLAYERDB_URL = os.environ.get("SHARD_PLAYERDB_URL") or "https://playerdb.co/api/player/minecraft"
PLAYERDB_TIMEOUT = 10

ENTITES = ("civilisation", "ville", "quartier")
# Lieux dont la population du site est réécrite à chaque relevé (une civilisation n'a pas de population)
ENTITES_PEUPLEES = {"ville": models.Villes, "quartier": models.Quartiers}


def _uuid_hex(value: str | None) -> str:
    return (value or "").replace("-", "").strip().lower()


def cle_configuree() -> str:
    """Clé partagée du générateur de cartes (platforms.monde.key, ou SHARD_MONDE_KEY pour les tests)."""
    return (os.environ.get("SHARD_MONDE_KEY")
            or str(((utils.PLATFORMS or {}).get("monde") or {}).get("key") or "")).strip()


def verifier_cle(cle: str | None) -> bool:
    attendue = cle_configuree()
    return bool(attendue) and (cle or "").strip() == attendue


def _comptes_minecraft(db: Session):
    """{ uuid Minecraft: (user_id, pseudo) } d'après les comptes Microsoft liés sur le site."""
    comptes = {}
    for platform in db.exec(select(models.UserPlatforms).where(models.UserPlatforms.platform == "microsoft")).all():
        comptes[_uuid_hex(platform.uid)] = (platform.user_id, platform.username)
    return comptes


def _populations_declarees(db: Session):
    populations = {"ville": {}, "quartier": {}, "civilisation": {}}
    for ville in db.exec(select(models.Villes)).all():
        populations["ville"][ville.id] = ville.population
    for quartier in db.exec(select(models.Quartiers)).all():
        populations["quartier"][quartier.id] = quartier.population
    return populations


def _personnages_domicilies(db: Session):
    return {residence: crud_personnages.residents_count(db, residence) for residence in ENTITES}


def _somme(valeurs):
    valeurs = [v for v in valeurs if v is not None]
    return sum(valeurs) if valeurs else 0


# ---------------------------------------------------------------------------
#region Enregistrement

def enregistrer_releve(db: Session, payload: schemas.MondeReleveCreate):
    """Enregistre un relevé complet et renvoie son résumé."""
    releve = models.MondeReleves(
        source=payload.source or "map-generator",
        releve_at=payload.releve_at or dt.datetime.now(),
        world_name=payload.world_name,
        world_version=payload.world_version,
        data_version=payload.data_version,
        duration_seconds=payload.duration_seconds,
        taille_octets=payload.taille_octets,
        seuil_heures_lit=payload.seuil_heures_lit,
        seuil_jours_actif=payload.seuil_jours_actif,
        seuil_heures_actif=payload.seuil_heures_actif,
        taille_tuile=payload.taille_tuile,
    )
    # Totaux recalculés ici : le relevé reste cohérent avec le détail conservé
    releve.chunks = _somme(d.chunks for d in payload.dimensions)
    releve.chunks_actifs = _somme(d.chunks_actifs for d in payload.dimensions)
    releve.heures_presence = round(_somme(d.heures_presence for d in payload.dimensions), 2)
    releve.lits = _somme(d.lits for d in payload.dimensions)
    releve.lits_actifs = _somme(d.lits_actifs for d in payload.dimensions)
    releve.villageois = _somme(d.villageois for d in payload.dimensions)
    releve.entites = _somme(d.entites for d in payload.dimensions)
    releve.joueurs = len(payload.joueurs)
    releve.joueurs_actifs = len([j for j in payload.joueurs if j.is_actif])
    releve.heures_jeu = round(_somme(j.heures_jeu for j in payload.joueurs), 2)
    db.add(releve)
    db.commit()
    db.refresh(releve)

    for dimension in payload.dimensions:
        db.add(models.MondeDimensionsStats(releve_id=releve.id, **dimension.model_dump()))

    populations = _populations_declarees(db)
    personnages = _personnages_domicilies(db)
    for lieu in payload.lieux:
        if lieu.entity_type not in ENTITES:
            continue
        db.add(models.MondeLieux(
            releve_id=releve.id,
            population_declaree=populations.get(lieu.entity_type, {}).get(lieu.entity_id),
            personnages=personnages.get(lieu.entity_type, {}).get(lieu.entity_id, 0),
            **lieu.model_dump(),
        ))

    for rang, zone in enumerate(payload.zones, start=1):
        valeurs = zone.model_dump()
        valeurs["rang"] = valeurs.get("rang") or rang
        db.add(models.MondeZones(releve_id=releve.id, **valeurs))

    comptes = _comptes_minecraft(db)
    for joueur in payload.joueurs:
        valeurs = joueur.model_dump()
        user_id, pseudo = comptes.get(_uuid_hex(joueur.uuid), (None, None))
        valeurs["pseudo"] = valeurs.get("pseudo") or pseudo
        db.add(models.MondeJoueurs(releve_id=releve.id, user_id=user_id, **valeurs))

    db.commit()
    populations_appliquees = _appliquer_populations(db, payload)
    supprimes = _purger_anciens_releves(db)
    db.refresh(releve)  # le commit périme l'objet : le relire avant de le renvoyer
    resoudre_pseudos_en_fond(releve.id)
    return {"releve": releve, "supprimes": supprimes, "populations": populations_appliquees}


def _appliquer_populations(db: Session, payload: schemas.MondeReleveCreate):
    """Écrit la population mesurée dans les villes et les quartiers du site.

    Seuls les lieux d'une dimension réellement lue sont touchés : une dimension absente de la sauvegarde
    ne doit pas remettre ses villes à zéro. La valeur précédente reste consultable dans le relevé
    (MondeLieux.population_declaree).
    """
    sources_lues = {dimension.source for dimension in payload.dimensions if dimension.source is not None}
    modifies = {"villes": 0, "quartiers": 0}
    for lieu in payload.lieux:
        table = ENTITES_PEUPLEES.get(lieu.entity_type)
        if table is None or lieu.population is None or lieu.source is None or lieu.source not in sources_lues:
            continue
        entite = db.get(table, lieu.entity_id)
        if entite is None or entite.population == lieu.population:
            continue
        entite.population = lieu.population
        db.add(entite)
        modifies["villes" if lieu.entity_type == "ville" else "quartiers"] += 1
    if modifies["villes"] or modifies["quartiers"]:
        db.commit()
    return modifies


def _purger_anciens_releves(db: Session):
    """Ne conserve que les MAX_RELEVES derniers relevés."""
    anciens = db.exec(
        select(models.MondeReleves).order_by(models.MondeReleves.id.desc()).offset(MAX_RELEVES)
    ).all()
    for releve in anciens:
        _supprimer(db, releve)
    if anciens:
        db.commit()
    return len(anciens)


def _supprimer(db: Session, releve: models.MondeReleves):
    for table in (models.MondeDimensionsStats, models.MondeLieux, models.MondeZones, models.MondeJoueurs):
        for ligne in db.exec(select(table).where(table.releve_id == releve.id)).all():
            db.delete(ligne)
    db.delete(releve)


def supprimer_releve(db: Session, releve_id: int):
    releve = db.get(models.MondeReleves, releve_id)
    if not releve:
        raise HTTPException(status_code=404, detail="Relevé introuvable")
    _supprimer(db, releve)
    db.commit()
    return {"text": "Le relevé a été supprimé"}

#endregion
# ---------------------------------------------------------------------------
#region Pseudos Minecraft

def _profil_playerdb(uuid: str):
    """(pseudo, adresse de la tête) d'après playerdb.co, ou None si le joueur est inconnu."""
    requete = urllib.request.Request(f"{PLAYERDB_URL}/{uuid}", headers={"User-Agent": "Tetrago/Shard-API"})
    try:
        with urllib.request.urlopen(requete, timeout=PLAYERDB_TIMEOUT) as reponse:
            joueur = (json.loads(reponse.read().decode("utf-8")).get("data") or {}).get("player") or {}
    except (urllib.error.URLError, ValueError, OSError):
        return None
    return (joueur.get("username"), joueur.get("avatar")) if joueur.get("username") else None


def resoudre_pseudos(db: Session, releve_id: int | None = None, limite: int = 200):
    """Complète les joueurs sans pseudo d'un relevé, et reporte le nom trouvé sur tous les relevés.

    Un joueur dont le compte Minecraft est lié au site a déjà son pseudo : seuls les autres sont cherchés.
    """
    releve = _releve_ou_dernier(db, releve_id)
    inconnus = []
    for joueur in _lignes(db, models.MondeJoueurs, releve.id, models.MondeJoueurs.heures_jeu.desc()):
        if not joueur.pseudo and joueur.uuid not in inconnus:
            inconnus.append(joueur.uuid)
    resultat = {"cherches": 0, "trouves": 0}
    for uuid in inconnus[:limite]:
        resultat["cherches"] += 1
        profil = _profil_playerdb(uuid)
        if not profil:
            continue
        pseudo, avatar = profil
        for ligne in db.exec(select(models.MondeJoueurs).where(models.MondeJoueurs.uuid == uuid)).all():
            ligne.pseudo = ligne.pseudo or pseudo
            ligne.avatar_url = ligne.avatar_url or avatar
            db.add(ligne)
        resultat["trouves"] += 1
    if resultat["trouves"]:
        db.commit()
    return {**resultat, "releve_id": releve.id, "manquants": max(0, len(inconnus) - limite)}


def resoudre_pseudos_en_fond(releve_id: int):
    """Même travail, hors de la requête : l'envoi du relevé n'attend pas playerdb.co."""
    def chercher():
        with Session(engine) as db:
            try:
                resultat = resoudre_pseudos(db, releve_id)
                print(f"Pseudos Minecraft du relevé {releve_id} : {resultat['trouves']}/{resultat['cherches']} trouvés")
            except Exception as erreur:  # un service indisponible ne doit pas laisser de trace d'erreur bloquante
                print(f"Pseudos Minecraft du relevé {releve_id} impossibles : {erreur}")

    threading.Thread(target=chercher, daemon=True).start()

#endregion
# ---------------------------------------------------------------------------
#region Lecture

def liste_releves(db: Session, limit: int = 50):
    return db.exec(select(models.MondeReleves).order_by(models.MondeReleves.id.desc()).limit(limit)).all()


def dernier_releve(db: Session):
    return db.exec(select(models.MondeReleves).order_by(models.MondeReleves.id.desc())).first()


def _releve_ou_dernier(db: Session, releve_id: int | None):
    releve = db.get(models.MondeReleves, releve_id) if releve_id else dernier_releve(db)
    if not releve:
        raise HTTPException(status_code=404, detail="Aucun relevé du monde n'a encore été enregistré")
    return releve


def _lignes(db: Session, table, releve_id: int, tri=None, limit: int | None = None):
    statement = select(table).where(table.releve_id == releve_id)
    if tri is not None:
        statement = statement.order_by(tri)
    if limit:
        statement = statement.limit(limit)
    return db.exec(statement).all()


def joueurs(db: Session, releve_id: int | None = None, actifs_seulement: bool = False, limit: int = 500):
    """Joueurs d'un relevé, les plus présents d'abord, avec le compte du site quand il est lié."""
    releve = _releve_ou_dernier(db, releve_id)
    lignes = _lignes(db, models.MondeJoueurs, releve.id, models.MondeJoueurs.heures_jeu.desc(), limit)
    resultat = []
    for joueur in lignes:
        if actifs_seulement and not joueur.is_actif:
            continue
        user = crud.get_user_by_id(db, joueur.user_id) if joueur.user_id else None
        resultat.append({
            **joueur.model_dump(),
            "utilisateur": {"id": user.id, "full_name": user.full_name, "username": user.username} if user else None,
        })
    return {"releve": releve, "joueurs": resultat}


def zones(db: Session, releve_id: int | None = None, limit: int = 50):
    """Zones les plus fréquentées du relevé."""
    releve = _releve_ou_dernier(db, releve_id)
    return {"releve": releve, "zones": _lignes(db, models.MondeZones, releve.id, models.MondeZones.rang, limit)}


def _lieu_infos(db: Session, lieu: models.MondeLieux):
    entite = None
    if lieu.entity_type == "ville":
        entite = crud.get_ville_by_id(db, lieu.entity_id)
    elif lieu.entity_type == "quartier":
        entite = crud.get_quartier_by_id(db, lieu.entity_id)
    elif lieu.entity_type == "civilisation":
        entite = crud.get_civilisation_by_id(db, lieu.entity_id)
    return {**lieu.model_dump(), "titre_actuel": entite.title if entite else None, "supprime": entite is None}


def lieux(db: Session, releve_id: int | None = None):
    """Mesures par ville, quartier et civilisation, les plus fréquentés d'abord."""
    releve = _releve_ou_dernier(db, releve_id)
    lignes = _lignes(db, models.MondeLieux, releve.id, models.MondeLieux.heures_presence.desc())
    return {"releve": releve, "lieux": [_lieu_infos(db, lieu) for lieu in lignes]}


def historique_lieu(db: Session, entity_type: str, entity_id: int, limit: int = 52):
    """Évolution d'un lieu relevé après relevé (le plus récent en premier)."""
    if entity_type not in ENTITES:
        raise HTTPException(status_code=404, detail="Type de lieu inconnu")
    lignes = db.exec(
        select(models.MondeLieux, models.MondeReleves)
        .where(models.MondeLieux.entity_type == entity_type, models.MondeLieux.entity_id == entity_id)
        .where(models.MondeReleves.id == models.MondeLieux.releve_id)
        .order_by(models.MondeLieux.releve_id.desc())
        .limit(limit)
    ).all()
    return [{**lieu.model_dump(), "releve_at": releve.releve_at, "created_at": releve.created_at}
            for lieu, releve in lignes]


def resume(db: Session, releve_id: int | None = None, zones_limit: int = 20, joueurs_limit: int = 200):
    """Tableau de bord : dernier relevé, évolution depuis le précédent et détail complet."""
    releve = _releve_ou_dernier(db, releve_id)
    precedent = db.exec(
        select(models.MondeReleves).where(models.MondeReleves.id < releve.id).order_by(models.MondeReleves.id.desc())
    ).first()
    evolution = {}
    if precedent:
        for champ in ("chunks", "chunks_actifs", "heures_presence", "lits", "lits_actifs", "villageois",
                      "joueurs", "joueurs_actifs", "heures_jeu"):
            ancien, nouveau = getattr(precedent, champ), getattr(releve, champ)
            if ancien is not None and nouveau is not None:
                evolution[champ] = round(nouveau - ancien, 2)
    return {
        "releve": releve,
        "precedent": precedent,
        "evolution": evolution,
        "dimensions": _lignes(db, models.MondeDimensionsStats, releve.id, models.MondeDimensionsStats.id),
        "lieux": lieux(db, releve.id)["lieux"],
        "zones": zones(db, releve.id, zones_limit)["zones"],
        "joueurs": joueurs(db, releve.id, limit=joueurs_limit)["joueurs"],
        "releves": liste_releves(db, 52),
    }

#endregion
