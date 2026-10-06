"""
Population officielle des villes et des civilisations.

- Population mesurée : écrite dans `villes.population` par chaque relevé de la sauvegarde (crud_monde) ; elle n'est
  plus saisie à la main (seul un administrateur du site peut encore la corriger directement).
- Ajustements : un écart motivé (+40 réfugiés, −30 morts de la peste), demandé par les dirigeants de la civilisation
  et accepté ou refusé par un modérateur RP, qui ne peut pas valider sa propre demande. Un écart accepté reste valable
  d'un relevé à l'autre, jusqu'à ce qu'un modérateur le retire.
- Population officielle d'une ville = mesure + écarts acceptés (jamais négative) ; celle d'une civilisation est la
  somme de ses villes. Le Codex en tire l'armée autorisée : un soldat pour dix habitants (« Guerres & batailles »).
"""
import datetime as dt

from fastapi import HTTPException
from sqlmodel import Session, select

from ..db import models, schemas
from .crud import _check_civilisation_rights, get_civilisation_by_id, get_ville_by_id, get_villes_by_civilisation_id
from . import crud_conflits, crud_notifications

HABITANTS_PAR_SOLDAT = 10
STATUTS = ("en_attente", "accepte", "refuse", "retire")


#region Calcul

def _ajustements(db: Session, villeID: int, statuts=STATUTS):
    statement = select(models.PopulationAjustements).where(
        models.PopulationAjustements.ville_id == villeID, models.PopulationAjustements.status.in_(statuts)
    ).order_by(models.PopulationAjustements.demande_at)
    return db.exec(statement).all()

def population_officielle(db: Session, db_ville: models.Villes) -> int:
    ecarts = sum(ajustement.ecart for ajustement in _ajustements(db, db_ville.id, ("accepte",)))
    return max(0, (db_ville.population or 0) + ecarts)

def _derniere_mesure(db: Session, villeID: int):
    # Dernier relevé qui a mesuré la ville : date et méthode (frontières tracées, ou rayon approximatif)
    ligne = db.exec(
        select(models.MondeLieux, models.MondeReleves)
        .where(models.MondeLieux.entity_type == "ville", models.MondeLieux.entity_id == villeID)
        .where(models.MondeReleves.id == models.MondeLieux.releve_id)
        .order_by(models.MondeLieux.releve_id.desc())
    ).first()
    if not ligne:
        return None
    lieu, releve = ligne
    return {"releve_at": releve.releve_at or releve.created_at, "methode": lieu.methode, "rayon": lieu.rayon, "population": lieu.population}

def ajustement_infos(db: Session, ajustement: models.PopulationAjustements):
    return {
        "id": ajustement.id,
        "ville_id": ajustement.ville_id,
        "ecart": ajustement.ecart,
        "motif": ajustement.motif,
        "status": ajustement.status,
        "demande_par": crud_conflits._user_summary(db, ajustement.demande_par),
        "demande_at": ajustement.demande_at,
        "moderateur": crud_conflits._user_summary(db, ajustement.moderateur_id),
        "decision_at": ajustement.decision_at,
        "decision_note": ajustement.decision_note,
    }

#endregion
#region Lecture

def _require_ville(db: Session, villeID: int) -> models.Villes:
    db_ville = get_ville_by_id(db, villeID)
    if not db_ville:
        raise HTTPException(status_code=404, detail="La ville n'existe pas")
    return db_ville

def population_ville(db: Session, villeID: int):
    db_ville = _require_ville(db, villeID)
    ajustements = _ajustements(db, villeID, ("accepte", "en_attente"))
    return {
        "ville_id": db_ville.id,
        "mesuree": db_ville.population or 0,
        "mesure": _derniere_mesure(db, villeID),
        "ajustements": [ajustement_infos(db, a) for a in ajustements if a.status == "accepte"],
        "en_attente": [ajustement_infos(db, a) for a in ajustements if a.status == "en_attente"],
        "officielle": population_officielle(db, db_ville),
    }

def population_civilisation(db: Session, civilisationID: int):
    if not get_civilisation_by_id(db, civilisationID):
        raise HTTPException(status_code=404, detail="La civilisation n'existe pas")
    villes = [
        {"id": ville.id, "title": ville.title, "mesuree": ville.population or 0, "officielle": population_officielle(db, ville)}
        for ville in get_villes_by_civilisation_id(db, civilisationID, limit=10000)
    ]
    officielle = sum(ville["officielle"] for ville in villes)
    return {
        "civilisation_id": civilisationID,
        "officielle": officielle,
        "armee": officielle // HABITANTS_PAR_SOLDAT,
        "habitants_par_soldat": HABITANTS_PAR_SOLDAT,
        "villes": villes,
    }

