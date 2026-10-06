"""
Troupes des guerres : levées ville par ville, toujours sur un champ de bataille ou en mouvement.

- Une civilisation engagée dans une guerre en cours lève des troupes dans ses villes (Fondateur ou Admin). Une ville
  fournit au plus un soldat pour dix habitants de sa population officielle (crud_population), toutes guerres en cours
  et compagnies de mercenaires confondues : un soldat ne combat jamais en deux lieux à la fois (Codex, « Guerres & batailles »).
- Une troupe mobilisée est soit sur un champ de bataille (une zone de conflit tracée pour la guerre), soit en
  mouvement, vers une zone de la guerre ou sans destination annoncée. Sans zone tracée, elle ne peut qu'être en mouvement.
- Un déplacement public s'inscrit dans la chronologie de la guerre ; un déplacement secret ne laisse pas de trace
  publique et doit être scellé en action secrète (Codex). Levée et effectifs ne sont pas annoncés : la répartition
  est déclarée au modérateur RP.
- Visibilité : les troupes d'un camp sont vues par les dirigeants de ses belligérants engagés et par les modérateurs RP ;
  une fois la guerre terminée, par tous (archives).
- Démobilisation : à la demande de la civilisation ou d'un modérateur, au retrait du belligérant, à la fin de la guerre
  (crud_nettoyage.demobiliser_troupes). La troupe reste archivée et libère les soldats de sa ville.

Mercenaires : une civilisation déclare en temps de paix des compagnies (ville, effectif, tarif), dont les soldats restent
réservés dans sa ville. Un belligérant engagé (civilisation ou religion) en engage une dans sa guerre : elle devient une
troupe de son camp, qu'il commande, sans que la civilisation des mercenaires entre dans la guerre. La compagnie revient
sur le marché, avec les soldats qui lui restent, quand la troupe est démobilisée (renvoi, rupture du contrat par sa
civilisation, départ de l'employeur, fin de la guerre) ; une civilisation déjà engagée dans une guerre n'y loue pas ses
compagnies, et celles qui y servent lui reviennent si elle y entre.
"""
import datetime as dt

from fastapi import HTTPException
from sqlmodel import Session, select

from ..db import models, schemas
from . import crud_conflits, crud_nettoyage, crud_population
from .crud import get_civilisation_by_id, get_ville_by_id, get_villes_by_civilisation_id

POSITIONS = {"champ_de_bataille": "sur un champ de bataille", "en_mouvement": "en mouvement"}
COMPAGNIE_STATUTS_ACTIFS = ("disponible", "sous_contrat")
TITRE_MAX = 80
TARIF_MAX = 120


#region Calcul

def _zones(db: Session, guerreID: int):
    # Champs de bataille possibles : zones de conflit tracées pour la guerre (cartographie de type "guerre")
    statement = select(models.Cartographie).where(models.Cartographie.type == "guerre", models.Cartographie.type_id == guerreID)
    return db.exec(statement).all()

def _zone_title(zone: models.Cartographie | None) -> str:
    if not zone:
        return "un lieu inconnu"
    return (zone.title or "").strip() or f"la zone n° {zone.id}"

def _troupes(db: Session, guerreID: int):
    statement = select(models.GuerreTroupes).where(models.GuerreTroupes.guerre_id == guerreID)
    return sorted(db.exec(statement).all(), key=lambda t: (t.status != "mobilisee", t.created_at, t.id))

