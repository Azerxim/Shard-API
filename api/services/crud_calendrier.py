"""
Calendrier des événements RP : batailles prévues, fêtes, couronnements, cérémonies, tournois, conseils.

- Dates en heure réelle du serveur (le serveur se joue en temps réel) : un événement s'annonce avant de commencer,
  dure au plus 31 jours, et ne se modifie plus une fois terminé.
- Organisé au nom du joueur lui-même, ou d'une civilisation, d'une religion, d'un commerce (Fondateur ou Admin) ou
  d'une alliance (Fondateur ou Admin de la civilisation chef de file). Une bataille peut être rattachée à une guerre en
  cours par un chef de camp ou un modérateur RP (mêmes droits que la chronologie de la guerre).
- Gèrent l'événement (modifier, annuler) : son créateur, les dirigeants de l'organisateur, les modérateurs RP.
- Inscriptions : tout joueur connecté, jusqu'au début, éventuellement sous les traits d'un de ses personnages (vivant
  ou disparu), dans la limite des places.
- Annoncé dans le salon Discord `platforms.discord.channels.evenements` (annonce, changement de date, annulation), et
  reproduit en événement programmé du serveur Discord (créé, mis à jour, supprimé à l'annulation), en tâche de fond.
- Les foires des villes publiques (crud_marches) figurent aussi au calendrier, en lecture seule.
"""
import asyncio
import datetime as dt
import json
import os
import threading

from fastapi import HTTPException
from sqlmodel import Session, select

from ..core import utils
from ..db import models, schemas
from ..integrations import discord_handler
from . import crud_conflits, crud_marches, crud_personnages
from .crud import announce_discord, _check_commerce_rights, get_commerce_by_id, get_ville_by_id

TYPES = {
    "bataille": "Bataille",
    "fete": "Fête",
    "couronnement": "Couronnement",
    "ceremonie": "Cérémonie",
    "tournoi": "Tournoi",
    "conseil": "Conseil",
    "autre": "Événement",
}
ORGANISATEURS = ("joueur", "civilisation", "religion", "commerce", "alliance")
TITLE_MAX = 120
DUREE_MAX = dt.timedelta(days=31)
# Discord exige une fin pour un événement « lieu externe » : durée prêtée à un événement sans heure de fin
DUREE_DISCORD = dt.timedelta(hours=2)
PLAGE_MAX = dt.timedelta(days=400)

# Une synchronisation Discord à la fois : une modification qui suit de près une création attend l'ID de l'événement
_discord_lock = threading.Lock()


#region Outils

def _date_heure_texte(moment: dt.datetime) -> str:
    # « samedi 10 octobre 2026 à 21 h » (21 h 30 si les minutes ne sont pas rondes)
    heure = f"{moment.hour} h" if moment.minute == 0 else f"{moment.hour} h {moment.minute:02d}"
    return f"{crud_marches._date_texte(moment.date())} à {heure}"

def _fin(evenement: models.Evenements) -> dt.datetime:
    return evenement.date_fin or evenement.date_debut

def est_termine(evenement: models.Evenements) -> bool:
    return _fin(evenement) < dt.datetime.now()

def _entite(db: Session, kind: str, ID: int | None):
    if ID is None:
        return None
    if kind in ("civilisation", "religion"):
        return crud_conflits._get_entity(db, kind, ID)
    if kind == "commerce":
        return get_commerce_by_id(db, ID)
    if kind == "alliance":
        return crud_conflits.get_alliance(db, ID)
    return None

def peut_parler_au_nom_de(db: Session, user: schemas.Users | None, kind: str, ID: int | None) -> bool:
    # Fondateur ou Admin de la civilisation, religion ou commerce ; de la civilisation chef de file pour une alliance
    if not user or user.is_disabled:
        return False
    if kind in ("civilisation", "religion"):
        return crud_conflits.can_manage_entity(db, user, kind, ID)
    if kind == "commerce":
        db_commerce = get_commerce_by_id(db, ID)
        if not db_commerce:
            return False
        try:
            _check_commerce_rights(db, user, db_commerce)
            return True
        except HTTPException:
            return False
    if kind == "alliance":
        chef = crud_conflits._alliance_chef(db, ID)
        return bool(chef and crud_conflits.can_manage_entity(db, user, "civilisation", chef.civilisation_id))
    return False

def peut_gerer(db: Session, user: schemas.Users | None, evenement: models.Evenements) -> bool:
    if not user or user.is_disabled:
        return False
    if crud_conflits.is_moderateur(user) or evenement.created_by == user.id:
        return True
    return evenement.organisateur_type != "joueur" and peut_parler_au_nom_de(db, user, evenement.organisateur_type, evenement.organisateur_id)

