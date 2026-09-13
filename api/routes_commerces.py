from typing import List, Annotated
from fastapi import Depends
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, FileResponse
from sqlmodel import Session

from . import crud, schemas
from .database import get_db

# Créer un routeur pour les routes utilisateur
router = APIRouter(prefix="/api/commerces", tags=["Commerces"])

# -----------------------------------------------
#region Commerces
@router.get("/list", tags=["Commerces"])
def read_commerces(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    result = crud.get_commerces(db=db, skip=skip, limit=limit)
    table = [crud.get_all_of_commerce_by_id(db=db, ID=commerce.id) for commerce in result]
    return JSONResponse(content=jsonable_encoder(table))

@router.get("/id/{CommerceID}", tags=["Commerces"])
def read_commerce(CommerceID: int, db: Session = Depends(get_db)):
    commerce = crud.get_commerce_by_id(db=db, ID=CommerceID)
    if commerce is None:
        raise HTTPException(status_code=404, detail=f"Le commerce {CommerceID} n'existe pas")
    return JSONResponse(content=jsonable_encoder({'error': 200, 'commerce': commerce}))

@router.get("/read/{CommerceID}", tags=["Commerces"])
def read_commerce_all(CommerceID: int, db: Session = Depends(get_db)):
    infos = crud.get_all_of_commerce_by_id(db=db, ID=CommerceID)
    if infos is None:
        raise HTTPException(status_code=404, detail=f"Le commerce {CommerceID} n'existe pas")
    # dirigeant : {id, title} du commerce dirigeant ; diriges : commerces dirigés avec leurs magasins
    return JSONResponse(content=jsonable_encoder({'error': 200, **infos, **crud.get_commerce_links(db=db, db_commerce=infos['commerce'])}))

@router.get("/get/{CommerceID}/diriges", tags=["Commerces"])
def read_commerce_diriges(CommerceID: int, db: Session = Depends(get_db)):
    diriges = crud.get_diriges_of_commerce(db=db, commerceID=CommerceID)
    table = [crud.get_all_of_commerce_by_id(db=db, ID=commerce.id) for commerce in diriges]
    return JSONResponse(content=jsonable_encoder(table))

@router.get("/user/{UserID}", tags=["Commerces"])
def read_commerces_by_user(UserID: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # Commerces dont l'utilisateur est membre (Fondateur, Admin ou Membre)
    result = crud.get_commerces_by_member_id(db=db, userID=UserID, skip=skip, limit=limit)
    table = [crud.get_all_of_commerce_by_id(db=db, ID=commerce.id) for commerce in result]
    return JSONResponse(content=jsonable_encoder(table))

@router.post("/create", tags=["Commerces"])
def create_commerce(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], commerce: schemas.CommerceCreate, db: Session = Depends(get_db)):
    result = crud.create_commerce(db=db, user=current_user, v_commerce=commerce)
    infos = crud.get_all_of_commerce_by_id(db=db, ID=result.id)
    return JSONResponse(content=jsonable_encoder({'error': 200, **infos}))

@router.put("/update/{CommerceID}", tags=["Commerces"])
def update_commerce(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], CommerceID: int, commerce: schemas.CommerceUpdate, db: Session = Depends(get_db)):
    result = crud.update_commerce(db=db, user=current_user, commerceID=CommerceID, v_commerce=commerce)
    return JSONResponse(content=jsonable_encoder({'error': 200, 'text': "Le commerce a été mis à jour", 'commerce': result}))

@router.delete("/delete/{CommerceID}", tags=["Commerces"])
def delete_commerce(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], CommerceID: int, db: Session = Depends(get_db)):
    crud.delete_commerce(db=db, user=current_user, commerceID=CommerceID)
    return JSONResponse(content=jsonable_encoder({'error': 200, 'text': "Le commerce et ses magasins ont été supprimés"}))

#endregion
# -----------------------------------------------
#region Membres
@router.get("/members/{CommerceID}/list", tags=["Commerces"])
def list_commerce_members(CommerceID: int, db: Session = Depends(get_db)):
    members = crud.get_members_of_commerce(db=db, commerceID=CommerceID)
    return JSONResponse(content=jsonable_encoder(crud.members_table(db, members)))

@router.put("/members/{CommerceID}/transfer", tags=["Commerces"])
def transfer_commerce_founder(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], CommerceID: int, transfer: schemas.CommerceFounderTransfer, db: Session = Depends(get_db)):
    members = crud.transfer_founder_of_commerce(db=db, user=current_user, commerceID=CommerceID, new_founder_id=transfer.user_id, former_role=transfer.former_role)
    return JSONResponse(content=jsonable_encoder({'code': 200, 'text': "Le fondateur du commerce a été transféré", 'members': crud.members_table(db, members)}))

