from typing import List, Annotated
from fastapi import Depends
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, FileResponse
from sqlmodel import Session

from . import crud, schemas
from .database import get_db

# Créer un routeur pour les routes utilisateur
router = APIRouter(prefix="/api/civilisations")


@router.get("/list/", tags=["Civilisations"])
def read_civilisations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    result = crud.get_civilisations(db=db, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(result))

@router.get("/id/{CivilisationID}", tags=["Civilisations"])
def read_civilisation(CivilisationID: int, db: Session = Depends(get_db)):
    civilisation = crud.get_civilisation_by_id(db=db, ID=CivilisationID)
    if civilisation is None:
        func = {'error': 404, 'civilisation': civilisation}
    else:
        func = {'error': 200, 'civilisation': civilisation}
    return JSONResponse(content=jsonable_encoder(func))

@router.post("/create/", tags=["Civilisations"])
def create_civilisation(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], civilisation: schemas.CivilisationCreate, db: Session = Depends(get_db)):
    return crud.create_civilisation(
        db=db,
        v_civilisation=civilisation
    )

@router.delete("/delete/", tags=["Civilisations"])
def delete_civilisation(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], CivilisationID: int, db: Session = Depends(get_db)):
    delete=crud.delete_civilisation(db=db, v_civilisationid=CivilisationID)
    if not delete:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'error': 400, 'text': f"Une erreur est survenue lors de la suppression de la civilisation"}))
    return JSONResponse(content=jsonable_encoder({'error': 200, 'text': f"La civilisation et ses dépendances ont été supprimées"}))

@router.put("/update/{CivilisationID}", tags=["Civilisations"])
def update_civilisation(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], CivilisationID: int, civilisation: schemas.CivilisationCreate, db: Session = Depends(get_db)):
    return crud.update_civilisation(
        db=db,
        civilisationID=CivilisationID,
        v_civilisation=civilisation
    )

# -----------------------------------------------

@router.get("/gouvernements/list/", tags=["Gouvernements"])
def read_gouvernements(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    result = crud.get_gouvernements(db=db, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(result))

@router.get("/gouvernements/id/{GouvernementID}", tags=["Gouvernements"])
def read_gouvernement(GouvernementID: int, db: Session = Depends(get_db)):
    gouvernement = crud.get_gouvernement_by_id(db=db, ID=GouvernementID)
    if gouvernement is None:
        func = {'error': 404, 'gouvernement': gouvernement}
    else:
        func = {'error': 200, 'gouvernement': gouvernement}
    return JSONResponse(content=jsonable_encoder(func))

@router.post("/gouvernements/create/", tags=["Gouvernements"])
def create_gouvernement(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], gouvernement: schemas.GouvernementCreate, db: Session = Depends(get_db)):
    return crud.create_gouvernement(
        db=db,
        v_gouvernement=gouvernement
    )

@router.delete("/gouvernements/delete/", tags=["Gouvernements"])
def delete_gouvernement(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], GouvernementID: int, db: Session = Depends(get_db)):
    delete=crud.delete_gouvernement(db=db, v_gouvernementid=GouvernementID)
    if not delete:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'error': 400, 'text': f"Une erreur est survenue lors de la suppression du gouvernement"}))
    return JSONResponse(content=jsonable_encoder({'error': 200, 'text': f"Le gouvernement a été supprimé"}))

@router.put("/gouvernements/update/{GouvernementID}", tags=["Gouvernements"])
def update_gouvernement(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], GouvernementID: int, gouvernement: schemas.Gouvernement, db: Session = Depends(get_db)):
    return crud.update_gouvernement(
        db=db,
        gouvernementID=GouvernementID,
        v_gouvernement=gouvernement
    )

# -----------------------------------------------

@router.get("/villes/list/", tags=["Villes"])
def read_villes(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    result = crud.get_villes(db=db, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(result))

@router.get("/villes/id/{VilleID}", tags=["Villes"])
def read_ville(VilleID: int, db: Session = Depends(get_db)):
    ville = crud.get_ville_by_id(db=db, ID=VilleID)
    if ville is None:
        func = {'error': 404, 'ville': ville}
    else:
        func = {'error': 200, 'ville': ville}
    return JSONResponse(content=jsonable_encoder(func))

@router.post("/villes/create/", tags=["Villes"])
def create_ville(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], ville: schemas.VilleCreate, db: Session = Depends(get_db)):
    return crud.create_ville(
        db=db,
        v_ville=ville
    )

@router.delete("/villes/delete/", tags=["Villes"])
def delete_ville(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], VilleID: int, db: Session = Depends(get_db)):
    delete=crud.delete_ville(db=db, v_villeid=VilleID)
    if not delete:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'error': 400, 'text': f"Une erreur est survenue lors de la suppression de la ville"}))
    return JSONResponse(content=jsonable_encoder({'error': 200, 'text': f"La ville et ses dépendances ont été supprimées"}))

@router.put("/villes/update/{VilleID}", tags=["Villes"])
def update_ville(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], VilleID: int, ville: schemas.Ville, db: Session = Depends(get_db)):
    return crud.update_ville(
        db=db,
        villeID=VilleID,
        v_ville=ville
    )

# -----------------------------------------------

@router.get("/quartiers/list/", tags=["Quartiers"])
def read_quartiers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    result = crud.get_quartiers(db=db, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(result))

@router.get("/quartiers/id/{QuartierID}", tags=["Quartiers"])
def read_quartier(QuartierID: int, db: Session = Depends(get_db)):
    quartier = crud.get_quartier_by_id(db=db, ID=QuartierID)
    if quartier is None:
        func = {'error': 404, 'quartier': quartier}
    else:
        func = {'error': 200, 'quartier': quartier}
    return JSONResponse(content=jsonable_encoder(func))

@router.post("/quartiers/create/", tags=["Quartiers"])
def create_quartier(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], quartier: schemas.QuartierCreate, db: Session = Depends(get_db)):
    return crud.create_quartier(
        db=db,
        v_quartier=quartier
    )

@router.delete("/quartiers/delete/", tags=["Quartiers"])
def delete_quartier(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], QuartierID: int, db: Session = Depends(get_db)):
    delete=crud.delete_quartier(db=db, v_quartierid=QuartierID)
    if not delete:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'error': 400, 'text': f"Une erreur est survenue lors de la suppression du quartier"}))
    return JSONResponse(content=jsonable_encoder({'error': 200, 'text': f"Le quartier a été supprimé"}))

@router.put("/quartiers/update/{QuartierID}", tags=["Quartiers"])
def update_quartier(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], QuartierID: int, quartier: schemas.Quartier, db: Session = Depends(get_db)):
    return crud.update_quartier(
        db=db,
        quartierID=QuartierID,
        v_quartier=quartier
    )

# -----------------------------------------------