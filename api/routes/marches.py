from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ..db import schemas
from ..services import crud, crud_marches
from ..db.database import get_db

# Jours de marché des zones commerciales et foires des villes (voir crud_marches)
router = APIRouter(prefix="/api/marches", tags=["Marchés et foires"])

CurrentUser = Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)]

def _json(content):
    return JSONResponse(content=jsonable_encoder(content))

@router.get("/list")
def read_marches(db: Session = Depends(get_db)):
    # Villes publiques : { jours: [{ cartographie_id, jours, horaires }], foires: [foire à venir ou en cours] }
    return _json(crud_marches.marches_publics(db))

@router.get("/ville/{VilleID}")
def read_marches_ville(VilleID: int, db: Session = Depends(get_db)):
    # { jours, a_venir, passees (les 5 dernières) }
    return _json(crud_marches.marches_ville(db, VilleID))

@router.put("/zones/{CartographieID}/jours")
def set_jours(current_user: CurrentUser, CartographieID: int, body: schemas.MarcheJoursUpdate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "Les jours de marché sont enregistrés", 'jours': crud_marches.set_jours(db, current_user, CartographieID, body)})

@router.post("/foires")
def create_foire(current_user: CurrentUser, body: schemas.FoireCreate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La foire est annoncée", 'foire': crud_marches.create_foire(db, current_user, body)})

@router.put("/foires/{FoireID}")
def update_foire(current_user: CurrentUser, FoireID: int, body: schemas.FoireUpdate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La foire est mise à jour", 'foire': crud_marches.update_foire(db, current_user, FoireID, body)})

@router.delete("/foires/{FoireID}")
def delete_foire(current_user: CurrentUser, FoireID: int, db: Session = Depends(get_db)):
    crud_marches.delete_foire(db, current_user, FoireID)
    return _json({'code': 200, 'text': "La foire est annulée"})
