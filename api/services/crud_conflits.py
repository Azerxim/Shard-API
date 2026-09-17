"""
Alliances et guerres.

- Alliances militaires ou diplomatiques entre civilisations : un chef de file, des membres et des observateurs.
  On entre par invitation de l'alliance ou par demande de la civilisation, acceptée par l'autre partie.
- Guerres militaires (entre civilisations) ou de religion (entre religions, que des civilisations peuvent rejoindre).
  Déclarée par le fondateur ou un admin du camp attaquant, une guerre reste privée tant qu'un modérateur RP ne l'a pas
  validée (Codex : « Les guerres se déclarent, elles ne s'improvisent pas »). Une guerre commencée est archivée, jamais supprimée.

Agir au nom d'une civilisation ou d'une religion demande d'en être Fondateur ou Admin (ou administrateur du site).
"""
import datetime as dt

from fastapi import HTTPException
from sqlmodel import Session, select

from ..core import utils
from ..db import models, schemas
from .crud import (
    announce_discord,
    delete_cartographies_by_types,
    get_civilisation_by_id,
    get_members_of_civilisation,
    get_members_of_religion,
    get_religion_by_id,
    get_user_by_id,
)

ALLIANCE_TYPES = ("Militaire", "Diplomatique")
ALLIANCE_ROLE_ORDER = {"Chef de file": 0, "Membre": 1, "Observateur": 2}
GUERRE_TYPES = {"Militaire": "civilisation", "Religion": "religion"}
CAMPS = ("attaquant", "defenseur")
GUERRE_STATUTS_PUBLICS = ("en_cours", "terminee")
ENTITY_LABELS = {"civilisation": "la civilisation", "religion": "la religion"}
CAMP_NAMES = {"attaquant": "attaquant", "defenseur": "défenseur"}
# Faits racontés dans la chronologie (les autres types sont inscrits automatiquement) ; les premiers sont annoncés sur Discord
EVENEMENTS_RACONTES = {"bataille": "Bataille", "siege": "Siège", "traite": "Traité", "autre": "Événement"}
EVENEMENTS_ANNONCES = ("bataille", "siege", "traite")


#region Droits et entités

def is_moderateur(user: schemas.Users | None) -> bool:
    return bool(user and not user.is_disabled and (user.is_admin or user.is_moderateur))

def _require_moderateur(user: schemas.Users):
    if not is_moderateur(user):
        raise HTTPException(status_code=403, detail="Seul un modérateur RP ou un administrateur peut le faire")

def _get_entity(db: Session, entity_type: str, entity_id: int):
    if entity_type == "civilisation":
        return get_civilisation_by_id(db, entity_id)
    if entity_type == "religion":
        return get_religion_by_id(db, entity_id)
    return None

def can_manage_entity(db: Session, user: schemas.Users | None, entity_type: str, entity_id: int) -> bool:
    # Fondateur ou Admin de la civilisation / religion, ou administrateur du site
    if not user or user.is_disabled:
        return False
    if user.is_admin:
        return True
    members = get_members_of_civilisation(db, entity_id, limit=10000) if entity_type == "civilisation" else get_members_of_religion(db, entity_id, limit=10000)
    return any(member.user_id == user.id and member.role in ("Fondateur", "Admin") for member in members)

def _require_entity_rights(db: Session, user: schemas.Users, entity_type: str, entity_id: int):
    if not can_manage_entity(db, user, entity_type, entity_id):
        raise HTTPException(status_code=403, detail=f"Seuls le fondateur et les admins de {ENTITY_LABELS[entity_type]} peuvent agir en son nom")

def _entity_summary(db: Session, entity_type: str, entity_id: int, archived_title: str | None = None):
    entity = _get_entity(db, entity_type, entity_id)
    if not entity:
        # deleted : l'entité n'existe plus (lien inutile) ; son nom reste dans les archives des guerres
        return {"type": entity_type, "id": entity_id, "title": archived_title or "Entité supprimée", "is_public": False, "deleted": True}
    summary = {"type": entity_type, "id": entity.id, "title": entity.title, "is_public": entity.is_public}
    if entity_type == "religion":
        summary.update({"color": entity.color, "icon": entity.icon})
    return summary

def _user_summary(db: Session, user_id: int | None):
    user = get_user_by_id(db, user_id) if user_id else None
    return {"id": user.id, "username": user.username, "full_name": user.full_name} if user else None

#endregion
#region Alliances

def get_alliance(db: Session, ID: int):
    return db.exec(select(models.Alliances).where(models.Alliances.id == ID)).first()

def _require_alliance(db: Session, ID: int):
    db_alliance = get_alliance(db, ID)
    if not db_alliance:
        raise HTTPException(status_code=404, detail="L'alliance n'existe pas")
    return db_alliance

def _alliance_membres(db: Session, allianceID: int):
    return db.exec(select(models.AllianceMembres).where(models.AllianceMembres.alliance_id == allianceID)).all()

