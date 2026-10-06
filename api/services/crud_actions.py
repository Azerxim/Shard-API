"""
Actions secrètes : une action RP consignée avant d'être jouée, révélée plus tard.

- Déposée au nom d'un personnage (par son joueur), d'une civilisation ou d'une religion (Fondateur ou Admin, ou
  administrateur du site), éventuellement rattachée à une guerre en cours.
- Scellée à l'heure réelle du serveur : son contenu ne change plus. Son empreinte SHA-256 (« sel, titre, contenu »),
  publiée dès le dépôt, prouve à la révélation que rien n'a été réécrit après coup.
- Avant révélation, le public ne voit que son existence : code, date de dépôt et empreinte.
- Lecture tracée : les administrateurs et modérateurs RP jouent aussi. Ils peuvent lire une action scellée, mais chaque
  lecture est enregistrée, visible de l'auteur aussitôt et de tous à la révélation.
- Révélation par l'auteur, par un modérateur RP (motif obligatoire), ou automatiquement à la date fixée au dépôt.
  Aucune suppression ni modification : une action gênante ne peut pas disparaître.
- Piège mortel (Codex, « L'assassinat par piège ») : déclaré comme tel au dépôt (jamais après), il ne tue qu'une fois
  validé par un modérateur RP après sa révélation, qui peut aussi le réduire à une blessure (motif obligatoire). Un
  modérateur ne tranche pas un piège dont il est l'auteur. Tant qu'elle est scellée, rien ne dit qu'une action est un piège.
"""
import datetime as dt
import hashlib
import secrets

from fastapi import HTTPException
from sqlmodel import Session, select

from ..core import utils
from ..db import models, schemas
from .crud import announce_discord, get_members_of_civilisation, get_members_of_religion
from . import crud_conflits, crud_notifications, crud_personnages

ENTITY_TYPES = ("personnage", "civilisation", "religion")


#region Outils

def code_action(db_action: models.ActionsSecretes) -> str:
    return f"AS-{db_action.id:04d}"

def calculer_empreinte(sel: str, title: str, content: str) -> str:
    # Même calcul côté site (vérification après révélation) : SHA-256 hexadécimal de « sel\ntitre\ncontenu »
    return hashlib.sha256(f"{sel}\n{title}\n{content}".encode("utf-8")).hexdigest()

def _get_action(db: Session, ID: int):
    return db.exec(select(models.ActionsSecretes).where(models.ActionsSecretes.id == ID)).first()

def _require_action(db: Session, ID: int) -> models.ActionsSecretes:
    db_action = _get_action(db, ID)
    if not db_action:
        raise HTTPException(status_code=404, detail="Cette action secrète n'existe pas")
    _reveler_si_echue(db, db_action)
    return db_action

def _entity(db: Session, entity_type: str, entity_id: int):
    if entity_type == "personnage":
        return crud_personnages.get_personnage(db, entity_id)
    return crud_conflits._get_entity(db, entity_type, entity_id)

def _entity_summary(db: Session, db_action: models.ActionsSecretes):
    if db_action.entity_type == "personnage":
        personnage = crud_personnages.get_personnage(db, db_action.entity_id)
        if not personnage:
            return {"type": "personnage", "id": db_action.entity_id, "title": db_action.entity_title or "Personnage supprimé", "deleted": True}
        return {"type": "personnage", "id": personnage.id, "title": personnage.name}
    return crud_conflits._entity_summary(db, db_action.entity_type, db_action.entity_id, db_action.entity_title)

def est_auteur(db: Session, user: schemas.Users | None, db_action: models.ActionsSecretes) -> bool:
    # Le joueur qui l'a déposée, le joueur du personnage, ou un Fondateur / Admin de l'entité.
    # Être administrateur du site ne suffit pas : sa lecture doit rester tracée.
    if not user or user.is_disabled:
        return False
    if db_action.created_by == user.id:
        return True
    if db_action.entity_type == "personnage":
        personnage = crud_personnages.get_personnage(db, db_action.entity_id)
        return bool(personnage and personnage.user_id == user.id)
    get_members = get_members_of_civilisation if db_action.entity_type == "civilisation" else get_members_of_religion
    return any(member.user_id == user.id and member.role in ("Fondateur", "Admin") for member in get_members(db, db_action.entity_id, limit=10000))

