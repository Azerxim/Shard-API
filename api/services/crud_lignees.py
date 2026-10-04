"""
Lignées et généalogie : liens de parenté entre personnages, et maisons nobles.

- Liens : parent (source est parent de cible), conjoint (dans les deux sens), héritier (cible hérite de source, rang 1
  d'abord). Un personnage a au plus deux parents, et nul n'est son propre ancêtre.
- Accord : un lien entre deux personnages du même joueur est établi aussitôt ; vers le personnage d'un autre joueur,
  il attend l'accord de celui-ci (refuser supprime la demande). Les administrateurs et modérateurs RP établissent
  directement. Seul le joueur du personnage dont on hérite désigne ses héritiers.
- Retirer un lien : le joueur de l'un des deux personnages, ou un modérateur RP.
- Maisons nobles : une maison a un chef (un de ses membres). Comme pour la résidence, chaque joueur fait entrer ou
  sortir ses propres personnages ; les gestionnaires de la maison (son créateur, le joueur du chef, les administrateurs
  et modérateurs RP) la modifient, en excluent des membres, la dissolvent.
- Arbre d'une maison : ses membres, les liens de parenté et de mariage acceptés entre eux, et les conjoints venus
  d'autres maisons (« alliés ») ; le site le dessine.
- Seuls les liens acceptés sont publics ; une demande n'est visible que des joueurs concernés.
- Annonces Discord (salon `platforms.discord.channels.lignees`) : fondation d'une maison, mariage établi.
"""
import datetime as dt
import re

from fastapi import HTTPException
from sqlmodel import Session, select

from ..core import utils
from ..db import models, schemas
from . import crud_conflits, crud_marches, crud_personnages
from .crud import announce_discord, get_civilisation_by_id

TYPES = ("parent", "conjoint", "heritier")
TITLE_MAX = 80
DEVISE_MAX = 120
COULEUR = re.compile(r"^#[0-9a-fA-F]{6}$")


#region Outils

def _peut_gerer_personnage(user: schemas.Users | None, personnage: models.Personnages | None) -> bool:
    # Le joueur du personnage, ou un administrateur
    return bool(personnage) and crud_personnages.can_manage(user, personnage)

def _require_personnage(db: Session, ID: int) -> models.Personnages:
    personnage = crud_personnages.get_personnage(db, ID)
    if not personnage:
        raise HTTPException(status_code=404, detail="Ce personnage n'existe pas")
    return personnage

def personnage_resume(personnage: models.Personnages | None):
    # Ce qu'il faut pour afficher un personnage dans une famille ou un arbre (avatar compris)
    if not personnage:
        return None
    return {
        "id": personnage.id, "name": personnage.name, "status": personnage.status, "user_id": personnage.user_id,
        "image_url": personnage.image_url, "image_fichier": personnage.image_fichier, "minecraft_uuid": personnage.minecraft_uuid,
        "date_naissance": personnage.date_naissance, "date_deces": personnage.date_deces, "maison_id": personnage.maison_id,
    }

def _liens(db: Session, personnageID: int, *, acceptes: bool = True):
    statement = select(models.PersonnageLiens).where(
        (models.PersonnageLiens.source_id == personnageID) | (models.PersonnageLiens.cible_id == personnageID)
    )
    liens = db.exec(statement).all()
    return [lien for lien in liens if lien.status == "accepte"] if acceptes else liens

def _parents_ids(db: Session, personnageID: int, *, avec_demandes: bool = False):
    statement = select(models.PersonnageLiens).where(models.PersonnageLiens.type == "parent", models.PersonnageLiens.cible_id == personnageID)
    return [lien.source_id for lien in db.exec(statement).all() if avec_demandes or lien.status == "accepte"]

def _ancetres(db: Session, personnageID: int) -> set:
    # Tous les ancêtres, demandes en attente comprises (pour refuser une boucle avant même l'accord)
    vus, a_voir = set(), [personnageID]
    while a_voir:
        for parent in _parents_ids(db, a_voir.pop(), avec_demandes=True):
            if parent not in vus:
                vus.add(parent)
                a_voir.append(parent)
    return vus