def soldats_mobilises(db: Session, villeID: int, sauf_troupe: int | None = None, sauf_compagnie: int | None = None) -> int:
    # Soldats de la ville levés dans les guerres en cours, plus ceux de ses compagnies de mercenaires (sous contrat ou non :
    # une compagnie engagée compte une seule fois, par elle-même). sauf_* : troupe ou compagnie dont on modifie l'effectif
    statement = (
        select(models.GuerreTroupes, models.Guerres)
        .where(models.GuerreTroupes.ville_id == villeID, models.GuerreTroupes.status == "mobilisee", models.GuerreTroupes.mercenaire_id.is_(None))
        .where(models.Guerres.id == models.GuerreTroupes.guerre_id, models.Guerres.status == "en_cours")
    )
    troupes = sum(troupe.effectif for troupe, _ in db.exec(statement).all() if troupe.id != sauf_troupe)
    compagnies = db.exec(select(models.Mercenaires).where(models.Mercenaires.ville_id == villeID, models.Mercenaires.status.in_(COMPAGNIE_STATUTS_ACTIFS))).all()
    return troupes + sum(compagnie.effectif for compagnie in compagnies if compagnie.id != sauf_compagnie)

def levee_ville(db: Session, db_ville: models.Villes):
    # Armée autorisée d'une ville, soldats déjà mobilisés et soldats encore disponibles
    population = crud_population.population_officielle(db, db_ville)
    armee = population // crud_population.HABITANTS_PAR_SOLDAT
    mobilises = soldats_mobilises(db, db_ville.id)
    return {
        "id": db_ville.id, "title": db_ville.title, "population": population,
        "armee": armee, "mobilises": mobilises, "disponibles": max(0, armee - mobilises),
    }

def _ville_summary(ville_id: int | None, ville_title: str | None, db: Session | None = None):
    # Avec db : position de la ville (point de départ des troupes en mouvement sur la carte de la guerre)
    if not (ville_id or ville_title):
        return None
    summary = {"id": ville_id, "title": ville_title}
    db_ville = get_ville_by_id(db, ville_id) if db is not None and ville_id else None
    if db_ville:
        summary.update({"dimension_id": db_ville.dimension_id, "x": db_ville.x, "z": db_ville.z})
    return summary

def troupe_infos(db: Session, troupe: models.GuerreTroupes, zones: dict):
    zone = zones.get(troupe.zone_id)
    employeur_type, employeur_id = crud_nettoyage.employeur(troupe)
    return {
        "id": troupe.id,
        "camp": troupe.camp,
        "title": troupe.title,
        "effectif": troupe.effectif,
        "position": troupe.position,
        "zone": {"id": zone.id, "title": _zone_title(zone), "dimension_id": zone.dimension_id} if zone else None,
        "status": troupe.status,
        "civilisation": crud_conflits._entity_summary(db, "civilisation", troupe.civilisation_id, troupe.civilisation_title),
        "ville": _ville_summary(troupe.ville_id, troupe.ville_title, db),
        # Compagnie de mercenaires : sa civilisation n'est pas dans la guerre, l'employeur la commande
        "mercenaire_id": troupe.mercenaire_id,
        "employeur": crud_conflits._entity_summary(db, employeur_type, employeur_id, troupe.employeur_title) if troupe.mercenaire_id else None,
        "created_at": troupe.created_at,
        "updated_at": troupe.updated_at,
        "demobilisee_at": troupe.demobilisee_at,
    }

#endregion
#region Droits

def _engagements(db: Session, guerreID: int):
    return [b for b in crud_conflits._belligerants(db, guerreID) if b.status == "engage"]

def _civilisation_engagee(db: Session, guerreID: int, civilisationID: int) -> bool:
    return any(b.entity_type == "civilisation" and b.entity_id == civilisationID for b in _engagements(db, guerreID))

def camps_visibles(db: Session, user: schemas.Users | None, db_guerre: models.Guerres):
    # Camps dont l'utilisateur voit les troupes
    if db_guerre.status == "terminee" or crud_conflits.is_moderateur(user):
        return set(crud_conflits.CAMPS)
    return {b.camp for b in _engagements(db, db_guerre.id) if crud_conflits.can_manage_entity(db, user, b.entity_type, b.entity_id)}

