from typing import List, Annotated
from fastapi import Depends
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, FileResponse
from sqlmodel import Session

from ..db import schemas
from ..services import crud
from ..db.database import get_db

# Créer un routeur pour les routes utilisateur
router = APIRouter(prefix="/api/religions")

# -----------------------------------------------
#region Religions
@router.get("/list", tags=["Religions"])
def read_religions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    result = crud.get_religions(db=db, skip=skip, limit=limit)
    table = []
    for religion in result:
        table.append(crud.get_all_of_religion_by_id(db=db, ID=religion.id))
    return JSONResponse(content=jsonable_encoder(table))

@router.get("/id/{ReligionID}", tags=["Religions"])
def read_religion(ReligionID: int, db: Session = Depends(get_db)):
    religion = crud.get_all_of_religion_by_id(db=db, ID=ReligionID)
    if religion is None:
        func = {'error': 404, 'religion': religion}
    else:
        func = {'error': 200, 'religion': religion}
    return JSONResponse(content=jsonable_encoder(func))

@router.get("/read/{ReligionID}", tags=["Religions"])
def read_religion_all(ReligionID: int, db: Session = Depends(get_db)):
    infos = crud.get_all_of_religion_by_id(db=db, ID=ReligionID)
    if infos is None:
        func = {'error': 404, 'message': f"Religion with ID {ReligionID} not found"}
    else:
        func = {
            'error': 200,
            'religion': infos['religion'],
            'members': jsonable_encoder(infos['members']) if infos['members'] else [],
            'villes': jsonable_encoder(infos['villes']) if infos['villes'] else [],
            'quartiers': jsonable_encoder(infos['quartiers']) if infos['quartiers'] else [],
        }
    return JSONResponse(content=jsonable_encoder(func))

@router.get("/ville/{VilleID}/read/{ReligionID}", tags=["Religions"])
def read_ville_religion(VilleID: int, ReligionID: int, db: Session = Depends(get_db)):
    ville_religion = crud.get_ville_religion_by_id(db=db, villeID=VilleID, religionID=ReligionID)
    if ville_religion is None:
        func = {'error': 404, 'ville_religion': ville_religion}
    else:
        func = {'error': 200, 'ville_religion': ville_religion}
    return JSONResponse(content=jsonable_encoder(func))

@router.get("/ville/{VilleID}", tags=["Religions"])
def read_religions_by_ville(VilleID: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    result = crud.get_religions_by_ville_id(db=db, villeID=VilleID, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(result))

@router.put("/members/{ReligionID}/transfer", tags=["Religions"])
def transfer_religion_founder(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], ReligionID: int, transfer: schemas.ReligionFounderTransfer, db: Session = Depends(get_db)):
    members = crud.transfer_founder_of_religion(
        db=db,
        user=current_user,
        religionID=ReligionID,
        new_founder_id=transfer.user_id,
        former_role=transfer.former_role
    )
    # Même format que "members" de /religions/read
    return JSONResponse(content=jsonable_encoder({'code': 200, 'text': "Le fondateur de la religion a été transféré", 'members': members}))

@router.get("/members/{ReligionID}/list", tags=["Religions"])
def list_religion_members(ReligionID: int, db: Session = Depends(get_db)):
    members = crud.get_members_of_religion(db=db, religionID=ReligionID, limit=10000)
    return JSONResponse(content=jsonable_encoder(crud.members_table(db, members)))

@router.get("/members/{ReligionID}/{MemberID}/read", tags=["Religions"])
def read_religion_member(ReligionID: int, MemberID: int, db: Session = Depends(get_db)):
    member = crud.get_member_of_religion(db=db, religionID=ReligionID, userID=MemberID)
    if member is None:
        raise HTTPException(status_code=404, detail=f"L'utilisateur {MemberID} n'est pas membre de la religion {ReligionID}")
    infos = crud.members_table(db, [member])[0]
    # "religion_member_edit" : clé lue par la modale d'édition (Config_Modal_Religion_Member_Edit)
    return JSONResponse(content=jsonable_encoder({'error': 200, 'member': infos, 'religion_member_edit': infos}))

@router.post("/members/{ReligionID}/add", tags=["Religions"])
def add_religion_member(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], ReligionID: int, member: schemas.ReligionMemberAdd, db: Session = Depends(get_db)):
    result = crud.add_member_to_religion(db=db, user=current_user, religionID=ReligionID, new_member_id=member.user_id, role=member.role)
    return JSONResponse(content=jsonable_encoder(result))

@router.delete("/members/{ReligionID}/remove", tags=["Religions"])
def remove_religion_member(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], ReligionID: int, member_id: int, db: Session = Depends(get_db)):
    result = crud.remove_member_from_religion(db=db, user=current_user, religionID=ReligionID, member_id=member_id)
    return JSONResponse(content=jsonable_encoder(result))

