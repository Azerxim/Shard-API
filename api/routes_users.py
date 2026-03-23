from typing import List, Annotated
from fastapi import Depends
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.encoders import jsonable_encoder
from sqlmodel import Session

from . import crud, schemas, models
from .database import get_db

# Créer un routeur pour les routes utilisateur
router = APIRouter(prefix="/api/users", tags=["Users"])

# -----------------------------------------------
@router.post("/create", response_model=schemas.UserRead)
def create_user(user: schemas.UserLogin, db: Session = Depends(get_db)):
    """Créer un nouvel utilisateur"""
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Le nom d'utilisateur ou l'email est incorrect")
    
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Le nom d'utilisateur ou l'email est incorrect")
    return crud.create_user(db=db, user=user)

# -----------------------------------------------
@router.put("/update/{user_id}", response_model=schemas.UserRead)
async def update_current_user(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], user_id: int, user_update: schemas.UserUpdate, db: Session = Depends(get_db)):
    """Mettre à jour un utilisateur (l'utilisateur lui-même ou un admin)"""
    from sqlmodel import select
    
    db_user = crud.get_user_by_id(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Vérifier que l'utilisateur actuel est soit l'utilisateur lui-même, soit un admin
    if current_user.id != user_id and not current_user.is_admin and not current_user.is_disabled:
        raise HTTPException(status_code=403, detail="Accès refusé")

    return crud.update_user(db=db, user_id=user_id, user_update=user_update)

# -----------------------------------------------
@router.delete("/delete/{user_id}", tags=["Users"])
async def delete_current_user(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], user_id: int, db: Session = Depends(get_db)):
    """Supprimer un utilisateur (l'utilisateur lui-même ou un admin)"""
    from sqlmodel import select
    
    db_user = crud.get_user_by_id(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Vérifier que l'utilisateur actuel est soit l'utilisateur lui-même, soit un admin
    if current_user.id != user_id and not current_user.is_admin and not current_user.is_disabled:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    return crud.delete_user(db=db, user_id=user_id)

# -----------------------------------------------
@router.get("/name/{username}", response_model=schemas.UserRead)
def read_user_by_username(username: str, db: Session = Depends(get_db)):
    """Récupérer un utilisateur par nom d'utilisateur"""
    db_user = crud.get_user_by_username(db, username=username)
    if db_user is None:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    return crud.build_user_read(db_user)

# -----------------------------------------------
@router.get("/id/{user_id}", response_model=schemas.UserRead)
def read_user_by_id(user_id: int, db: Session = Depends(get_db)):
    """Récupérer un utilisateur par ID"""
    db_user = crud.get_user_by_id(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    return crud.build_user_read(db_user)

# -----------------------------------------------
@router.get("/get/{user_id}")
async def get_user_by_id_endpoint(user_id: int, db: Session = Depends(get_db)):
    """Récupérer les informations d'un utilisateur spécifique par ID (admin uniquement)"""
    try:
        from sqlmodel import select
        
        # Récupérer l'utilisateur demandé
        user = crud.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Vérifier qu'il y a au moins un admin
        statement = select(models.Users)
        all_users = db.exec(statement).all()
        has_admin = any(u.is_admin and not u.is_disabled for u in all_users)
        if not has_admin:
            raise HTTPException(status_code=403, detail="Accès refusé")
        
        return JSONResponse(content=jsonable_encoder(crud.build_user_read(user)))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=403, detail="Accès refusé")

# -----------------------------------------------
@router.get("/list", response_model=List[schemas.UserRead])
async def get_users_list(db: Session = Depends(get_db)):
    """Récupérer la liste de tous les utilisateurs (admin uniquement)"""
    try:
        from sqlmodel import select
        
        # Récupérer tous les utilisateurs
        statement = select(models.Users)
        results = db.exec(statement).all()
        
        # Vérifier qu'il y a au moins un admin
        has_admin = any(user.is_admin and not user.is_disabled for user in results)
        if not has_admin:
            raise HTTPException(status_code=403, detail="Accès refusé")
        
        # Retourner tous les utilisateurs
        return JSONResponse(content=jsonable_encoder([crud.build_user_read(user) for user in results]))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=403, detail="Accès refusé")

# -----------------------------------------------
@router.post("/login")
def login_user(user: schemas.UserLogin, db: Session = Depends(get_db)):
    username = "" if user.username is None else user.username
    email = "" if user.email is None else user.email
    password = "" if user.password is None else user.password
    
    if username == "" and email == "":
        func = {'code': 404, 'text': "Il manque les informations de login (username et email)"}
    else:
        if username != "" and email != "":
            (check, user) = crud.check_user_all(db=db, email=email, username=username, password=password)
        elif email != "":
            (check, user) = crud.check_user_from_email(db=db, email=email, password=password)
        else:
            (check, user) = crud.check_user_from_name(db=db, username=username, password=password)
        if check:
            func = {'code': 200, 'user': user}
        elif user is None:
            func = {'code': 404, 'user': {}, 'text': "Aucun utilisateur n'a été trouvé"}
        else:
            func = {'code': 204, 'user': {}, 'text': "Mot de passe incorrect"}
    return JSONResponse(content=jsonable_encoder(func))

# -----------------------------------------------
@router.get("/me", response_model=schemas.UserRead)
async def read_current_user(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], db: Session = Depends(get_db)):
    """Récupérer les informations de l'utilisateur actuellement connecté"""
    user = crud.get_user_by_username(db, username=current_user.username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return JSONResponse(content=jsonable_encoder(crud.build_user_read(user)))

# -----------------------------------------------
@router.post("/token")
async def get_user_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)):
    """
    Authentification OAuth2
    """
    # # Vérifier le client_id et client_secret
    # if utils.CLIENT_ID and utils.CLIENT_SECRET:
    #     client_id = form_data.client_id if form_data.client_id else None
    #     client_secret = form_data.client_secret if form_data.client_secret else None

    #     if not client_id or client_id != utils.CLIENT_ID:
    #         raise HTTPException(status_code=400, detail="Invalid client_id")
    #     if not client_secret or client_secret != utils.CLIENT_SECRET:
    #         raise HTTPException(status_code=400, detail="Invalid client_secret")
    
    # Vérifier les credentials de l'utilisateur
    user_dict = crud.get_user_by_username(db, form_data.username)
    if not user_dict:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    hashed_password = crud.hash_password(form_data.password)
    if not hashed_password == user_dict.hashed_password:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    session = crud.create_active_session(db, user_dict.username)
    return {"access_token": session.access_token, "token_type": "bearer"}