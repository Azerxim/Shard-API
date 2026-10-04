from typing import Annotated
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from sqlmodel import Session

from ..db import schemas
from ..services import crud, crud_fermes
from ..db.database import get_db

# Déclaration des fermes, validées par un modérateur RP (voir crud_fermes)
router = APIRouter(prefix="/api/fermes", tags=["Fermes"])

CurrentUser = Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)]

def _json(content):
    return JSONResponse(content=jsonable_encoder(content))

@router.get("/mine")
def read_mes_fermes(current_user: CurrentUser, db: Session = Depends(get_db)):
    return _json(crud_fermes.mes_fermes(db, current_user))

@router.get("/list")
def read_fermes(current_user: CurrentUser, status: str | None = None, db: Session = Depends(get_db)):
    # Modérateurs RP : toutes les fermes, en attente d'abord
    return _json(crud_fermes.toutes_les_fermes(db, current_user, status))

@router.get("/read/{FermeID}")
def read_ferme(current_user: CurrentUser, FermeID: int, db: Session = Depends(get_db)):
    return _json(crud_fermes.read_ferme(db, current_user, FermeID))

@router.get("/photo/{Nom}")
def read_photo(Nom: str):
    # Nom aléatoire de 32 caractères : il tient lieu de droit d'accès (une balise <img> n'envoie pas de jeton)
    return FileResponse(crud_fermes.chemin_photo(Nom), headers={"Cache-Control": "private, max-age=86400"})

@router.post("/create")
def declarer_ferme(current_user: CurrentUser, body: schemas.FermeCreate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La ferme est déclarée : un modérateur RP va l'examiner", 'ferme': crud_fermes.declarer(db, current_user, body)})

@router.put("/update/{FermeID}")
def modifier_ferme(current_user: CurrentUser, FermeID: int, body: schemas.FermeUpdate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La ferme est mise à jour", 'ferme': crud_fermes.modifier(db, current_user, FermeID, body)})

@router.post("/photo/{FermeID}")
async def envoyer_photo(current_user: CurrentUser, FermeID: int, photo: UploadFile = File(...), db: Session = Depends(get_db)):
    contenu = await photo.read(crud_fermes.PHOTO_MAX_OCTETS + 1)
    return _json({'code': 200, 'text': "La photo est enregistrée", 'ferme': crud_fermes.enregistrer_photo(db, current_user, FermeID, contenu)})

@router.put("/decision/{FermeID}")
def decider_ferme(current_user: CurrentUser, FermeID: int, body: schemas.FermeDecision, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La décision est enregistrée", 'ferme': crud_fermes.decider(db, current_user, FermeID, body)})

@router.delete("/delete/{FermeID}")
def supprimer_ferme(current_user: CurrentUser, FermeID: int, db: Session = Depends(get_db)):
    crud_fermes.supprimer(db, current_user, FermeID)
    return _json({'code': 200, 'text': "La déclaration de la ferme est retirée"})
