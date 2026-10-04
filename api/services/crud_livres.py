"""
Liens des livres de la bibliothèque avec une civilisation, une religion, un commerce, une alliance ou un personnage.

- Un livre peut avoir plusieurs liens (une chronique peut concerner plusieurs personnages, un traité deux civilisations).
  Seul un lien vers une civilisation donne des droits : ses dirigeants peuvent modifier le livre (crud._check_livre_rights).
- Créer un lien demande des droits sur le livre (crud._check_livre_rights) ET sur l'entité, pour qu'on ne puisse pas
  attribuer un texte à une religion ou au personnage d'un autre :
  civilisation et religion : Fondateur ou Admin ; commerce : Fondateur ou Admin (ou du commerce dirigeant) ; alliance : Fondateur ou
  Admin de la civilisation chef de file ; personnage : son joueur. L'administrateur du site peut tout.
- Retirer un lien : droits sur le livre OU sur l'entité (une religion peut refuser un livre qu'on lui attribue).
- Les liens disparaissent avec le livre ou l'entité (crud_nettoyage.supprimer_liens_livres, et au démarrage).
"""
from fastapi import HTTPException
from sqlmodel import Session, select

from ..db import models, schemas
from .crud import _check_commerce_rights, _check_livre_rights, get_civilisation_by_id, get_commerce_by_id, get_livre, get_religion_by_id
from . import crud_conflits, crud_personnages

ENTITES = ("civilisation", "religion", "commerce", "alliance", "personnage")


#region Entités

def _entite(db: Session, entity_type: str, entity_id: int):
    if entity_type == "civilisation":
        return get_civilisation_by_id(db, entity_id)
    if entity_type == "religion":
        return get_religion_by_id(db, entity_id)
    if entity_type == "commerce":
        return get_commerce_by_id(db, entity_id)
    if entity_type == "alliance":
        return db.get(models.Alliances, entity_id)
    if entity_type == "personnage":
        return crud_personnages.get_personnage(db, entity_id)
    raise HTTPException(status_code=400, detail="Un livre se lie à une civilisation, une religion, un commerce, une alliance ou un personnage")

def _resume(entity_type: str, entite):
    if entity_type == "personnage":
        return {"type": entity_type, "id": entite.id, "title": entite.name, "image_url": entite.image_url, "user_id": entite.user_id}
    resume = {"type": entity_type, "id": entite.id, "title": entite.title, "is_public": entite.is_public}
    if entity_type in ("religion", "alliance"):
        resume.update(color=entite.color, icon=entite.icon)
    return resume

def peut_gerer_entite(db: Session, user: schemas.Users, entity_type: str, entite) -> bool:
    if not user or user.is_disabled:
        return False
    if user.is_admin:
        return True
    try:
        if entity_type in ("civilisation", "religion"):
            return crud_conflits.can_manage_entity(db, user, entity_type, entite.id)
        if entity_type == "commerce":
            _check_commerce_rights(db, user, entite)
            return True
        if entity_type == "alliance":
            crud_conflits._require_alliance_chef(db, user, entite)
            return True
        if entity_type == "personnage":
            return crud_personnages.can_manage(user, entite)
    except HTTPException:
        return False
    return False

#endregion
#region Lecture

def lien_infos(db: Session, lien: models.LivresLiens):
    entite = _entite(db, lien.entity_type, lien.entity_id)
    return {"id": lien.id, "livre_id": lien.livre_id, "entite": _resume(lien.entity_type, entite) if entite else None}

def liens_du_livre(db: Session, livreID: int):
    # Liens dont l'entité existe encore, par type puis par nom
    if not get_livre(db, livreID):
        raise HTTPException(status_code=404, detail="Le livre n'existe pas")
    liens = db.exec(select(models.LivresLiens).where(models.LivresLiens.livre_id == livreID)).all()
    infos = [info for info in (lien_infos(db, lien) for lien in liens) if info["entite"]]
    return sorted(infos, key=lambda info: (ENTITES.index(info["entite"]["type"]), info["entite"]["title"].lower()))

def livres_de_entite(db: Session, entity_type: str, entity_id: int):
    # Livres liés à l'entité : [{ lien_id, livre }] ; le site masque les livres privés comme ailleurs
    if entity_type not in ENTITES:
        raise HTTPException(status_code=400, detail="Un livre se lie à une civilisation, une religion, un commerce, une alliance ou un personnage")
    liens = db.exec(select(models.LivresLiens).where(models.LivresLiens.entity_type == entity_type, models.LivresLiens.entity_id == entity_id)).all()
    resultats = []
    for lien in liens:
        livre = get_livre(db, lien.livre_id)
        if livre:
            resultats.append({"lien_id": lien.id, "livre": livre})
    return sorted(resultats, key=lambda r: r["livre"].title.lower())

#endregion
#region Gestion

def lier(db: Session, user: schemas.Users, body: schemas.LivreLienCreate):
    livre = get_livre(db, body.livre_id)
    if not livre:
        raise HTTPException(status_code=404, detail="Le livre n'existe pas")
    _check_livre_rights(db, user, livre)
    entite = _entite(db, body.entity_type, body.entity_id)
    if not entite:
        raise HTTPException(status_code=404, detail="Cette entité n'existe pas")
    if not peut_gerer_entite(db, user, body.entity_type, entite):
        raise HTTPException(status_code=403, detail="Lier un livre demande aussi des droits sur ce que vous liez (dirigeant, chef de file ou joueur du personnage)")
    deja = db.exec(select(models.LivresLiens).where(
        models.LivresLiens.livre_id == livre.id, models.LivresLiens.entity_type == body.entity_type, models.LivresLiens.entity_id == entite.id,
    )).first()
    if deja:
        raise HTTPException(status_code=400, detail="Ce livre y est déjà lié")
    lien = models.LivresLiens(livre_id=livre.id, entity_type=body.entity_type, entity_id=entite.id, created_by=user.id)
    db.add(lien)
    db.commit()
    db.refresh(lien)
    return lien_infos(db, lien)

def delier(db: Session, user: schemas.Users, lienID: int):
    lien = db.get(models.LivresLiens, lienID)
    if not lien:
        raise HTTPException(status_code=404, detail="Ce lien n'existe pas")
    livre = get_livre(db, lien.livre_id)
    entite = _entite(db, lien.entity_type, lien.entity_id)
    try:
        if not livre:
            raise HTTPException(status_code=404)
        _check_livre_rights(db, user, livre)
    except HTTPException:
        if not (entite and peut_gerer_entite(db, user, lien.entity_type, entite)):
            raise HTTPException(status_code=403, detail="Seuls les gestionnaires du livre ou de ce qui y est lié peuvent retirer ce lien")
    db.delete(lien)
    db.commit()
    return True

#endregion
