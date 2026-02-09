from typing import List, Annotated
from fastapi import Depends
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, FileResponse
from sqlmodel import Session

from . import crud, schemas
from .database import get_db

# Créer un routeur pour les routes utilisateur
router = APIRouter(prefix="/api/bibliotheque")

# -----------------------------------------------
# Journaux
# -----------------------------------------------
@router.post("/journaux/create/", tags=["Journaux"])
def create_journal(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], journal: schemas.Journal, db: Session = Depends(get_db)):
    return crud.create_journal(
        db=db,
        v_journal=journal
    )

@router.post("/journaux/create/db/", tags=["Journaux"])
def create_journal(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], journal: schemas.Journal, db: Session = Depends(get_db)):
    return crud.create_journal_db(
        db=db,
        v_journal=journal
    )

@router.delete("/journaux/delete/", tags=["Journaux"])
def delete_journal(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], JournalID: int, db: Session = Depends(get_db)):
    delete=crud.delete_journal(db=db, v_journalid=JournalID)
    if not delete:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'code': 400, 'text': f"Une erreur est survenue lors de la suppression du journal"}))
    return JSONResponse(content=jsonable_encoder({'code': 200, 'text': f"Le journal a été supprimé"}))

@router.get("/journaux/list/", tags=["Journaux"])
def read_journaux(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    journals = crud.get_journaux(db=db, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(journals))

@router.get("/journaux/read/{JournalID}", tags=["Journaux"])
def read_journal(JournalID: int, db: Session = Depends(get_db)):
    journal = crud.get_journal(db=db, ID=JournalID)
    if journal is None:
        func = {'code': 404, 'journal': journal}
    else:
        func = {'code': 200, 'journal': journal}
    return JSONResponse(content=jsonable_encoder(func))

@router.get("/journaux/user/{UserID}/list", tags=["Journaux"])
def read_journaux_by_user(UserID: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    journals = crud.get_journaux_by_user(db=db, userID=UserID, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(journals))

@router.get("/journaux/contents/{JournalID}", tags=["Journaux"])
def read_journal_contents(JournalID: int, skip: int = 0, limit: int = 10000, db: Session = Depends(get_db)):
    content = crud.get_journal_contents(db=db, journalID=JournalID, skip=skip, limit=limit)
    if content is None:
        func = {'code': 404, 'content': content}
    else:
        func = {'code': 200, 'content': content}
    return JSONResponse(content=jsonable_encoder(func))


# -----------------------------------------------
# Livres
# -----------------------------------------------
@router.post("/livres/create/", tags=["Livres"])
def create_livre(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], livre: schemas.Livre, db: Session = Depends(get_db)):
    return crud.create_livre(
        db=db,
        v_livre=livre
    )

@router.delete("/livres/delete/", tags=["Livres"])
def delete_livre(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], LivreID: int, db: Session = Depends(get_db)):
    delete=crud.delete_livre(db=db, v_livreid=LivreID)
    if not delete:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'code': 400, 'text': f"Une erreur est survenue lors de la suppression du livre"}))
    return JSONResponse(content=jsonable_encoder({'code': 200, 'text': f"Le livre a été supprimé"}))

@router.get("/livres/list/", tags=["Livres"])
def read_livres(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    livres = crud.get_livres(db=db, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(livres))

@router.get("/livres/read/{LivreID}", tags=["Livres"])
def read_livre(LivreID: int, db: Session = Depends(get_db)):
    livre = crud.get_livre(db=db, ID=LivreID)
    if livre is None:
        func = {'code': 404, 'livre': livre}
    else:
        func = {'code': 200, 'livre': livre}
    return JSONResponse(content=jsonable_encoder(func))

@router.get("/livres/user/{UserID}/list", tags=["Livres"])
def read_livres_by_user(UserID: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    livres = crud.get_livres_by_user(db=db, userID=UserID, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(livres))