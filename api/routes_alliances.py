from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session

from . import crud, crud_conflits, schemas
from .database import get_db

# Alliances militaires ou diplomatiques entre civilisations (voir crud_conflits)
router = APIRouter(prefix="/api/alliances", tags=["Alliances"])

CurrentUser = Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)]

def _json(content):
    return JSONResponse(content=jsonable_encoder(content))

# -----------------------------------------------
#region Alliances

@router.get("/list")
def read_alliances(db: Session = Depends(get_db)):
    # [{ alliance, membres, chef_de_file }]
    return _json(crud_conflits.list_alliances(db))

@router.get("/read/{AllianceID}")
def read_alliance(AllianceID: int, db: Session = Depends(get_db)):
    # { alliance, membres, chef_de_file, invitations (en attente), guerres (publiques des membres) }
    return _json({'code': 200, **crud_conflits.read_alliance(db, AllianceID)})

@router.get("/civilisation/{CivilisationID}")
def read_alliances_of_civilisation(CivilisationID: int, db: Session = Depends(get_db)):
    return _json(crud_conflits.alliances_of_civilisation(db, CivilisationID))

@router.post("/create")
def create_alliance(current_user: CurrentUser, alliance: schemas.AllianceCreate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "L'alliance a été fondée", **crud_conflits.create_alliance(db, current_user, alliance)})

@router.put("/update/{AllianceID}")
def update_alliance(current_user: CurrentUser, AllianceID: int, alliance: schemas.AllianceUpdate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "L'alliance a été mise à jour", **crud_conflits.update_alliance(db, current_user, AllianceID, alliance)})

@router.delete("/delete/{AllianceID}")
def delete_alliance(current_user: CurrentUser, AllianceID: int, db: Session = Depends(get_db)):
    crud_conflits.delete_alliance(db, current_user, AllianceID)
    return _json({'code': 200, 'text': "L'alliance a été dissoute"})

#endregion
# -----------------------------------------------
#region Invitations et demandes

@router.get("/invitations/mine")
def read_my_invitations(current_user: CurrentUser, db: Session = Depends(get_db)):
    # Invitations et demandes auxquelles l'utilisateur peut répondre
    return _json(crud_conflits.invitations_for_user(db, current_user))

@router.post("/{AllianceID}/invitations")
def invite_civilisation(current_user: CurrentUser, AllianceID: int, body: schemas.AllianceCivilisation, db: Session = Depends(get_db)):
    return _json({'code': 200, **crud_conflits.invite_civilisation(db, current_user, AllianceID, body.civilisation_id)})

@router.post("/{AllianceID}/demandes")
def request_join(current_user: CurrentUser, AllianceID: int, body: schemas.AllianceCivilisation, db: Session = Depends(get_db)):
    return _json({'code': 200, **crud_conflits.request_join(db, current_user, AllianceID, body.civilisation_id)})

@router.put("/invitations/{InvitationID}/repondre")
def answer_invitation(current_user: CurrentUser, InvitationID: int, body: schemas.ReponseInvitation, db: Session = Depends(get_db)):
    return _json({'code': 200, **crud_conflits.answer_invitation(db, current_user, InvitationID, body.accepter)})

@router.delete("/invitations/{InvitationID}")
def cancel_invitation(current_user: CurrentUser, InvitationID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, **crud_conflits.cancel_invitation(db, current_user, InvitationID)})

#endregion
# -----------------------------------------------
#region Membres

@router.put("/{AllianceID}/membres/{CivilisationID}")
def update_membre(current_user: CurrentUser, AllianceID: int, CivilisationID: int, body: schemas.AllianceMembreUpdate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "Le rôle a été modifié", **crud_conflits.update_membre(db, current_user, AllianceID, CivilisationID, body.role)})

@router.put("/{AllianceID}/transfert")
def transfer_chef(current_user: CurrentUser, AllianceID: int, body: schemas.AllianceCivilisation, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "Le rôle de chef de file a été transféré", **crud_conflits.transfer_chef(db, current_user, AllianceID, body.civilisation_id)})

@router.delete("/{AllianceID}/membres/{CivilisationID}")
def remove_membre(current_user: CurrentUser, AllianceID: int, CivilisationID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La civilisation a quitté l'alliance", **crud_conflits.remove_membre(db, current_user, AllianceID, CivilisationID)})

#endregion
# -----------------------------------------------
