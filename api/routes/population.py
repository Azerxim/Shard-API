from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ..db import schemas
from ..services import crud, crud_population
from ..db.database import get_db

# Population officielle : mesure du dernier relevé + écarts motivés validés par un modérateur RP (voir crud_population)
router = APIRouter(prefix="/api/population", tags=["Population"])

CurrentUser = Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)]

def _json(content):
    return JSONResponse(content=jsonable_encoder(content))

@router.get("/ville/{VilleID}")
def read_population_ville(VilleID: int, db: Session = Depends(get_db)):
    # { mesuree, mesure: { releve_at, methode, rayon }, ajustements (acceptés), en_attente, officielle }
    return _json(crud_population.population_ville(db, VilleID))

@router.get("/civilisation/{CivilisationID}")
def read_population_civilisation(CivilisationID: int, db: Session = Depends(get_db)):
    # { officielle, armee, habitants_par_soldat, villes: [{ id, title, mesuree, officielle }] }
    return _json(crud_population.population_civilisation(db, CivilisationID))

@router.get("/ajustements/en-attente")
def read_ajustements_en_attente(current_user: CurrentUser, db: Session = Depends(get_db)):
    # Modérateurs RP : demandes à valider
    return _json(crud_population.ajustements_en_attente(db, current_user))

@router.post("/ajustements")
def demander_ajustement(current_user: CurrentUser, body: schemas.PopulationAjustementCreate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La demande attend la validation d'un modérateur RP", **crud_population.demander_ajustement(db, current_user, body)})

@router.put("/ajustements/{AjustementID}/decision")
def decider_ajustement(current_user: CurrentUser, AjustementID: int, body: schemas.PopulationAjustementDecision, db: Session = Depends(get_db)):
    return _json({'code': 200, **crud_population.decider_ajustement(db, current_user, AjustementID, body)})

@router.delete("/ajustements/{AjustementID}")
def retirer_ajustement(current_user: CurrentUser, AjustementID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "L'ajustement est retiré", **crud_population.retirer_ajustement(db, current_user, AjustementID)})
