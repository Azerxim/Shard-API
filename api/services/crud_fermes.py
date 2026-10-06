"""
Déclaration des fermes (Codex, « Fermes & ressources ») : sur le site plutôt que par ticket Discord.

- Un joueur déclare sa ferme : position, ce qu'elle produit, justification RP, bâtiment qui l'habille, photo.
- Un modérateur RP la valide, ou demande une mise en conformité (note obligatoire). Il ne décide jamais sur sa propre
  ferme. Une ferme modifiée par son déclarant repasse en attente ; un modérateur peut aussi rouvrir une ferme validée
  en demandant une mise en conformité.
- Visibilité : le déclarant et les modérateurs RP (et administrateurs) seulement — une ferme est une position de jeu.
- Photo : PNG, JPEG ou WebP de 5 Mo au plus, rangée dans ./uploads/fermes (voir services/fichiers.py) et servie par
  /api/fermes/photo/{nom}.
- Chaque nouvelle déclaration (ou déclaration corrigée) est signalée dans le salon Discord
  `platforms.discord.channels.fermes`, s'il est configuré.
"""
import datetime as dt

from fastapi import HTTPException
from sqlmodel import Session, select

from ..core import utils
from ..db import models, schemas
from .crud import announce_discord, get_dimension_by_id, get_ville_by_id
from .crud_conflits import _require_moderateur, _user_summary, is_moderateur
from . import crud_notifications, fichiers

TYPES = ("cultures", "elevage", "mobs", "ressources", "automatique", "autre")
STATUTS = ("en_attente", "validee", "a_corriger")
PHOTO_DOSSIER = "fermes"
PHOTO_MAX_OCTETS = fichiers.MAX_OCTETS


#region Outils

def ferme_infos(db: Session, ferme: models.Fermes):
    db_ville = get_ville_by_id(db, ferme.ville_id) if ferme.ville_id else None
    db_dimension = get_dimension_by_id(db, ferme.dimension_id) if ferme.dimension_id else None
    return {
        "id": ferme.id,
        "title": ferme.title,
        "type": ferme.type,
        "production": ferme.production,
        "justification": ferme.justification,
        "habillage": ferme.habillage,
        "dimension": {"id": db_dimension.id, "title": db_dimension.title, "link": db_dimension.link} if db_dimension else None,
        "x": ferme.x,
        "y": ferme.y,
        "z": ferme.z,
        "ville": {"id": db_ville.id, "title": db_ville.title, "civilisation_id": db_ville.civilisation_id} if db_ville else None,
        "photo": ferme.photo,
        "status": ferme.status,
        "declarant": _user_summary(db, ferme.user_id),
        "moderateur": _user_summary(db, ferme.moderateur_id),
        "decision_note": ferme.decision_note,
        "decision_at": ferme.decision_at,
        "created_at": ferme.created_at,
        "updated_at": ferme.updated_at,
    }

def _valider(db: Session, type_: str | None, dimension_id: int | None, ville_id: int | None):
    if type_ is not None and type_ not in TYPES:
        raise HTTPException(status_code=400, detail=f"Type de ferme inconnu : {type_}")
    if dimension_id is not None and not get_dimension_by_id(db, dimension_id):
        raise HTTPException(status_code=404, detail="La dimension n'existe pas")
    if ville_id is not None and not get_ville_by_id(db, ville_id):
        raise HTTPException(status_code=404, detail="La ville n'existe pas")

def _texte(valeur: str | None) -> str | None:
    return (valeur or "").strip() or None

def _signaler(db: Session, ferme: models.Fermes, texte: str):
    # Salon des modérateurs ; le lien mène à la file de validation
    site = ((utils.PLATFORMS or {}).get("discord") or {}).get("site_url")
    declarant = _user_summary(db, ferme.user_id)
    nom = (declarant or {}).get("full_name") or (declarant or {}).get("username") or "un joueur"
    lien = f"\n{str(site).rstrip('/')}/fermes#ferme-{ferme.id}" if site else ""
    announce_discord("fermes", f"🌾 {texte} : **{ferme.title}** ({nom}), X {ferme.x} · Z {ferme.z}.{lien}")
    crud_notifications.notifier(db, crud_notifications.moderateurs(db), "moderation", f"{texte} : {ferme.title}", f"Déclarée par {nom}.", f"/fermes#ferme-{ferme.id}", sauf=ferme.user_id)

#endregion
#region Lecture

def _require_ferme(db: Session, user: schemas.Users, ID: int) -> models.Fermes:
    # Le déclarant et les modérateurs RP lisent, modifient et suppriment ; pour les autres, la ferme n'existe pas
    ferme = db.get(models.Fermes, ID)
    if not ferme or not (ferme.user_id == user.id or is_moderateur(user)):
        raise HTTPException(status_code=404, detail="Cette ferme n'existe pas")
    return ferme

def mes_fermes(db: Session, user: schemas.Users):
    statement = select(models.Fermes).where(models.Fermes.user_id == user.id).order_by(models.Fermes.created_at.desc())
    return [ferme_infos(db, ferme) for ferme in db.exec(statement).all()]

def toutes_les_fermes(db: Session, user: schemas.Users, status: str | None = None):
    # Modérateurs : la file (en attente d'abord, de la plus ancienne à la plus récente), puis le reste
    _require_moderateur(user)
    if status is not None and status not in STATUTS:
        raise HTTPException(status_code=400, detail=f"Statut inconnu : {status}")
    statement = select(models.Fermes)
    if status:
        statement = statement.where(models.Fermes.status == status)
    rang = {"en_attente": 0, "a_corriger": 1, "validee": 2}
    fermes = sorted(db.exec(statement).all(), key=lambda f: (rang.get(f.status, 3), f.updated_at))
    return [ferme_infos(db, ferme) for ferme in fermes]