def ajustements_en_attente(db: Session, user: schemas.Users):
    # File de validation des modérateurs RP, avec la ville et sa civilisation
    crud_conflits._require_moderateur(user)
    statement = select(models.PopulationAjustements).where(models.PopulationAjustements.status == "en_attente").order_by(models.PopulationAjustements.demande_at)
    resultats = []
    for ajustement in db.exec(statement).all():
        db_ville = get_ville_by_id(db, ajustement.ville_id)
        if not db_ville:
            continue
        resultats.append({
            **ajustement_infos(db, ajustement),
            "ville": {"id": db_ville.id, "title": db_ville.title, "civilisation_id": db_ville.civilisation_id, "mesuree": db_ville.population or 0},
        })
    return resultats

#endregion
#region Demande et modération

def demander_ajustement(db: Session, user: schemas.Users, body: schemas.PopulationAjustementCreate):
    db_ville = _require_ville(db, body.ville_id)
    _check_civilisation_rights(db, user, db_ville.civilisation_id)
    motif = (body.motif or "").strip()
    if not body.ecart:
        raise HTTPException(status_code=400, detail="L'écart doit être positif ou négatif, pas nul")
    if not motif:
        raise HTTPException(status_code=400, detail="Un ajustement de population doit être motivé")
    ajustement = models.PopulationAjustements(ville_id=db_ville.id, ecart=body.ecart, motif=motif, demande_par=user.id)
    db.add(ajustement)
    db.commit()
    db.refresh(ajustement)
    crud_notifications.notifier(db, crud_notifications.moderateurs(db), "moderation", f"Ajustement de population à valider : {db_ville.title}",
                                f"Écart de {body.ecart:+d} habitants. {motif}", "/moderation", sauf=user.id)
    return {"ajustement": ajustement_infos(db, ajustement)}

def _require_ajustement(db: Session, ID: int) -> models.PopulationAjustements:
    ajustement = db.get(models.PopulationAjustements, ID)
    if not ajustement:
        raise HTTPException(status_code=404, detail="Cet ajustement n'existe pas")
    return ajustement

def decider_ajustement(db: Session, user: schemas.Users, ID: int, body: schemas.PopulationAjustementDecision):
    crud_conflits._require_moderateur(user)
    ajustement = _require_ajustement(db, ID)
    if ajustement.status != "en_attente":
        raise HTTPException(status_code=400, detail="Cet ajustement a déjà été traité")
    if ajustement.demande_par == user.id:
        raise HTTPException(status_code=403, detail="Un modérateur ne valide pas sa propre demande")
    ajustement.status = "accepte" if body.accepte else "refuse"
    ajustement.moderateur_id = user.id
    ajustement.decision_at = dt.datetime.now()
    ajustement.decision_note = (body.note or "").strip() or None
    db.add(ajustement)
    db.commit()
    db.refresh(ajustement)
    db_ville = get_ville_by_id(db, ajustement.ville_id)
    if db_ville:
        title = f"Ajustement de population {'accepté' if body.accepte else 'refusé'} : {db_ville.title}"
        text = f"Écart de {ajustement.ecart:+d} habitants." + (f" {ajustement.decision_note}" if ajustement.decision_note else "")
        crud_notifications.notifier(db, {ajustement.demande_par}, "decision", title, text, f"/civilisation/{db_ville.civilisation_id}/ville/{db_ville.id}", sauf=user.id)
    return {"ajustement": ajustement_infos(db, ajustement), "population": population_ville(db, ajustement.ville_id)}

def retirer_ajustement(db: Session, user: schemas.Users, ID: int):
    # Le demandeur retire sa demande en attente ; un modérateur retire n'importe quel ajustement (accepté compris)
    ajustement = _require_ajustement(db, ID)
    if ajustement.status not in ("en_attente", "accepte"):
        raise HTTPException(status_code=400, detail="Cet ajustement n'est plus en vigueur")
    moderateur = crud_conflits.is_moderateur(user)
    if not moderateur and not (ajustement.status == "en_attente" and ajustement.demande_par == user.id):
        raise HTTPException(status_code=403, detail="Seuls le demandeur (demande en attente) et les modérateurs RP peuvent retirer un ajustement")
    ajustement.status = "retire"
    if moderateur:
        ajustement.moderateur_id = user.id
        ajustement.decision_at = dt.datetime.now()
    db.add(ajustement)
    db.commit()
    return {"population": population_ville(db, ajustement.ville_id)}

def supprimer_ajustements_ville(db: Session, villeID: int):
    # Nettoyage à la suppression de la ville ; le commit reste à l'appelant
    for ajustement in _ajustements(db, villeID):
        db.delete(ajustement)

#endregion
