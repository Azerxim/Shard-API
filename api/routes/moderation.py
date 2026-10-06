from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ..db import schemas
from ..services import crud, crud_moderation
from ..db.database import get_db

# Tableau de bord des modérateurs RP (lecture seule : chaque décision passe par la route de son domaine)
router = APIRouter(prefix="/api/moderation", tags=["Modération"])

CurrentUser = Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)]

@router.get("/tableau")
def read_tableau(current_user: CurrentUser, db: Session = Depends(get_db)):
    # { a_traiter: { guerres, ajustements, fermes, pieges }, suivi: { guerres, fermes, actions_scellees }, historique }
    return JSONResponse(content=jsonable_encoder(crud_moderation.tableau(db, current_user)))
