from typing import List, Annotated
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import time as t, datetime as dt
from starlette_discord import DiscordOAuthClient

from . import utils
from topazdevsdk import file as f, colors
from . import crud, models, schemas, crud_security as crudSecu
from .database import SessionLocal, engine


models.Base.metadata.create_all(bind=engine)
app = FastAPI()

################# Dependency ###################
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

################# Templates #####################

templates = Jinja2Templates(directory="html")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

favicon_path = 'assets/images/favicon.ico'
@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse(favicon_path)


################# Security ######################

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# -----------------------------------------------
async def secu_get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)):
    user = crudSecu.secu_decode_token(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# -----------------------------------------------
async def secu_get_current_active_user(current_user: Annotated[schemas.SecurityUsers, Depends(secu_get_current_user)]):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return JSONResponse(content=jsonable_encoder(current_user))

# -----------------------------------------------
@app.post("/token", tags=["Security"])
async def secu_login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)):
    user_dict = crudSecu.secu_get_user_from_username(db, form_data.username)
    if not user_dict:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    hashed_password = crudSecu.hash_password(form_data.password)
    if not hashed_password == user_dict.hashed_password:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    return {"access_token": user_dict.username, "token_type": "bearer"}

# -----------------------------------------------
@app.get("/security/me", tags=["Security"])
async def read_securityusers_me(current_user: Annotated[schemas.SecurityUsers, Depends(secu_get_current_active_user)], db: Session = Depends(get_db)):
    return JSONResponse(content=jsonable_encoder(current_user))

# -----------------------------------------------
@app.get("/security/load", tags=["Security"])
async def security_load(db: Session = Depends(get_db)):
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     -------------------")
    result = crudSecu.loadsecurity(db, utils.SECURITY)
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     -------------------")
    return JSONResponse(content=jsonable_encoder(result))


################### API #########################

@app.on_event("startup")
async def startup_event():
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     -------------------")
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     {colors.BColors.PURPLE}{utils.CONFIG['api']['name']}{colors.BColors.END}")
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Version {colors.BColors.LIGHTBLUE}{utils.CONFIG['api']['version']}{colors.BColors.END}")
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     -------------------")

# -----------------------------------------------
@app.get("/", response_class=HTMLResponse)
def html_main(request: Request):
    return templates.TemplateResponse("version.html", {"request": request, "version": utils.CONFIG['api']['version'], "api": utils.CONFIG['api']['name']})

# @app.get("/")
# def app_main():
#     result = {'api': utils.CONFIG['api']['name'], 'version': utils.CONFIG['api']['version']}
#     return JSONResponse(content=jsonable_encoder(result))

# -----------------------------------------------
@app.get("/version/")
def app_version():
    result = {'api': utils.CONFIG['api']['name'], 'version': utils.CONFIG['api']['version']}
    return JSONResponse(content=jsonable_encoder(result))


################### API #########################

@app.post("/user/create/", tags=["Users"])
def create_user(current_user: Annotated[schemas.SecurityUsers, Depends(secu_get_current_active_user)], user: schemas.createUser, db: Session = Depends(get_db)):
    # Vérification si l'email ou le username existe déjà
    (db_check, db_user) = crud.user_exist(db, username=user.username)
    if db_check:
        raise HTTPException(status_code=400, detail=f"Le nom d'utilisateur '{user.username}' est déjà utilisé !")
    (db_check, db_user) = crud.user_exist(db, email=user.email)
    if db_check:
        raise HTTPException(status_code=400, detail=f"L'adresse email '{user.email}' est déjà utilisée !")
    return crud.create_user(
        db=db,
        v_user=user
    )

# -----------------------------------------------
@app.put("/user/update/", tags=["Users"])
def update_user(current_user: Annotated[schemas.SecurityUsers, Depends(secu_get_current_active_user)], user: schemas.updateUser, db: Session = Depends(get_db)):
    return crud.update_user(
        db=db,
        userID=user.id,
        v_user=user
    )

# -----------------------------------------------
@app.delete("/user/delete/", tags=["Users"])
def delete_user(current_user: Annotated[schemas.SecurityUsers, Depends(secu_get_current_active_user)], UserID: int, db: Session = Depends(get_db)):
    delete=crud.delete_user(db=db, v_userid=UserID)
    if not delete:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'error': 400, 'text': f"Une erreur est survenue lors de la suppression de l'utilisateur"}))
    return JSONResponse(content=jsonable_encoder({'error': 200, 'text': f"L'utilisateur a été supprimé"}))

# -----------------------------------------------
@app.post("/user/login/", tags=["Users"])
def login_user(user: schemas.loginUser, db: Session = Depends(get_db)):
    username = "" if user.username is None else user.username
    email = "" if user.email is None else user.email
    password = "" if user.password is None else user.password
    
    if username == "" and email == "":
        func = {'error': 404, 'text': "Il manque les informations de login (username et email)"}
    else:
        if username != "" and email != "":
            (check, user) = crud.check_user_all(db=db, email=email, username=username, password=password)
        elif email != "":
            (check, user) = crud.check_user_from_email(db=db, email=email, password=password)
        else:
            (check, user) = crud.check_user_from_name(db=db, username=username, password=password)
        if check:
            func = {'error': 200, 'user': user}
        elif user is None:
            func = {'error': 404, 'user': {}, 'text': "Aucun utilisateur n'a été trouvé"}
        else:
            func = {'error': 204, 'user': {}, 'text': "Mot de passe incorrect"}
    return JSONResponse(content=jsonable_encoder(func))

# -----------------------------------------------
@app.get("/user/read/{UserID}", tags=["Users"])
def read_user(UserID: int, db: Session = Depends(get_db)):
    db_user = crud.get_read_user(db=db, ID=UserID)
    if db_user is None:
        func = {'error': 404, 'user': db_user}
    else:
        func = {'error': 200, 'user': db_user}
    return JSONResponse(content=jsonable_encoder(func))

# -----------------------------------------------
@app.get("/users/read/", tags=["Users"])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = crud.get_read_users(db=db, skip=skip, limit=limit)
    if users is None:
        func = {'error': 404, 'skip': skip, 'limit': limit, 'users': users}
    else:
        func = {'error': 200, 'skip': skip, 'limit': limit, 'users': users}
    return JSONResponse(content=jsonable_encoder(func))


################# HTML ##########################

# ==== ERROR ====
# -----------------------------------------------
@app.get("/error-404", response_class=HTMLResponse, include_in_schema=False)
def app_error_404(request: Request):
    return templates.TemplateResponse("error-404.html", {"request": request})

# -----------------------------------------------
@app.get("/error", response_class=HTMLResponse, include_in_schema=False)
def app_error(request: Request, text: str):
    return templates.TemplateResponse("error.html", {"request": request, "text": text})


# ==== READ ====
# -----------------------------------------------
@app.get("/html/users/read/", response_class=HTMLResponse, tags=["HTML"], include_in_schema=False)
def html_read_users(request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = crud.get_read_users(db=db, skip=skip, limit=limit)
    return templates.TemplateResponse("users.html", {"request": request, "users": users})

# -----------------------------------------------
@app.get("/html/user/read/{UserID}", response_class=HTMLResponse, tags=["HTML"], include_in_schema=False)
def html_read_user(request: Request, UserID: int, db: Session = Depends(get_db)):
    user = crud.get_read_user(db=db, ID=UserID)
    if user is None:
        return templates.TemplateResponse("error.html", {"request": request, "text": "Utilisateur non trouvé"})
    return templates.TemplateResponse("user.html", {"request": request, "user": user})