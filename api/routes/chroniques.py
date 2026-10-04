from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ..db import schemas
from ..services import crud, crud_chroniques
from ..db.database import get_db

# Chroniques de Tetrago : frise déduite des données publiques, et faits marquants des modérateurs RP (voir crud_chroniques)
router = APIRouter(prefix="/api/chroniques", tags=["Chroniques"])

CurrentUser = Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)]

def _json(content):
    return JSONResponse(content=jsonable_encoder(content))

@router.get("/list")
def read_chroniques(db: Session = Depends(get_db)):
    # [{ id, categorie, date, date_rp, title, description, lien, fait_id? }], plus récent d'abord
    return _json(crud_chroniques.chroniques(db))

@router.post("/faits")
def create_fait(current_user: CurrentUser, body: schemas.ChroniqueFait, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "Le fait est inscrit dans les chroniques", 'fait': crud_chroniques.create_fait(db, current_user, body)})

@router.put("/faits/{FaitID}")
def update_fait(current_user: CurrentUser, FaitID: int, body: schemas.ChroniqueFait, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "Le fait est mis à jour", 'fait': crud_chroniques.update_fait(db, current_user, FaitID, body)})

@router.delete("/faits/{FaitID}")
def delete_fait(current_user: CurrentUser, FaitID: int, db: Session = Depends(get_db)):
    crud_chroniques.delete_fait(db, current_user, FaitID)
    return _json({'code': 200, 'text': "Le fait est retiré des chroniques"})
