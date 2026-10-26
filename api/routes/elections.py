from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ..db import schemas
from ..services import crud, crud_elections
from ..db.database import get_db

# Élections RP et postes de gouvernement (voir crud_elections)
router = APIRouter(prefix="/api/elections", tags=["Élections"])

CurrentUser = Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)]
Viewer = Annotated[schemas.Users | None, Depends(crud.secu_get_current_user_optional)]

def _json(content):
    return JSONResponse(content=jsonable_encoder(content))

# -----------------------------------------------
#region Postes de gouvernement

@router.get("/postes/personnage/{PersonnageID}")
def read_postes_personnage(PersonnageID: int, db: Session = Depends(get_db)):
    # Rôles d'un personnage : [{ id, title, is_representant, lieu: { type, id, title, lien } }]
    return _json(crud_elections.postes_du_personnage(db, PersonnageID))

@router.get("/postes/{EntityType}/{EntityID}")
def read_postes(EntityType: str, EntityID: int, db: Session = Depends(get_db)):
    # Postes du gouvernement d'une civilisation ou d'une ville, et leurs titulaires
    return _json(crud_elections.list_postes(db, EntityType, EntityID))

@router.post("/postes")
def create_poste(current_user: CurrentUser, body: schemas.PosteCreate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "Le poste est créé", 'poste': crud_elections.create_poste(db, current_user, body)})

@router.put("/postes/{PosteID}")
def update_poste(current_user: CurrentUser, PosteID: int, body: schemas.PosteUpdate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "Le poste est mis à jour", 'poste': crud_elections.update_poste(db, current_user, PosteID, body)})

@router.delete("/postes/{PosteID}")
def delete_poste(current_user: CurrentUser, PosteID: int, db: Session = Depends(get_db)):
    crud_elections.delete_poste(db, current_user, PosteID)
    return _json({'code': 200, 'text': "Le poste est supprimé"})

#endregion
# -----------------------------------------------
#region Scrutins

@router.get("/list")
def read_scrutins(entity_type: str | None = None, entity_id: int | None = None, db: Session = Depends(get_db)):
    # Scrutins d'une entité, ou de toutes les entités publiques
    return _json(crud_elections.list_scrutins(db, entity_type, entity_id))

@router.get("/mes-votes")
def read_mes_votes(current_user: CurrentUser, db: Session = Depends(get_db)):
    # Scrutins où le joueur a encore une voix à donner
    return _json(crud_elections.mes_votes(db, current_user))

@router.get("/{ScrutinID}")
def read_scrutin(ScrutinID: int, viewer: Viewer, db: Session = Depends(get_db)):
    # Voix et bulletins seulement au dépouillement ; mes_voix et mes_candidats_possibles selon le demandeur
    return _json({'code': 200, 'scrutin': crud_elections.read_scrutin(db, viewer, ScrutinID)})

@router.post("")
def create_scrutin(current_user: CurrentUser, body: schemas.ScrutinCreate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "Le scrutin est ouvert aux candidatures", 'scrutin': crud_elections.create_scrutin(db, current_user, body)})

@router.post("/{ScrutinID}/annuler")
def annuler_scrutin(current_user: CurrentUser, ScrutinID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "Le scrutin est annulé", 'scrutin': crud_elections.annuler_scrutin(db, current_user, ScrutinID)})

@router.post("/{ScrutinID}/candidatures")
def candidater(current_user: CurrentUser, ScrutinID: int, body: schemas.CandidatureCreate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La candidature est déposée", 'scrutin': crud_elections.candidater(db, current_user, ScrutinID, body)})

@router.delete("/{ScrutinID}/candidatures/{CandidatID}")
def retirer_candidature(current_user: CurrentUser, ScrutinID: int, CandidatID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La candidature est retirée", 'scrutin': crud_elections.retirer_candidature(db, current_user, ScrutinID, CandidatID)})

@router.post("/{ScrutinID}/votes")
def voter(current_user: CurrentUser, ScrutinID: int, body: schemas.VoteCreate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "Le vote est enregistré", 'scrutin': crud_elections.voter(db, current_user, ScrutinID, body)})

#endregion