def _organisateur_infos(db: Session, evenement: models.Evenements):
    if evenement.organisateur_type == "joueur":
        auteur = crud_conflits._user_summary(db, evenement.created_by)
        return {"type": "joueur", "id": auteur["id"] if auteur else None, "title": (auteur["full_name"] or auteur["username"]) if auteur else "Compte supprimé"}
    entite = _entite(db, evenement.organisateur_type, evenement.organisateur_id)
    if not entite:
        return {"type": evenement.organisateur_type, "id": evenement.organisateur_id, "title": evenement.organisateur_title or "Organisateur disparu", "deleted": True}
    return {"type": evenement.organisateur_type, "id": entite.id, "title": entite.title}

def _inscriptions(db: Session, evenementID: int):
    statement = select(models.EvenementInscriptions).where(models.EvenementInscriptions.evenement_id == evenementID)
    return sorted(db.exec(statement).all(), key=lambda inscription: (inscription.created_at, inscription.id))

def _inscription_infos(db: Session, inscription: models.EvenementInscriptions):
    personnage = crud_personnages.get_personnage(db, inscription.personnage_id) if inscription.personnage_id else None
    return {
        "user": crud_conflits._user_summary(db, inscription.user_id),
        "personnage": {"id": personnage.id, "name": personnage.name} if personnage else None,
        "created_at": inscription.created_at,
    }

def evenement_infos(db: Session, evenement: models.Evenements):
    db_ville = get_ville_by_id(db, evenement.ville_id) if evenement.ville_id else None
    db_guerre = crud_conflits.get_guerre(db, evenement.guerre_id) if evenement.guerre_id else None
    inscrits = [_inscription_infos(db, inscription) for inscription in _inscriptions(db, evenement.id)]
    return {
        "id": evenement.id,
        "title": evenement.title,
        "description": evenement.description,
        "type": evenement.type,
        "date_debut": evenement.date_debut,
        "date_fin": evenement.date_fin,
        "lieu": evenement.lieu,
        # Une ville privée ne se montre pas au public
        "ville": {"id": db_ville.id, "title": db_ville.title, "civilisation_id": db_ville.civilisation_id} if db_ville and db_ville.is_public is not False else None,
        "organisateur": _organisateur_infos(db, evenement),
        "guerre": {"id": db_guerre.id, "title": db_guerre.title} if db_guerre and db_guerre.status in crud_conflits.GUERRE_STATUTS_PUBLICS else None,
        "places": evenement.places,
        "inscrits": inscrits,
        "complet": evenement.places is not None and len(inscrits) >= evenement.places,
        "status": evenement.status,
        "motif_annulation": evenement.motif_annulation,
        "termine": est_termine(evenement),
        "created_by": crud_conflits._user_summary(db, evenement.created_by),
        "created_at": evenement.created_at,
    }

def _lien(evenement: models.Evenements) -> str | None:
    site = ((utils.PLATFORMS or {}).get("discord") or {}).get("site_url")
    return f"{str(site).rstrip('/')}/calendrier?mois={evenement.date_debut:%Y-%m}#evenement-{evenement.id}" if site else None

def _annoncer(evenement: models.Evenements, texte: str):
    lien = _lien(evenement)
    announce_discord("evenements", f"{texte}\n{lien}" if lien else texte)

def _lieu_texte(db: Session, evenement: models.Evenements) -> str:
    db_ville = get_ville_by_id(db, evenement.ville_id) if evenement.ville_id else None
    ville = db_ville.title if db_ville and db_ville.is_public is not False else None
    return ", ".join(part for part in (evenement.lieu, ville) if part) or "Tetrago"

#endregion
#region Événements Discord programmés

def _ecrire_simulation(fichier: str, ligne: dict):
    with open(fichier, "a", encoding="utf-8") as file:
        file.write(json.dumps(ligne, ensure_ascii=False, default=str) + "\n")