def lien_infos(db: Session, lien: models.PersonnageLiens):
    return {
        "id": lien.id,
        "type": lien.type,
        "source": personnage_resume(crud_personnages.get_personnage(db, lien.source_id)),
        "cible": personnage_resume(crud_personnages.get_personnage(db, lien.cible_id)),
        "rang": lien.rang,
        "date_rp": lien.date_rp,
        "status": lien.status,
        "en_attente_de": lien.en_attente_de,
        "demande_par": crud_conflits._user_summary(db, lien.demande_par),
        "created_at": lien.created_at,
    }

def _date_rp_texte(date: dt.date) -> str:
    # « 21 juin de l'an 419 » (années RP : pas de jour de la semaine, qui n'aurait pas de sens)
    return f"{date.day}{'er' if date.day == 1 else ''} {crud_marches.MOIS[date.month - 1]} de l'an {date.year}"

def _annoncer(texte: str, chemin: str):
    # Salon Discord « lignees », avec le lien du site si site_url est configuré
    site = ((utils.PLATFORMS or {}).get("discord") or {}).get("site_url")
    announce_discord("lignees", f"{texte}\n{str(site).rstrip('/')}{chemin}" if site else texte)

def _annoncer_mariage(db: Session, lien: models.PersonnageLiens):
    a, b = crud_personnages.get_personnage(db, lien.source_id), crud_personnages.get_personnage(db, lien.cible_id)
    if lien.type != "conjoint" or not a or not b:
        return
    quand = f", le {_date_rp_texte(lien.date_rp)}" if lien.date_rp else ""
    _annoncer(f"💍 Mariage de **{a.name}** et **{b.name}**{quand}.", f"/personnage/{a.id}#famille")

#endregion
#region Famille d'un personnage

def famille(db: Session, personnageID: int):
    # { maison, parents, enfants, conjoints: [{ personnage, date_rp, lien_id }], fratrie, heritiers, heritier_de }
    personnage = _require_personnage(db, personnageID)
    get = lambda ID: personnage_resume(crud_personnages.get_personnage(db, ID))
    liens = _liens(db, personnage.id)
    autre = lambda lien: lien.cible_id if lien.source_id == personnage.id else lien.source_id
    entree = lambda lien, ID: {"personnage": get(ID), "date_rp": lien.date_rp, "rang": lien.rang, "lien_id": lien.id}

    parents = [entree(l, l.source_id) for l in liens if l.type == "parent" and l.cible_id == personnage.id]
    enfants = [entree(l, l.cible_id) for l in liens if l.type == "parent" and l.source_id == personnage.id]
    conjoints = [entree(l, autre(l)) for l in liens if l.type == "conjoint"]
    heritiers = sorted((entree(l, l.cible_id) for l in liens if l.type == "heritier" and l.source_id == personnage.id), key=lambda e: (e["rang"] is None, e["rang"] or 0))
    heritier_de = [entree(l, l.source_id) for l in liens if l.type == "heritier" and l.cible_id == personnage.id]

    # Frères et sœurs : les autres enfants de ses parents (demi-frères et demi-sœurs compris)
    fratrie_ids = set()
    for parent in parents:
        for lien in _liens(db, parent["personnage"]["id"]):
            if lien.type == "parent" and lien.source_id == parent["personnage"]["id"] and lien.cible_id != personnage.id:
                fratrie_ids.add(lien.cible_id)
    fratrie = sorted((get(ID) for ID in fratrie_ids), key=lambda p: p["name"].lower())

    maison = db.get(models.Maisons, personnage.maison_id) if personnage.maison_id else None
    par_naissance = lambda e: (e["personnage"]["date_naissance"] is None, e["personnage"]["date_naissance"] or dt.date.min, e["personnage"]["name"].lower())
    return {
        "maison": _maison_resume(maison),
        "parents": sorted(parents, key=par_naissance),
        "enfants": sorted(enfants, key=par_naissance),
        "conjoints": conjoints,
        "fratrie": fratrie,
        "heritiers": heritiers,
        "heritier_de": heritier_de,
    }