def _employeurs(db: Session, user: schemas.Users | None, db_guerre: models.Guerres):
    # Belligérants engagés (civilisations ou religions) que l'utilisateur dirige, pendant la guerre
    if not user or db_guerre.status != "en_cours":
        return []
    return [b for b in _engagements(db, db_guerre.id) if crud_conflits.can_manage_entity(db, user, b.entity_type, b.entity_id)]

def _civilisations_levables(db: Session, user: schemas.Users, db_guerre: models.Guerres):
    # Civilisations engagées que l'utilisateur dirige : [(belligérant, civilisation)]
    result = []
    for b in _employeurs(db, user, db_guerre):
        db_civilisation = get_civilisation_by_id(db, b.entity_id) if b.entity_type == "civilisation" else None
        if db_civilisation:
            result.append((b, db_civilisation))
    return result

def can_command_troupe(db: Session, user: schemas.Users | None, troupe: models.GuerreTroupes) -> bool:
    # Le belligérant qui la commande (sa civilisation, ou l'employeur des mercenaires), ou un modérateur RP (arbitrage)
    if not user or user.is_disabled:
        return False
    return crud_conflits.is_moderateur(user) or crud_conflits.can_manage_entity(db, user, *crud_nettoyage.employeur(troupe))

def can_demobiliser_troupe(db: Session, user: schemas.Users | None, troupe: models.GuerreTroupes) -> bool:
    # Celui qui la commande ; pour des mercenaires, aussi leur civilisation (rupture du contrat)
    if can_command_troupe(db, user, troupe):
        return True
    return bool(troupe.mercenaire_id and user and not user.is_disabled and crud_conflits.can_manage_entity(db, user, "civilisation", troupe.civilisation_id))

def _require_guerre_en_cours(db: Session, guerreID: int):
    db_guerre = crud_conflits._require_guerre(db, guerreID)
    if db_guerre.status != "en_cours":
        raise HTTPException(status_code=400, detail="Les troupes ne bougent que pendant une guerre en cours")
    return db_guerre

def _require_troupe(db: Session, user: schemas.Users, guerreID: int, troupeID: int, demobilisation: bool = False):
    db_guerre = _require_guerre_en_cours(db, guerreID)
    troupe = db.get(models.GuerreTroupes, troupeID)
    if not troupe or troupe.guerre_id != guerreID:
        raise HTTPException(status_code=404, detail="Cette troupe ne participe pas à cette guerre")
    autorise = can_demobiliser_troupe(db, user, troupe) if demobilisation else can_command_troupe(db, user, troupe)
    if not autorise:
        raise HTTPException(status_code=403, detail="Seuls ceux qui commandent cette troupe et les modérateurs RP peuvent le faire")
    if troupe.status != "mobilisee":
        raise HTTPException(status_code=400, detail="Cette troupe est démobilisée")
    return db_guerre, troupe

#endregion
#region Vérifications

def _check_title(title: str | None, quoi: str = "la troupe") -> str:
    title = (title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail=f"Donnez un nom à {quoi}")
    if len(title) > TITRE_MAX:
        raise HTTPException(status_code=400, detail=f"Le nom ne dépasse pas {TITRE_MAX} caractères")
    return title

def _check_effectif(db: Session, db_ville: models.Villes | None, effectif: int | None, sauf_troupe: int | None = None, sauf_compagnie: int | None = None) -> int:
    if effectif is None or effectif < 1:
        raise HTTPException(status_code=400, detail="Une troupe compte au moins un soldat")
    if db_ville is None:
        return effectif  # ville disparue : plus de population de référence, l'effectif ne peut que baisser (voir les appelants)
    armee = crud_population.population_officielle(db, db_ville) // crud_population.HABITANTS_PAR_SOLDAT
    disponibles = armee - soldats_mobilises(db, db_ville.id, sauf_troupe=sauf_troupe, sauf_compagnie=sauf_compagnie)
    if effectif > disponibles:
        modification = sauf_troupe is not None or sauf_compagnie is not None
        combien = f"au plus {max(0, disponibles)} soldat(s) à cette troupe" if modification else f"que {max(0, disponibles)} soldat(s) de plus"
        raise HTTPException(
            status_code=400,
            detail=f"{db_ville.title} ne peut fournir {combien} "
                   f"(un pour {crud_population.HABITANTS_PAR_SOLDAT} habitants, guerres en cours et mercenaires déduits)",
        )
    return effectif

