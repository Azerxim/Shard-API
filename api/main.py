from typing import List, Annotated
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import time as t, datetime as dt
from starlette_discord import DiscordOAuthClient

from core import file as f, utils
from . import crud, models, schemas
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

################# Templates ####################

templates = Jinja2Templates(directory="html")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")


################# Security #####################

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def secu_get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)):
    user = crud.secu_decode_token(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def secu_get_current_active_user(current_user: Annotated[schemas.SecurityUsers, Depends(secu_get_current_user)]):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return JSONResponse(content=jsonable_encoder(current_user))

@app.post("/token", tags=["Security"])
async def secu_login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)):
    user_dict = crud.secu_get_user_from_username(db, form_data.username)
    if not user_dict:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    hashed_password = crud.hash_password(form_data.password)
    if not hashed_password == user_dict.hashed_password:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    return {"access_token": user_dict.username, "token_type": "bearer"}

@app.get("/security/me", tags=["Security"])
async def read_securityusers_me(current_user: Annotated[schemas.SecurityUsers, Depends(secu_get_current_active_user)], db: Session = Depends(get_db)):
    return JSONResponse(content=jsonable_encoder(current_user))

@app.get("/security/load", tags=["Security"])
async def security_load(db: Session = Depends(get_db)):
    print(f"{utils.bcolors.green}INFO{utils.bcolors.end}:     -------------------")
    result = crud.loadsecurity(db, utils.SECURITY)
    print(f"{utils.bcolors.green}INFO{utils.bcolors.end}:     -------------------")
    return JSONResponse(content=jsonable_encoder(result))


################### API ########################

@app.on_event("startup")
async def startup_event():
    print(f"{utils.bcolors.green}INFO{utils.bcolors.end}:     -------------------")
    print(f"{utils.bcolors.green}INFO{utils.bcolors.end}:     {utils.bcolors.purple}{utils.CONFIG['api']['name']}{utils.bcolors.end}")
    print(f"{utils.bcolors.green}INFO{utils.bcolors.end}:     Version {utils.bcolors.lightblue}{utils.CONFIG['api']['version']}{utils.bcolors.end}")
    print(f"{utils.bcolors.green}INFO{utils.bcolors.end}:     -------------------")


@app.get("/", response_class=HTMLResponse)
def html_main(request: Request):
    return templates.TemplateResponse("version.html", {"request": request, "version": utils.CONFIG['api']['version'], "api": utils.CONFIG['api']['name']})


@app.get("/version/")
def app_version():
    result = {'api': utils.CONFIG['api']['name'], 'version': utils.CONFIG['api']['version']}
    return JSONResponse(content=jsonable_encoder(result))


################### API ########################
@app.post("/user/create/", tags=["Users"])
def create_user(current_user: Annotated[schemas.SecurityUsers, Depends(secu_get_current_active_user)], user: schemas.iUsers, db: Session = Depends(get_db)):
    (db_check, db_user) = crud.user_exist(db, user.email, user.username)
    if db_check:
        raise HTTPException(status_code=400, detail=f"L'utilisateur existe déja avec la plateforme {db_user.platform}")
    return crud.create_user(
        db=db,
        v_user = user
    )


@app.delete("/user/delete/", tags=["Users"])
def delete_user(current_user: Annotated[schemas.SecurityUsers, Depends(secu_get_current_active_user)], UserID: int, db: Session = Depends(get_db)):
    crud.delete_user(db=db, v_userid=UserID)
    return True


@app.get("/user/login", tags=["Users"])
def login_user(password: str, username: str = "", email: str = "", db: Session = Depends(get_db)):
    if username == "" and email == "":
        func = {'error': 404, 'text': "Il manque les informations de login (username et/ou email)"}
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
            func = {'error': 204, 'user': user, 'text': "Aucun utilisateur n'a été trouvé"}
        else:
            func = {'error': 204, 'user': user, 'text': "Mot de passe incorrect"}
    return JSONResponse(content=jsonable_encoder(func))


