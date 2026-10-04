from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ..db import schemas
from ..services import crud, crud_lignees
from ..db.database import get_db

# Lignées et généalogie : liens de parenté entre personnages, maisons nobles et leur arbre (voir crud_lignees)
router = APIRouter(prefix="/api/lignees", tags=["Lignées"])

CurrentUser = Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)]

def _json(content):
    return JSONResponse(content=jsonable_encoder(content))

# -----------------------------------------------
#region Liens de parenté

@router.get("/personnage/{PersonnageID}")
def read_famille(PersonnageID: int, db: Session = Depends(get_db)):
    # { maison, parents, enfants, conjoints, fratrie, heritiers, heritier_de } (liens acceptés seulement)
    return _json(crud_lignees.famille(db, PersonnageID))

@router.get("/demandes")
def read_demandes(current_user: CurrentUser, db: Session = Depends(get_db)):
    # { recues, envoyees } : demandes en attente qui concernent les personnages du joueur
    return _json(crud_lignees.demandes(db, current_user))

@router.post("/liens")
def create_lien(current_user: CurrentUser, body: schemas.PersonnageLienCreate, db: Session = Depends(get_db)):
    lien = crud_lignees.create_lien(db, current_user, body)
    texte = "La demande est envoyée au joueur de l'autre personnage" if lien["status"] == "en_attente" else "Le lien de parenté est établi"
    return _json({'code': 200, 'text': texte, 'lien': lien})

@router.post("/liens/{LienID}/accepter")
def accepter_lien(current_user: CurrentUser, LienID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "Le lien de parenté est établi", 'lien': crud_lignees.repondre_lien(db, current_user, LienID, True)})

@router.post("/liens/{LienID}/refuser")
def refuser_lien(current_user: CurrentUser, LienID: int, db: Session = Depends(get_db)):
    crud_lignees.repondre_lien(db, current_user, LienID, False)
    return _json({'code': 200, 'text': "La demande est refusée"})

@router.delete("/liens/{LienID}")
def delete_lien(current_user: CurrentUser, LienID: int, db: Session = Depends(get_db)):
    crud_lignees.delete_lien(db, current_user, LienID)
    return _json({'code': 200, 'text': "Le lien est retiré"})

#endregion
# -----------------------------------------------
#region Maisons

@router.get("/maisons")
def read_maisons(db: Session = Depends(get_db)):
    return _json(crud_lignees.list_maisons(db))

@router.get("/maisons/{MaisonID}")
def read_maison(MaisonID: int, db: Session = Depends(get_db)):
    # { maison, membres, allies, liens } : de quoi dessiner l'arbre
    return _json({'code': 200, **crud_lignees.read_maison(db, MaisonID)})

@router.post("/maisons")
def create_maison(current_user: CurrentUser, body: schemas.MaisonCreate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La maison est fondée", 'maison': crud_lignees.create_maison(db, current_user, body)})

@router.put("/maisons/{MaisonID}")
def update_maison(current_user: CurrentUser, MaisonID: int, body: schemas.MaisonUpdate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La maison est mise à jour", 'maison': crud_lignees.update_maison(db, current_user, MaisonID, body)})

@router.delete("/maisons/{MaisonID}")
def delete_maison(current_user: CurrentUser, MaisonID: int, db: Session = Depends(get_db)):
    crud_lignees.delete_maison(db, current_user, MaisonID)
    return _json({'code': 200, 'text': "La maison est dissoute"})

@router.post("/maisons/{MaisonID}/membres")
def rejoindre_maison(current_user: CurrentUser, MaisonID: int, body: schemas.MaisonMembre, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "Le personnage entre dans la maison", **crud_lignees.rejoindre(db, current_user, MaisonID, body)})

@router.delete("/maisons/{MaisonID}/membres/{PersonnageID}")
def retirer_membre(current_user: CurrentUser, MaisonID: int, PersonnageID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "Le personnage quitte la maison", **crud_lignees.retirer_membre(db, current_user, MaisonID, PersonnageID)})

#endregion