def _check_position(db: Session, guerreID: int, position: str | None, zone_id: int | None):
    # Une troupe mobilisée est sur un champ de bataille de la guerre, ou en mouvement (destination facultative)
    if position not in POSITIONS:
        raise HTTPException(status_code=400, detail="Une troupe est « champ_de_bataille » ou « en_mouvement »")
    if position == "champ_de_bataille" and zone_id is None:
        raise HTTPException(status_code=400, detail="Choisissez le champ de bataille de la troupe, ou mettez-la en mouvement")
    if zone_id is None:
        return None
    zone = db.get(models.Cartographie, zone_id)
    if not zone or zone.type != "guerre" or zone.type_id != guerreID:
        raise HTTPException(status_code=400, detail="Ce lieu n'est pas une zone de conflit de cette guerre")
    return zone

#endregion
#region Lecture

def troupes_guerre(db: Session, user: schemas.Users | None, guerreID: int):
    # { champs: [zones], camps_visibles, troupes: { attaquant: [...] | None, defenseur: [...] | None }, levees: [...],
    #   employeurs: [belligérants que l'utilisateur dirige], mercenaires: [compagnies qu'il peut engager] }
    # Un camp invisible vaut None ; levees, employeurs et mercenaires ne sont remplis que pendant la guerre
    db_guerre = crud_conflits._require_visible_guerre(db, user, guerreID)
    zones = {zone.id: zone for zone in _zones(db, guerreID)}
    visibles = camps_visibles(db, user, db_guerre)
    troupes = {camp: [] if camp in visibles else None for camp in crud_conflits.CAMPS}
    for troupe in _troupes(db, guerreID):
        if troupes.get(troupe.camp) is not None:
            infos = troupe_infos(db, troupe, zones)
            infos["peut_commander"] = db_guerre.status == "en_cours" and troupe.status == "mobilisee" and can_command_troupe(db, user, troupe)
            troupes[troupe.camp].append(infos)

    levees = []
    for b, db_civilisation in _civilisations_levables(db, user, db_guerre):
        villes = sorted(get_villes_by_civilisation_id(db, db_civilisation.id, limit=10000), key=lambda ville: ville.title)
        levees.append({
            "camp": b.camp,
            "civilisation": crud_conflits._entity_summary(db, "civilisation", db_civilisation.id),
            "villes": [levee_ville(db, ville) for ville in villes],
        })

    employeurs = _employeurs(db, user, db_guerre)
    mercenaires = []
    if employeurs:
        engagees = {b.entity_id for b in _engagements(db, guerreID) if b.entity_type == "civilisation"}
        statement = select(models.Mercenaires).where(models.Mercenaires.status == "disponible")
        mercenaires = [compagnie_infos(db, c) for c in db.exec(statement).all() if c.civilisation_id not in engagees]
        mercenaires.sort(key=lambda c: (c["civilisation"]["title"], c["title"]))
    return {
        "champs": sorted(
            [{"id": zone.id, "title": _zone_title(zone), "dimension_id": zone.dimension_id} for zone in zones.values()],
            key=lambda zone: zone["title"],
        ),
        "camps_visibles": sorted(visibles),
        "troupes": troupes,
        "levees": levees,
        "employeurs": [{**crud_conflits._entity_summary(db, b.entity_type, b.entity_id, b.entity_title), "camp": b.camp} for b in employeurs],
        "mercenaires": mercenaires,
    }

#endregion
#region Levée et commandement