def _synchroniser_maintenant(evenementID: int):
    # Aligne l'événement programmé Discord sur l'état en base : créé, mis à jour, ou supprimé s'il est annulé.
    # Tests : SHARD_FAKE_DISCORD_EVENTS désigne un fichier (une opération JSON par ligne) au lieu de Discord.
    from ..db.database import engine

    simulation = os.environ.get("SHARD_FAKE_DISCORD_EVENTS")
    with _discord_lock, Session(engine) as db:
        evenement = db.get(models.Evenements, evenementID)
        if not evenement:
            return
        if evenement.status == "annule":
            if evenement.discord_event_id:
                if simulation:
                    _ecrire_simulation(simulation, {"action": "delete", "evenement_id": evenement.id, "discord_event_id": evenement.discord_event_id})
                else:
                    asyncio.run(discord_handler.delete_scheduled_event(evenement.discord_event_id))
                evenement.discord_event_id = None
                db.add(evenement)
                db.commit()
            return
        # Discord refuse un début dans le passé : un événement commencé n'est plus mis à jour
        if evenement.date_debut <= dt.datetime.now():
            return
        nature = TYPES.get(evenement.type, TYPES["autre"])
        details = {
            # « Tournoi · Joute du printemps », mais pas « Couronnement · Couronnement de la reine »
            "name": evenement.title if evenement.title.lower().startswith(nature.lower()) else f"{nature} · {evenement.title}",
            "start_time": evenement.date_debut.astimezone(),
            "end_time": (evenement.date_fin or evenement.date_debut + DUREE_DISCORD).astimezone(),
            "location": _lieu_texte(db, evenement),
            "description": "\n\n".join(part for part in (evenement.description, _lien(evenement)) if part),
        }
        if simulation:
            action = "edit" if evenement.discord_event_id else "create"
            _ecrire_simulation(simulation, {"action": action, "evenement_id": evenement.id, **details})
            evenement.discord_event_id = evenement.discord_event_id or f"simulation-{evenement.id}"
        elif evenement.discord_event_id and asyncio.run(discord_handler.edit_scheduled_event(evenement.discord_event_id, **details)):
            return
        else:
            # Pas encore créé, ou supprimé à la main sur Discord : on le recrée
            evenement.discord_event_id = asyncio.run(discord_handler.create_scheduled_event(**details))
        db.add(evenement)
        db.commit()

def _synchroniser_discord(evenementID: int):
    # En tâche de fond : un échec (bot sans la permission « Gérer les événements »…) ne fait pas échouer la requête
    if os.environ.get("SHARD_FAKE_DISCORD_EVENTS"):
        _synchroniser_maintenant(evenementID)
        return
    discord = (utils.PLATFORMS or {}).get("discord") or {}
    if not discord.get("token") or not discord.get("guild_id"):
        return

    def run():
        try:
            _synchroniser_maintenant(evenementID)
        except Exception as error:
            print(f"Événement Discord {evenementID} non synchronisé : {error}")

    threading.Thread(target=run, daemon=True).start()

#endregion
#region Lecture

def _require_evenement(db: Session, ID: int) -> models.Evenements:
    evenement = db.get(models.Evenements, ID)
    if not evenement:
        raise HTTPException(status_code=404, detail="Cet événement n'existe pas")
    return evenement

def read_evenement(db: Session, ID: int):
    return evenement_infos(db, _require_evenement(db, ID))

def calendrier(db: Session, debut: dt.date | None = None, fin: dt.date | None = None):
    # Événements (annulés compris) et foires des villes publiques qui touchent la période [debut, fin]
    today = dt.date.today()
    debut = debut or today - dt.timedelta(days=31)
    fin = fin or today + dt.timedelta(days=365)
    if fin < debut:
        raise HTTPException(status_code=400, detail="La période finit avant de commencer")
    if fin - debut > PLAGE_MAX:
        raise HTTPException(status_code=400, detail="La période demandée dépasse 400 jours")
    borne_debut = dt.datetime.combine(debut, dt.time.min)
    borne_fin = dt.datetime.combine(fin, dt.time.max)
    # Un événement dure au plus DUREE_MAX : ceux qui commencent avant la période peuvent encore la toucher
    statement = select(models.Evenements).where(
        models.Evenements.date_debut <= borne_fin,
        models.Evenements.date_debut >= borne_debut - DUREE_MAX,
    )
    evenements = [e for e in db.exec(statement).all() if _fin(e) >= borne_debut]

    villes = {}
    def ville(ID):
        if ID not in villes:
            villes[ID] = get_ville_by_id(db, ID)
        return villes[ID]
    foires = db.exec(select(models.Foires).where(models.Foires.date_debut <= fin, models.Foires.date_fin >= debut)).all()
    return {
        "evenements": [evenement_infos(db, e) for e in sorted(evenements, key=lambda e: (e.date_debut, e.id))],
        "foires": [crud_marches.foire_infos(db, f, ville(f.ville_id)) for f in sorted(foires, key=lambda f: (f.date_debut, f.id)) if crud_marches._ville_publique(ville(f.ville_id))],
    }