def _alliance_membre(db: Session, allianceID: int, civilisationID: int):
    statement = select(models.AllianceMembres).where(
        models.AllianceMembres.alliance_id == allianceID,
        models.AllianceMembres.civilisation_id == civilisationID
    )
    return db.exec(statement).first()

def _alliance_chef(db: Session, allianceID: int):
    return next((membre for membre in _alliance_membres(db, allianceID) if membre.role == "Chef de file"), None)

def _require_alliance_chef(db: Session, user: schemas.Users, db_alliance: models.Alliances):
    chef = _alliance_chef(db, db_alliance.id)
    if not chef or not can_manage_entity(db, user, "civilisation", chef.civilisation_id):
        raise HTTPException(status_code=403, detail="Seuls le fondateur et les admins de la civilisation chef de file peuvent gérer l'alliance")

def _pending_invitations(db: Session, allianceID: int | None = None):
    statement = select(models.AllianceInvitations).where(models.AllianceInvitations.status == "en_attente")
    if allianceID is not None:
        statement = statement.where(models.AllianceInvitations.alliance_id == allianceID)
    return db.exec(statement).all()

def _invitation_infos(db: Session, invitation: models.AllianceInvitations):
    db_alliance = get_alliance(db, invitation.alliance_id)
    return {
        "id": invitation.id,
        "direction": invitation.direction,
        "status": invitation.status,
        "created_at": invitation.created_at,
        "alliance": {"id": db_alliance.id, "title": db_alliance.title, "color": db_alliance.color, "icon": db_alliance.icon} if db_alliance else None,
        "civilisation": _entity_summary(db, "civilisation", invitation.civilisation_id),
    }

def alliance_infos(db: Session, db_alliance: models.Alliances, details: bool = False):
    membres = sorted(_alliance_membres(db, db_alliance.id), key=lambda membre: (ALLIANCE_ROLE_ORDER.get(membre.role, 9), membre.joined_at))
    membres_infos = [
        {"civilisation": _entity_summary(db, "civilisation", membre.civilisation_id), "role": membre.role, "joined_at": membre.joined_at}
        for membre in membres
    ]
    infos = {
        "alliance": db_alliance,
        "membres": membres_infos,
        "chef_de_file": next((membre["civilisation"] for membre in membres_infos if membre["role"] == "Chef de file"), None),
    }
    if details:
        infos["invitations"] = [_invitation_infos(db, invitation) for invitation in _pending_invitations(db, db_alliance.id)]
        civilisation_ids = {membre.civilisation_id for membre in membres}
        infos["guerres"] = [
            guerre_infos(db, db_guerre)
            for db_guerre in _guerres_of_entities(db, "civilisation", civilisation_ids)
            if db_guerre.status in GUERRE_STATUTS_PUBLICS
        ]
    return infos

def list_alliances(db: Session):
    return [alliance_infos(db, db_alliance) for db_alliance in db.exec(select(models.Alliances)).all()]

def read_alliance(db: Session, ID: int):
    return alliance_infos(db, _require_alliance(db, ID), details=True)

def alliances_of_civilisation(db: Session, civilisationID: int):
    membres = db.exec(select(models.AllianceMembres).where(models.AllianceMembres.civilisation_id == civilisationID)).all()
    result = []
    for membre in membres:
        db_alliance = get_alliance(db, membre.alliance_id)
        if db_alliance:
            result.append({"alliance": db_alliance, "role": membre.role, "joined_at": membre.joined_at})
    return result

def _check_alliance_type(value: str | None):
    if value is not None and value not in ALLIANCE_TYPES:
        raise HTTPException(status_code=400, detail="Le type d'alliance doit être « Militaire » ou « Diplomatique »")

def create_alliance(db: Session, user: schemas.Users, v_alliance: schemas.AllianceCreate):
    _check_alliance_type(v_alliance.type)
    if not get_civilisation_by_id(db, v_alliance.civilisation_id):
        raise HTTPException(status_code=404, detail="La civilisation n'existe pas")
    _require_entity_rights(db, user, "civilisation", v_alliance.civilisation_id)

    db_alliance = models.Alliances(
        title=v_alliance.title,
        description=v_alliance.description,
        type=v_alliance.type or "Militaire",
        color=v_alliance.color,
        icon=v_alliance.icon,
        flag_url=v_alliance.flag_url,
        date_founded=v_alliance.date_founded,
        is_public=v_alliance.is_public if v_alliance.is_public is not None else True,
        created_at=dt.datetime.now(),
    )
    db.add(db_alliance)
    db.commit()
    db.refresh(db_alliance)
    db.add(models.AllianceMembres(alliance_id=db_alliance.id, civilisation_id=v_alliance.civilisation_id, role="Chef de file"))
    db.commit()
    return alliance_infos(db, db_alliance)

def update_alliance(db: Session, user: schemas.Users, ID: int, v_alliance: schemas.AllianceUpdate):
    db_alliance = _require_alliance(db, ID)
    _require_alliance_chef(db, user, db_alliance)
    data = v_alliance.model_dump(exclude_unset=True)
    _check_alliance_type(data.get("type"))
    if data.get("title") is None:
        data.pop("title", None)
    for key, value in data.items():
        setattr(db_alliance, key, value)
    db.add(db_alliance)
    db.commit()
    db.refresh(db_alliance)
    return alliance_infos(db, db_alliance)

