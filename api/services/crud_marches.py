"""
Jours de marché et foires.

- Jours de marché : chaque zone commerciale (cartographie de type "commerciale", type_id = ville) peut afficher ses
  jours d'ouverture, en jours de la semaine réelle (le serveur se joue en temps réel), et des horaires libres.
- Foires : une ville annonce une foire datée (jours réels), dans l'une de ses zones commerciales ou à défaut en son
  centre. Elle apparaît sur la fiche de la ville, la page des commerces et la vue Commerces de la carte, et elle est
  annoncée dans le salon Discord `platforms.discord.channels.marches` (création, report, annulation).
- Droits : ceux du tracé des zones commerciales (Fondateur ou Admin de la civilisation de la ville, administrateur),
  voir crud.check_cartographie_authorisation.
- Une ville privée ne montre ni ses jours ni ses foires au public.
"""
import datetime as dt
import json

from fastapi import HTTPException
from sqlmodel import Session, select

from ..core import utils
from ..db import models, schemas
from .crud import announce_discord, check_cartographie_authorisation, get_cartographie_by_id, get_ville_by_id

JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")
DUREE_MAX_JOURS = 31


#region Outils

def _date_texte(date: dt.date) -> str:
    return f"{JOURS[date.weekday()]} {date.day}{'er' if date.day == 1 else ''} {MOIS[date.month - 1]} {date.year}"

def _periode_texte(foire: models.Foires) -> str:
    if foire.date_debut == foire.date_fin:
        return f"le {_date_texte(foire.date_debut)}"
    return f"du {_date_texte(foire.date_debut)} au {_date_texte(foire.date_fin)}"

def _centre(zone: models.Cartographie):
    # Centre (moyenne des sommets) d'un polygone stocké en [[-z, x], …] ; None si illisible
    try:
        sommets = json.loads(zone.coordinates or "")
        return round(sum(s[1] for s in sommets) / len(sommets)), round(-sum(s[0] for s in sommets) / len(sommets))
    except (TypeError, ValueError, ZeroDivisionError, IndexError, KeyError):
        return None

def _ville_publique(db_ville: models.Villes | None) -> bool:
    return bool(db_ville) and db_ville.is_public is not False

def _lien_ville(db_ville: models.Villes) -> str | None:
    site = ((utils.PLATFORMS or {}).get("discord") or {}).get("site_url")
    return f"{str(site).rstrip('/')}/civilisation/{db_ville.civilisation_id}/ville/{db_ville.id}#marches" if site else None

def _annoncer(db_ville: models.Villes, texte: str):
    # Salon Discord « marches » ; rien pour une ville privée
    if not _ville_publique(db_ville):
        return
    lien = _lien_ville(db_ville)
    announce_discord("marches", f"{texte}\n{lien}" if lien else texte)

def jours_infos(marche: models.MarcheJours):
    jours = sorted(int(j) for j in marche.jours.split(",") if j.strip().isdigit())
    return {"cartographie_id": marche.cartographie_id, "jours": jours, "horaires": marche.horaires, "updated_at": marche.updated_at}

def foire_infos(db: Session, foire: models.Foires, db_ville: models.Villes | None = None):
    db_ville = db_ville or get_ville_by_id(db, foire.ville_id)
    zone = get_cartographie_by_id(db, foire.zone_id) if foire.zone_id else None
    return {
        "id": foire.id,
        "title": foire.title,
        "description": foire.description,
        "date_debut": foire.date_debut,
        "date_fin": foire.date_fin,
        "horaires": foire.horaires,
        "dimension_id": foire.dimension_id,
        "x": foire.x,
        "z": foire.z,
        "zone": {"id": zone.id, "title": zone.title} if zone else None,
        "ville": {"id": db_ville.id, "title": db_ville.title, "civilisation_id": db_ville.civilisation_id} if db_ville else None,
        "created_at": foire.created_at,
    }

def _zones_commerciales(db: Session, villeID: int | None = None):
    statement = select(models.Cartographie).where(models.Cartographie.type == "commerciale")
    if villeID is not None:
        statement = statement.where(models.Cartographie.type_id == villeID)
    return db.exec(statement).all()

def _jours_des_zones(db: Session, zones):
    ids = [zone.id for zone in zones]
    if not ids:
        return []
    statement = select(models.MarcheJours).where(models.MarcheJours.cartographie_id.in_(ids))
    return [jours_infos(marche) for marche in db.exec(statement).all()]