def lever_troupe(db: Session, user: schemas.Users, guerreID: int, body: schemas.GuerreTroupeLevee):
    db_guerre = _require_guerre_en_cours(db, guerreID)
    db_ville = get_ville_by_id(db, body.ville_id)
    if not db_ville:
        raise HTTPException(status_code=404, detail="La ville n'existe pas")
    belligerant = next((b for b, civ in _civilisations_levables(db, user, db_guerre) if civ.id == db_ville.civilisation_id), None)
    if not belligerant:
        raise HTTPException(status_code=403, detail="Seuls le fondateur et les admins d'une civilisation engagée dans la guerre lèvent des troupes dans ses villes")
    title = _check_title(body.title)
    effectif = _check_effectif(db, db_ville, body.effectif)
    zone = _check_position(db, guerreID, body.position, body.zone_id)
    db_civilisation = get_civilisation_by_id(db, db_ville.civilisation_id)

    troupe = models.GuerreTroupes(
        guerre_id=guerreID, camp=belligerant.camp,
        civilisation_id=db_civilisation.id, civilisation_title=db_civilisation.title,
        ville_id=db_ville.id, ville_title=db_ville.title,
        title=title, effectif=effectif, position=body.position, zone_id=zone.id if zone else None,
        created_by=user.id,
    )
    db.add(troupe)
    db.commit()
    db.refresh(troupe)
    return {"troupe": troupe_infos(db, troupe, {zone.id: zone} if zone else {})}

def engager_mercenaires(db: Session, user: schemas.Users, guerreID: int, body: schemas.GuerreMercenaireEngagement):
    # Un belligérant engagé loue une compagnie : elle rejoint son camp, sa civilisation reste hors de la guerre
    db_guerre = _require_guerre_en_cours(db, guerreID)
    employeur = next((b for b in _employeurs(db, user, db_guerre) if (b.entity_type, b.entity_id) == (body.employeur_type, body.employeur_id)), None)
    if not employeur:
        raise HTTPException(status_code=403, detail="Seuls le fondateur et les admins d'un belligérant engagé engagent des mercenaires en son nom")
    compagnie = db.get(models.Mercenaires, body.mercenaire_id)
    if not compagnie or compagnie.status == "dissoute":
        raise HTTPException(status_code=404, detail="Cette compagnie de mercenaires n'existe pas")
    if compagnie.status != "disponible":
        raise HTTPException(status_code=400, detail="Cette compagnie est déjà sous contrat")
    if _civilisation_engagee(db, guerreID, compagnie.civilisation_id):
        raise HTTPException(status_code=400, detail="La civilisation de cette compagnie est engagée dans la guerre : elle y lève ses propres troupes")
    zone = _check_position(db, guerreID, body.position, body.zone_id)
    db_civilisation = get_civilisation_by_id(db, compagnie.civilisation_id)

    troupe = models.GuerreTroupes(
        guerre_id=guerreID, camp=employeur.camp,
        civilisation_id=compagnie.civilisation_id, civilisation_title=db_civilisation.title if db_civilisation else None,
        ville_id=compagnie.ville_id, ville_title=compagnie.ville_title,
        title=compagnie.title, effectif=compagnie.effectif, position=body.position, zone_id=zone.id if zone else None,
        mercenaire_id=compagnie.id, employeur_type=employeur.entity_type, employeur_id=employeur.entity_id,
        employeur_title=crud_conflits._entity_summary(db, employeur.entity_type, employeur.entity_id, employeur.entity_title)["title"],
        created_by=user.id,
    )
    compagnie.status = "sous_contrat"
    compagnie.updated_at = dt.datetime.now()
    db.add(compagnie)
    db.add(troupe)
    db.commit()
    db.refresh(troupe)
    return {"troupe": troupe_infos(db, troupe, {zone.id: zone} if zone else {})}