def delete_alliance(db: Session, user: schemas.Users, ID: int):
    # Dissolution : membres et invitations disparaissent, les guerres gardent leurs belligérants
    db_alliance = _require_alliance(db, ID)
    _require_alliance_chef(db, user, db_alliance)
    for db_membre in _alliance_membres(db, ID):
        db.delete(db_membre)
    for db_invitation in db.exec(select(models.AllianceInvitations).where(models.AllianceInvitations.alliance_id == ID)).all():
        db.delete(db_invitation)
    for db_belligerant in db.exec(select(models.GuerreBelligerants).where(models.GuerreBelligerants.alliance_id == ID)).all():
        db_belligerant.alliance_id = None
        db.add(db_belligerant)
    db.delete(db_alliance)
    db.commit()
    return {"resultat": "Alliance dissoute"}

def _check_can_join(db: Session, allianceID: int, civilisationID: int):
    if not get_civilisation_by_id(db, civilisationID):
        raise HTTPException(status_code=404, detail="La civilisation n'existe pas")
    if _alliance_membre(db, allianceID, civilisationID):
        raise HTTPException(status_code=400, detail="Cette civilisation fait déjà partie de l'alliance")
    if any(invitation.civilisation_id == civilisationID for invitation in _pending_invitations(db, allianceID)):
        raise HTTPException(status_code=400, detail="Une invitation ou une demande est déjà en attente pour cette civilisation")

def invite_civilisation(db: Session, user: schemas.Users, ID: int, civilisationID: int):
    db_alliance = _require_alliance(db, ID)
    _require_alliance_chef(db, user, db_alliance)
    _check_can_join(db, ID, civilisationID)
    invitation = models.AllianceInvitations(alliance_id=ID, civilisation_id=civilisationID, direction="invitation", created_by=user.id)
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return {"resultat": "Invitation envoyée", "invitation": _invitation_infos(db, invitation)}

def request_join(db: Session, user: schemas.Users, ID: int, civilisationID: int):
    db_alliance = _require_alliance(db, ID)
    _require_entity_rights(db, user, "civilisation", civilisationID)
    if db_alliance.is_public is False:
        raise HTTPException(status_code=403, detail="Cette alliance est privée : elle recrute uniquement sur invitation")
    _check_can_join(db, ID, civilisationID)
    invitation = models.AllianceInvitations(alliance_id=ID, civilisation_id=civilisationID, direction="demande", created_by=user.id)
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return {"resultat": "Demande envoyée", "invitation": _invitation_infos(db, invitation)}

def _require_pending_invitation(db: Session, invitationID: int):
    invitation = db.exec(select(models.AllianceInvitations).where(models.AllianceInvitations.id == invitationID)).first()
    if not invitation:
        raise HTTPException(status_code=404, detail="L'invitation n'existe pas")
    if invitation.status != "en_attente":
        raise HTTPException(status_code=400, detail="Cette invitation a déjà reçu une réponse")
    return invitation

def can_answer_invitation(db: Session, user: schemas.Users, invitation: models.AllianceInvitations) -> bool:
    # Une invitation se règle côté civilisation, une demande côté chef de file
    if invitation.direction == "invitation":
        return can_manage_entity(db, user, "civilisation", invitation.civilisation_id)
    chef = _alliance_chef(db, invitation.alliance_id)
    return bool(chef and can_manage_entity(db, user, "civilisation", chef.civilisation_id))

def answer_invitation(db: Session, user: schemas.Users, invitationID: int, accepter: bool):
    invitation = _require_pending_invitation(db, invitationID)
    if not can_answer_invitation(db, user, invitation):
        raise HTTPException(status_code=403, detail="Vous ne pouvez pas répondre à cette invitation")
    invitation.status = "acceptee" if accepter else "refusee"
    invitation.answered_at = dt.datetime.now()
    db.add(invitation)
    if accepter and not _alliance_membre(db, invitation.alliance_id, invitation.civilisation_id):
        db.add(models.AllianceMembres(alliance_id=invitation.alliance_id, civilisation_id=invitation.civilisation_id, role="Membre"))
    db.commit()
    return {"resultat": "Invitation acceptée" if accepter else "Invitation refusée"}

def cancel_invitation(db: Session, user: schemas.Users, invitationID: int):
    # L'auteur retire son invitation (chef de file) ou sa demande (civilisation)
    invitation = _require_pending_invitation(db, invitationID)
    if invitation.direction == "invitation":
        _require_alliance_chef(db, user, _require_alliance(db, invitation.alliance_id))
    else:
        _require_entity_rights(db, user, "civilisation", invitation.civilisation_id)
    invitation.status = "annulee"
    invitation.answered_at = dt.datetime.now()
    db.add(invitation)
    db.commit()
    return {"resultat": "Invitation annulée"}