#endregion
#region Lecture

def marches_ville(db: Session, villeID: int):
    # { jours: [{ cartographie_id, jours, horaires }], a_venir: [foire], passees: [foire] (les 5 dernières) }
    db_ville = get_ville_by_id(db, villeID)
    if not db_ville:
        raise HTTPException(status_code=404, detail="La ville n'existe pas")
    today = dt.date.today()
    foires = db.exec(select(models.Foires).where(models.Foires.ville_id == villeID)).all()
    a_venir = sorted((f for f in foires if f.date_fin >= today), key=lambda f: f.date_debut)
    passees = sorted((f for f in foires if f.date_fin < today), key=lambda f: f.date_debut, reverse=True)[:5]
    return {
        "jours": _jours_des_zones(db, _zones_commerciales(db, villeID)),
        "a_venir": [foire_infos(db, f, db_ville) for f in a_venir],
        "passees": [foire_infos(db, f, db_ville) for f in passees],
    }

def marches_publics(db: Session):
    # Page des commerces et carte : jours des zones des villes publiques, foires à venir (ou en cours) de ces villes
    villes = {}
    def ville(ID):
        if ID not in villes:
            villes[ID] = get_ville_by_id(db, ID)
        return villes[ID]

    zones = [zone for zone in _zones_commerciales(db) if _ville_publique(ville(zone.type_id))]
    today = dt.date.today()
    foires = db.exec(select(models.Foires).where(models.Foires.date_fin >= today)).all()
    return {
        "jours": _jours_des_zones(db, zones),
        "foires": [foire_infos(db, f, ville(f.ville_id)) for f in sorted(foires, key=lambda f: f.date_debut) if _ville_publique(ville(f.ville_id))],
    }

#endregion
#region Jours de marché

def _require_zone(db: Session, cartographieID: int) -> models.Cartographie:
    zone = get_cartographie_by_id(db, cartographieID)
    if not zone or zone.type != "commerciale":
        raise HTTPException(status_code=404, detail="Cette zone commerciale n'existe pas")
    return zone

def set_jours(db: Session, user: schemas.Users, cartographieID: int, body: schemas.MarcheJoursUpdate):
    zone = _require_zone(db, cartographieID)
    check_cartographie_authorisation(db, user, "commerciale", zone.type_id)
    if any(jour not in range(7) for jour in body.jours):
        raise HTTPException(status_code=400, detail="Les jours vont de 0 (lundi) à 6 (dimanche)")
    marche = db.exec(select(models.MarcheJours).where(models.MarcheJours.cartographie_id == zone.id)).first()
    marche = marche or models.MarcheJours(cartographie_id=zone.id)
    marche.jours = ",".join(str(jour) for jour in sorted(set(body.jours)))
    marche.horaires = (body.horaires or "").strip() or None
    marche.updated_at = dt.datetime.now()
    db.add(marche)
    db.commit()
    db.refresh(marche)
    return jours_infos(marche)

def supprimer_jours_zone(db: Session, cartographieID: int):
    # Nettoyage à la suppression de la zone ; le commit reste à l'appelant
    for marche in db.exec(select(models.MarcheJours).where(models.MarcheJours.cartographie_id == cartographieID)).all():
        db.delete(marche)

#endregion
#region Foires

def _placer(db: Session, foire: models.Foires, db_ville: models.Villes):
    # Dans sa zone commerciale (qui doit appartenir à la ville), sinon au centre de la ville
    if foire.zone_id:
        zone = _require_zone(db, foire.zone_id)
        if zone.type_id != db_ville.id:
            raise HTTPException(status_code=400, detail="Cette zone commerciale n'appartient pas à la ville")
        centre = _centre(zone)
        foire.dimension_id = zone.dimension_id
        foire.x, foire.z = centre if centre else (db_ville.x, db_ville.z)
    else:
        foire.dimension_id, foire.x, foire.z = db_ville.dimension_id, db_ville.x, db_ville.z

