"""
Chroniques de Tetrago : frise de l'histoire du monde, remplie toute seule à partir des données du site.

- Fondations des civilisations, villes, religions et commerces publics ; alliances conclues ; débuts et fins des
  guerres validées, batailles, sièges et traités de leur chronologie ; lignées : fondation des maisons nobles,
  naissances et morts de leurs membres, mariages (crud_lignees).
- Les modérateurs RP y ajoutent des faits marquants (table chroniquesfaits) : ce que les données ne disent pas.
- Rien de privé : entités publiques, guerres validées seulement.
- La frise se lit en dates RP (date de fondation, dates de la guerre, date d'un fait raconté…), la plus récente
  d'abord. Ce qui n'a pas de date RP n'y figure pas : révélations d'actions secrètes, adhésions aux alliances et
  événements du calendrier (datés en heure réelle seulement), fondations et faits racontés sans date.
"""
import datetime as dt

from fastapi import HTTPException
from sqlmodel import Session, select

from ..db import models, schemas
from . import crud_conflits, crud_lignees

CATEGORIES = ("fondations", "diplomatie", "guerres", "lignees", "faits")
TITLE_MAX = 120


def _public(entite) -> bool:
    return bool(entite) and entite.is_public is not False

def _entree(cle: str, categorie: str, date, title: str, lien: str | None = None, description: str | None = None, date_rp=None, **extra):
    if isinstance(date, dt.date) and not isinstance(date, dt.datetime):
        date = dt.datetime.combine(date, dt.time.min)
    if isinstance(date_rp, dt.datetime):
        date_rp = date_rp.date()
    return {"id": cle, "categorie": categorie, "date": date, "date_rp": date_rp, "title": title, "description": description, "lien": lien, **extra}

#region Sources

def _fondations(db: Session):
    entrees = []
    civilisations = {c.id: c for c in db.exec(select(models.Civilisations)).all()}
    for civ in civilisations.values():
        if _public(civ) and civ.created_at:
            entrees.append(_entree(f"civilisation-{civ.id}", "fondations", civ.created_at, f"Fondation : {civ.title}", f"/civilisation/{civ.id}",
                                   "Civilisation", civ.date_founded))
    for ville in db.exec(select(models.Villes)).all():
        civ = civilisations.get(ville.civilisation_id)
        if _public(ville) and _public(civ) and ville.created_at:
            nature = "Capitale" if ville.is_capital else "Ville"
            entrees.append(_entree(f"ville-{ville.id}", "fondations", ville.created_at, f"Fondation : {ville.title}",
                                   f"/civilisation/{civ.id}/ville/{ville.id}", f"{nature} de {civ.title}", ville.founded_date))
    for religion in db.exec(select(models.Religions)).all():
        if _public(religion) and religion.created_at:
            entrees.append(_entree(f"religion-{religion.id}", "fondations", religion.created_at, f"Fondation : {religion.title}",
                                   f"/religion/{religion.id}", "Religion", religion.date_founded))
    for commerce in db.exec(select(models.Commerces)).all():
        if _public(commerce) and commerce.created_at:
            entrees.append(_entree(f"commerce-{commerce.id}", "fondations", commerce.created_at, f"Ouverture : {commerce.title}",
                                   f"/commerce/{commerce.id}", "Commerce", commerce.date_founded))
    return entrees

def _alliances(db: Session):
    entrees = []
    for alliance in db.exec(select(models.Alliances)).all():
        if not _public(alliance) or not alliance.created_at:
            continue
        entrees.append(_entree(f"alliance-{alliance.id}", "diplomatie", alliance.created_at, f"Alliance conclue : {alliance.title}", f"/alliance/{alliance.id}",
                               f"Alliance {alliance.type.lower()}", alliance.date_founded))
    return entrees