def _require_membre(db: Session, allianceID: int, civilisationID: int):
    db_membre = _alliance_membre(db, allianceID, civilisationID)
    if not db_membre:
        raise HTTPException(status_code=404, detail="Cette civilisation ne fait pas partie de l'alliance")
    return db_membre

def update_membre(db: Session, user: schemas.Users, ID: int, civilisationID: int, role: str):
    db_alliance = _require_alliance(db, ID)
    _require_alliance_chef(db, user, db_alliance)
    if role not in ("Membre", "Observateur"):
        raise HTTPException(status_code=400, detail="Le rôle doit être « Membre » ou « Observateur » (le chef de file change par transfert)")
    db_membre = _require_membre(db, ID, civilisationID)
    if db_membre.role == "Chef de file":
        raise HTTPException(status_code=400, detail="Transférer d'abord le rôle de chef de file")
    db_membre.role = role
    db.add(db_membre)
    db.commit()
    return alliance_infos(db, db_alliance)

def transfer_chef(db: Session, user: schemas.Users, ID: int, civilisationID: int):
    db_alliance = _require_alliance(db, ID)
    _require_alliance_chef(db, user, db_alliance)
    target = _require_membre(db, ID, civilisationID)
    if target.role == "Chef de file":
        raise HTTPException(status_code=400, detail="Cette civilisation est déjà chef de file")
    chef = _alliance_chef(db, ID)
    if chef:
        chef.role = "Membre"
        db.add(chef)
    target.role = "Chef de file"
    db.add(target)
    db.commit()
    return alliance_infos(db, db_alliance)

def remove_membre(db: Session, user: schemas.Users, ID: int, civilisationID: int):
    # Exclusion par le chef de file, ou départ décidé par la civilisation elle-même
    db_alliance = _require_alliance(db, ID)
    db_membre = _require_membre(db, ID, civilisationID)
    if db_membre.role == "Chef de file":
        raise HTTPException(status_code=400, detail="Le chef de file ne peut pas quitter l'alliance : transférer d'abord son rôle")
    if not can_manage_entity(db, user, "civilisation", civilisationID):
        _require_alliance_chef(db, user, db_alliance)
    db.delete(db_membre)
    db.commit()
    return alliance_infos(db, db_alliance)

def invitations_for_user(db: Session, user: schemas.Users):
    # Invitations et demandes auxquelles l'utilisateur peut répondre
    return [_invitation_infos(db, invitation) for invitation in _pending_invitations(db) if can_answer_invitation(db, user, invitation)]

#endregion
#region Guerres

def get_guerre(db: Session, ID: int):
    return db.exec(select(models.Guerres).where(models.Guerres.id == ID)).first()

def _belligerants(db: Session, guerreID: int):
    return db.exec(select(models.GuerreBelligerants).where(models.GuerreBelligerants.guerre_id == guerreID)).all()

def _camp_leader(db: Session, guerreID: int, camp: str):
    return next((b for b in _belligerants(db, guerreID) if b.camp == camp and b.is_leader), None)

def _guerres_of_entities(db: Session, entity_type: str, entity_ids):
    if not entity_ids:
        return []
    statement = select(models.GuerreBelligerants).where(
        models.GuerreBelligerants.entity_type == entity_type,
        models.GuerreBelligerants.entity_id.in_(list(entity_ids)),
        models.GuerreBelligerants.status == "engage"
    )
    guerre_ids = {b.guerre_id for b in db.exec(statement).all()}
    guerres = [get_guerre(db, guerre_id) for guerre_id in guerre_ids]
    return sorted([g for g in guerres if g], key=lambda g: g.declared_at, reverse=True)

def can_see_guerre(db: Session, user: schemas.Users | None, db_guerre: models.Guerres) -> bool:
    # Publique une fois validée ; avant, seulement pour les modérateurs et les parties concernées
    if db_guerre.status in GUERRE_STATUTS_PUBLICS:
        return True
    if is_moderateur(user):
        return True
    return any(can_manage_entity(db, user, b.entity_type, b.entity_id) for b in _belligerants(db, db_guerre.id))

def guerre_infos(db: Session, db_guerre: models.Guerres):
    camps = {camp: [] for camp in CAMPS}
    for b in sorted(_belligerants(db, db_guerre.id), key=lambda b: (not b.is_leader, b.status != "engage", b.joined_at)):
        db_alliance = get_alliance(db, b.alliance_id) if b.alliance_id else None
        camps.setdefault(b.camp, []).append({
            "id": b.id,
            "camp": b.camp,
            "is_leader": bool(b.is_leader),
            "status": b.status,
            "joined_at": b.joined_at,
            "entite": _entity_summary(db, b.entity_type, b.entity_id, b.entity_title),
            "alliance": {"id": db_alliance.id, "title": db_alliance.title} if db_alliance else None,
        })
    return {
        "guerre": db_guerre,
        "camps": camps,
        "declarant": _user_summary(db, db_guerre.declared_by),
        "moderateur": _user_summary(db, db_guerre.moderator_id),
    }