def read_ferme(db: Session, user: schemas.Users, ID: int):
    return ferme_infos(db, _require_ferme(db, user, ID))

#endregion
#region Déclaration

def declarer(db: Session, user: schemas.Users, body: schemas.FermeCreate):
    if user.is_disabled:
        raise HTTPException(status_code=403, detail="Accès refusé")
    title, justification = _texte(body.title), _texte(body.justification)
    if not title:
        raise HTTPException(status_code=400, detail="Donnez un nom à la ferme")
    if not justification:
        raise HTTPException(status_code=400, detail="Une ferme se déclare avec sa justification RP")
    _valider(db, body.type or "autre", body.dimension_id, body.ville_id)
    ferme = models.Fermes(
        user_id=user.id, title=title, type=body.type or "autre", production=_texte(body.production),
        justification=justification, habillage=_texte(body.habillage), dimension_id=body.dimension_id,
        x=body.x, y=body.y, z=body.z, ville_id=body.ville_id,
    )
    db.add(ferme)
    db.commit()
    db.refresh(ferme)
    _signaler(db, ferme, "Nouvelle ferme à valider")
    return ferme_infos(db, ferme)

def modifier(db: Session, user: schemas.Users, ID: int, body: schemas.FermeUpdate):
    ferme = _require_ferme(db, user, ID)
    data = body.model_dump(exclude_unset=True)
    for key in ("title", "type", "justification", "x", "z"):
        if data.get(key) is None:
            data.pop(key, None)
    for key in ("title", "justification", "production", "habillage"):
        if key in data:
            data[key] = _texte(data[key])
    if "title" in data and not data["title"]:
        raise HTTPException(status_code=400, detail="Donnez un nom à la ferme")
    if "justification" in data and not data["justification"]:
        raise HTTPException(status_code=400, detail="Une ferme se déclare avec sa justification RP")
    _valider(db, data.get("type"), data.get("dimension_id"), data.get("ville_id"))
    for key, value in data.items():
        setattr(ferme, key, value)
    _apres_modification(db, user, ferme)
    return ferme_infos(db, ferme)

def _apres_modification(db: Session, user: schemas.Users, ferme: models.Fermes):
    # Une ferme retouchée par son déclarant repasse en attente : le modérateur doit revoir ce qui a changé
    rouverte = ferme.user_id == user.id and ferme.status != "en_attente"
    if rouverte:
        ferme.status = "en_attente"
    ferme.updated_at = dt.datetime.now()
    db.add(ferme)
    db.commit()
    db.refresh(ferme)
    if rouverte:
        _signaler(db, ferme, "Ferme modifiée, à revoir")

def supprimer(db: Session, user: schemas.Users, ID: int):
    ferme = _require_ferme(db, user, ID)
    _supprimer_photo(ferme.photo)
    db.delete(ferme)
    db.commit()
    return True

def decider(db: Session, user: schemas.Users, ID: int, body: schemas.FermeDecision):
    _require_moderateur(user)
    ferme = _require_ferme(db, user, ID)
    if ferme.user_id == user.id:
        raise HTTPException(status_code=403, detail="Un modérateur ne valide pas sa propre ferme")
    if body.status not in ("validee", "a_corriger"):
        raise HTTPException(status_code=400, detail="Décision : validee ou a_corriger")
    note = _texte(body.note)
    if body.status == "a_corriger" and not note:
        raise HTTPException(status_code=400, detail="Dites ce qu'il faut mettre en conformité")
    ferme.status = body.status
    ferme.moderateur_id = user.id
    ferme.decision_note = note
    ferme.decision_at = dt.datetime.now()
    db.add(ferme)
    db.commit()
    db.refresh(ferme)
    title = f"Ferme validée : {ferme.title}" if ferme.status == "validee" else f"Ferme à corriger : {ferme.title}"
    crud_notifications.notifier(db, {ferme.user_id}, "decision", title, note, f"/fermes#ferme-{ferme.id}", sauf=user.id)
    return ferme_infos(db, ferme)

#endregion
#region Photo

def _supprimer_photo(nom: str | None):
    fichiers.supprimer(PHOTO_DOSSIER, nom)

def chemin_photo(nom: str) -> str:
    return fichiers.chemin(PHOTO_DOSSIER, nom)

def enregistrer_photo(db: Session, user: schemas.Users, ID: int, contenu: bytes):
    ferme = _require_ferme(db, user, ID)
    nom = fichiers.enregistrer(PHOTO_DOSSIER, contenu, libelle="La photo")
    _supprimer_photo(ferme.photo)
    ferme.photo = nom
    _apres_modification(db, user, ferme)
    return ferme_infos(db, ferme)

#endregion
#region Nettoyage

def detacher_ville(db: Session, villeID: int):
    # Suppression de la ville : la ferme reste déclarée, sans ville ; le commit reste à l'appelant
    for ferme in db.exec(select(models.Fermes).where(models.Fermes.ville_id == villeID)).all():
        ferme.ville_id = None
        db.add(ferme)

def supprimer_fermes_utilisateur(db: Session, userID: int):
    for ferme in db.exec(select(models.Fermes).where(models.Fermes.user_id == userID)).all():
        _supprimer_photo(ferme.photo)
        db.delete(ferme)

#endregion
