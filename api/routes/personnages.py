from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ..db import schemas
from ..services import crud, crud_personnages
from ..db.database import get_db

# Personnages des joueurs, référentiels (espèces, classes) et messages de journaux attribués (voir crud_personnages)
router = APIRouter(prefix="/api/personnages", tags=["Personnages"])

CurrentUser = Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)]

def _json(content):
    return JSONResponse(content=jsonable_encoder(content))

# -----------------------------------------------
#region Personnages

@router.get("/list")
def read_personnages(db: Session = Depends(get_db)):
    # [{ personnage, joueur, civilisation, ville, quartier, espece, classe, messages_count }]
    return _json(crud_personnages.list_personnages(db))

@router.get("/read/{PersonnageID}")
def read_personnage(PersonnageID: int, db: Session = Depends(get_db)):
    # { ...fiche, messages: [{ id, message_id, excerpt, message_timestamp, journal }] }
    return _json({'code': 200, **crud_personnages.read_personnage(db, PersonnageID)})

@router.get("/user/{UserID}")
def read_personnages_of_user(UserID: int, db: Session = Depends(get_db)):
    return _json(crud_personnages.personnages_of_user(db, UserID))

@router.get("/residence/{Residence}/{ID}")
def read_personnages_of_residence(Residence: str, ID: int, db: Session = Depends(get_db)):
    # Residence : civilisation, ville ou quartier
    return _json(crud_personnages.personnages_of_residence(db, Residence, ID))

@router.get("/habitants/{Residence}")
def read_residents_count(Residence: str, db: Session = Depends(get_db)):
    # { id du lieu: nombre de personnages résidents } (carte)
    return _json(crud_personnages.residents_count(db, Residence))

@router.post("/create")
def create_personnage(current_user: CurrentUser, body: schemas.PersonnageCreate, db: Session = Depends(get_db)):
    infos = crud_personnages.create_personnage(db, current_user, body)
    return _json({'code': 200, 'text': f"{infos['personnage']['name']} a été créé", **infos})

@router.put("/update/{PersonnageID}")
def update_personnage(current_user: CurrentUser, PersonnageID: int, body: schemas.PersonnageUpdate, db: Session = Depends(get_db)):
    infos = crud_personnages.update_personnage(db, current_user, PersonnageID, body)
    return _json({'code': 200, 'text': "Le personnage a été mis à jour", **infos})

@router.delete("/delete/{PersonnageID}")
def delete_personnage(current_user: CurrentUser, PersonnageID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, **crud_personnages.delete_personnage(db, current_user, PersonnageID)})

#endregion
# -----------------------------------------------
#region Référentiels : espèces et classes

@router.get("/referentiel")
def read_referentiels(db: Session = Depends(get_db)):
    # { especes: [{ id, title, description }], classes: [...] }
    return _json(crud_personnages.list_referentiels(db))

@router.post("/referentiel/{Kind}")
def create_referentiel(current_user: CurrentUser, Kind: str, body: schemas.ReferentielItem, db: Session = Depends(get_db)):
    # Kind : especes ou classes ; administrateurs et modérateurs RP
    return _json({'code': 200, **crud_personnages.create_referentiel(db, current_user, Kind, body)})

@router.put("/referentiel/{Kind}/{ID}")
def update_referentiel(current_user: CurrentUser, Kind: str, ID: int, body: schemas.ReferentielItem, db: Session = Depends(get_db)):
    return _json({'code': 200, **crud_personnages.update_referentiel(db, current_user, Kind, ID, body)})

@router.delete("/referentiel/{Kind}/{ID}")
def delete_referentiel(current_user: CurrentUser, Kind: str, ID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, **crud_personnages.delete_referentiel(db, current_user, Kind, ID)})

#endregion
# -----------------------------------------------
#region Messages de journaux

@router.get("/journal/{JournalID}")
def read_links_of_journal(JournalID: int, db: Session = Depends(get_db)):
    # [{ id, message_id, author_uid, user_id, personnage: { id, name, image_url, minecraft_uuid, status } }]
    return _json(crud_personnages.links_of_journal(db, JournalID))

@router.post("/messages")
def link_message(current_user: CurrentUser, body: schemas.PersonnageMessageLink, db: Session = Depends(get_db)):
    # Réservé à l'auteur Discord du message (compte Discord lié), pour l'un de ses personnages
    return _json({'code': 200, **crud_personnages.link_message(db, current_user, body)})

@router.delete("/messages/{LienID}")
def unlink_message(current_user: CurrentUser, LienID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, **crud_personnages.unlink_message(db, current_user, LienID)})

#endregion
# -----------------------------------------------
