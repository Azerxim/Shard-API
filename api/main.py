from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager

from sqlmodel import Session
from .database import get_db, create_db_and_tables, check_database_tables

from . import utils
from topazdevsdk import colors
from . import schemas, crud, models
from .routes_users import router as users_router
from .routes_bibliotheque import router as bibliotheque_router
from .routes_civilisations import router as civilisations_router
from .routes_cartographie import router as cartographie_router
from .routes_religions import router as religions_router


################# App Initialization #################

@asynccontextmanager
async def lifespan(app_: FastAPI):
    # Démarrage de l'application
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     -------------------")
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     {colors.BColors.PURPLE}{utils.CONFIG['api']['name']}{colors.BColors.END}")
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Version {colors.BColors.LIGHTBLUE}{utils.VERSION}{colors.BColors.END}")
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     -------------------")
    
    # Initialisation de la base de données
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Initialisation de la base de données...")
    create_db_and_tables()
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Base de données initialisée.")
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     -------------------")
    
    # Vérification des tables de la base de données existantes par rapport aux modèles
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Vérification des tables de la base de données...")
    check_database_tables()
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Vérification terminée.")
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     -------------------")
    
    # Initialisation de la sécurité
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Initialisation de la sécurité...")
    db = next(get_db())
    result = crud.loadsecurity(db, utils.SECURITY)
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Sécurité initialisée. Résultat: {result.get('result') if result.get('result') is not None else result.get('erreur', 'Erreur inconnue')}")
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     -------------------")

    # Fonctionnement de l'application
    yield
    
    # Arrêt de l'application
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     -------------------")
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Arrêt en cours...")

# Paramétrage de l'application FastAPI
app = FastAPI(
    title=utils.CONFIG['api']['name'],
    version=utils.VERSION,
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan
)

################# Templates #################

templates = Jinja2Templates(directory="templates")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

favicon_path = 'assets/images/favicon_shard.ico'
@app.get('/favicon_shard.ico', include_in_schema=False)
async def favicon():
    return FileResponse(favicon_path)

robots_path = 'robots.txt'
@app.get('/robots.txt', include_in_schema=False)
async def robots():
    return FileResponse(robots_path, media_type='text/plain')

@app.get('/sitemap.xml', include_in_schema=False)
async def sitemap(request: Request):
    """Generate sitemap.xml dynamically"""
    base_url = str(request.base_url).rstrip('/')
    
    # Define routes with their priority and change frequency
    routes = [
        {'loc': '/', 'priority': '1.0', 'changefreq': 'weekly'},
        # {'loc': '/login', 'priority': '0.8', 'changefreq': 'monthly'},
        # {'loc': '/register', 'priority': '0.8', 'changefreq': 'monthly'},
        # {'loc': '/profile', 'priority': '0.7', 'changefreq': 'weekly'},
        # {'loc': '/users', 'priority': '0.7', 'changefreq': 'daily'},
        {'loc': '/docs', 'priority': '0.6', 'changefreq': 'monthly'},
    ]
    
    # Build XML sitemap
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for route in routes:
        xml_content += '  <url>\n'
        xml_content += f'    <loc>{base_url}{route["loc"]}</loc>\n'
        xml_content += f'    <changefreq>{route["changefreq"]}</changefreq>\n'
        xml_content += f'    <priority>{route["priority"]}</priority>\n'
        xml_content += '  </url>\n'
    
    xml_content += '</urlset>'
    
    return Response(content=xml_content, media_type='application/xml')

################# Security #################

# -----------------------------------------------
@app.post("/token", tags=["Security"])
async def secu_login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)):
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
    user_dict = crud.secu_get_user_by_username(db, form_data.username)
    if not user_dict:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    hashed_password = crud.hash_password(form_data.password)
    if not hashed_password == user_dict.hashed_password:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    return {"access_token": user_dict.username, "token_type": "bearer"}

# -----------------------------------------------
@app.get("/security/me", tags=["Security"])
async def read_securityusers_me(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], db: Session = Depends(get_db)):
    return JSONResponse(content=jsonable_encoder(current_user))

################# Include Routers #################

app.include_router(users_router)

app.include_router(bibliotheque_router)

app.include_router(civilisations_router)

app.include_router(religions_router)

app.include_router(cartographie_router)

################# Main Routes #################

# -----------------------------------------------
@app.get("/", response_class=HTMLResponse)
def html_main(request: Request):
    return templates.TemplateResponse("landing.html", {
        "request": request, 
        "name": utils.CONFIG['api']['name'],
        "version": utils.VERSION, 
        "hostname": utils.HOSTNAME
    })

################# Docs Routes #################

# -----------------------------------------------
@app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
async def custom_swagger_ui_html(request: Request):
    swagger_ui = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{utils.CONFIG['api']['name']} - Documentation",
        swagger_favicon_url="/assets/images/favicon.ico"
    )
    return templates.TemplateResponse("docs.html", {
        "request": request, 
        "name": utils.CONFIG['api']['name'],
        "version": utils.VERSION,
        "hostname": utils.HOSTNAME,
        "swagger_ui_html": swagger_ui.body.decode()
    })

# -----------------------------------------------
@app.get("/redoc", response_class=HTMLResponse, include_in_schema=False)
async def redoc_html(request: Request):
    redoc_ui = get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{utils.CONFIG['api']['name']} - ReDoc Documentation",
        redoc_favicon_url="/assets/images/favicon.ico"
    )
    return templates.TemplateResponse("redoc.html", {
        "request": request, 
        "name": utils.CONFIG['api']['name'],
        "version": utils.VERSION,
        "hostname": utils.HOSTNAME,
        "redoc_ui_html": redoc_ui.body.decode()
    })

###################  API Endpoints #################

# -----------------------------------------------
@app.get("/api/version/")
def app_version():
    result = {'name': utils.CONFIG['api']['name'], 'version': utils.VERSION, 'version_dev': utils.VERSION_DEV, 'version_short': utils.VERSION_SHORT, 'hostname': utils.HOSTNAME}
    return JSONResponse(content=jsonable_encoder(result))

################# 404 Handler #################

# -----------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions, including 404 errors"""
    # For 404 errors with HTML accept header, return 404 template
    if exc.status_code == 404:
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header or not request.url.path.startswith("/api"):
            return templates.TemplateResponse("404.html", {
                "request": request,
                "name": utils.CONFIG['api']['name'],
                "version": utils.VERSION_SHORT,
                "hostname": utils.HOSTNAME
            }, status_code=404)
    
    # For API requests or non-404 errors, return JSON
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

# -----------------------------------------------
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(full_path: str):
    """Catch-all route for undefined paths"""
    raise StarletteHTTPException(status_code=404, detail="Not Found")