def modifier_troupe(db: Session, user: schemas.Users, guerreID: int, troupeID: int, body: schemas.GuerreTroupeUpdate):
    # Nom, pertes ou renforts ; les renforts restent dans la limite de la ville. Des mercenaires ne reçoivent pas de
    # renforts et gardent le nom de leur compagnie : seules leurs pertes s'inscrivent, et la compagnie les garde
    _, troupe = _require_troupe(db, user, guerreID, troupeID)
    data = body.model_dump(exclude_unset=True)
    if data.get("title") is not None and not troupe.mercenaire_id:
        troupe.title = _check_title(data["title"])
    if data.get("effectif") is not None:
        db_ville = get_ville_by_id(db, troupe.ville_id) if troupe.ville_id else None
        if data["effectif"] > troupe.effectif and troupe.mercenaire_id:
            raise HTTPException(status_code=400, detail="Une compagnie de mercenaires ne reçoit pas de renforts en pleine guerre")
        if data["effectif"] > troupe.effectif and db_ville is None:
            raise HTTPException(status_code=400, detail="La ville de cette troupe a disparu : elle ne reçoit plus de renforts")
        troupe.effectif = _check_effectif(db, None if troupe.mercenaire_id else db_ville, data["effectif"], sauf_troupe=troupe.id)
        compagnie = db.get(models.Mercenaires, troupe.mercenaire_id) if troupe.mercenaire_id else None
        if compagnie:
            compagnie.effectif = troupe.effectif
            db.add(compagnie)
    troupe.updated_at = dt.datetime.now()
    db.add(troupe)
    db.commit()
    db.refresh(troupe)
    return {"troupe": troupe_infos(db, troupe, {zone.id: zone for zone in _zones(db, guerreID)})}

def deplacer_troupe(db: Session, user: schemas.Users, guerreID: int, troupeID: int, body: schemas.GuerreTroupeMouvement):
    _, troupe = _require_troupe(db, user, guerreID, troupeID)
    zone = _check_position(db, guerreID, body.position, body.zone_id)
    zone_id = zone.id if zone else None
    if (body.position, zone_id) == (troupe.position, troupe.zone_id):
        raise HTTPException(status_code=400, detail="La troupe est déjà à cette position")
    troupe.position = body.position
    troupe.zone_id = zone_id
    troupe.updated_at = dt.datetime.now()
    db.add(troupe)
    if not body.secret:
        # Déplacement public : inscrit dans la chronologie, sans l'effectif (la répartition reste au modérateur RP)
        qui = f"{troupe.title} ({troupe.civilisation_title})" if troupe.civilisation_title else troupe.title
        if body.position == "champ_de_bataille":
            title = f"{qui} prend position : {_zone_title(zone)}"
        elif zone:
            title = f"{qui} fait mouvement vers {_zone_title(zone)}"
        else:
            title = f"{qui} se met en marche"
        crud_conflits._add_evenement(db, guerreID, "deplacement", title[:200], camp=troupe.camp, user=user)
    db.commit()
    db.refresh(troupe)
    return {"troupe": troupe_infos(db, troupe, {zone.id: zone} if zone else {})}

def demobiliser_troupe(db: Session, user: schemas.Users, guerreID: int, troupeID: int):
    # La troupe rentre : elle reste dans les archives de la guerre et rend ses soldats à sa ville ; des mercenaires
    # (renvoyés par l'employeur, ou rappelés par leur civilisation) reviennent sur le marché
    _, troupe = _require_troupe(db, user, guerreID, troupeID, demobilisation=True)
    crud_nettoyage.demobiliser(db, troupe)
    db.commit()
    return {"resultat": "Troupe démobilisée"}

#endregion
#region Compagnies de mercenaires

def _contrat(db: Session, compagnie: models.Mercenaires):
    # Troupe qui sert la compagnie dans une guerre, si elle est sous contrat
    statement = select(models.GuerreTroupes).where(models.GuerreTroupes.mercenaire_id == compagnie.id, models.GuerreTroupes.status == "mobilisee")
    return db.exec(statement).first()