def _leaders(db: Session, guerreID: int):
    # Noms des chefs de camp : (attaquant, défenseur)
    titles = {}
    for b in _belligerants(db, guerreID):
        if b.is_leader and b.camp not in titles:
            titles[b.camp] = _entity_summary(db, b.entity_type, b.entity_id, b.entity_title)["title"]
    return titles.get("attaquant", "?"), titles.get("defenseur", "?")

def _add_evenement(db: Session, guerreID: int, kind: str, title: str, description: str | None = None, camp: str | None = None,
                   date_rp: dt.date | None = None, user: schemas.Users | None = None, auto: bool = True):
    # Sans commit : l'étape est validée avec l'action qui la produit
    db.add(models.GuerreEvenements(
        guerre_id=guerreID, type=kind, title=title, description=description, camp=camp,
        date_rp=date_rp, is_auto=auto, created_by=user.id if user else None,
    ))

def evenement_infos(db: Session, evenement: models.GuerreEvenements):
    return {
        "id": evenement.id,
        "type": evenement.type,
        "title": evenement.title,
        "description": evenement.description,
        "camp": evenement.camp,
        "date_rp": evenement.date_rp,
        "is_auto": bool(evenement.is_auto),
        "created_at": evenement.created_at,
        "created_by": evenement.created_by,
        "auteur": _user_summary(db, evenement.created_by),
    }

def _evenements(db: Session, guerreID: int):
    # Ordre d'inscription : les dates RP sont affichées, mais ne se comparent pas aux dates réelles des étapes automatiques
    statement = select(models.GuerreEvenements).where(models.GuerreEvenements.guerre_id == guerreID)
    return sorted(db.exec(statement).all(), key=lambda evenement: (evenement.created_at, evenement.id))

def guerre_details(db: Session, db_guerre: models.Guerres):
    # Fiche complète : camps et chronologie
    return {**guerre_infos(db, db_guerre), "evenements": [evenement_infos(db, e) for e in _evenements(db, db_guerre.id)]}

def _annoncer(db_guerre: models.Guerres, text: str):
    # Salon Discord « guerres » (platforms.discord.channels.guerres), avec le lien de la guerre si site_url est configuré
    site = ((utils.PLATFORMS or {}).get("discord") or {}).get("site_url")
    announce_discord("guerres", f"{text}\n{str(site).rstrip('/')}/guerre/{db_guerre.id}" if site else text)

def _require_visible_guerre(db: Session, user: schemas.Users | None, ID: int):
    db_guerre = get_guerre(db, ID)
    if not db_guerre or not can_see_guerre(db, user, db_guerre):
        raise HTTPException(status_code=404, detail="La guerre n'existe pas")
    return db_guerre

def list_guerres_publiques(db: Session):
    statement = select(models.Guerres).where(models.Guerres.status.in_(GUERRE_STATUTS_PUBLICS))
    guerres = sorted(db.exec(statement).all(), key=lambda g: g.declared_at, reverse=True)
    return [guerre_infos(db, g) for g in guerres]

def read_guerre(db: Session, ID: int, user: schemas.Users | None = None):
    return guerre_details(db, _require_visible_guerre(db, user, ID))

def guerres_of_entity(db: Session, entity_type: str, entity_id: int):
    if entity_type not in ENTITY_LABELS:
        raise HTTPException(status_code=400, detail="Type d'entité inconnu : civilisation ou religion")
    return [guerre_infos(db, g) for g in _guerres_of_entities(db, entity_type, {entity_id}) if g.status in GUERRE_STATUTS_PUBLICS]

def guerres_for_user(db: Session, user: schemas.Users):
    # Ce qui attend l'utilisateur : déclarations à valider (modérateurs), ses guerres non validées, ses appels aux armes
    en_attente = db.exec(select(models.Guerres).where(models.Guerres.status.in_(("en_attente", "refusee")))).all()
    a_valider = [guerre_infos(db, g) for g in en_attente if g.status == "en_attente"] if is_moderateur(user) else []
    mes_guerres = [
        guerre_infos(db, g) for g in en_attente
        if any(can_manage_entity(db, user, b.entity_type, b.entity_id) for b in _belligerants(db, g.id) if b.status == "engage")
    ]

    appels = []
    statement = select(models.GuerreBelligerants).where(models.GuerreBelligerants.status == "appele")
    for b in db.exec(statement).all():
        db_guerre = get_guerre(db, b.guerre_id)
        if db_guerre and db_guerre.status in ("en_attente", "en_cours") and can_manage_entity(db, user, b.entity_type, b.entity_id):
            appels.append({"belligerant_id": b.id, "camp": b.camp, "entite": _entity_summary(db, b.entity_type, b.entity_id, b.entity_title), "guerre": db_guerre})
    return {"a_valider": a_valider, "mes_guerres": mes_guerres, "appels": appels}