@router.put("/members/{ReligionID}/{MemberID}/update", tags=["Religions"])
def update_religion_member(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], ReligionID: int, MemberID: int, member: schemas.ReligionMemberUpdate, db: Session = Depends(get_db)):
    result = crud.update_member_of_religion(db=db, user=current_user, religionID=ReligionID, member_id=MemberID, member=member)
    return JSONResponse(content=jsonable_encoder(result))

@router.post("/create", tags=["Religions"])
def create_religion(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], religion: schemas.ReligionCreate, db: Session = Depends(get_db)):
    result = crud.create_religion(
        db=db,
        user=current_user,
        v_religion=religion
    )
    return JSONResponse(content=jsonable_encoder({'error': 200, 'religion': result[0], 'member': result[1]}))

@router.delete("/delete/{ReligionID}", tags=["Religions"])
def delete_religion(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], ReligionID: int, db: Session = Depends(get_db)):
    delete=crud.delete_religion(db=db, user=current_user, v_religionid=ReligionID)
    if not delete:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'error': 400, 'text': f"Une erreur est survenue lors de la suppression de la religion"}))
    return JSONResponse(content=jsonable_encoder({'error': 200, 'text': f"La religion et ses dépendances ont été supprimées"}))

@router.put("/update/{ReligionID}", tags=["Religions"])
def update_religion(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], ReligionID: int, religion: schemas.ReligionCreate, db: Session = Depends(get_db)):
    update = crud.update_religion(
        db=db,
        user=current_user,
        religionID=ReligionID,
        v_religion=religion
    )
    if not update:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'error': 400, 'text': f"Une erreur est survenue lors de la mise à jour de la religion"}))
    return JSONResponse(content=jsonable_encoder({'error': 200, 'text': f"La religion a été mise à jour", 'religion': update}))

@router.get("/quartier/{QuartierID}", tags=["Religions"])
def read_religions_by_quartier(QuartierID: int, db: Session = Depends(get_db)):
    return JSONResponse(content=jsonable_encoder(crud.get_religions_by_quartier_id(db=db, quartierID=QuartierID)))

@router.post("/quartier/{QuartierID}/add", tags=["Religions"])
def add_religion_to_quartier(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], QuartierID: int, body: schemas.VillesReligionsUpdate, db: Session = Depends(get_db)):
    result = crud.add_religion_to_quartier(db=db, user=current_user, quartierID=QuartierID, religionID=body.ReligionID, influence=body.influence)
    return JSONResponse(content=jsonable_encoder(result))

@router.put("/quartier/{QuartierID}/update/influence", tags=["Religions"])
def update_influence_of_religion_in_quartier(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], QuartierID: int, body: schemas.VillesReligionsUpdate, db: Session = Depends(get_db)):
    result = crud.update_influence_of_religion_in_quartier(db=db, user=current_user, quartierID=QuartierID, religionID=body.ReligionID, influence=body.influence)
    return JSONResponse(content=jsonable_encoder(result))

@router.delete("/quartier/{QuartierID}/delete/{religionID}", tags=["Religions"])
def delete_religion_from_quartier(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], QuartierID: int, religionID: int, db: Session = Depends(get_db)):
    result = crud.delete_religion_from_quartier(db=db, user=current_user, quartierID=QuartierID, religionID=religionID)
    return JSONResponse(content=jsonable_encoder(result))

@router.post("/ville/{VilleID}/add", tags=["Religions"])
def add_religion_to_ville(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], VilleID: int, body: schemas.VillesReligionsUpdate, db: Session = Depends(get_db)):
    return crud.add_religion_to_ville(
        db=db,
        user=current_user,
        villeID=VilleID,
        v_religionid=body.ReligionID,
        influence=body.influence
    )

@router.put("/ville/{VilleID}/update/influence", tags=["Religions"])
def update_influence_of_religion_in_ville(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], VilleID: int, body: schemas.VillesReligionsUpdate, db: Session = Depends(get_db)):
    return crud.update_influence_of_religion_in_ville(
        db=db,
        user=current_user,
        villeID=VilleID,
        v_religionid=body.ReligionID,
        influence=body.influence
    )

@router.delete("/ville/{VilleID}/delete/{religionID}", tags=["Religions"])
def delete_religion_from_ville(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], VilleID: int, religionID: int, db: Session = Depends(get_db)):
    delete = crud.delete_religion_from_ville(db=db, user=current_user, villeID=VilleID, v_religionid=religionID)
    if not delete:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'error': 400, 'text': f"Une erreur est survenue lors de la suppression de la religion de la ville"}))
    return JSONResponse(content=jsonable_encoder({'error': 200, 'text': f"La religion a été supprimée de la ville"}))

#endregion
# -----------------------------------------------