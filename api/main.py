from typing import List

import time as t, datetime as dt

from fastapi import Depends, FastAPI, HTTPException, Security, Request, status
from fastapi.security.api_key import APIKeyHeader, APIKey
from sqlalchemy.orm import Session
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import crud, models, schemas
from . import gestion as ge
from .database import SessionLocal, engine


models.Base.metadata.create_all(bind=engine)

# initialisation des variables.
SECRET_KEY = ge.SECRET_KEY
SECRET_KEY_NAME = "access_token"

app = FastAPI()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

################# Templates ####################

templates = Jinja2Templates(directory="html")


################# Security #####################

api_key_header = APIKeyHeader(name=SECRET_KEY_NAME)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == SECRET_KEY:
        return api_key_header
    else:
        raise HTTPException(status_code=403, detail="Could not validate credentials")


################### API ########################
@app.on_event("startup")
async def startup_event():
    print(f"{ge.bcolors.green}INFO{ge.bcolors.end}:     -------------------")
    print(f"{ge.bcolors.green}INFO{ge.bcolors.end}:     {ge.bcolors.purple}{ge.CONFIG['api']['name']}{ge.bcolors.end}")
    print(f"{ge.bcolors.green}INFO{ge.bcolors.end}:     Version {ge.bcolors.lightblue}{ge.CONFIG['api']['version']}{ge.bcolors.end}")
    print(f"{ge.bcolors.green}INFO{ge.bcolors.end}:     -------------------")


@app.get("/", response_class=HTMLResponse)
def html_main(request: Request):
    # path = "html/index.html"
    # html_content = open(path).read()
    # return HTMLResponse(content=html_content, status_code=200)
    return templates.TemplateResponse("version.html", {"request": request, "version": ge.CONFIG['api']['version'], "api": ge.CONFIG['api']['name']})


@app.get("/version/")
def app_version():
    return {'api': ge.CONFIG['api']['name'], 'version': ge.CONFIG['api']['version']}


@app.post("/user/create/", tags=["Users"])
def create_user(platform: str, mail: str, pseudo: str, mdp: str, id_platform: str, img_platform: str, db: Session = Depends(get_db), api_key: APIKey = Depends(get_api_key)):
    db_user = crud.user_exist(db, platform, mail, pseudo, mdp)
    if db_user:
        raise HTTPException(status_code=400, detail=f"L'utilisateur existe déja avec la plateforme {platform}")
    return crud.create_user(
        db=db, 
        v_platform = platform, 
        v_mail = mail, 
        v_pseudo = pseudo, 
        v_mdp = mdp, 
        v_id_platform = id_platform, 
        v_img_platform = img_platform
    )


@app.get("/user/read/{UserID}", response_model=schemas.TableAuth, tags=["Users"])
def read_user(UserID: int, db: Session = Depends(get_db)):
    db_user = crud.get_user(db=db, ID=UserID)
    if db_user is None:
        func = {'error': 404, 'user': db_user}
    else:
        func = {'error': 0, 'user': db_user}
    return JSONResponse(content=jsonable_encoder(func))


@app.get("/users/read/", response_model=List[schemas.TableAuth], tags=["Users"])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = crud.get_users(db=db, skip=skip, limit=limit)
    if users is None:
        func = {'error': 404, 'skip': skip, 'limit': limit, 'users': users}
    else:
        func = {'error': 0, 'skip': skip, 'limit': limit, 'users': users}
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
