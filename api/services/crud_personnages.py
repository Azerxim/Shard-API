"""
Personnages.

- Un joueur crée autant de personnages qu'il le souhaite, sans validation ; seuls lui et les administrateurs les modifient.
- Fiche RP : espèce et classe (référentiels gérés par les administrateurs et modérateurs RP), grade libre, statut, dates.
- Skin : aucun, celui du compte Minecraft lié du joueur (UUID copié à l'enregistrement) ou un lien vers un fichier de skin.
- Résidence cohérente : le quartier appartient à la ville et la ville à la civilisation (niveaux supérieurs complétés).
- Un message d'un journal (salon Discord) est attribué à un personnage par l'auteur Discord du message, reconnu grâce au
  compte Discord lié à son compte Tetrago. Seul ce message est relu ; un extrait est conservé pour la fiche.
"""
import datetime as dt

from fastapi import HTTPException
from sqlmodel import Session, select

from ..db import models, schemas
from .crud import (
    get_channel_message,
    get_civilisation_by_id,
    get_journal,
    get_quartier_by_id,
    get_user_by_id,
    get_ville_by_id,
)
from .crud_conflits import is_moderateur

STATUTS = ("vivant", "mort", "disparu")
SKIN_SOURCES = ("aucun", "minecraft", "lien")
RESIDENCES = ("civilisation", "ville", "quartier")
NAME_MAX = 80
GRADE_MAX = 80
EXCERPT_MAX = 280

REFERENTIELS = {
    "especes": {"model": models.PersonnageEspeces, "column": "espece_id", "label": "espèce"},
    "classes": {"model": models.PersonnageClasses, "column": "classe_id", "label": "classe"},
}

# Valeurs de départ, reprises de s2 (perso_especes, perso_classes)
REFERENTIELS_S2 = {
    "especes": ["Humain", "Homme-Chouette", "Piglin", "Villager", "Pillager", "Géant", "Witch", "Divinité", "Elfe", "Ange",
                "Démon", "Squelette", "Zombie", "Vindicator", "Evoker", "Illusioner", "Iceologer"],
    "classes": ["Alchimiste", "Archerie", "Artillerie", "Assassin", "Mage", "Barbare", "Barde", "Berserk", "Chevalerie",
                "Paladin", "Druide", "Guerrier", "Prêtre", "Sage", "Soldat", "Voleur", "Villageois"],
}


#region Référentiels (espèces et classes)

def seed_referentiels(db: Session):
    # Au démarrage : remplit un référentiel vide avec les valeurs de s2 ; renvoie le nombre de valeurs ajoutées
    added = {}
    for kind, titles in REFERENTIELS_S2.items():
        model = REFERENTIELS[kind]["model"]
        added[kind] = 0
        if db.exec(select(model)).first():
            continue
        for title in titles:
            db.add(model(title=title))
        added[kind] = len(titles)
    db.commit()
    return added

def _referentiel_config(kind: str):
    if kind not in REFERENTIELS:
        raise HTTPException(status_code=404, detail="Référentiel inconnu : especes ou classes")
    return REFERENTIELS[kind]

def _item_infos(item):
    return {"id": item.id, "title": item.title, "description": item.description} if item else None

def list_referentiels(db: Session):
    # { especes: [{ id, title, description }], classes: [...] }, par ordre alphabétique
    return {
        kind: sorted((_item_infos(item) for item in db.exec(select(config["model"])).all()), key=lambda item: item["title"].lower())
        for kind, config in REFERENTIELS.items()
    }

def _require_referentiel_rights(user: schemas.Users):
    if not is_moderateur(user):
        raise HTTPException(status_code=403, detail="Seuls les administrateurs et modérateurs RP gèrent les espèces et les classes")

def _clean_item(db: Session, config: dict, body: schemas.ReferentielItem, current_id: int | None = None):
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail=f"Donnez un nom à cette {config['label']}")
    if len(title) > NAME_MAX:
        raise HTTPException(status_code=400, detail=f"Le nom ne dépasse pas {NAME_MAX} caractères")
    for item in db.exec(select(config["model"])).all():
        if item.id != current_id and item.title.lower() == title.lower():
            raise HTTPException(status_code=400, detail=f"Cette {config['label']} existe déjà")
    return title