def demandes(db: Session, user: schemas.Users):
    # Demandes en attente qui concernent les personnages du joueur : { recues, envoyees }
    en_attente = db.exec(select(models.PersonnageLiens).where(models.PersonnageLiens.status == "en_attente")).all()
    recues = [l for l in en_attente if _peut_gerer_personnage(user, crud_personnages.get_personnage(db, l.en_attente_de))]
    envoyees = [l for l in en_attente if l.demande_par == user.id and l not in recues]
    return {"recues": [lien_infos(db, l) for l in recues], "envoyees": [lien_infos(db, l) for l in envoyees]}

#endregion
#region Liens de parenté

def _existe(db: Session, type_: str, sourceID: int, cibleID: int) -> bool:
    statement = select(models.PersonnageLiens).where(models.PersonnageLiens.type == type_)
    for lien in db.exec(statement).all():
        if (lien.source_id, lien.cible_id) == (sourceID, cibleID):
            return True
        if type_ in ("conjoint", "parent") and (lien.source_id, lien.cible_id) == (cibleID, sourceID):
            return True
    return False

def create_lien(db: Session, user: schemas.Users, body: schemas.PersonnageLienCreate):
    if body.type not in TYPES:
        raise HTTPException(status_code=400, detail="Type de lien inconnu : parent, conjoint ou heritier")
    if body.source_id == body.cible_id:
        raise HTTPException(status_code=400, detail="Un personnage ne peut pas être lié à lui-même")
    source, cible = _require_personnage(db, body.source_id), _require_personnage(db, body.cible_id)
    moderateur = crud_conflits.is_moderateur(user)
    gere_source, gere_cible = _peut_gerer_personnage(user, source), _peut_gerer_personnage(user, cible)
    if not (moderateur or gere_source or gere_cible):
        raise HTTPException(status_code=403, detail="Il faut jouer l'un des deux personnages pour les lier")
    if body.type == "heritier" and not (moderateur or gere_source):
        raise HTTPException(status_code=403, detail=f"Seul le joueur de {source.name} désigne ses héritiers")

    if _existe(db, body.type, source.id, cible.id) or (body.type != "heritier" and _existe(db, "conjoint" if body.type == "parent" else "parent", source.id, cible.id)):
        raise HTTPException(status_code=400, detail=f"{source.name} et {cible.name} sont déjà liés")
    if body.type == "parent":
        if len(_parents_ids(db, cible.id, avec_demandes=True)) >= 2:
            raise HTTPException(status_code=400, detail=f"{cible.name} a déjà deux parents")
        if cible.id in _ancetres(db, source.id):
            raise HTTPException(status_code=400, detail=f"{cible.name} est un ancêtre de {source.name} : il ne peut pas être son enfant")
    if body.rang is not None and (body.type != "heritier" or body.rang < 1):
        raise HTTPException(status_code=400, detail="Le rang, à partir de 1, ne concerne que les héritiers")

    lien = models.PersonnageLiens(type=body.type, source_id=source.id, cible_id=cible.id, rang=body.rang, date_rp=body.date_rp, demande_par=user.id)
    # Établi aussitôt par un modérateur, ou entre deux personnages qu'on joue ; sinon l'autre joueur doit accepter
    if not moderateur and not (gere_source and gere_cible):
        lien.status = "en_attente"
        lien.en_attente_de = cible.id if gere_source else source.id
    db.add(lien)
    db.commit()
    db.refresh(lien)
    if lien.status == "accepte":
        _annoncer_mariage(db, lien)
    return lien_infos(db, lien)

def _require_lien(db: Session, ID: int) -> models.PersonnageLiens:
    lien = db.get(models.PersonnageLiens, ID)
    if not lien:
        raise HTTPException(status_code=404, detail="Ce lien n'existe pas")
    return lien