def _valider_dates(foire: models.Foires, nouvelle: bool):
    if foire.date_fin < foire.date_debut:
        raise HTTPException(status_code=400, detail="La foire ne peut pas finir avant de commencer")
    if (foire.date_fin - foire.date_debut).days >= DUREE_MAX_JOURS:
        raise HTTPException(status_code=400, detail=f"Une foire dure au plus {DUREE_MAX_JOURS} jours")
    if nouvelle and foire.date_fin < dt.date.today():
        raise HTTPException(status_code=400, detail="Une foire s'annonce avant d'avoir eu lieu")

def create_foire(db: Session, user: schemas.Users, body: schemas.FoireCreate):
    db_ville = get_ville_by_id(db, body.ville_id)
    if not db_ville:
        raise HTTPException(status_code=404, detail="La ville n'existe pas")
    check_cartographie_authorisation(db, user, "commerciale", db_ville.id)
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Une foire doit avoir un nom")
    foire = models.Foires(
        ville_id=db_ville.id,
        title=title,
        description=(body.description or "").strip() or None,
        date_debut=body.date_debut,
        date_fin=body.date_fin or body.date_debut,
        horaires=(body.horaires or "").strip() or None,
        zone_id=body.zone_id,
        created_by=user.id,
    )
    _valider_dates(foire, nouvelle=True)
    _placer(db, foire, db_ville)
    db.add(foire)
    db.commit()
    db.refresh(foire)
    lieu = f" ({get_cartographie_by_id(db, foire.zone_id).title})" if foire.zone_id else ""
    _annoncer(db_ville, f"🎪 **{foire.title}** : foire à {db_ville.title}{lieu}, {_periode_texte(foire)}{f', {foire.horaires}' if foire.horaires else ''}.")
    return foire_infos(db, foire, db_ville)

def _require_foire(db: Session, user: schemas.Users, ID: int):
    foire = db.get(models.Foires, ID)
    if not foire:
        raise HTTPException(status_code=404, detail="Cette foire n'existe pas")
    check_cartographie_authorisation(db, user, "commerciale", foire.ville_id)
    return foire, get_ville_by_id(db, foire.ville_id)

def update_foire(db: Session, user: schemas.Users, ID: int, body: schemas.FoireUpdate):
    foire, db_ville = _require_foire(db, user, ID)
    data = body.model_dump(exclude_unset=True)
    for key in ("title", "date_debut"):
        if data.get(key) is None:
            data.pop(key, None)
    if "title" in data:
        data["title"] = data["title"].strip()
        if not data["title"]:
            raise HTTPException(status_code=400, detail="Une foire doit avoir un nom")
    for key in ("description", "horaires"):
        if key in data:
            data[key] = (data[key] or "").strip() or None
    avant = (foire.date_debut, foire.date_fin)
    for key, value in data.items():
        setattr(foire, key, value)
    if foire.date_fin is None or ("date_debut" in data and "date_fin" not in data and foire.date_fin < foire.date_debut):
        foire.date_fin = foire.date_debut
    _valider_dates(foire, nouvelle=False)
    _placer(db, foire, db_ville)
    db.add(foire)
    db.commit()
    db.refresh(foire)
    if (foire.date_debut, foire.date_fin) != avant and foire.date_fin >= dt.date.today():
        _annoncer(db_ville, f"🎪 **{foire.title}** à {db_ville.title} change de dates : {_periode_texte(foire)}.")
    return foire_infos(db, foire, db_ville)

def delete_foire(db: Session, user: schemas.Users, ID: int):
    foire, db_ville = _require_foire(db, user, ID)
    if foire.date_fin >= dt.date.today():
        _annoncer(db_ville, f"🎪 **{foire.title}** à {db_ville.title} ({_periode_texte(foire)}) est annulée.")
    db.delete(foire)
    db.commit()
    return True

def detacher_zone(db: Session, cartographieID: int):
    # Suppression de la zone commerciale : ses foires restent, au centre de leur ville ; le commit reste à l'appelant
    for foire in db.exec(select(models.Foires).where(models.Foires.zone_id == cartographieID)).all():
        db_ville = get_ville_by_id(db, foire.ville_id)
        foire.zone_id = None
        if db_ville:
            foire.dimension_id, foire.x, foire.z = db_ville.dimension_id, db_ville.x, db_ville.z
        db.add(foire)

def supprimer_foires_ville(db: Session, villeID: int):
    # Nettoyage à la suppression de la ville ; le commit reste à l'appelant
    for foire in db.exec(select(models.Foires).where(models.Foires.ville_id == villeID)).all():
        db.delete(foire)

#endregion
