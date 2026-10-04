from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session
from typing import Annotated

from ..db import schemas
from ..services import crud, crud_catalogue
from ..db.database import get_db

# Catalogue des boutiques : articles et prix en tetras par magasin, recherche « où acheter » (voir crud_catalogue)
router = APIRouter(prefix="/api/catalogue", tags=["Catalogue"])

CurrentUser = Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)]

def _json(content):
    return JSONResponse(content=jsonable_encoder(content))

@router.get("/magasin/{MagasinID}")
def read_catalogue_magasin(MagasinID: int, db: Session = Depends(get_db)):
    # [{ id, title, categorie, description, prix, quantite, prix_unitaire, en_stock, updated_at }]
    return _json(crud_catalogue.catalogue_magasin(db, MagasinID))

@router.get("/recherche")
def rechercher_articles(q: str | None = None, categorie: str | None = None, ville_id: int | None = None, en_stock: bool = False, db: Session = Depends(get_db)):
    # { total, resultats: [{ ...article, magasin, commerce, ville, dimension }] }, en stock puis du moins cher à l'unité
    return _json(crud_catalogue.rechercher(db, q=q, categorie=categorie, ville_id=ville_id, en_stock=en_stock))

@router.post("/articles")
def create_article(current_user: CurrentUser, body: schemas.ArticleCreate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "L'article est ajouté au catalogue", 'article': crud_catalogue.create_article(db, current_user, body)})

@router.put("/articles/{ArticleID}")
def update_article(current_user: CurrentUser, ArticleID: int, body: schemas.ArticleUpdate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "L'article est mis à jour", 'article': crud_catalogue.update_article(db, current_user, ArticleID, body)})

@router.delete("/articles/{ArticleID}")
def delete_article(current_user: CurrentUser, ArticleID: int, db: Session = Depends(get_db)):
    crud_catalogue.delete_article(db, current_user, ArticleID)
    return _json({'code': 200, 'text': "L'article est retiré du catalogue"})