def repondre_lien(db: Session, user: schemas.Users, ID: int, accepter: bool):
    lien = _require_lien(db, ID)
    if lien.status != "en_attente":
        raise HTTPException(status_code=400, detail="Ce lien n'attend aucune réponse")
    if not (_peut_gerer_personnage(user, crud_personnages.get_personnage(db, lien.en_attente_de)) or crud_conflits.is_moderateur(user)):
        raise HTTPException(status_code=403, detail="Seul le joueur du personnage concerné répond à cette demande")
    if not accepter:
        db.delete(lien)
        db.commit()
        return None
    lien.status = "accepte"
    lien.en_attente_de = None
    db.add(lien)
    db.commit()
    db.refresh(lien)
    _annoncer_mariage(db, lien)
    return lien_infos(db, lien)

def delete_lien(db: Session, user: schemas.Users, ID: int):
    lien = _require_lien(db, ID)
    concernes = (crud_personnages.get_personnage(db, lien.source_id), crud_personnages.get_personnage(db, lien.cible_id))
    if not (crud_conflits.is_moderateur(user) or lien.demande_par == user.id or any(_peut_gerer_personnage(user, p) for p in concernes)):
        raise HTTPException(status_code=403, detail="Seuls les joueurs des deux personnages et les modérateurs RP retirent ce lien")
    db.delete(lien)
    db.commit()
    return True

#endregion
#region Maisons

def nom_maison(maison: models.Maisons) -> str:
    # « maison d'Orval », sauf si le nom le dit déjà (« Maison d'Or »)
    return maison.title if maison.title.lower().startswith("maison") else f"maison {maison.title}"

def majuscule(texte: str) -> str:
    # Première lettre seulement (str.capitalize mettrait le reste en minuscules)
    return texte[:1].upper() + texte[1:]

def _maison_resume(maison: models.Maisons | None):
    if not maison:
        return None
    return {"id": maison.id, "title": maison.title, "couleur": maison.couleur, "icon": maison.icon, "devise": maison.devise, "chef_id": maison.chef_id}

def _membres(db: Session, maisonID: int):
    return db.exec(select(models.Personnages).where(models.Personnages.maison_id == maisonID)).all()

def maison_infos(db: Session, maison: models.Maisons):
    civilisation = get_civilisation_by_id(db, maison.civilisation_id) if maison.civilisation_id else None
    chef = crud_personnages.get_personnage(db, maison.chef_id) if maison.chef_id else None
    return {
        **maison.model_dump(),
        "civilisation": {"id": civilisation.id, "title": civilisation.title} if civilisation and civilisation.is_public is not False else None,
        "chef": personnage_resume(chef),
        "membres_count": len(_membres(db, maison.id)),
        "created_by_user": crud_conflits._user_summary(db, maison.created_by),
    }

def list_maisons(db: Session):
    return [maison_infos(db, maison) for maison in sorted(db.exec(select(models.Maisons)).all(), key=lambda m: m.title.lower())]

def _require_maison(db: Session, ID: int) -> models.Maisons:
    maison = db.get(models.Maisons, ID)
    if not maison:
        raise HTTPException(status_code=404, detail="Cette maison n'existe pas")
    return maison

def read_maison(db: Session, ID: int):
    # Fiche et arbre : { maison, membres, allies (conjoints d'autres maisons), liens (parent et conjoint acceptés) }
    maison = _require_maison(db, ID)
    membres = _membres(db, maison.id)
    ids = {membre.id for membre in membres}
    liens, allies = {}, {}
    for membre in membres:
        for lien in _liens(db, membre.id):
            if lien.type == "parent" and lien.source_id in ids and lien.cible_id in ids:
                liens[lien.id] = lien
            elif lien.type == "conjoint":
                liens[lien.id] = lien
                autre = lien.cible_id if lien.source_id == membre.id else lien.source_id
                if autre not in ids:
                    allies[autre] = crud_personnages.get_personnage(db, autre)
    return {
        "maison": maison_infos(db, maison),
        "membres": [personnage_resume(m) for m in sorted(membres, key=lambda m: m.name.lower())],
        "allies": [personnage_resume(p) for p in allies.values() if p],
        "liens": [{"id": l.id, "type": l.type, "source_id": l.source_id, "cible_id": l.cible_id, "date_rp": l.date_rp} for l in liens.values()],
    }

