from typing import List, Annotated
from fastapi import Depends
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, FileResponse
from sqlmodel import Session

from . import crud, schemas
from .database import get_db

# Créer un routeur pour les routes utilisateur
router = APIRouter(prefix="/api/cartographie")


@router.get("/list/", tags=["Cartographie"])
def read_cartographies(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    result = crud.get_cartographies(db=db, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(result))

@router.get("/id/{CartographieID}", tags=["Cartographie"])
def read_cartographie(CartographieID: int, db: Session = Depends(get_db)):
    cartographie = crud.get_cartographie(db=db, ID=CartographieID)
    if cartographie is None:
        func = {'error': 404, 'cartographie': cartographie}
    else:
        func = {'error': 200, 'cartographie': cartographie}
    return JSONResponse(content=jsonable_encoder(func))

@router.post("/create/", tags=["Cartographie"])
def create_cartographie(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], cartographie: schemas.CartographieCreate, db: Session = Depends(get_db)):
    return crud.create_cartographie(
        db=db,
        v_cartographie=cartographie
    )

@router.delete("/delete/", tags=["Cartographie"])
def delete_cartographie(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], cartographieID: int, db: Session = Depends(get_db)):
    delete=crud.delete_cartographie(db=db, v_cartographieid=cartographieID)
    if not delete:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'error': 400, 'text': f"Une erreur est survenue lors de la suppression du marqueur de cartographie"}))
    return JSONResponse(content=jsonable_encoder({'error': 200, 'text': f"Le marqueur de cartographie a été supprimé"}))

@router.put("/update/", tags=["Cartographie"])
def update_cartographie(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], cartographie: schemas.Cartographie, db: Session = Depends(get_db)):
    return crud.update_cartographie(
        db=db,
        cartographieID=cartographie.id,
        v_cartographie=cartographie
    )

# -----------------------------------------------
@router.get("/types/", tags=["Cartographie"])
def read_cartographie_types(db: Session = Depends(get_db)):
    result = crud.get_cartographies_type(db=db)
    return JSONResponse(content=jsonable_encoder(result))

# -----------------------------------------------
@router.get("/dimensions/read/", tags=["Dimensions"])
def read_dimensions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    result = crud.get_dimensions(db=db, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(result))

@router.get("/dimensions/id/{DimensionID}", tags=["Dimensions"])
def read_dimension(DimensionID: int, db: Session = Depends(get_db)):
    dimension = crud.get_dimension(db=db, ID=DimensionID)
    if dimension is None:
        func = {'error': 404, 'dimension': dimension}
    else:
        func = {'error': 200, 'dimension': dimension}
    return JSONResponse(content=jsonable_encoder(func))

@router.get("/dimensions/title/{DimensionTitle}", tags=["Dimensions"])
def read_dimensions_by_title(DimensionTitle: str, db: Session = Depends(get_db)):
    dimension = crud.get_dimensions_by_title(db=db, title=DimensionTitle)
    if dimension is None:
        func = {'error': 404, 'dimension': dimension}
    else:
        func = {'error': 200, 'dimension': dimension}
    return JSONResponse(content=jsonable_encoder(func))

@router.post("/dimensions/create/", tags=["Dimensions"])
def create_dimension(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], dimension: schemas.DimensionCreate, db: Session = Depends(get_db)):
    return crud.create_dimension(
        db=db,
        v_dimension=dimension
    )

@router.delete("/dimensions/delete/", tags=["Dimensions"])
def delete_dimension(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], DimensionID: int, db: Session = Depends(get_db)):
    delete=crud.delete_dimension(db=db, v_dimensionid=DimensionID)
    if not delete:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'error': 400, 'text': f"Une erreur est survenue lors de la suppression de la dimension"}))
    return JSONResponse(content=jsonable_encoder({'error': 200, 'text': f"La dimension a été supprimée"}))

@router.put("/dimensions/update/", tags=["Dimensions"])
def update_dimension(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], dimension: schemas.Dimension, db: Session = Depends(get_db)):
    return crud.update_dimension(
        db=db,
        dimensionID=dimension.id,
        v_dimension=dimension
    )

# -----------------------------------------------