def create_referentiel(db: Session, user: schemas.Users, kind: str, body: schemas.ReferentielItem):
    _require_referentiel_rights(user)
    config = _referentiel_config(kind)
    item = config["model"](title=_clean_item(db, config, body), description=(body.description or "").strip() or None)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"text": f"« {item.title} » a été ajoutée", "item": _item_infos(item)}

def update_referentiel(db: Session, user: schemas.Users, kind: str, ID: int, body: schemas.ReferentielItem):
    _require_referentiel_rights(user)
    config = _referentiel_config(kind)
    item = db.get(config["model"], ID)
    if not item:
        raise HTTPException(status_code=404, detail=f"Cette {config['label']} n'existe pas")
    item.title = _clean_item(db, config, body, current_id=item.id)
    item.description = (body.description or "").strip() or None
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"text": f"« {item.title} » a été modifiée", "item": _item_infos(item)}

def delete_referentiel(db: Session, user: schemas.Users, kind: str, ID: int):
    # Les personnages concernés perdent simplement cette espèce ou classe
    _require_referentiel_rights(user)
    config = _referentiel_config(kind)
    item = db.get(config["model"], ID)
    if not item:
        raise HTTPException(status_code=404, detail=f"Cette {config['label']} n'existe pas")
    column = getattr(models.Personnages, config["column"])
    for personnage in db.exec(select(models.Personnages).where(column == ID)).all():
        setattr(personnage, config["column"], None)
        db.add(personnage)
    db.delete(item)
    db.commit()
    return {"text": f"« {item.title} » a été supprimée"}

#endregion
#region Lecture

def get_personnage(db: Session, ID: int):
    return db.exec(select(models.Personnages).where(models.Personnages.id == ID)).first()

def _require_personnage(db: Session, ID: int):
    personnage = get_personnage(db, ID)
    if not personnage:
        raise HTTPException(status_code=404, detail="Ce personnage n'existe pas")
    return personnage

def can_manage(user: schemas.Users | None, personnage: models.Personnages) -> bool:
    return bool(user and not user.is_disabled and (user.is_admin or personnage.user_id == user.id))

def _require_rights(user: schemas.Users, personnage: models.Personnages):
    if not can_manage(user, personnage):
        raise HTTPException(status_code=403, detail="Seul le joueur de ce personnage peut le modifier")

def _links_of_personnage(db: Session, personnageID: int):
    statement = select(models.PersonnageMessages).where(models.PersonnageMessages.personnage_id == personnageID)
    return db.exec(statement).all()

def personnage_infos(db: Session, personnage: models.Personnages):
    user = get_user_by_id(db, personnage.user_id) if personnage.user_id else None
    civilisation = get_civilisation_by_id(db, personnage.civilisation_id) if personnage.civilisation_id else None
    ville = get_ville_by_id(db, personnage.ville_id) if personnage.ville_id else None
    quartier = get_quartier_by_id(db, personnage.quartier_id) if personnage.quartier_id else None
    espece = db.get(models.PersonnageEspeces, personnage.espece_id) if personnage.espece_id else None
    classe = db.get(models.PersonnageClasses, personnage.classe_id) if personnage.classe_id else None
    return {
        "personnage": personnage.model_dump(),
        "joueur": {"id": user.id, "username": user.username, "full_name": user.full_name} if user else None,
        "civilisation": {"id": civilisation.id, "title": civilisation.title} if civilisation else None,
        "ville": {"id": ville.id, "title": ville.title, "civilisation_id": ville.civilisation_id} if ville else None,
        "quartier": {"id": quartier.id, "title": quartier.title, "ville_id": quartier.ville_id} if quartier else None,
        "espece": {"id": espece.id, "title": espece.title} if espece else None,
        "classe": {"id": classe.id, "title": classe.title} if classe else None,
        "messages_count": len(_links_of_personnage(db, personnage.id)),
    }