#endregion
#region Création et gestion

def _verifier(db: Session, user: schemas.Users, evenement: models.Evenements, nouveau: bool, verifier_guerre: bool = True):
    evenement.title = (evenement.title or "").strip()
    if not evenement.title:
        raise HTTPException(status_code=400, detail="Donnez un nom à l'événement")
    if len(evenement.title) > TITLE_MAX:
        raise HTTPException(status_code=400, detail=f"Le nom d'un événement ne dépasse pas {TITLE_MAX} caractères")
    evenement.type = evenement.type or "autre"
    if evenement.type not in TYPES:
        raise HTTPException(status_code=400, detail=f"Type d'événement inconnu : {', '.join(TYPES)}")
    for key in ("description", "lieu"):
        setattr(evenement, key, (getattr(evenement, key) or "").strip() or None)
    # Heures de saisie (datetime-local) : sans fuseau ; une heure avec fuseau est ramenée à l'heure du serveur
    for key in ("date_debut", "date_fin"):
        value = getattr(evenement, key)
        if value is not None and value.tzinfo is not None:
            setattr(evenement, key, value.astimezone().replace(tzinfo=None))
    if nouveau and evenement.date_debut <= dt.datetime.now():
        raise HTTPException(status_code=400, detail="Un événement s'annonce avant de commencer")
    if evenement.date_fin is not None:
        if evenement.date_fin < evenement.date_debut:
            raise HTTPException(status_code=400, detail="L'événement ne peut pas finir avant de commencer")
        if evenement.date_fin - evenement.date_debut > DUREE_MAX:
            raise HTTPException(status_code=400, detail="Un événement dure au plus 31 jours")
    if evenement.places is not None and evenement.places < 1:
        raise HTTPException(status_code=400, detail="Le nombre de places est d'au moins 1 (laissez vide : sans limite)")
    if evenement.ville_id is not None and not get_ville_by_id(db, evenement.ville_id):
        raise HTTPException(status_code=404, detail="La ville n'existe pas")
    if evenement.guerre_id is not None and verifier_guerre:
        db_guerre = crud_conflits.get_guerre(db, evenement.guerre_id)
        if not db_guerre or db_guerre.status != "en_cours":
            raise HTTPException(status_code=400, detail="Seule une guerre en cours peut accueillir une bataille")
        if not crud_conflits.can_raconter(db, user, db_guerre):
            raise HTTPException(status_code=403, detail="Seuls les chefs de camp et les modérateurs RP rattachent un événement à cette guerre")

def create_evenement(db: Session, user: schemas.Users, body: schemas.EvenementCreate):
    kind = body.organisateur_type or "joueur"
    if kind not in ORGANISATEURS:
        raise HTTPException(status_code=400, detail=f"Organisateur inconnu : {', '.join(ORGANISATEURS)}")
    entite = None
    if kind != "joueur":
        entite = _entite(db, kind, body.organisateur_id)
        if not entite:
            raise HTTPException(status_code=404, detail="L'organisateur n'existe pas")
        if not peut_parler_au_nom_de(db, user, kind, entite.id):
            raise HTTPException(status_code=403, detail="Seuls ses dirigeants organisent un événement en son nom")
    evenement = models.Evenements(
        title=body.title, description=body.description, type=body.type, date_debut=body.date_debut, date_fin=body.date_fin,
        lieu=body.lieu, ville_id=body.ville_id, guerre_id=body.guerre_id, places=body.places,
        organisateur_type=kind, organisateur_id=entite.id if entite else None, organisateur_title=entite.title if entite else None,
        created_by=user.id,
    )
    _verifier(db, user, evenement, nouveau=True)
    db.add(evenement)
    db.commit()
    db.refresh(evenement)
    organisateur = _organisateur_infos(db, evenement)["title"]
    _annoncer(evenement, f"📅 **{evenement.title}** ({TYPES[evenement.type].lower()}, par {organisateur}) : {_date_heure_texte(evenement.date_debut)}, {_lieu_texte(db, evenement)}.")
    _synchroniser_discord(evenement.id)
    return evenement_infos(db, evenement)

def _require_gestion(db: Session, user: schemas.Users, ID: int) -> models.Evenements:
    evenement = _require_evenement(db, ID)
    if not peut_gerer(db, user, evenement):
        raise HTTPException(status_code=403, detail="Seuls l'organisateur et les modérateurs RP gèrent cet événement")
    if evenement.status == "annule":
        raise HTTPException(status_code=400, detail="Cet événement est annulé")
    if est_termine(evenement):
        raise HTTPException(status_code=400, detail="Un événement terminé ne se modifie plus")
    return evenement