def auteurs(db: Session, db_action: models.ActionsSecretes) -> set:
    # Comptes à prévenir de ce qui arrive à l'action : son déposant et ceux qui agissent au nom de son auteur
    return {db_action.created_by} | crud_notifications.gestionnaires(db, db_action.entity_type, db_action.entity_id)

def _lien(db_action: models.ActionsSecretes) -> str:
    return f"/actions-secretes#{code_action(db_action)}"

def _lectures(db: Session, db_action: models.ActionsSecretes):
    statement = select(models.ActionSecreteLectures).where(models.ActionSecreteLectures.action_id == db_action.id).order_by(models.ActionSecreteLectures.read_at)
    return [{"user": crud_conflits._user_summary(db, lecture.user_id), "role": lecture.role, "read_at": lecture.read_at} for lecture in db.exec(statement).all()]

def action_publique(db: Session, db_action: models.ActionsSecretes):
    # Avant révélation : l'existence seulement. Après : tout, y compris les lectures tracées.
    if db_action.revealed_at is None:
        return {"id": db_action.id, "code": code_action(db_action), "created_at": db_action.created_at, "empreinte": db_action.empreinte, "revealed": False}
    return action_complete(db, db_action)

def action_complete(db: Session, db_action: models.ActionsSecretes):
    db_guerre = crud_conflits.get_guerre(db, db_action.guerre_id) if db_action.guerre_id else None
    revealed = db_action.revealed_at is not None
    return {
        "id": db_action.id,
        "code": code_action(db_action),
        "title": db_action.title,
        "content": db_action.content,
        "entite": _entity_summary(db, db_action),
        "guerre": {"id": db_guerre.id, "title": db_guerre.title} if db_guerre else None,
        "created_at": db_action.created_at,
        "created_by": crud_conflits._user_summary(db, db_action.created_by),
        "empreinte": db_action.empreinte,
        # Le sel n'est publié qu'à la révélation : il permet alors à chacun de recalculer l'empreinte
        "sel": db_action.sel if revealed else None,
        "reveal_at": db_action.reveal_at,
        "revealed": revealed,
        "revealed_at": db_action.revealed_at,
        "revealed_by": crud_conflits._user_summary(db, db_action.revealed_by),
        "reveal_mode": db_action.reveal_mode,
        "reveal_motif": db_action.reveal_motif,
        "lectures": _lectures(db, db_action),
        "piege": bool(db_action.piege),
        "piege_verdict": db_action.piege_verdict,
        "piege_moderateur": crud_conflits._user_summary(db, db_action.piege_moderateur_id),
        "piege_note": db_action.piege_note,
        "piege_decision_at": db_action.piege_decision_at,
    }

#endregion
#region Révélation

def _annoncer_revelation(db: Session, db_action: models.ActionsSecretes):
    # Salon Discord « actions » (platforms.discord.channels.actions), avec le lien si site_url est configuré
    entite = _entity_summary(db, db_action)["title"]
    text = f"🔓 Action secrète **{code_action(db_action)}** révélée : **{db_action.title}** ({entite}), scellée le {db_action.created_at:%d/%m/%Y à %H:%M}."
    site = ((utils.PLATFORMS or {}).get("discord") or {}).get("site_url")
    announce_discord("actions", f"{text}\n{str(site).rstrip('/')}/actions-secretes#{code_action(db_action)}" if site else text)

def _reveler(db: Session, db_action: models.ActionsSecretes, mode: str, user_id: int | None = None, motif: str | None = None, when: dt.datetime | None = None):
    db_action.revealed_at = when or dt.datetime.now()
    db_action.revealed_by = user_id
    db_action.reveal_mode = mode
    db_action.reveal_motif = motif
    db.add(db_action)
    db.commit()
    db.refresh(db_action)
    _annoncer_revelation(db, db_action)
    _notifier_revelation(db, db_action)