def _guerres(db: Session):
    entrees = []
    for guerre in db.exec(select(models.Guerres).where(models.Guerres.status.in_(crud_conflits.GUERRE_STATUTS_PUBLICS))).all():
        lien = f"/guerre/{guerre.id}"
        attaquant, defenseur = crud_conflits._leaders(db, guerre.id)
        entrees.append(_entree(f"guerre-{guerre.id}", "guerres", guerre.validated_at or guerre.declared_at, f"Début de la guerre « {guerre.title} »", lien,
                               f"{attaquant} contre {defenseur}", guerre.date_debut))
        if guerre.status == "terminee" and guerre.ended_at:
            entrees.append(_entree(f"paix-{guerre.id}", "guerres", guerre.ended_at, f"Fin de la guerre « {guerre.title} »", lien,
                                   guerre.issue, guerre.date_fin))
        for evenement in crud_conflits._evenements(db, guerre.id):
            if evenement.is_auto or evenement.type not in crud_conflits.EVENEMENTS_RACONTES:
                continue
            nature = crud_conflits.EVENEMENTS_RACONTES[evenement.type]
            entrees.append(_entree(f"guerre-evenement-{evenement.id}", "guerres", evenement.created_at, f"{nature} : {evenement.title}", lien,
                                   f"Guerre « {guerre.title} »", evenement.date_rp))
    return entrees

def _lignees(db: Session):
    return [_entree(e["id"], "lignees", e["date"], e["title"], e["lien"], e["description"], e["date_rp"]) for e in crud_lignees.entrees_chroniques(db)]

def _faits(db: Session):
    return [_fait_infos(fait) for fait in db.exec(select(models.ChroniquesFaits)).all()]

def _fait_infos(fait: models.ChroniquesFaits):
    return _entree(f"fait-{fait.id}", "faits", fait.date, fait.title, None, fait.description, fait.date_rp, fait_id=fait.id)

#endregion
#region Lecture

def chroniques(db: Session):
    # Toute la frise, par date RP, la plus récente d'abord (à date égale, la dernière inscrite d'abord) ;
    # sans date RP, une entrée n'y figure pas
    entrees = _fondations(db) + _alliances(db) + _guerres(db) + _lignees(db) + _faits(db)
    return sorted((e for e in entrees if e["date_rp"]), key=lambda e: (e["date_rp"], e["date"], e["id"]), reverse=True)

#endregion
#region Faits marquants (modérateurs RP)

def _valider(body: schemas.ChroniqueFait):
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Donnez un titre au fait marquant")
    if len(title) > TITLE_MAX:
        raise HTTPException(status_code=400, detail=f"Le titre ne dépasse pas {TITLE_MAX} caractères")
    return title, (body.description or "").strip() or None

def create_fait(db: Session, user: schemas.Users, body: schemas.ChroniqueFait):
    crud_conflits._require_moderateur(user)
    title, description = _valider(body)
    # date : jour réel de l'inscription, qui départage deux faits de même date RP
    fait = models.ChroniquesFaits(title=title, description=description, date=dt.date.today(), date_rp=body.date_rp, created_by=user.id)
    db.add(fait)
    db.commit()
    db.refresh(fait)
    return _fait_infos(fait)

def _require_fait(db: Session, user: schemas.Users, ID: int) -> models.ChroniquesFaits:
    crud_conflits._require_moderateur(user)
    fait = db.get(models.ChroniquesFaits, ID)
    if not fait:
        raise HTTPException(status_code=404, detail="Ce fait marquant n'existe pas")
    return fait

def update_fait(db: Session, user: schemas.Users, ID: int, body: schemas.ChroniqueFait):
    fait = _require_fait(db, user, ID)
    fait.title, fait.description = _valider(body)
    fait.date_rp = body.date_rp
    db.add(fait)
    db.commit()
    db.refresh(fait)
    return _fait_infos(fait)

def delete_fait(db: Session, user: schemas.Users, ID: int):
    db.delete(_require_fait(db, user, ID))
    db.commit()
    return True

#endregion