def update_evenement(db: Session, user: schemas.Users, ID: int, body: schemas.EvenementUpdate):
    evenement = _require_gestion(db, user, ID)
    data = body.model_dump(exclude_unset=True)
    for key in ("title", "date_debut", "type"):
        if data.get(key) is None:
            data.pop(key, None)
    avant = (evenement.date_debut, evenement.date_fin)
    guerre_avant = evenement.guerre_id
    for key, value in data.items():
        setattr(evenement, key, value)
    # Rattacher à une autre guerre demande les droits sur celle-ci ; garder la même ne les redemande pas
    _verifier(db, user, evenement, nouveau=evenement.date_debut != avant[0], verifier_guerre=evenement.guerre_id != guerre_avant)
    inscrits = len(_inscriptions(db, evenement.id))
    if evenement.places is not None and evenement.places < inscrits:
        raise HTTPException(status_code=400, detail=f"Il y a déjà {inscrits} inscrits : prévoyez au moins autant de places")
    evenement.updated_at = dt.datetime.now()
    db.add(evenement)
    db.commit()
    db.refresh(evenement)
    if (evenement.date_debut, evenement.date_fin) != avant:
        _annoncer(evenement, f"📅 **{evenement.title}** change de date : {_date_heure_texte(evenement.date_debut)}, {_lieu_texte(db, evenement)}.")
    _synchroniser_discord(evenement.id)
    return evenement_infos(db, evenement)

def annuler_evenement(db: Session, user: schemas.Users, ID: int, body: schemas.EvenementAnnulation):
    evenement = _require_gestion(db, user, ID)
    evenement.status = "annule"
    evenement.motif_annulation = (body.motif or "").strip() or None
    evenement.updated_at = dt.datetime.now()
    db.add(evenement)
    db.commit()
    db.refresh(evenement)
    motif = f" Motif : {evenement.motif_annulation}" if evenement.motif_annulation else ""
    _annoncer(evenement, f"📅 **{evenement.title}** ({_date_heure_texte(evenement.date_debut)}) est annulé.{motif}")
    _synchroniser_discord(evenement.id)
    return evenement_infos(db, evenement)

#endregion
#region Inscriptions

def _inscription(db: Session, evenementID: int, userID: int):
    statement = select(models.EvenementInscriptions).where(
        models.EvenementInscriptions.evenement_id == evenementID, models.EvenementInscriptions.user_id == userID
    )
    return db.exec(statement).first()

def _require_ouvert(db: Session, ID: int) -> models.Evenements:
    evenement = _require_evenement(db, ID)
    if evenement.status == "annule":
        raise HTTPException(status_code=400, detail="Cet événement est annulé")
    if evenement.date_debut <= dt.datetime.now():
        raise HTTPException(status_code=400, detail="Les inscriptions ferment au début de l'événement")
    return evenement

def inscrire(db: Session, user: schemas.Users, ID: int, body: schemas.EvenementInscription):
    # S'inscrire, ou changer le personnage d'une inscription existante
    if user.is_disabled:
        raise HTTPException(status_code=403, detail="Accès refusé")
    evenement = _require_ouvert(db, ID)
    personnage = None
    if body.personnage_id is not None:
        personnage = crud_personnages.get_personnage(db, body.personnage_id)
        if not personnage or personnage.user_id != user.id:
            raise HTTPException(status_code=403, detail="On ne s'inscrit que sous les traits de ses propres personnages")
        if personnage.status == "mort":
            raise HTTPException(status_code=400, detail=f"{personnage.name} est mort : il ne participe plus aux événements")
    inscription = _inscription(db, evenement.id, user.id)
    if not inscription:
        if evenement.places is not None and len(_inscriptions(db, evenement.id)) >= evenement.places:
            raise HTTPException(status_code=400, detail="L'événement est complet")
        inscription = models.EvenementInscriptions(evenement_id=evenement.id, user_id=user.id)
    inscription.personnage_id = personnage.id if personnage else None
    db.add(inscription)
    db.commit()
    return evenement_infos(db, evenement)

def desinscrire(db: Session, user: schemas.Users, ID: int):
    evenement = _require_ouvert(db, ID)
    inscription = _inscription(db, evenement.id, user.id)
    if not inscription:
        raise HTTPException(status_code=404, detail="Vous n'êtes pas inscrit à cet événement")
    db.delete(inscription)
    db.commit()
    return evenement_infos(db, evenement)

#endregion
