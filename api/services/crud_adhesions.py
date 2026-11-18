"""
Demandes d'adhésion à une civilisation.

- Un joueur connecté demande à devenir membre d'une civilisation, avec un court message s'il le souhaite. Une seule
  demande en attente par joueur et par civilisation ; jamais s'il en est déjà membre.
- Le Fondateur et les Admins de la civilisation (ou un administrateur du site) l'acceptent, ce qui fait du joueur un
  « Membre », ou la refusent. Le joueur peut retirer sa demande tant qu'elle attend.
- Notifications : la demande va aux dirigeants de la civilisation, la réponse au joueur.
- Être membre ouvre la résidence : seul un membre (ou un administrateur) installe un personnage dans la civilisation,
  ses villes et ses quartiers (crud_personnages._apply_residence).
"""
import datetime as dt

from fastapi import HTTPException
from sqlmodel import Session, select

from ..db import models, schemas
from . import crud_notifications
from .crud import get_civilisation_by_id, get_member_of_civilisation, get_user_by_id

MESSAGE_MAX = 500


#region Lecture

def _infos(db: Session, demande: models.CivilisationDemandes):
    user = get_user_by_id(db, demande.user_id)
    civilisation = get_civilisation_by_id(db, demande.civilisation_id)
    return {
        "id": demande.id,
        "civilisation_id": demande.civilisation_id,
        "civilisation": civilisation.title if civilisation else None,
        "user_id": demande.user_id,
        "username": user.username if user else None,
        "message": demande.message,
        "status": demande.status,
        "created_at": demande.created_at,
        "answered_at": demande.answered_at,
    }

def peut_repondre(db: Session, user: schemas.Users | None, civilisationID: int) -> bool:
    # Fondateur ou Admin de la civilisation, ou administrateur du site
    if not user or user.is_disabled:
        return False
    return bool(user.is_admin or user.id in crud_notifications.gestionnaires(db, "civilisation", civilisationID))

def _en_attente(db: Session, civilisationID: int | None = None, userID: int | None = None):
    statement = select(models.CivilisationDemandes).where(models.CivilisationDemandes.status == "en_attente")
    if civilisationID is not None:
        statement = statement.where(models.CivilisationDemandes.civilisation_id == civilisationID)
    if userID is not None:
        statement = statement.where(models.CivilisationDemandes.user_id == userID)
    return db.exec(statement.order_by(models.CivilisationDemandes.created_at)).all()

def demandes_de_civilisation(db: Session, user: schemas.Users, civilisationID: int):
    # Demandes en attente, pour ceux qui y répondent
    if not get_civilisation_by_id(db, civilisationID):
        raise HTTPException(status_code=404, detail="La civilisation n'existe pas")
    if not peut_repondre(db, user, civilisationID):
        raise HTTPException(status_code=403, detail="Seuls les dirigeants de la civilisation voient ses demandes d'adhésion")
    return [_infos(db, demande) for demande in _en_attente(db, civilisationID=civilisationID)]

def mes_demandes(db: Session, user: schemas.Users):
    # Demandes en attente du joueur, toutes civilisations confondues
    return [_infos(db, demande) for demande in _en_attente(db, userID=user.id)]

#endregion
#region Demande et réponse

def demander(db: Session, user: schemas.Users, civilisationID: int, body: schemas.DemandeAdhesion):
    civilisation = get_civilisation_by_id(db, civilisationID)
    if not civilisation:
        raise HTTPException(status_code=404, detail="La civilisation n'existe pas")
    if get_member_of_civilisation(db, civilisationID, user.id):
        raise HTTPException(status_code=400, detail="Vous êtes déjà membre de cette civilisation")
    if _en_attente(db, civilisationID=civilisationID, userID=user.id):
        raise HTTPException(status_code=400, detail="Votre demande attend déjà une réponse")
    message = (body.message or "").strip() or None
    if message and len(message) > MESSAGE_MAX:
        raise HTTPException(status_code=400, detail=f"Le message ne dépasse pas {MESSAGE_MAX} caractères")
    demande = models.CivilisationDemandes(civilisation_id=civilisationID, user_id=user.id, message=message)
    db.add(demande)
    db.commit()
    db.refresh(demande)
    crud_notifications.notifier(
        db, crud_notifications.gestionnaires(db, "civilisation", civilisationID), "invitation",
        f"{user.username} demande à rejoindre {civilisation.title}", message or "Une réponse est attendue.",
        f"/civilisation/{civilisationID}#demandes-adhesion", sauf=user.id,
    )
    return {"resultat": "Demande envoyée", "demande": _infos(db, demande)}

def _require_en_attente(db: Session, demandeID: int):
    demande = db.get(models.CivilisationDemandes, demandeID)
    if not demande:
        raise HTTPException(status_code=404, detail="Cette demande n'existe pas")
    if demande.status != "en_attente":
        raise HTTPException(status_code=400, detail="Cette demande a déjà reçu une réponse")
    return demande

def repondre(db: Session, user: schemas.Users, demandeID: int, accepter: bool):
    demande = _require_en_attente(db, demandeID)
    if not peut_repondre(db, user, demande.civilisation_id):
        raise HTTPException(status_code=403, detail="Seuls les dirigeants de la civilisation répondent à ses demandes d'adhésion")
    demande.status = "acceptee" if accepter else "refusee"
    demande.answered_at = dt.datetime.now()
    demande.answered_by = user.id
    db.add(demande)
    if accepter and not get_member_of_civilisation(db, demande.civilisation_id, demande.user_id):
        db.add(models.CivilisationMembers(user_id=demande.user_id, civilisation_id=demande.civilisation_id, role="Membre", joined_at=dt.datetime.now()))
    db.commit()
    civilisation = get_civilisation_by_id(db, demande.civilisation_id)
    nom = civilisation.title if civilisation else "la civilisation"
    crud_notifications.notifier(
        db, {demande.user_id}, "decision",
        f"Bienvenue dans {nom}" if accepter else f"Demande refusée par {nom}",
        "Vous en êtes désormais membre : vos personnages peuvent y résider." if accepter else "Vous pouvez en parler avec ses dirigeants, ou demander à rejoindre une autre civilisation.",
        f"/civilisation/{demande.civilisation_id}", sauf=user.id,
    )
    return {"resultat": "Demande acceptée" if accepter else "Demande refusée"}

def retirer(db: Session, user: schemas.Users, demandeID: int):
    # Le joueur retire sa propre demande
    demande = _require_en_attente(db, demandeID)
    if demande.user_id != user.id:
        raise HTTPException(status_code=403, detail="Seul l'auteur de la demande peut la retirer")
    demande.status = "annulee"
    demande.answered_at = dt.datetime.now()
    db.add(demande)
    db.commit()
    return {"resultat": "Demande retirée"}

#endregion