@app.get("/user/read/{UserID}", response_model=schemas.Users, tags=["Users"])
def read_user(UserID: int, db: Session = Depends(get_db)):
    db_user = crud.get_user(db=db, ID=UserID)
    if db_user is None:
        func = {'error': 404, 'user': db_user}
    else:
        func = {'error': 200, 'user': db_user}
    return JSONResponse(content=jsonable_encoder(func))


@app.get("/users/read/", response_model=List[schemas.TableAuth], tags=["Users"])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = crud.get_users(db=db, skip=skip, limit=limit)
    if users is None:
        func = {'error': 404, 'skip': skip, 'limit': limit, 'users': users}
    else:
        func = {'error': 200, 'skip': skip, 'limit': limit, 'users': users}
    return JSONResponse(content=jsonable_encoder(func))


# --------------------------------------
# ---------------- HTML ----------------
# --------------------------------------

# ==== ERROR ====
@app.get("/error-404", response_class=HTMLResponse)
def app_error(request: Request):
    return templates.TemplateResponse("error-404.html", {"request": request})

@app.get("/error", response_class=HTMLResponse)
def error(request: Request, text: str):
    return templates.TemplateResponse("error.html", {"request": request, "text": text})


# ==== READ ====
@app.get("/html/users/read/", response_class=HTMLResponse, tags=["HTML"])
def html_read_users(request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = crud.get_users(db=db, skip=skip, limit=limit)
    return templates.TemplateResponse("users.html", {"request": request, "users": users})

@app.get("/html/user/read/{UserID}", response_class=HTMLResponse, tags=["HTML"])
def html_read_user(request: Request, UserID: int, db: Session = Depends(get_db)):
    user = crud.get_user(db=db, ID=UserID)
    if user is None:
        return templates.TemplateResponse("error.html", {"request": request, "text": "Utilisateur non trouvé"})
    return templates.TemplateResponse("user.html", {"request": request, "user": user})


################# OAuth2 #####################

discord_client = DiscordOAuthClient(utils.DISCORD_ID, utils.DISCORD_SECRET, utils.DISCORD_REDIRECT, ("identify", "guilds", "email", "connections"))

@app.get("/oauth2/login", tags=["Oauth2"])
async def oauth2_login(platform: str, url: str = ""):
    platform = platform.lower()
    if platform == "discord":
        response = RedirectResponse("/oauth2/discord/login", status_code=302)
    else:
        return RedirectResponse("/error?text=La plateforme de connexion est inconnu", status_code=302)
    response.set_cookie(key="SpinelleAuth", value=f"{platform}|{url}")
    return response


@app.get("/oauth2/discord/login", tags=["Oauth2"])
async def oauth2_discord_login():
    return discord_client.redirect()


@app.get("/oauth2/discord/callback", tags=["Oauth2"])
async def oauth2_discord_callback(code: str, request: Request, db: Session = Depends(get_db)):
    async with discord_client.session(code) as session:
        platform_user = await session.identify()
        # guilds = await session.guilds()
        # connections = await session.connections()

    user = schemas.iUsers(
        username=platform_user.username,
        full_name=platform_user.username,
        email=platform_user.email,
        password=str(platform_user.id)
    )
    (db_check, db_user) = crud.user_exist_platform(db, user, "discord")
    if db_check:
        return RedirectResponse(f"/error?text=L'utilisateur existe déja avec la plateforme {db_user.platform}", status_code=302)
    crud.create_user_platform(db=db, v_user=user, platform="discord")

    cookies = request.cookies.get("SpinelleAuth")
    cookie = cookies.split('|')
    if cookie[1] is None:
        response = RedirectResponse("/error?text=URL de retour n'a pas été trouvée", status_code=302)
    response = RedirectResponse(cookie[1], status_code=302)
    response.delete_cookie(key="SpinelleAuth")
    return response