def peut_gerer_maison(db: Session, user: schemas.Users | None, maison: models.Maisons) -> bool:
    if not user or user.is_disabled:
        return False
    if crud_conflits.is_moderateur(user) or maison.created_by == user.id:
        return True
    return _peut_gerer_personnage(user, crud_personnages.get_personnage(db, maison.chef_id) if maison.chef_id else None)

def _require_gestion(db: Session, user: schemas.Users, ID: int) -> models.Maisons:
    maison = _require_maison(db, ID)
    if not peut_gerer_maison(db, user, maison):
        raise HTTPException(status_code=403, detail="Seuls le chef de la maison, son fondateur et les modérateurs RP la gèrent")
    return maison

def _verifier_maison(db: Session, maison: models.Maisons):
    maison.title = (maison.title or "").strip()
    if not maison.title:
        raise HTTPException(status_code=400, detail="Donnez un nom à la maison")
    if len(maison.title) > TITLE_MAX:
        raise HTTPException(status_code=400, detail=f"Le nom d'une maison ne dépasse pas {TITLE_MAX} caractères")
    for key in ("devise", "description", "icon", "couleur"):
        setattr(maison, key, (getattr(maison, key) or "").strip() or None)
    if maison.devise and len(maison.devise) > DEVISE_MAX:
        raise HTTPException(status_code=400, detail=f"Une devise ne dépasse pas {DEVISE_MAX} caractères")
    if maison.couleur and not COULEUR.match(maison.couleur):
        raise HTTPException(status_code=400, detail="La couleur s'écrit #rrggbb")
    if maison.civilisation_id is not None and not get_civilisation_by_id(db, maison.civilisation_id):
        raise HTTPException(status_code=404, detail="La civilisation n'existe pas")

def create_maison(db: Session, user: schemas.Users, body: schemas.MaisonCreate):
    chef = _require_personnage(db, body.chef_id)
    if not _peut_gerer_personnage(user, chef):
        raise HTTPException(status_code=403, detail="Le chef de la maison est l'un de vos personnages")
    maison = models.Maisons(**body.model_dump(), created_by=user.id)
    _verifier_maison(db, maison)
    db.add(maison)
    db.commit()
    db.refresh(maison)
    chef.maison_id = maison.id
    db.add(chef)
    db.commit()
    details = [f"sous la conduite de **{chef.name}**"]
    if maison.date_fondation:
        details.append(f"le {_date_rp_texte(maison.date_fondation)}")
    devise = f" Devise : « {maison.devise} »." if maison.devise else ""
    _annoncer(f"🏰 Fondation de la {nom_maison(maison)}, {', '.join(details)}.{devise}", f"/maison/{maison.id}")
    return maison_infos(db, maison)

def update_maison(db: Session, user: schemas.Users, ID: int, body: schemas.MaisonUpdate):
    maison = _require_gestion(db, user, ID)
    data = body.model_dump(exclude_unset=True)
    for key in ("title", "chef_id"):
        if data.get(key) is None:
            data.pop(key, None)
    if "chef_id" in data:
        chef = _require_personnage(db, data["chef_id"])
        if chef.maison_id != maison.id:
            raise HTTPException(status_code=400, detail=f"{chef.name} doit être membre de la maison pour en prendre la tête")
    for key, value in data.items():
        setattr(maison, key, value)
    _verifier_maison(db, maison)
    db.add(maison)
    db.commit()
    db.refresh(maison)
    return maison_infos(db, maison)

def delete_maison(db: Session, user: schemas.Users, ID: int):
    maison = _require_gestion(db, user, ID)
    for membre in _membres(db, maison.id):
        membre.maison_id = None
        db.add(membre)
    db.delete(maison)
    db.commit()
    return True

