from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ..db import schemas
from ..services import crud, crud_actions
from ..db.database import get_db

# Actions secrètes : scellées à l'heure réelle, lecture tracée des administrateurs et modérateurs RP (voir crud_actions)
router = APIRouter(prefix="/api/actions", tags=["Actions secrètes"])

CurrentUser = Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)]

def _json(content):
    return JSONResponse(content=jsonable_encoder(content))

# -----------------------------------------------
#region Lecture

@router.get("/list")
def read_actions(db: Session = Depends(get_db)):
    # Registre public : code, date et empreinte des actions scellées ; tout pour les actions révélées
    return _json(crud_actions.list_actions(db))

@router.get("/read/{ActionID}")
def read_action(ActionID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, **crud_actions.read_action(db, ActionID)})

@router.get("/guerre/{GuerreID}")
def read_actions_of_guerre(GuerreID: int, db: Session = Depends(get_db)):
    # Actions révélées rattachées à la guerre
    return _json(crud_actions.actions_of_guerre(db, GuerreID))

@router.get("/mine")
def read_my_actions(current_user: CurrentUser, db: Session = Depends(get_db)):
    # Actions dont l'utilisateur est l'auteur, en entier, avec les lectures tracées
    return _json(crud_actions.actions_for_user(db, current_user))

@router.post("/lire/{ActionID}")
def lire_action(current_user: CurrentUser, ActionID: int, db: Session = Depends(get_db)):
    # POST : lire une action scellée laisse une trace quand on n'en est pas l'auteur (administrateur, modérateur RP)
    return _json({'code': 200, **crud_actions.lire_action(db, current_user, ActionID)})

#endregion
# -----------------------------------------------
#region Dépôt et révélation

@router.post("/create")
def create_action(current_user: CurrentUser, action: schemas.ActionSecreteCreate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "L'action est scellée", **crud_actions.create_action(db, current_user, action)})

@router.post("/{ActionID}/reveler")
def reveler_action(current_user: CurrentUser, ActionID: int, body: schemas.ActionSecreteRevelation, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "L'action est révélée", **crud_actions.reveler(db, current_user, ActionID, body)})

@router.put("/{ActionID}/piege")
def decider_piege(current_user: CurrentUser, ActionID: int, body: schemas.PiegeDecision, db: Session = Depends(get_db)):
    # Modérateur RP : un piège révélé est-il mortel, ou ne fait-il que blesser ?
    return _json({'code': 200, 'text': "Le piège a été jugé", **crud_actions.decider_piege(db, current_user, ActionID, body)})

#endregion