@router.get("/members/{CommerceID}/{MemberID}/read", tags=["Commerces"])
def read_commerce_member(CommerceID: int, MemberID: int, db: Session = Depends(get_db)):
    member = crud.get_member_of_commerce(db=db, commerceID=CommerceID, userID=MemberID)
    if member is None:
        raise HTTPException(status_code=404, detail=f"L'utilisateur {MemberID} n'est pas membre du commerce {CommerceID}")
    infos = crud.members_table(db, [member])[0]
    # "commerce_member_edit" : clé lue par la modale d'édition (Config_Modal_Commerce_Member_Edit)
    return JSONResponse(content=jsonable_encoder({'error': 200, 'member': infos, 'commerce_member_edit': infos}))

@router.post("/members/{CommerceID}/add", tags=["Commerces"])
def add_commerce_member(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], CommerceID: int, member: schemas.CommerceMemberAdd, db: Session = Depends(get_db)):
    result = crud.add_member_to_commerce(db=db, user=current_user, commerceID=CommerceID, new_member_id=member.user_id, role=member.role)
    return JSONResponse(content=jsonable_encoder(result))

@router.delete("/members/{CommerceID}/remove", tags=["Commerces"])
def remove_commerce_member(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], CommerceID: int, member_id: int, db: Session = Depends(get_db)):
    result = crud.remove_member_from_commerce(db=db, user=current_user, commerceID=CommerceID, member_id=member_id)
    return JSONResponse(content=jsonable_encoder(result))

@router.put("/members/{CommerceID}/{MemberID}/update", tags=["Commerces"])
def update_commerce_member(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], CommerceID: int, MemberID: int, member: schemas.CommerceMemberUpdate, db: Session = Depends(get_db)):
    result = crud.update_member_of_commerce(db=db, user=current_user, commerceID=CommerceID, member_id=MemberID, member=member)
    return JSONResponse(content=jsonable_encoder(result))

#endregion
# -----------------------------------------------
#region Magasins
@router.get("/magasins/list", tags=["Magasins"])
def read_magasins(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    result = crud.get_magasins(db=db, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(result))

@router.get("/magasins/id/{MagasinID}", tags=["Magasins"])
def read_magasin(MagasinID: int, db: Session = Depends(get_db)):
    magasin = crud.get_magasin_by_id(db=db, ID=MagasinID)
    if magasin is None:
        raise HTTPException(status_code=404, detail=f"Le magasin {MagasinID} n'existe pas")
    return JSONResponse(content=jsonable_encoder({'error': 200, 'magasin': magasin}))

@router.get("/magasins/commerce/{CommerceID}", tags=["Magasins"])
def read_magasins_by_commerce(CommerceID: int, skip: int = 0, limit: int = 1000, db: Session = Depends(get_db)):
    result = crud.get_magasins_by_commerce_id(db=db, commerceID=CommerceID, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(result))

@router.get("/magasins/ville/{VilleID}", tags=["Magasins"])
def read_magasins_by_ville(VilleID: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    result = crud.get_magasins_by_ville_id(db=db, villeID=VilleID, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(result))

@router.post("/magasins/create", tags=["Magasins"])
def create_magasin(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], magasin: schemas.MagasinCreate, db: Session = Depends(get_db)):
    result = crud.create_magasin(db=db, user=current_user, v_magasin=magasin)
    return JSONResponse(content=jsonable_encoder({'error': 200, 'magasin': result}))

@router.put("/magasins/update/{MagasinID}", tags=["Magasins"])
def update_magasin(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], MagasinID: int, magasin: schemas.MagasinUpdate, db: Session = Depends(get_db)):
    result = crud.update_magasin(db=db, user=current_user, magasinID=MagasinID, v_magasin=magasin)
    return JSONResponse(content=jsonable_encoder({'error': 200, 'text': "Le magasin a été mis à jour", 'magasin': result}))

@router.delete("/magasins/delete/{MagasinID}", tags=["Magasins"])
def delete_magasin(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], MagasinID: int, db: Session = Depends(get_db)):
    crud.delete_magasin(db=db, user=current_user, magasinID=MagasinID)
    return JSONResponse(content=jsonable_encoder({'error': 200, 'text': "Le magasin a été supprimé"}))

#endregion
# -----------------------------------------------
