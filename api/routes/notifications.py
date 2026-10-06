from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ..db import schemas
from ..services import crud, crud_notifications
from ..db.database import get_db

# Notifications du joueur connecté (cloche de la barre du site) ; elles sont écrites par les autres domaines
router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

CurrentUser = Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)]

@router.get("/mine")
def read_mes_notifications(current_user: CurrentUser, limite: int = 30, db: Session = Depends(get_db)):
    # { non_lues, notifications: [{ id, type, title, text, link, created_at, lue }] }, plus récentes d'abord
    return JSONResponse(content=jsonable_encoder(crud_notifications.mes_notifications(db, current_user, limite)))

@router.put("/lue/{NotificationID}")
def marquer_lue(current_user: CurrentUser, NotificationID: int, db: Session = Depends(get_db)):
    crud_notifications.marquer_lue(db, current_user, NotificationID)
    return JSONResponse(content={'code': 200, 'text': "Notification lue"})

@router.put("/lues")
def marquer_toutes_lues(current_user: CurrentUser, db: Session = Depends(get_db)):
    crud_notifications.marquer_toutes_lues(db, current_user)
    return JSONResponse(content={'code': 200, 'text': "Toutes les notifications sont lues"})
