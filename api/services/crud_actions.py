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
- Pacte secret : une civilisation, une alliance ou un commerce propose un pacte à une autre partie de ces trois sortes.
  Son texte et son empreinte sont figés dès la proposition ; la partie invitée le signe tel quel ou le refuse, celle qui
  propose peut le retirer tant qu'il n'est pas signé. Il faut l'accord d'un second joueur : celui qui propose ne signe
  pas. Non signé, il n'existe que pour les deux parties ; signé, il entre au registre comme une action scellée (rien ne
  dit alors que c'est un pacte, ni entre qui). Chaque partie peut le révéler seule : trahir un pacte reste possible.
"""
import datetime as dt
import hashlib
import secrets

from fastapi import HTTPException
from sqlmodel import Session, select

from ..db import models, schemas
from .crud import get_commerce_by_id
from . import annonces, crud_conflits, crud_notifications, crud_personnages

ENTITY_TYPES = ("personnage", "civilisation", "religion")
PACTE_TYPES = ("civilisation", "alliance", "commerce")


#region Outils

def code_action(db_action: models.ActionsSecretes) -> str:
    return f"AS-{db_action.id:04d}"

def calculer_empreinte(sel: str, title: str, content: str) -> str:
    # Même calcul côté site (vérification après révélation) : SHA-256 hexadécimal de « sel\ntitre\ncontenu »
    return hashlib.sha256(f"{sel}\n{title}\n{content}".encode("utf-8")).hexdigest()

def est_pacte(db_action: models.ActionsSecretes) -> bool:
    return db_action.partie_type is not None

def est_scellee(db_action: models.ActionsSecretes) -> bool:
    # Au registre public : toute action, et les pactes une fois signés (une proposition n'existe que pour ses deux parties)
    return not est_pacte(db_action) or db_action.pacte_statut == "signe"

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
    if entity_type == "alliance":
        return crud_conflits.get_alliance(db, entity_id)
    if entity_type == "commerce":
        return get_commerce_by_id(db, entity_id)
    return crud_conflits._get_entity(db, entity_type, entity_id)

def _summary(db: Session, entity_type: str, entity_id: int, archived_title: str | None = None):
    entity = _entity(db, entity_type, entity_id)
    if entity_type in ("civilisation", "religion"):
        return crud_conflits._entity_summary(db, entity_type, entity_id, archived_title)
    if not entity:
        return {"type": entity_type, "id": entity_id, "title": archived_title or "Entité supprimée", "deleted": True}
    if entity_type == "personnage":
        return {"type": "personnage", "id": entity.id, "title": entity.name}
    summary = {"type": entity_type, "id": entity.id, "title": entity.title}
    if entity_type == "alliance":
        summary.update({"color": entity.color, "icon": entity.icon})
    return summary

def _entity_summary(db: Session, db_action: models.ActionsSecretes):
    return _summary(db, db_action.entity_type, db_action.entity_id, db_action.entity_title)

def _partie_summary(db: Session, db_action: models.ActionsSecretes):
    return _summary(db, db_action.partie_type, db_action.partie_id, db_action.partie_title)

def _gere(db: Session, user: schemas.Users, entity_type: str, entity_id: int) -> bool:
    # Joueur du personnage ; Fondateur / Admin de la civilisation, de la religion, du commerce (ou de son dirigeant),
    # ou de la civilisation chef de file de l'alliance
    return user.id in crud_notifications.gestionnaires(db, entity_type, entity_id)

def _peut_agir(db: Session, user: schemas.Users, entity_type: str, entity_id: int) -> bool:
    # Agir au nom d'une entité : ses gestionnaires, ou un administrateur du site
    return bool(user and not user.is_disabled and (user.is_admin or _gere(db, user, entity_type, entity_id)))

def est_auteur(db: Session, user: schemas.Users | None, db_action: models.ActionsSecretes) -> bool:
    # Le joueur qui l'a déposée, le joueur du personnage, ou un Fondateur / Admin de l'entité ; pour un pacte, aussi
    # ceux de la partie invitée. Être administrateur du site ne suffit pas : sa lecture doit rester tracée.
    if not user or user.is_disabled:
        return False
    if db_action.created_by == user.id or _gere(db, user, db_action.entity_type, db_action.entity_id):
        return True
    return est_pacte(db_action) and _gere(db, user, db_action.partie_type, db_action.partie_id)

def _proposants(db: Session, db_action: models.ActionsSecretes) -> set:
    return {db_action.created_by} | crud_notifications.gestionnaires(db, db_action.entity_type, db_action.entity_id)

def _invites(db: Session, db_action: models.ActionsSecretes) -> set:
    return crud_notifications.gestionnaires(db, db_action.partie_type, db_action.partie_id) if est_pacte(db_action) else set()

def auteurs(db: Session, db_action: models.ActionsSecretes) -> set:
    # Comptes à prévenir de ce qui arrive à l'action : son déposant et ceux qui agissent au nom de son auteur
    # (et, pour un pacte, au nom de la partie invitée)
    return _proposants(db, db_action) | _invites(db, db_action)

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
        "pacte": _pacte_infos(db, db_action) if est_pacte(db_action) else None,
    }

def _pacte_infos(db: Session, db_action: models.ActionsSecretes):
    return {
        "partie": _partie_summary(db, db_action),
        "statut": db_action.pacte_statut,
        "reponse_at": db_action.pacte_reponse_at,
        "reponse_by": crud_conflits._user_summary(db, db_action.pacte_reponse_by),
        # Le motif d'un refus ne regarde que les deux parties : un pacte refusé n'est jamais public
        "motif": db_action.pacte_motif,
    }

#endregion
#region Révélation

def _annoncer_revelation(db: Session, db_action: models.ActionsSecretes):
    # Salon Discord « actions » (platforms.discord.channels.actions), avec le lien si site_url est configuré
    entite = _entity_summary(db, db_action)["title"]
    pacte = est_pacte(db_action)
    if pacte:
        partie = _partie_summary(db, db_action)["title"]
        text = f"🤝 Pacte secret **{code_action(db_action)}** révélé : **{db_action.title}**, entre {entite} et {partie}, signé le {db_action.pacte_reponse_at:%d/%m/%Y à %H:%M}."
    else:
        text = f"🔓 Action secrète **{code_action(db_action)}** révélée : **{db_action.title}** ({entite}), scellée le {db_action.created_at:%d/%m/%Y à %H:%M}."
    if db_action.reveal_mode == "date":
        revelation = "À la date fixée au dépôt"
    elif db_action.reveal_mode == "moderateur":
        revelation = f"Par la modération RP. Motif : {db_action.reveal_motif}"
    else:
        revelation = "Par son auteur"
    guerre = db.get(models.Guerres, db_action.guerre_id) if db_action.guerre_id else None
    annonces.annoncer("actions", "🤝 Pacte secret révélé" if pacte else "🔓 Action secrète révélée", text, _lien(db_action), [
        annonces.champ("Code", code_action(db_action)),
        annonces.champ("Entre", f"{entite} et {partie}" if pacte else None),
        annonces.champ("Au nom de", None if pacte else entite),
        annonces.champ("Proposé le" if pacte else "Scellée le", f"{db_action.created_at:%d/%m/%Y à %H:%M}"),
        annonces.champ("Signé le", f"{db_action.pacte_reponse_at:%d/%m/%Y à %H:%M}" if pacte else None),
        annonces.champ("Révélée", revelation),
        annonces.champ("Guerre", guerre.title if guerre else None),
        annonces.champ("Piège", "Oui : la modération RP jugera s'il est mortel" if db_action.piege else None),
        annonces.champ("Contenu", db_action.content, en_ligne=False),
    ])

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
    nom, e = ("pacte", "") if est_pacte(db_action) else ("action", "e")
    if est_pacte(db_action):
        entite = f"Pacte entre {entite} et {_partie_summary(db, db_action)['title']}"
        comment = comment.replace("par son auteur", "par l'une des parties")
    crud_notifications.notifier(db, auteurs(db, db_action), "revelation", f"Votre {nom} {code} est révélé{e}", f"« {db_action.title} », révélé{e} {comment}.", _lien(db_action), sauf=db_action.revealed_by)
    if db_action.guerre_id:
        concernes = crud_conflits._gestionnaires_guerre(db, db_action.guerre_id) - auteurs(db, db_action)
        crud_notifications.notifier(db, concernes, "revelation", f"Action {code} révélée : {db_action.title}", f"{entite}, dans une guerre où vous êtes engagé.", _lien(db_action), sauf=db_action.revealed_by)
    if db_action.piege:
        crud_notifications.notifier(db, crud_notifications.moderateurs(db) - auteurs(db, db_action), "moderation", f"Piège à juger : {code}", f"« {db_action.title} » ({entite}) est révélée.", "/moderation", sauf=db_action.revealed_by)

def _reveler_si_echue(db: Session, db_action: models.ActionsSecretes):
    # Révélation automatique, faite à la première lecture après la date fixée (pas de tâche planifiée)
    if db_action.revealed_at is None and est_scellee(db_action) and db_action.reveal_at and db_action.reveal_at <= dt.datetime.now():
        _reveler(db, db_action, "date", when=db_action.reveal_at)

def reveler(db: Session, user: schemas.Users, ID: int, body: schemas.ActionSecreteRevelation):
    db_action = _require_action(db, ID)
    if db_action.revealed_at is not None:
        raise HTTPException(status_code=400, detail="Cette action est déjà révélée")
    if not est_scellee(db_action):
        raise HTTPException(status_code=400, detail="Un pacte ne se révèle qu'une fois signé par les deux parties")
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
    annonces.annoncer("actions", "☠️ Piège jugé", text, _lien(db_action), [
        annonces.champ("Code", code_action(db_action)),
        annonces.champ("Action", db_action.title),
        annonces.champ("Au nom de", entite),
        annonces.champ("Verdict", "Mortel" if db_action.piege_verdict == "mortel" else "Simple blessure"),
        annonces.champ("Décision de la modération", db_action.piege_note, en_ligne=False),
    ])

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
    actions = [db_action for db_action in db.exec(select(models.ActionsSecretes).order_by(models.ActionsSecretes.created_at.desc())).all() if est_scellee(db_action)]
    for db_action in actions:
        _reveler_si_echue(db, db_action)
    return [action_publique(db, db_action) for db_action in actions]

def read_action(db: Session, ID: int):
    db_action = _require_action(db, ID)
    if not est_scellee(db_action):
        raise HTTPException(status_code=404, detail="Cette action secrète n'existe pas")
    return {"action": action_publique(db, db_action)}

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
            infos = action_complete(db, db_action)
            if est_pacte(db_action) and db_action.pacte_statut == "en_attente":
                # Boutons proposés : signer ou refuser (partie invitée), retirer (partie qui propose)
                infos["peut_signer"] = user.id != db_action.created_by and _gere(db, user, db_action.partie_type, db_action.partie_id)
                infos["peut_retirer"] = user.id == db_action.created_by or _gere(db, user, db_action.entity_type, db_action.entity_id)
            mine.append(infos)
    return mine

def lire_action(db: Session, user: schemas.Users, ID: int):
    # Contenu d'une action scellée : l'auteur la lit librement, un administrateur ou modérateur RP laisse une trace
    db_action = _require_action(db, ID)
    if not est_scellee(db_action) and not est_auteur(db, user, db_action):
        raise HTTPException(status_code=404, detail="Cette action secrète n'existe pas")
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

def _texte(body) -> tuple[str, str]:
    title, content = (body.title or "").strip(), (body.content or "").strip()
    if not title or not content:
        raise HTTPException(status_code=400, detail="Le titre et le contenu de l'action sont obligatoires")
    return title, content

def _verifier_guerre(db: Session, guerre_id: int | None):
    if guerre_id is not None:
        db_guerre = crud_conflits.get_guerre(db, guerre_id)
        if not db_guerre or db_guerre.status != "en_cours":
            raise HTTPException(status_code=400, detail="Une action ne se rattache qu'à une guerre en cours")

def _date_revelation(reveal_at: dt.datetime | None) -> dt.datetime | None:
    # Heure locale du serveur, comme created_at ; une date avec fuseau est convertie
    if reveal_at and reveal_at.tzinfo:
        reveal_at = reveal_at.astimezone().replace(tzinfo=None)
    if reveal_at and reveal_at <= dt.datetime.now():
        raise HTTPException(status_code=400, detail="La date de révélation automatique doit être dans le futur")
    return reveal_at

def create_action(db: Session, user: schemas.Users, body: schemas.ActionSecreteCreate):
    if body.entity_type not in ENTITY_TYPES:
        raise HTTPException(status_code=400, detail="Une action se dépose au nom d'un personnage, d'une civilisation ou d'une religion")
    title, content = _texte(body)

    entity = _entity(db, body.entity_type, body.entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="L'auteur choisi n'existe pas")
    if body.entity_type == "personnage":
        # Un administrateur du site choisit parmi tous les personnages
        if not crud_personnages.can_manage(user, entity):
            raise HTTPException(status_code=403, detail="On ne dépose une action qu'au nom de ses propres personnages")
        entity_title = entity.name
    else:
        crud_conflits._require_entity_rights(db, user, body.entity_type, body.entity_id)
        entity_title = entity.title

    _verifier_guerre(db, body.guerre_id)
    reveal_at = _date_revelation(body.reveal_at)

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
#region Pactes

TYPE_LABELS = {"civilisation": "la civilisation", "alliance": "l'alliance", "commerce": "le commerce"}

def create_pacte(db: Session, user: schemas.Users, body: schemas.PacteCreate):
    if body.entity_type not in PACTE_TYPES or body.partie_type not in PACTE_TYPES:
        raise HTTPException(status_code=400, detail="Un pacte se conclut entre civilisations, alliances ou commerces")
    if (body.entity_type, body.entity_id) == (body.partie_type, body.partie_id):
        raise HTTPException(status_code=400, detail="Un pacte se conclut entre deux parties différentes")
    title, content = _texte(body)

    entity = _entity(db, body.entity_type, body.entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="La partie qui propose le pacte n'existe pas")
    partie = _entity(db, body.partie_type, body.partie_id)
    if not partie:
        raise HTTPException(status_code=404, detail="La partie invitée à signer n'existe pas")
    if not _peut_agir(db, user, body.entity_type, body.entity_id):
        detail = "Seuls le fondateur et les admins de la civilisation chef de file proposent un pacte au nom de l'alliance" if body.entity_type == "alliance" \
            else f"Seuls le fondateur et les admins de {TYPE_LABELS[body.entity_type]} proposent un pacte en son nom"
        raise HTTPException(status_code=403, detail=detail)
    _verifier_guerre(db, body.guerre_id)
    reveal_at = _date_revelation(body.reveal_at)

    sel = secrets.token_hex(16)
    db_action = models.ActionsSecretes(
        title=title,
        content=content,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        entity_title=entity.title,
        partie_type=body.partie_type,
        partie_id=body.partie_id,
        partie_title=partie.title,
        pacte_statut="en_attente",
        guerre_id=body.guerre_id,
        sel=sel,
        empreinte=calculer_empreinte(sel, title, content),
        created_by=user.id,
        reveal_at=reveal_at,
    )
    db.add(db_action)
    db.commit()
    db.refresh(db_action)
    crud_notifications.notifier(db, _invites(db, db_action), "invitation", f"Pacte secret proposé : {title}",
                                f"{entity.title} propose un pacte secret à {partie.title}. Signez-le ou refusez-le sur la page des actions secrètes.", _lien(db_action), sauf=user.id)
    return {"action": action_complete(db, db_action)}

def _require_pacte_en_attente(db: Session, ID: int) -> models.ActionsSecretes:
    db_action = _require_action(db, ID)
    if not est_pacte(db_action):
        raise HTTPException(status_code=400, detail="Cette action n'est pas un pacte")
    if db_action.pacte_statut != "en_attente":
        raise HTTPException(status_code=400, detail="Ce pacte n'attend plus de réponse")
    return db_action

def _require_partie_invitee(db: Session, user: schemas.Users, db_action: models.ActionsSecretes):
    if not _peut_agir(db, user, db_action.partie_type, db_action.partie_id):
        raise HTTPException(status_code=403, detail="Seuls les dirigeants de la partie invitée peuvent répondre à ce pacte")

def _repondre(db: Session, user: schemas.Users, db_action: models.ActionsSecretes, statut: str, motif: str | None = None):
    db_action.pacte_statut = statut
    db_action.pacte_reponse_at = dt.datetime.now()
    db_action.pacte_reponse_by = user.id
    db_action.pacte_motif = motif
    db.add(db_action)
    db.commit()
    db.refresh(db_action)

def signer_pacte(db: Session, user: schemas.Users, ID: int):
    db_action = _require_pacte_en_attente(db, ID)
    _require_partie_invitee(db, user, db_action)
    if user.id == db_action.created_by:
        raise HTTPException(status_code=403, detail="Un pacte demande l'accord de deux joueurs : celui qui le propose ne le signe pas")
    if db_action.reveal_at and db_action.reveal_at <= dt.datetime.now():
        raise HTTPException(status_code=400, detail="Sa date de révélation automatique est passée : le pacte doit être proposé à nouveau")
    _repondre(db, user, db_action, "signe")
    crud_notifications.notifier(db, _proposants(db, db_action), "decision", f"Pacte {code_action(db_action)} signé",
                                f"{db_action.partie_title} a signé « {db_action.title} ». Il reste scellé jusqu'à sa révélation.", _lien(db_action), sauf=user.id)
    return {"action": action_complete(db, db_action)}

def refuser_pacte(db: Session, user: schemas.Users, ID: int, body: schemas.PacteRefus):
    db_action = _require_pacte_en_attente(db, ID)
    _require_partie_invitee(db, user, db_action)
    motif = (body.motif or "").strip() or None
    _repondre(db, user, db_action, "refuse", motif)
    crud_notifications.notifier(db, _proposants(db, db_action), "decision", f"Pacte {code_action(db_action)} refusé",
                                f"{db_action.partie_title} refuse « {db_action.title} »." + (f" Motif : {motif}" if motif else ""), _lien(db_action), sauf=user.id)
    return {"action": action_complete(db, db_action)}

def retirer_pacte(db: Session, user: schemas.Users, ID: int):
    # La partie qui propose reprend sa proposition tant qu'elle n'est pas signée
    db_action = _require_pacte_en_attente(db, ID)
    if user.id != db_action.created_by and not _peut_agir(db, user, db_action.entity_type, db_action.entity_id):
        raise HTTPException(status_code=403, detail="Seuls les dirigeants de la partie qui propose peuvent retirer ce pacte")
    _repondre(db, user, db_action, "annule")
    crud_notifications.notifier(db, _invites(db, db_action), "decision", f"Pacte {code_action(db_action)} retiré",
                                f"{db_action.entity_title} retire sa proposition « {db_action.title} ».", _lien(db_action), sauf=user.id)
    return {"action": action_complete(db, db_action)}

def parties_pactes(db: Session, user: schemas.Users):
    # Parties possibles d'un pacte : civilisations, alliances et commerces publics, et ceux qu'on dirige ;
    # gere : l'utilisateur peut proposer en leur nom (tous pour un administrateur du site)
    parties = []
    for entity_type, model in (("civilisation", models.Civilisations), ("alliance", models.Alliances), ("commerce", models.Commerces)):
        for entity in db.exec(select(model)).all():
            gere = _peut_agir(db, user, entity_type, entity.id)
            if entity.is_public is False and not gere:
                continue
            parties.append({"type": entity_type, "id": entity.id, "title": entity.title, "gere": gere})
    return sorted(parties, key=lambda partie: (PACTE_TYPES.index(partie["type"]), (partie["title"] or "").lower()))

#endregion