def compagnie_infos(db: Session, compagnie: models.Mercenaires, prive: bool = False):
    # Public : ce que la compagnie propose. Privé (sa civilisation, modérateurs) : où elle sert sous contrat
    infos = {
        "id": compagnie.id,
        "title": compagnie.title,
        "description": compagnie.description,
        "tarif": compagnie.tarif,
        "effectif": compagnie.effectif,
        "status": compagnie.status,
        "civilisation": crud_conflits._entity_summary(db, "civilisation", compagnie.civilisation_id),
        "ville": _ville_summary(compagnie.ville_id, compagnie.ville_title),
        "updated_at": compagnie.updated_at,
    }
    if prive:
        troupe = _contrat(db, compagnie) if compagnie.status == "sous_contrat" else None
        db_guerre = crud_conflits.get_guerre(db, troupe.guerre_id) if troupe else None
        infos["contrat"] = {
            "guerre": {"id": db_guerre.id, "title": db_guerre.title},
            "troupe": troupe_infos(db, troupe, {zone.id: zone for zone in _zones(db, troupe.guerre_id)}),
        } if troupe and db_guerre else None
    return infos

def _visible(db: Session, viewer: schemas.Users | None, compagnie: models.Mercenaires) -> bool:
    db_civilisation = get_civilisation_by_id(db, compagnie.civilisation_id)
    if not db_civilisation or compagnie.status == "dissoute":
        return False
    return db_civilisation.is_public is not False or crud_conflits.can_manage_entity(db, viewer, "civilisation", db_civilisation.id) or crud_conflits.is_moderateur(viewer)

def list_mercenaires(db: Session, viewer: schemas.Users | None):
    # Marché des mercenaires : compagnies des civilisations publiques, disponibles d'abord
    compagnies = db.exec(select(models.Mercenaires).where(models.Mercenaires.status.in_(COMPAGNIE_STATUTS_ACTIFS))).all()
    result = [compagnie_infos(db, c) for c in compagnies if _visible(db, viewer, c)]
    return sorted(result, key=lambda c: (c["status"] != "disponible", c["civilisation"]["title"], c["title"]))

def mercenaires_civilisation(db: Session, viewer: schemas.Users | None, civilisationID: int):
    # { compagnies, gere, villes } : villes (soldats disponibles) et contrats seulement pour ses dirigeants et les modérateurs
    db_civilisation = get_civilisation_by_id(db, civilisationID)
    if not db_civilisation:
        raise HTTPException(status_code=404, detail="La civilisation n'existe pas")
    gere = crud_conflits.can_manage_entity(db, viewer, "civilisation", civilisationID)
    prive = gere or crud_conflits.is_moderateur(viewer)
    if db_civilisation.is_public is False and not prive:
        return {"compagnies": [], "gere": False, "villes": []}
    statement = select(models.Mercenaires).where(models.Mercenaires.civilisation_id == civilisationID, models.Mercenaires.status.in_(COMPAGNIE_STATUTS_ACTIFS))
    compagnies = sorted(db.exec(statement).all(), key=lambda c: (c.status != "disponible", c.title))
    villes = sorted(get_villes_by_civilisation_id(db, civilisationID, limit=10000), key=lambda ville: ville.title) if gere else []
    return {
        "compagnies": [compagnie_infos(db, c, prive=prive) for c in compagnies],
        "gere": gere,
        "villes": [levee_ville(db, ville) for ville in villes],
    }

def _check_tarif(tarif: str | None):
    tarif = (tarif or "").strip() or None
    if tarif and len(tarif) > TARIF_MAX:
        raise HTTPException(status_code=400, detail=f"Le tarif ne dépasse pas {TARIF_MAX} caractères")
    return tarif

