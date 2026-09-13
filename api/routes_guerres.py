from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session

from . import crud, crud_conflits, schemas
from .database import get_db

# Guerres militaires (civilisations) et de religion (religions), validées par un modérateur RP (voir crud_conflits)
router = APIRouter(prefix="/api/guerres", tags=["Guerres"])

CurrentUser = Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)]

def _json(content):
    return JSONResponse(content=jsonable_encoder(content))

# -----------------------------------------------
#region Lecture

@router.get("/list")
def read_guerres(db: Session = Depends(get_db)):
    # Guerres publiques (en cours et terminées) : [{ guerre, camps, declarant, moderateur }]
    return _json(crud_conflits.list_guerres_publiques(db))

@router.get("/read/{GuerreID}")
def read_guerre(GuerreID: int, db: Session = Depends(get_db)):
    # Guerre publique ; une déclaration non validée renvoie 404 (voir /prive)
    return _json({'code': 200, **crud_conflits.read_guerre(db, GuerreID)})

@router.get("/prive/{GuerreID}")
def read_guerre_prive(current_user: CurrentUser, GuerreID: int, db: Session = Depends(get_db)):
    # Même réponse, y compris pour une déclaration non validée si l'utilisateur est concerné ou modérateur
    return _json({'code': 200, **crud_conflits.read_guerre(db, GuerreID, current_user)})

@router.get("/entite/{EntityType}/{EntityID}")
def read_guerres_of_entity(EntityType: str, EntityID: int, db: Session = Depends(get_db)):
    # EntityType : civilisation ou religion
    return _json(crud_conflits.guerres_of_entity(db, EntityType, EntityID))

@router.get("/mine")
def read_my_guerres(current_user: CurrentUser, db: Session = Depends(get_db)):
    # { a_valider (modérateurs), mes_guerres (non validées), appels (appels aux armes à accepter) }
    return _json(crud_conflits.guerres_for_user(db, current_user))

#endregion
# -----------------------------------------------
#region Déclaration et modération

@router.post("/declarer")
def declare_guerre(current_user: CurrentUser, guerre: schemas.GuerreDeclaration, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La déclaration de guerre attend la validation d'un modérateur RP", **crud_conflits.declare_guerre(db, current_user, guerre)})

@router.put("/update/{GuerreID}")
def update_guerre(current_user: CurrentUser, GuerreID: int, guerre: schemas.GuerreUpdate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La déclaration a été modifiée", **crud_conflits.update_guerre(db, current_user, GuerreID, guerre)})

@router.put("/{GuerreID}/valider")
def valider_guerre(current_user: CurrentUser, GuerreID: int, body: schemas.GuerreValidation, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La guerre est déclarée et commence", **crud_conflits.valider_guerre(db, current_user, GuerreID, body)})

@router.put("/{GuerreID}/refuser")
def refuser_guerre(current_user: CurrentUser, GuerreID: int, body: schemas.GuerreRefus, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La déclaration de guerre a été refusée", **crud_conflits.refuser_guerre(db, current_user, GuerreID, body)})

@router.put("/{GuerreID}/terminer")
def terminer_guerre(current_user: CurrentUser, GuerreID: int, body: schemas.GuerreFin, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La guerre est terminée", **crud_conflits.terminer_guerre(db, current_user, GuerreID, body)})

@router.delete("/delete/{GuerreID}")
def annuler_declaration(current_user: CurrentUser, GuerreID: int, db: Session = Depends(get_db)):
    crud_conflits.annuler_declaration(db, current_user, GuerreID)
    return _json({'code': 200, 'text': "La déclaration de guerre a été retirée"})

#endregion
# -----------------------------------------------
#region Camps

@router.post("/{GuerreID}/appels")
def appeler_aux_armes(current_user: CurrentUser, GuerreID: int, body: schemas.GuerreAppel, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "L'appel aux armes a été envoyé", **crud_conflits.appeler_aux_armes(db, current_user, GuerreID, body)})

@router.put("/{GuerreID}/appels/{BelligerantID}/repondre")
def repondre_appel(current_user: CurrentUser, GuerreID: int, BelligerantID: int, body: schemas.ReponseAppel, db: Session = Depends(get_db)):
    text = "Vous avez rejoint la guerre" if body.accepter else "Vous avez décliné l'appel aux armes"
    return _json({'code': 200, 'text': text, **crud_conflits.repondre_appel(db, current_user, GuerreID, BelligerantID, body.accepter)})

@router.delete("/{GuerreID}/belligerants/{BelligerantID}")
def retirer_belligerant(current_user: CurrentUser, GuerreID: int, BelligerantID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "Le belligérant a quitté la guerre", **crud_conflits.retirer_belligerant(db, current_user, GuerreID, BelligerantID)})

#endregion
# -----------------------------------------------