def declare_guerre(db: Session, user: schemas.Users, v_guerre: schemas.GuerreDeclaration):
    guerre_type = v_guerre.type or "Militaire"
    if guerre_type not in GUERRE_TYPES:
        raise HTTPException(status_code=400, detail="Le type de guerre doit être « Militaire » ou « Religion »")
    entity_type = GUERRE_TYPES[guerre_type]
    label = ENTITY_LABELS[entity_type]
    if not _get_entity(db, entity_type, v_guerre.attaquant_id) or not _get_entity(db, entity_type, v_guerre.defenseur_id):
        raise HTTPException(status_code=404, detail=f"L'attaquant et le défenseur doivent exister ({label})")
    if v_guerre.attaquant_id == v_guerre.defenseur_id:
        raise HTTPException(status_code=400, detail="Un camp ne peut pas se déclarer la guerre à lui-même")
    _require_entity_rights(db, user, entity_type, v_guerre.attaquant_id)

    # Pas deux guerres ouvertes entre les mêmes chefs de camp
    for g in db.exec(select(models.Guerres).where(models.Guerres.status.in_(("en_attente", "en_cours")))).all():
        leaders = {(b.entity_type, b.entity_id) for b in _belligerants(db, g.id) if b.is_leader}
        if leaders == {(entity_type, v_guerre.attaquant_id), (entity_type, v_guerre.defenseur_id)}:
            raise HTTPException(status_code=400, detail=f"Une guerre est déjà ouverte entre ces deux camps : « {g.title} »")

    db_guerre = models.Guerres(
        title=v_guerre.title,
        type=guerre_type,
        casus_belli=v_guerre.casus_belli,
        description=v_guerre.description,
        status="en_attente",
        declared_by=user.id,
    )
    db.add(db_guerre)
    db.commit()
    db.refresh(db_guerre)
    for camp, entity_id in (("attaquant", v_guerre.attaquant_id), ("defenseur", v_guerre.defenseur_id)):
        db.add(models.GuerreBelligerants(guerre_id=db_guerre.id, camp=camp, entity_type=entity_type, entity_id=entity_id, is_leader=True, status="engage"))
    attaquant = _get_entity(db, entity_type, v_guerre.attaquant_id)
    defenseur = _get_entity(db, entity_type, v_guerre.defenseur_id)
    _add_evenement(db, db_guerre.id, "declaration", f"Déclaration de guerre de {attaquant.title} contre {defenseur.title}", v_guerre.casus_belli, camp="attaquant", user=user)
    db.commit()
    return guerre_infos(db, db_guerre)

def _require_guerre(db: Session, ID: int):
    db_guerre = get_guerre(db, ID)
    if not db_guerre:
        raise HTTPException(status_code=404, detail="La guerre n'existe pas")
    return db_guerre

def _can_manage_camp(db: Session, user: schemas.Users, guerreID: int, camp: str) -> bool:
    leader = _camp_leader(db, guerreID, camp)
    return bool(leader and can_manage_entity(db, user, leader.entity_type, leader.entity_id))

def update_guerre(db: Session, user: schemas.Users, ID: int, v_guerre: schemas.GuerreUpdate):
    db_guerre = _require_guerre(db, ID)
    if not is_moderateur(user) and not (db_guerre.status == "en_attente" and _can_manage_camp(db, user, ID, "attaquant")):
        raise HTTPException(status_code=403, detail="Seul le camp attaquant (avant validation) ou un modérateur peut modifier la déclaration")
    data = v_guerre.model_dump(exclude_unset=True)
    if data.get("title") is None:
        data.pop("title", None)
    for key, value in data.items():
        setattr(db_guerre, key, value)
    db.add(db_guerre)
    db.commit()
    db.refresh(db_guerre)
    return guerre_infos(db, db_guerre)

def valider_guerre(db: Session, user: schemas.Users, ID: int, v_validation: schemas.GuerreValidation):
    _require_moderateur(user)
    db_guerre = _require_guerre(db, ID)
    if db_guerre.status != "en_attente":
        raise HTTPException(status_code=400, detail="Seule une déclaration en attente peut être validée")
    db_guerre.status = "en_cours"
    db_guerre.date_debut = v_validation.date_debut or dt.date.today()
    db_guerre.moderation_note = v_validation.note
    db_guerre.moderator_id = user.id
    db_guerre.validated_at = dt.datetime.now()
    _add_evenement(db, ID, "validation", "La guerre commence", v_validation.note, date_rp=db_guerre.date_debut, user=user)
    db.add(db_guerre)
    db.commit()
    db.refresh(db_guerre)
    attaquant, defenseur = _leaders(db, ID)
    _annoncer(db_guerre, f"⚔️ **{db_guerre.title}** : {attaquant} contre {defenseur}. La guerre commence.")
    return guerre_infos(db, db_guerre)

