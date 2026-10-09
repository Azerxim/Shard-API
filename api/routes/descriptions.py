from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ..db import schemas
from ..services import crud, crud_descriptions
from ..db.database import get_db

# Description longue (Markdown) des fiches : civilisation, commerce, religion, alliance, personnage (voir crud_descriptions)
router = APIRouter(prefix="/api/descriptions", tags=["Descriptions"])

CurrentUser = Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)]

@router.get("/{EntityType}/{EntityID}")
def read_description(EntityType: str, EntityID: int, db: Session = Depends(get_db)):
    # { type, id, description_longue }
    return JSONResponse(content=jsonable_encoder(crud_descriptions.lire(db, EntityType, EntityID)))

@router.put("/{EntityType}/{EntityID}")
def update_description(current_user: CurrentUser, EntityType: str, EntityID: int, body: schemas.DescriptionLongue, db: Session = Depends(get_db)):
    data = crud_descriptions.modifier(db, current_user, EntityType, EntityID, body)
    return JSONResponse(content=jsonable_encoder({'code': 200, 'text': "La description longue est enregistrée", **data}))