def _sorted_infos(db: Session, personnages):
    return [personnage_infos(db, personnage) for personnage in sorted(personnages, key=lambda p: p.name.lower())]

def list_personnages(db: Session):
    return _sorted_infos(db, db.exec(select(models.Personnages)).all())

def personnages_of_user(db: Session, userID: int):
    return _sorted_infos(db, db.exec(select(models.Personnages).where(models.Personnages.user_id == userID)).all())

def personnages_of_residence(db: Session, residence: str, ID: int):
    # Habitants d'une civilisation, d'une ville ou d'un quartier
    if residence not in RESIDENCES:
        raise HTTPException(status_code=404, detail="Type de lieu inconnu")
    column = getattr(models.Personnages, f"{residence}_id")
    return _sorted_infos(db, db.exec(select(models.Personnages).where(column == ID)).all())

def residents_count(db: Session, residence: str):
    # { id du lieu: nombre d'habitants } pour la carte
    if residence not in RESIDENCES:
        raise HTTPException(status_code=404, detail="Type de lieu inconnu")
    counts = {}
    for personnage in db.exec(select(models.Personnages)).all():
        ID = getattr(personnage, f"{residence}_id")
        if ID:
            counts[ID] = counts.get(ID, 0) + 1
    return counts

def link_infos(db: Session, link: models.PersonnageMessages):
    journal = get_journal(db, link.journal_id) if link.journal_id else None
    return {
        "id": link.id,
        "personnage_id": link.personnage_id,
        "message_id": link.message_id,
        "excerpt": link.excerpt,
        "message_timestamp": link.message_timestamp,
        "linked_at": link.linked_at,
        "journal": {"id": journal.id, "title": journal.title} if journal else None,
    }

def read_personnage(db: Session, ID: int):
    personnage = _require_personnage(db, ID)
    links = sorted(_links_of_personnage(db, personnage.id), key=lambda link: link.message_timestamp or link.linked_at, reverse=True)
    return {**personnage_infos(db, personnage), "messages": [link_infos(db, link) for link in links]}

#endregion
#region Écriture

def _check_values(db: Session, personnage: models.Personnages):
    personnage.name = (personnage.name or "").strip()
    if not personnage.name:
        raise HTTPException(status_code=400, detail="Donnez un nom à votre personnage")
    if len(personnage.name) > NAME_MAX:
        raise HTTPException(status_code=400, detail=f"Le nom d'un personnage ne dépasse pas {NAME_MAX} caractères")
    personnage.grade = (personnage.grade or "").strip() or None
    if personnage.grade and len(personnage.grade) > GRADE_MAX:
        raise HTTPException(status_code=400, detail=f"Le grade ne dépasse pas {GRADE_MAX} caractères")
    if personnage.status not in STATUTS:
        raise HTTPException(status_code=400, detail="Statut inconnu : vivant, mort ou disparu")
    if personnage.image_url and not personnage.image_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Le portrait doit être l'adresse d'une image (https://…)")
    if personnage.status == "vivant":
        personnage.date_deces = None
    if personnage.date_naissance and personnage.date_deces and personnage.date_deces < personnage.date_naissance:
        raise HTTPException(status_code=400, detail="La date de décès précède la date de naissance")
    for kind, config in REFERENTIELS.items():
        ID = getattr(personnage, config["column"])
        if ID and not db.get(config["model"], ID):
            raise HTTPException(status_code=404, detail=f"Cette {config['label']} n'existe pas")

def _apply_skin(db: Session, personnage: models.Personnages):
    personnage.skin_source = personnage.skin_source or "aucun"
    if personnage.skin_source not in SKIN_SOURCES:
        raise HTTPException(status_code=400, detail="Skin inconnu : aucun, minecraft ou lien")
    if personnage.skin_source == "lien":
        if not personnage.skin_url or not personnage.skin_url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="Indiquez l'adresse du fichier de skin (https://…)")
    else:
        personnage.skin_url = None
    personnage.minecraft_uuid = None
    if personnage.skin_source == "minecraft":
        # Skin du compte Minecraft lié au joueur du personnage (pas à celui qui modifie, s'il est administrateur)
        statement = select(models.UserPlatforms).where(models.UserPlatforms.user_id == personnage.user_id, models.UserPlatforms.platform == "microsoft")
        link = db.exec(statement).first()
        if not link:
            raise HTTPException(status_code=400, detail="Liez d'abord un compte Minecraft depuis le profil pour utiliser son skin")
        personnage.minecraft_uuid = link.uid

