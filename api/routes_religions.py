from typing import List, Annotated
from fastapi import Depends
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, FileResponse
from sqlmodel import Session

from . import crud, schemas
from .database import get_db

# Créer un routeur pour les routes utilisateur
router = APIRouter(prefix="/api/religions")

# @router.get("/list", tags=["Religions"])
# def read_religions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
#     result = crud.get_religions(db=db, skip=skip, limit=limit)
#     return JSONResponse(content=jsonable_encoder(result))

# @router.get("/id/{ReligionID}", tags=["Religions"])
# def read_religion(ReligionID: int, db: Session = Depends(get_db)):
#     religion = crud.get_religion_by_id(db=db, ID=ReligionID)
#     if religion is None:
#         func = {'error': 404, 'religion': religion}
#     else:
#         func = {'error': 200, 'religion': religion}
#     return JSONResponse(content=jsonable_encoder(func))

# @router.post("/create", tags=["Religions"])
# def create_religion(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], religion: schemas.ReligionCreate, db: Session = Depends(get_db)):
#     return crud.create_religion(
#         db=db,
#         v_religion=religion
#     )

# @router.delete("/delete", tags=["Religions"])
# def delete_religion(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], ReligionID: int, db: Session = Depends(get_db)):
#     delete=crud.delete_religion(db=db, v_religionid=ReligionID)
#     if not delete:
#         raise HTTPException(status_code=400, detail=jsonable_encoder({'error': 400, 'text': f"Une erreur est survenue lors de la suppression de la religion"}))
#     return JSONResponse(content=jsonable_encoder({'error': 200, 'text': f"La religion et ses dépendances ont été supprimées"}))

# @router.put("/update/{ReligionID}", tags=["Religions"])
# def update_religion(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], ReligionID: int, religion: schemas.ReligionCreate, db: Session = Depends(get_db)):
#     return crud.update_religion(
#         db=db,
#         religionID=ReligionID,
#         v_religion=religion
#     )

# -----------------------------------------------