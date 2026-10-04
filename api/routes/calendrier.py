import datetime as dt
from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ..db import schemas
from ..services import crud, crud_calendrier
from ..db.database import get_db

# Calendrier des événements RP : inscriptions, annonces et événements Discord synchronisés (voir crud_calendrier)
router = APIRouter(prefix="/api/calendrier", tags=["Calendrier"])

CurrentUser = Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)]

def _json(content):
    return JSONResponse(content=jsonable_encoder(content))

@router.get("/list")
def read_calendrier(debut: dt.date | None = None, fin: dt.date | None = None, db: Session = Depends(get_db)):
    # { evenements, foires } qui touchent la période (par défaut : du mois passé à l'an prochain, 400 jours au plus)
    return _json(crud_calendrier.calendrier(db, debut, fin))

@router.get("/read/{EvenementID}")
def read_evenement(EvenementID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, 'evenement': crud_calendrier.read_evenement(db, EvenementID)})

@router.post("/create")
def create_evenement(current_user: CurrentUser, body: schemas.EvenementCreate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "L'événement est annoncé", 'evenement': crud_calendrier.create_evenement(db, current_user, body)})

@router.put("/update/{EvenementID}")
def update_evenement(current_user: CurrentUser, EvenementID: int, body: schemas.EvenementUpdate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "L'événement est mis à jour", 'evenement': crud_calendrier.update_evenement(db, current_user, EvenementID, body)})

@router.post("/{EvenementID}/annuler")
def annuler_evenement(current_user: CurrentUser, EvenementID: int, body: schemas.EvenementAnnulation, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "L'événement est annulé", 'evenement': crud_calendrier.annuler_evenement(db, current_user, EvenementID, body)})

@router.post("/{EvenementID}/inscription")
def inscrire(current_user: CurrentUser, EvenementID: int, body: schemas.EvenementInscription, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "Vous êtes inscrit", 'evenement': crud_calendrier.inscrire(db, current_user, EvenementID, body)})

@router.delete("/{EvenementID}/inscription")
def desinscrire(current_user: CurrentUser, EvenementID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "Votre inscription est retirée", 'evenement': crud_calendrier.desinscrire(db, current_user, EvenementID)})