def _apply_residence(db: Session, personnage: models.Personnages):
    # Du plus précis au plus large : le quartier donne sa ville, la ville sa civilisation
    if personnage.quartier_id:
        quartier = get_quartier_by_id(db, personnage.quartier_id)
        if not quartier:
            raise HTTPException(status_code=404, detail="Ce quartier n'existe pas")
        if personnage.ville_id and quartier.ville_id != personnage.ville_id:
            raise HTTPException(status_code=400, detail="Ce quartier n'appartient pas à la ville choisie")
        personnage.ville_id = quartier.ville_id
    if personnage.ville_id:
        ville = get_ville_by_id(db, personnage.ville_id)
        if not ville:
            raise HTTPException(status_code=404, detail="Cette ville n'existe pas")
        if personnage.civilisation_id and ville.civilisation_id != personnage.civilisation_id:
            raise HTTPException(status_code=400, detail="Cette ville n'appartient pas à la civilisation choisie")
        personnage.civilisation_id = ville.civilisation_id
    if personnage.civilisation_id and not get_civilisation_by_id(db, personnage.civilisation_id):
        raise HTTPException(status_code=404, detail="Cette civilisation n'existe pas")

def _save(db: Session, personnage: models.Personnages):
    try:
        _check_values(db, personnage)
        _apply_skin(db, personnage)
        _apply_residence(db, personnage)
    except HTTPException:
        # Les valeurs refusées ne doivent pas rester sur l'objet si la session sert encore
        db.rollback()
        raise
    db.add(personnage)
    db.commit()
    db.refresh(personnage)
    return personnage_infos(db, personnage)

def create_personnage(db: Session, user: schemas.Users, body: schemas.PersonnageCreate):
    values = body.model_dump()
    values["status"] = values.get("status") or "vivant"
    return _save(db, models.Personnages(**values, user_id=user.id, created_at=dt.datetime.now()))

def update_personnage(db: Session, user: schemas.Users, ID: int, body: schemas.PersonnageUpdate):
    personnage = _require_personnage(db, ID)
    _require_rights(user, personnage)
    values = body.model_dump(exclude_unset=True)
    # Changer de civilisation (ou de ville) sans préciser la suite efface la ville et le quartier devenus incohérents
    if "civilisation_id" in values and values["civilisation_id"] != personnage.civilisation_id and "ville_id" not in values:
        values.update(ville_id=None, quartier_id=None)
    if "ville_id" in values and values["ville_id"] != personnage.ville_id and "quartier_id" not in values:
        values["quartier_id"] = None
    for key, value in values.items():
        if key in ("name", "status", "skin_source") and value is None:
            continue
        setattr(personnage, key, value)
    personnage.updated_at = dt.datetime.now()
    return _save(db, personnage)

def delete_personnage(db: Session, user: schemas.Users, ID: int):
    personnage = _require_personnage(db, ID)
    _require_rights(user, personnage)
    for link in _links_of_personnage(db, personnage.id):
        db.delete(link)
    db.delete(personnage)
    db.commit()
    return {"text": f"{personnage.name} a été supprimé"}

#endregion
#region Messages de journaux

def _discord_uid(db: Session, user: schemas.Users):
    statement = select(models.UserPlatforms).where(models.UserPlatforms.user_id == user.id, models.UserPlatforms.platform == "discord")
    link = db.exec(statement).first()
    return link.uid if link else None

def _journal_message(journal: models.Journaux, messageID: str):
    # Seul le message visé est relu sur Discord
    try:
        message = get_channel_message(journal.uid, messageID)
    except Exception as error:
        print(f"Lecture du message {messageID} du journal {journal.id} impossible : {error}")
        raise HTTPException(status_code=502, detail="Impossible de lire ce message sur Discord : réessayez dans un instant")
    if not message:
        raise HTTPException(status_code=404, detail="Ce message n'existe pas (ou plus) dans ce journal")
    return message