def _notifier_revelation(db: Session, db_action: models.ActionsSecretes):
    # Ses auteurs (sauf celui qui la révèle), les belligérants de sa guerre, et les modérateurs RP pour un piège à juger
    code, entite = code_action(db_action), _entity_summary(db, db_action)["title"]
    if db_action.reveal_mode == "date":
        comment = "à la date fixée au dépôt"
    elif db_action.reveal_mode == "moderateur":
        comment = f"par la modération RP. Motif : {db_action.reveal_motif}"
    else:
        comment = "par son auteur"
    crud_notifications.notifier(db, auteurs(db, db_action), "revelation", f"Votre action {code} est révélée", f"« {db_action.title} », révélée {comment}.", _lien(db_action), sauf=db_action.revealed_by)
    if db_action.guerre_id:
        concernes = crud_conflits._gestionnaires_guerre(db, db_action.guerre_id) - auteurs(db, db_action)
        crud_notifications.notifier(db, concernes, "revelation", f"Action {code} révélée : {db_action.title}", f"{entite}, dans une guerre où vous êtes engagé.", _lien(db_action), sauf=db_action.revealed_by)
    if db_action.piege:
        crud_notifications.notifier(db, crud_notifications.moderateurs(db) - auteurs(db, db_action), "moderation", f"Piège à juger : {code}", f"« {db_action.title} » ({entite}) est révélée.", "/moderation", sauf=db_action.revealed_by)

def _reveler_si_echue(db: Session, db_action: models.ActionsSecretes):
    # Révélation automatique, faite à la première lecture après la date fixée (pas de tâche planifiée)
    if db_action.revealed_at is None and db_action.reveal_at and db_action.reveal_at <= dt.datetime.now():
        _reveler(db, db_action, "date", when=db_action.reveal_at)

def reveler(db: Session, user: schemas.Users, ID: int, body: schemas.ActionSecreteRevelation):
    db_action = _require_action(db, ID)
    if db_action.revealed_at is not None:
        raise HTTPException(status_code=400, detail="Cette action est déjà révélée")
    if est_auteur(db, user, db_action):
        _reveler(db, db_action, "auteur", user.id)
    elif crud_conflits.is_moderateur(user):
        motif = (body.motif or "").strip()
        if not motif:
            raise HTTPException(status_code=400, detail="Un modérateur qui révèle l'action d'un autre doit en donner le motif")
        _reveler(db, db_action, "moderateur", user.id, motif)
    else:
        raise HTTPException(status_code=403, detail="Seuls l'auteur et les modérateurs RP peuvent révéler cette action")
    return {"action": action_complete(db, db_action)}

def _annoncer_piege(db: Session, db_action: models.ActionsSecretes):
    entite = _entity_summary(db, db_action)["title"]
    verdict = "le piège est mortel" if db_action.piege_verdict == "mortel" else "le piège ne fait que blesser"
    text = f"☠️ Piège **{code_action(db_action)}** ({entite}) : {verdict}, d'après la modération RP."
    site = ((utils.PLATFORMS or {}).get("discord") or {}).get("site_url")
    announce_discord("actions", f"{text}\n{str(site).rstrip('/')}/actions-secretes#{code_action(db_action)}" if site else text)

def decider_piege(db: Session, user: schemas.Users, ID: int, body: schemas.PiegeDecision):
    # Validation après les faits : mortel, ou simple blessure (motif obligatoire)
    crud_conflits._require_moderateur(user)
    db_action = _require_action(db, ID)
    if not db_action.piege:
        raise HTTPException(status_code=400, detail="Cette action n'a pas été déclarée comme un piège à son dépôt")
    if db_action.revealed_at is None:
        raise HTTPException(status_code=400, detail="Un piège se juge après sa révélation")
    if db_action.piege_verdict is not None:
        raise HTTPException(status_code=400, detail="Ce piège a déjà été jugé")
    if est_auteur(db, user, db_action):
        raise HTTPException(status_code=403, detail="Un modérateur ne juge pas un piège dont il est l'auteur")
    note = (body.note or "").strip() or None
    if not body.mortel and not note:
        raise HTTPException(status_code=400, detail="Expliquez pourquoi le piège ne tue pas")
    db_action.piege_verdict = "mortel" if body.mortel else "blessure"
    db_action.piege_note = note
    db_action.piege_moderateur_id = user.id
    db_action.piege_decision_at = dt.datetime.now()
    db.add(db_action)
    db.commit()
    db.refresh(db_action)
    _annoncer_piege(db, db_action)
    verdict = "Il est mortel, d'après la modération RP." if body.mortel else f"Il ne fait que blesser, d'après la modération RP : {note}"
    crud_notifications.notifier(db, auteurs(db, db_action), "decision", f"Piège {code_action(db_action)} jugé", verdict, _lien(db_action), sauf=user.id)
    return {"action": action_complete(db, db_action)}

#endregion
#region Lecture