def refuser_guerre(db: Session, user: schemas.Users, ID: int, v_refus: schemas.GuerreRefus):
    _require_moderateur(user)
    db_guerre = _require_guerre(db, ID)
    if db_guerre.status != "en_attente":
        raise HTTPException(status_code=400, detail="Seule une déclaration en attente peut être refusée")
    db_guerre.status = "refusee"
    db_guerre.moderation_note = v_refus.note
    db_guerre.moderator_id = user.id
    _add_evenement(db, ID, "refus", "Déclaration refusée par la modération", v_refus.note, user=user)
    db.add(db_guerre)
    db.commit()
    db.refresh(db_guerre)
    return guerre_infos(db, db_guerre)

def terminer_guerre(db: Session, user: schemas.Users, ID: int, v_fin: schemas.GuerreFin):
    _require_moderateur(user)
    db_guerre = _require_guerre(db, ID)
    if db_guerre.status != "en_cours":
        raise HTTPException(status_code=400, detail="Seule une guerre en cours peut être terminée")
    if not (v_fin.issue or "").strip():
        raise HTTPException(status_code=400, detail="Indiquer l'issue de la guerre")
    db_guerre.status = "terminee"
    db_guerre.issue = v_fin.issue.strip()
    db_guerre.date_fin = v_fin.date_fin or dt.date.today()
    db_guerre.ended_at = dt.datetime.now()
    if not db_guerre.moderator_id:
        db_guerre.moderator_id = user.id
    _add_evenement(db, ID, "fin", f"Fin de la guerre : {db_guerre.issue}", date_rp=db_guerre.date_fin, user=user)
    db.add(db_guerre)
    db.commit()
    db.refresh(db_guerre)
    _annoncer(db_guerre, f"🏳️ **{db_guerre.title}** est terminée : {db_guerre.issue}")
    return guerre_infos(db, db_guerre)

def annuler_declaration(db: Session, user: schemas.Users, ID: int):
    db_guerre = _require_guerre(db, ID)
    if db_guerre.status not in ("en_attente", "refusee"):
        raise HTTPException(status_code=400, detail="Une guerre validée est archivée : elle ne peut plus être supprimée")
    if not is_moderateur(user) and not _can_manage_camp(db, user, ID, "attaquant"):
        raise HTTPException(status_code=403, detail="Seul le camp attaquant ou un modérateur peut retirer la déclaration")
    for b in _belligerants(db, ID):
        db.delete(b)
    for evenement in _evenements(db, ID):
        db.delete(evenement)
    delete_cartographies_by_types(db, "guerre", ID)
    db.delete(db_guerre)
    db.commit()
    return {"resultat": "Déclaration retirée"}

def appeler_aux_armes(db: Session, user: schemas.Users, ID: int, v_appel: schemas.GuerreAppel):
    db_guerre = _require_guerre(db, ID)
    if db_guerre.status not in ("en_attente", "en_cours"):
        raise HTTPException(status_code=400, detail="On ne peut plus appeler d'alliés dans cette guerre")
    if v_appel.camp not in CAMPS:
        raise HTTPException(status_code=400, detail="Le camp doit être « attaquant » ou « defenseur »")
    leader = _camp_leader(db, ID, v_appel.camp)
    if not leader or not can_manage_entity(db, user, leader.entity_type, leader.entity_id):
        raise HTTPException(status_code=403, detail="Seuls le fondateur et les admins du chef de camp peuvent appeler des alliés")

    engages = {(b.entity_type, b.entity_id) for b in _belligerants(db, ID)}
    if v_appel.civilisation_id is not None:
        if not get_civilisation_by_id(db, v_appel.civilisation_id):
            raise HTTPException(status_code=404, detail="La civilisation n'existe pas")
        if ("civilisation", v_appel.civilisation_id) in engages:
            raise HTTPException(status_code=400, detail="Cette civilisation participe déjà à la guerre")
        cibles = [(v_appel.civilisation_id, None)]
    elif v_appel.alliance_id is not None:
        _require_alliance(db, v_appel.alliance_id)
        if leader.entity_type != "civilisation" or not _alliance_membre(db, v_appel.alliance_id, leader.entity_id):
            raise HTTPException(status_code=400, detail="Le chef de camp doit être membre de cette alliance pour l'appeler")
        cibles = [
            (membre.civilisation_id, v_appel.alliance_id)
            for membre in _alliance_membres(db, v_appel.alliance_id)
            if ("civilisation", membre.civilisation_id) not in engages and membre.role != "Observateur"
        ]
        if not cibles:
            raise HTTPException(status_code=400, detail="Tous les membres de l'alliance participent déjà à la guerre")
    else:
        raise HTTPException(status_code=400, detail="Choisir une civilisation ou une alliance à appeler")

    for civilisation_id, alliance_id in cibles:
        db.add(models.GuerreBelligerants(guerre_id=ID, camp=v_appel.camp, entity_type="civilisation", entity_id=civilisation_id, status="appele", alliance_id=alliance_id))
    db.commit()
    return guerre_infos(db, db_guerre)

def _require_belligerant(db: Session, guerreID: int, belligerantID: int):
    b = db.exec(select(models.GuerreBelligerants).where(models.GuerreBelligerants.id == belligerantID)).first()
    if not b or b.guerre_id != guerreID:
        raise HTTPException(status_code=404, detail="Ce belligérant ne participe pas à cette guerre")
    return b