def rejoindre(db: Session, user: schemas.Users, ID: int, body: schemas.MaisonMembre):
    # Comme la résidence : le joueur y fait entrer son personnage (qui quitte son ancienne maison)
    maison = _require_maison(db, ID)
    personnage = _require_personnage(db, body.personnage_id)
    if not _peut_gerer_personnage(user, personnage):
        raise HTTPException(status_code=403, detail="Vous ne faites entrer que vos propres personnages")
    ancienne = db.get(models.Maisons, personnage.maison_id) if personnage.maison_id and personnage.maison_id != maison.id else None
    if ancienne and ancienne.chef_id == personnage.id:
        raise HTTPException(status_code=400, detail=f"{personnage.name} est à la tête de la maison {ancienne.title} : désignez d'abord un autre chef")
    personnage.maison_id = maison.id
    db.add(personnage)
    db.commit()
    return read_maison(db, maison.id)

def retirer_membre(db: Session, user: schemas.Users, ID: int, personnageID: int):
    # Son joueur le fait sortir, ou un gestionnaire l'exclut ; le chef reste tant qu'il n'est pas remplacé
    maison = _require_maison(db, ID)
    personnage = _require_personnage(db, personnageID)
    if personnage.maison_id != maison.id:
        raise HTTPException(status_code=404, detail=f"{personnage.name} n'est pas membre de cette maison")
    if not (_peut_gerer_personnage(user, personnage) or peut_gerer_maison(db, user, maison)):
        raise HTTPException(status_code=403, detail="Seuls son joueur et les gestionnaires de la maison peuvent l'en retirer")
    if maison.chef_id == personnage.id:
        raise HTTPException(status_code=400, detail="Le chef ne quitte pas sa maison : désignez d'abord un autre chef, ou dissolvez-la")
    personnage.maison_id = None
    db.add(personnage)
    db.commit()
    return read_maison(db, maison.id)

#endregion
#region Chroniques

def entrees_chroniques(db: Session):
    # Pour crud_chroniques : fondations de maisons, naissances et morts de leurs membres, mariages ; date RP obligatoire
    entrees = []
    maisons = {maison.id: maison for maison in db.exec(select(models.Maisons)).all()}
    for maison in maisons.values():
        if maison.date_fondation:
            entrees.append({"id": f"maison-{maison.id}", "date": maison.created_at, "date_rp": maison.date_fondation,
                            "title": f"Fondation : {nom_maison(maison)}", "description": maison.devise, "lien": f"/maison/{maison.id}"})
    for personnage in db.exec(select(models.Personnages).where(models.Personnages.maison_id.is_not(None))).all():
        maison = maisons.get(personnage.maison_id)
        if not maison:
            continue
        lien = f"/personnage/{personnage.id}"
        if personnage.date_naissance:
            entrees.append({"id": f"naissance-{personnage.id}", "date": personnage.created_at, "date_rp": personnage.date_naissance,
                            "title": f"Naissance : {personnage.name}", "description": majuscule(nom_maison(maison)), "lien": lien})
        if personnage.date_deces and personnage.status == "mort":
            entrees.append({"id": f"mort-{personnage.id}", "date": personnage.updated_at or personnage.created_at, "date_rp": personnage.date_deces,
                            "title": f"Mort : {personnage.name}", "description": majuscule(nom_maison(maison)), "lien": lien})
    statement = select(models.PersonnageLiens).where(models.PersonnageLiens.type == "conjoint", models.PersonnageLiens.status == "accepte")
    for lien in db.exec(statement).all():
        a, b = crud_personnages.get_personnage(db, lien.source_id), crud_personnages.get_personnage(db, lien.cible_id)
        if lien.date_rp and a and b:
            entrees.append({"id": f"mariage-{lien.id}", "date": lien.created_at, "date_rp": lien.date_rp,
                            "title": f"Mariage : {a.name} et {b.name}", "description": None, "lien": f"/personnage/{a.id}"})
    return entrees

#endregion