def creer_compagnie(db: Session, user: schemas.Users, body: schemas.MercenaireCreate):
    db_ville = get_ville_by_id(db, body.ville_id)
    if not db_ville or not db_ville.civilisation_id:
        raise HTTPException(status_code=404, detail="La ville n'existe pas")
    crud_conflits._require_entity_rights(db, user, "civilisation", db_ville.civilisation_id)
    compagnie = models.Mercenaires(
        civilisation_id=db_ville.civilisation_id, ville_id=db_ville.id, ville_title=db_ville.title,
        title=_check_title(body.title, "la compagnie"), effectif=_check_effectif(db, db_ville, body.effectif),
        description=(body.description or "").strip() or None, tarif=_check_tarif(body.tarif), created_by=user.id,
    )
    db.add(compagnie)
    db.commit()
    db.refresh(compagnie)
    return {"compagnie": compagnie_infos(db, compagnie, prive=True)}

def _require_compagnie(db: Session, user: schemas.Users, ID: int):
    compagnie = db.get(models.Mercenaires, ID)
    if not compagnie or compagnie.status == "dissoute":
        raise HTTPException(status_code=404, detail="Cette compagnie de mercenaires n'existe pas")
    crud_conflits._require_entity_rights(db, user, "civilisation", compagnie.civilisation_id)
    if compagnie.status != "disponible":
        raise HTTPException(status_code=400, detail="Cette compagnie est sous contrat : rompez d'abord le contrat")
    return compagnie

def modifier_compagnie(db: Session, user: schemas.Users, ID: int, body: schemas.MercenaireUpdate):
    compagnie = _require_compagnie(db, user, ID)
    data = body.model_dump(exclude_unset=True)
    if data.get("title") is not None:
        compagnie.title = _check_title(data["title"], "la compagnie")
    if data.get("effectif") is not None:
        db_ville = get_ville_by_id(db, compagnie.ville_id) if compagnie.ville_id else None
        if db_ville is None and data["effectif"] > compagnie.effectif:
            raise HTTPException(status_code=400, detail="La ville de cette compagnie a disparu : elle ne recrute plus")
        compagnie.effectif = _check_effectif(db, db_ville, data["effectif"], sauf_compagnie=compagnie.id)
    if "description" in data:
        compagnie.description = (data["description"] or "").strip() or None
    if "tarif" in data:
        compagnie.tarif = _check_tarif(data["tarif"])
    compagnie.updated_at = dt.datetime.now()
    db.add(compagnie)
    db.commit()
    db.refresh(compagnie)
    return {"compagnie": compagnie_infos(db, compagnie, prive=True)}

def rompre_contrat(db: Session, user: schemas.Users, ID: int):
    # La civilisation rappelle sa compagnie (ou un modérateur l'y renvoie) : la troupe quitte la guerre
    compagnie = db.get(models.Mercenaires, ID)
    if not compagnie or compagnie.status == "dissoute":
        raise HTTPException(status_code=404, detail="Cette compagnie de mercenaires n'existe pas")
    if not crud_conflits.is_moderateur(user):
        crud_conflits._require_entity_rights(db, user, "civilisation", compagnie.civilisation_id)
    troupe = _contrat(db, compagnie)
    if compagnie.status != "sous_contrat" or not troupe:
        raise HTTPException(status_code=400, detail="Cette compagnie n'est pas sous contrat")
    crud_nettoyage.demobiliser(db, troupe)
    db.commit()
    db.refresh(compagnie)
    return {"compagnie": compagnie_infos(db, compagnie, prive=True)}

def dissoudre_compagnie(db: Session, user: schemas.Users, ID: int):
    # Ses soldats redeviennent disponibles dans la ville ; les troupes qu'elle a formées restent dans les archives des guerres
    compagnie = _require_compagnie(db, user, ID)
    compagnie.status = "dissoute"
    compagnie.updated_at = dt.datetime.now()
    db.add(compagnie)
    db.commit()
    return {"resultat": "Compagnie dissoute"}

#endregion
