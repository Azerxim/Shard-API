from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ..db import schemas
from ..services import crud, crud_troupes
from ..db.database import get_db

# Compagnies de mercenaires déclarées par les civilisations, engagées dans les guerres par /api/guerres/{id}/mercenaires
router = APIRouter(prefix="/api/mercenaires", tags=["Mercenaires"])

CurrentUser = Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)]
Viewer = Annotated[schemas.Users | None, Depends(crud.secu_get_current_user_optional)]

def _json(content):
    return JSONResponse(content=jsonable_encoder(content))

@router.get("/list")
def read_mercenaires(viewer: Viewer, db: Session = Depends(get_db)):
    # Marché : compagnies disponibles ou sous contrat (sans dire où elles servent)
    return _json(crud_troupes.list_mercenaires(db, viewer))

@router.get("/civilisation/{CivilisationID}")
def read_mercenaires_civilisation(viewer: Viewer, CivilisationID: int, db: Session = Depends(get_db)):
    # { compagnies, gere, villes } ; contrats et soldats disponibles pour ses dirigeants (et les modérateurs RP)
    return _json(crud_troupes.mercenaires_civilisation(db, viewer, CivilisationID))

@router.post("/create")
def create_compagnie(current_user: CurrentUser, body: schemas.MercenaireCreate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La compagnie est déclarée", **crud_troupes.creer_compagnie(db, current_user, body)})

@router.put("/{MercenaireID}")
def update_compagnie(current_user: CurrentUser, MercenaireID: int, body: schemas.MercenaireUpdate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La compagnie a été modifiée", **crud_troupes.modifier_compagnie(db, current_user, MercenaireID, body)})

@router.put("/{MercenaireID}/rompre")
def rompre_contrat(current_user: CurrentUser, MercenaireID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "Le contrat est rompu : la compagnie quitte la guerre", **crud_troupes.rompre_contrat(db, current_user, MercenaireID)})

@router.delete("/{MercenaireID}")
def dissoudre_compagnie(current_user: CurrentUser, MercenaireID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La compagnie est dissoute", **crud_troupes.dissoudre_compagnie(db, current_user, MercenaireID)})