def list_actions(db: Session):
    # Registre public, plus récentes d'abord
    actions = db.exec(select(models.ActionsSecretes).order_by(models.ActionsSecretes.created_at.desc())).all()
    for db_action in actions:
        _reveler_si_echue(db, db_action)
    return [action_publique(db, db_action) for db_action in actions]

def read_action(db: Session, ID: int):
    return {"action": action_publique(db, _require_action(db, ID))}

def actions_of_guerre(db: Session, guerreID: int):
    # Actions révélées rattachées à une guerre (les scellées ne disent pas à quelle guerre elles se rapportent)
    statement = select(models.ActionsSecretes).where(models.ActionsSecretes.guerre_id == guerreID).order_by(models.ActionsSecretes.created_at)
    actions = db.exec(statement).all()
    for db_action in actions:
        _reveler_si_echue(db, db_action)
    return [action_complete(db, db_action) for db_action in actions if db_action.revealed_at is not None]

def actions_for_user(db: Session, user: schemas.Users):
    # Actions dont l'utilisateur est l'auteur, en entier, avec les lectures déjà faites
    actions = db.exec(select(models.ActionsSecretes).order_by(models.ActionsSecretes.created_at.desc())).all()
    mine = []
    for db_action in actions:
        if est_auteur(db, user, db_action):
            _reveler_si_echue(db, db_action)
            mine.append(action_complete(db, db_action))
    return mine

def lire_action(db: Session, user: schemas.Users, ID: int):
    # Contenu d'une action scellée : l'auteur la lit librement, un administrateur ou modérateur RP laisse une trace
    db_action = _require_action(db, ID)
    if db_action.revealed_at is None and not est_auteur(db, user, db_action):
        if not crud_conflits.is_moderateur(user):
            raise HTTPException(status_code=403, detail="Cette action est scellée jusqu'à sa révélation")
        role = "administrateur" if user.is_admin else "modérateur RP"
        db.add(models.ActionSecreteLectures(action_id=db_action.id, user_id=user.id, role=role))
        db.commit()
        crud_notifications.notifier(db, auteurs(db, db_action), "lecture", f"Lecture tracée de votre action {code_action(db_action)}",
                                    f"{user.full_name or user.username} ({role}) a lu « {db_action.title} » avant sa révélation.", _lien(db_action), sauf=user.id)
    return {"action": action_complete(db, db_action)}

#endregion
#region Dépôt

def create_action(db: Session, user: schemas.Users, body: schemas.ActionSecreteCreate):
    if body.entity_type not in ENTITY_TYPES:
        raise HTTPException(status_code=400, detail="Une action se dépose au nom d'un personnage, d'une civilisation ou d'une religion")
    title, content = (body.title or "").strip(), (body.content or "").strip()
    if not title or not content:
        raise HTTPException(status_code=400, detail="Le titre et le contenu de l'action sont obligatoires")

    entity = _entity(db, body.entity_type, body.entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="L'auteur choisi n'existe pas")
    if body.entity_type == "personnage":
        if entity.user_id != user.id:
            raise HTTPException(status_code=403, detail="On ne dépose une action qu'au nom de ses propres personnages")
        entity_title = entity.name
    else:
        crud_conflits._require_entity_rights(db, user, body.entity_type, body.entity_id)
        entity_title = entity.title

    if body.guerre_id is not None:
        db_guerre = crud_conflits.get_guerre(db, body.guerre_id)
        if not db_guerre or db_guerre.status != "en_cours":
            raise HTTPException(status_code=400, detail="Une action ne se rattache qu'à une guerre en cours")

    # Heure locale du serveur, comme created_at ; une date avec fuseau est convertie
    reveal_at = body.reveal_at
    if reveal_at and reveal_at.tzinfo:
        reveal_at = reveal_at.astimezone().replace(tzinfo=None)
    if reveal_at and reveal_at <= dt.datetime.now():
        raise HTTPException(status_code=400, detail="La date de révélation automatique doit être dans le futur")

    sel = secrets.token_hex(16)
    db_action = models.ActionsSecretes(
        title=title,
        content=content,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        entity_title=entity_title,
        guerre_id=body.guerre_id,
        sel=sel,
        empreinte=calculer_empreinte(sel, title, content),
        created_by=user.id,
        reveal_at=reveal_at,
        piege=bool(body.piege),
    )
    db.add(db_action)
    db.commit()
    db.refresh(db_action)
    return {"action": action_complete(db, db_action)}

#endregion