def _parse_timestamp(value):
    try:
        timestamp = dt.datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return timestamp.astimezone(dt.timezone.utc).replace(tzinfo=None) if timestamp.tzinfo else timestamp

def _excerpt(message: dict):
    text = (message.get("content") or "").strip()
    if not text and message.get("attachments"):
        text = f"📎 {message['attachments'][0].get('filename') or 'Pièce jointe'}"
    return text if len(text) <= EXCERPT_MAX else f"{text[:EXCERPT_MAX - 1].rstrip()}…"

def _message_link(db: Session, journalID: int, messageID: str):
    statement = select(models.PersonnageMessages).where(models.PersonnageMessages.journal_id == journalID, models.PersonnageMessages.message_id == str(messageID))
    return db.exec(statement).first()

def link_message(db: Session, user: schemas.Users, body: schemas.PersonnageMessageLink):
    personnage = _require_personnage(db, body.personnage_id)
    if personnage.user_id != user.id:
        raise HTTPException(status_code=403, detail="Vous ne pouvez associer vos messages qu'à vos propres personnages")
    journal = get_journal(db, body.journal_id)
    if not journal:
        raise HTTPException(status_code=404, detail="Ce journal n'existe pas")
    if not journal.uid:
        raise HTTPException(status_code=400, detail="Ce journal n'est relié à aucun salon Discord")
    uid = _discord_uid(db, user)
    if not uid:
        raise HTTPException(status_code=400, detail="Liez votre compte Discord depuis votre profil pour associer vos messages à vos personnages")

    message = _journal_message(journal, body.message_id)
    if str((message.get("author") or {}).get("id")) != uid:
        raise HTTPException(status_code=403, detail="Seul l'auteur Discord de ce message peut l'associer à un personnage")

    link = _message_link(db, journal.id, body.message_id) or models.PersonnageMessages(journal_id=journal.id, message_id=str(body.message_id), author_uid=uid)
    link.personnage_id = personnage.id
    link.author_uid = uid
    link.excerpt = _excerpt(message)
    link.message_timestamp = _parse_timestamp(message.get("timestamp"))
    link.linked_by = user.id
    link.linked_at = dt.datetime.now()
    db.add(link)
    db.commit()
    db.refresh(link)
    return {"text": f"Le message est désormais signé par {personnage.name}", "lien": link_infos(db, link)}

def unlink_message(db: Session, user: schemas.Users, linkID: int):
    link = db.exec(select(models.PersonnageMessages).where(models.PersonnageMessages.id == linkID)).first()
    if not link:
        raise HTTPException(status_code=404, detail="Ce message n'est associé à aucun personnage")
    personnage = get_personnage(db, link.personnage_id) if link.personnage_id else None
    allowed = user.is_admin or (personnage and personnage.user_id == user.id) or _discord_uid(db, user) == link.author_uid
    if not allowed:
        raise HTTPException(status_code=403, detail="Seuls l'auteur du message et le joueur du personnage peuvent retirer cette association")
    db.delete(link)
    db.commit()
    return {"text": "Le message n'est plus associé à ce personnage"}

def links_of_journal(db: Session, journalID: int):
    # Associations d'un journal, pour afficher les personnages dans le fil des messages
    statement = select(models.PersonnageMessages).where(models.PersonnageMessages.journal_id == journalID)
    result = []
    for link in db.exec(statement).all():
        personnage = get_personnage(db, link.personnage_id) if link.personnage_id else None
        if not personnage:
            continue
        result.append({
            "id": link.id,
            "message_id": link.message_id,
            "author_uid": link.author_uid,
            "user_id": personnage.user_id,
            "personnage": {
                "id": personnage.id, "name": personnage.name, "image_url": personnage.image_url,
                "minecraft_uuid": personnage.minecraft_uuid, "status": personnage.status,
            },
        })
    return result

#endregion