def repondre_appel(db: Session, user: schemas.Users, ID: int, belligerantID: int, accepter: bool):
    db_guerre = _require_guerre(db, ID)
    b = _require_belligerant(db, ID, belligerantID)
    if b.status != "appele":
        raise HTTPException(status_code=400, detail="Cet appel aux armes a déjà reçu une réponse")
    _require_entity_rights(db, user, b.entity_type, b.entity_id)
    if accepter:
        b.status = "engage"
        b.joined_at = dt.datetime.now()
        db.add(b)
        titre = _entity_summary(db, b.entity_type, b.entity_id)["title"]
        _add_evenement(db, ID, "ralliement", f"{titre} rejoint le camp {CAMP_NAMES.get(b.camp, b.camp)}", camp=b.camp, user=user)
    else:
        db.delete(b)
    db.commit()
    return guerre_infos(db, db_guerre)

def retirer_belligerant(db: Session, user: schemas.Users, ID: int, belligerantID: int):
    # Retrait d'un allié par lui-même, ou annulation d'un appel par son chef de camp
    db_guerre = _require_guerre(db, ID)
    b = _require_belligerant(db, ID, belligerantID)
    if db_guerre.status == "terminee":
        raise HTTPException(status_code=400, detail="La guerre est terminée : ses camps sont archivés")
    if b.is_leader:
        raise HTTPException(status_code=400, detail="Un chef de camp ne peut pas se retirer de la guerre")
    if not can_manage_entity(db, user, b.entity_type, b.entity_id) and not _can_manage_camp(db, user, ID, b.camp):
        raise HTTPException(status_code=403, detail="Vous ne pouvez pas retirer ce belligérant")
    if b.status == "engage":
        titre = _entity_summary(db, b.entity_type, b.entity_id, b.entity_title)["title"]
        _add_evenement(db, ID, "retrait", f"{titre} quitte le camp {CAMP_NAMES.get(b.camp, b.camp)}", camp=b.camp, user=user)
    db.delete(b)
    db.commit()
    return guerre_infos(db, db_guerre)

#endregion
#region Chronologie et zones de conflit

def can_raconter(db: Session, user: schemas.Users | None, db_guerre: models.Guerres) -> bool:
    # Chefs de camp (fondateur ou admin) pendant la guerre ; modérateurs RP aussi une fois terminée
    if not user or user.is_disabled:
        return False
    if is_moderateur(user):
        return db_guerre.status in GUERRE_STATUTS_PUBLICS
    return db_guerre.status == "en_cours" and any(_can_manage_camp(db, user, db_guerre.id, camp) for camp in CAMPS)

def can_edit_zones(db: Session, user: schemas.Users | None, db_guerre: models.Guerres) -> bool:
    return db_guerre.status == "en_cours" and can_raconter(db, user, db_guerre)

def ajouter_evenement(db: Session, user: schemas.Users, ID: int, body: schemas.GuerreEvenementCreate):
    db_guerre = _require_guerre(db, ID)
    if not can_raconter(db, user, db_guerre):
        raise HTTPException(status_code=403, detail="Seuls les chefs de camp d'une guerre en cours et les modérateurs RP complètent sa chronologie")
    kind = body.type or "bataille"
    if kind not in EVENEMENTS_RACONTES:
        raise HTTPException(status_code=400, detail="Type d'événement inconnu : bataille, siege, traite ou autre")
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Donnez un titre à l'événement")
    if len(title) > 120:
        raise HTTPException(status_code=400, detail="Le titre d'un événement ne dépasse pas 120 caractères")
    if body.camp is not None and body.camp not in CAMPS:
        raise HTTPException(status_code=400, detail="Le camp doit être « attaquant » ou « defenseur »")
    _add_evenement(db, ID, kind, title, (body.description or "").strip() or None, camp=body.camp, date_rp=body.date_rp, user=user, auto=False)
    db.commit()
    if kind in EVENEMENTS_ANNONCES:
        _annoncer(db_guerre, f"📜 **{db_guerre.title}** — {EVENEMENTS_RACONTES[kind]} : {title}")
    return guerre_details(db, db_guerre)

def supprimer_evenement(db: Session, user: schemas.Users, ID: int, evenementID: int):
    db_guerre = _require_guerre(db, ID)
    evenement = db.get(models.GuerreEvenements, evenementID)
    if not evenement or evenement.guerre_id != ID:
        raise HTTPException(status_code=404, detail="Cet événement n'appartient pas à cette guerre")
    if evenement.is_auto:
        raise HTTPException(status_code=400, detail="Les étapes inscrites automatiquement restent dans la chronologie")
    if not (is_moderateur(user) or (evenement.created_by == user.id and db_guerre.status == "en_cours")):
        raise HTTPException(status_code=403, detail="Seuls son auteur (pendant la guerre) et les modérateurs RP peuvent retirer cet événement")
    db.delete(evenement)
    db.commit()
    return guerre_details(db, db_guerre)

#endregion
