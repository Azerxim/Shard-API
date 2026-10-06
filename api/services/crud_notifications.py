"""
Notifications du site : la cloche de la barre de ShardUI-2.

- Écrites par les autres domaines au moment des faits : appels aux armes, invitations d'alliance, liens de parenté à
  accepter, lectures tracées, révélations, décisions des modérateurs RP, demandes à leur soumettre, événements annulés,
  compagnies de mercenaires engagées.
- Jamais adressées à celui qui agit, ni à un compte désactivé.
- Le site les relève régulièrement (pas de connexion permanente). Une notification lue est gardée JOURS_LUES jours ;
  au-delà de MAX_PAR_JOUEUR, les plus anciennes disparaissent.
"""
import datetime as dt

from fastapi import HTTPException
from sqlmodel import Session, col, delete, func, select

from ..db import models, schemas
from .crud import get_members_of_civilisation, get_members_of_religion

JOURS_LUES = 30
MAX_PAR_JOUEUR = 200


#region Destinataires

def gestionnaires(db: Session, entity_type: str | None, entity_id: int | None) -> set[int]:
    # Ceux qui agissent au nom de l'entité : Fondateur et Admins d'une civilisation ou d'une religion, joueur d'un personnage
    if not entity_id:
        return set()
    if entity_type == "personnage":
        personnage = db.get(models.Personnages, entity_id)
        return {personnage.user_id} if personnage and personnage.user_id else set()
    get_members = {"civilisation": get_members_of_civilisation, "religion": get_members_of_religion}.get(entity_type)
    if not get_members:
        return set()
    return {member.user_id for member in get_members(db, entity_id, limit=10000) if member.role in ("Fondateur", "Admin")}

def moderateurs(db: Session) -> set[int]:
    statement = select(models.Users.id).where(models.Users.is_disabled == False, (models.Users.is_admin == True) | (models.Users.is_moderateur == True))  # noqa: E712
    return set(db.exec(statement).all())

#endregion
#region Envoi

def notifier(db: Session, destinataires, type_: str, title: str, text: str | None = None, link: str | None = None, sauf: int | None = None):
    # Une ligne par destinataire ; validée aussitôt (à appeler après le commit de l'action elle-même)
    ids = {user_id for user_id in destinataires if user_id and user_id != sauf}
    if not ids:
        return
    actifs = db.exec(select(models.Users.id).where(col(models.Users.id).in_(ids), models.Users.is_disabled == False)).all()  # noqa: E712
    for user_id in actifs:
        db.add(models.Notifications(user_id=user_id, type=type_, title=title, text=text, link=link))
    db.commit()

#endregion
#region Lecture

def _infos(notification: models.Notifications):
    return {
        "id": notification.id,
        "type": notification.type,
        "title": notification.title,
        "text": notification.text,
        "link": notification.link,
        "created_at": notification.created_at,
        "lue": notification.read_at is not None,
    }

def _purger(db: Session, userID: int):
    limite = dt.datetime.now() - dt.timedelta(days=JOURS_LUES)
    db.exec(delete(models.Notifications).where(models.Notifications.user_id == userID, col(models.Notifications.read_at).is_not(None), models.Notifications.read_at < limite))
    anciennes = db.exec(
        select(models.Notifications.id).where(models.Notifications.user_id == userID)
        .order_by(col(models.Notifications.created_at).desc(), col(models.Notifications.id).desc()).offset(MAX_PAR_JOUEUR)
    ).all()
    if anciennes:
        db.exec(delete(models.Notifications).where(col(models.Notifications.id).in_(anciennes)))
    db.commit()

def mes_notifications(db: Session, user: schemas.Users, limite: int = 30):
    _purger(db, user.id)
    non_lues = db.exec(select(func.count()).select_from(models.Notifications).where(models.Notifications.user_id == user.id, col(models.Notifications.read_at).is_(None))).one()
    statement = (
        select(models.Notifications).where(models.Notifications.user_id == user.id)
        .order_by(col(models.Notifications.created_at).desc(), col(models.Notifications.id).desc()).limit(max(1, min(limite, MAX_PAR_JOUEUR)))
    )
    return {"non_lues": non_lues, "notifications": [_infos(n) for n in db.exec(statement).all()]}

def marquer_lue(db: Session, user: schemas.Users, ID: int):
    notification = db.get(models.Notifications, ID)
    if not notification or notification.user_id != user.id:
        raise HTTPException(status_code=404, detail="Cette notification n'existe pas")
    if notification.read_at is None:
        notification.read_at = dt.datetime.now()
        db.add(notification)
        db.commit()
    return True

def marquer_toutes_lues(db: Session, user: schemas.Users):
    maintenant = dt.datetime.now()
    for notification in db.exec(select(models.Notifications).where(models.Notifications.user_id == user.id, col(models.Notifications.read_at).is_(None))).all():
        notification.read_at = maintenant
        db.add(notification)
    db.commit()
    return True

#endregion
