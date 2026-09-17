import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager

from .db.database import get_db, create_db_and_tables, check_database_tables, migrate_commerces_owner_to_members

from .core import utils
from topazdevsdk import colors
from .services import crud, crud_nettoyage, crud_personnages
from .routes.pages import router as pages_router, templates, page_context
from .routes.users import router as users_router
from .routes.bibliotheque import router as bibliotheque_router
from .routes.civilisations import router as civilisations_router
from .routes.cartographie import router as cartographie_router
from .routes.religions import router as religions_router
from .routes.commerces import router as commerces_router
from .routes.alliances import router as alliances_router
from .routes.guerres import router as guerres_router
from .routes.personnages import router as personnages_router
from .routes.monde import router as monde_router


################# App Initialization #################

@asynccontextmanager
async def lifespan(app_: FastAPI):
    # Démarrage de l'application
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     -------------------")
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     {colors.BColors.PURPLE}{utils.CONFIG['api']['name']}{colors.BColors.END}")
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Version: {colors.BColors.LIGHTBLUE}{utils.VERSION}{colors.BColors.END}")
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Hostname: {colors.BColors.LIGHTBLUE}{utils.HOSTNAME}{colors.BColors.END}")
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     API Mode: {colors.BColors.LIGHTBLUE}{utils.API_MODE}{colors.BColors.END}")
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Configuration: {colors.BColors.LIGHTBLUE}{' + '.join(utils.CONFIG_FILES) or 'aucune'}{colors.BColors.END}")
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     -------------------")
    
    # Initialisation de la base de données
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Initialisation de la base de données...")
    create_db_and_tables()
    migrate_commerces_owner_to_members()
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

    # Références laissées par d'anciennes suppressions (alliances, guerres, personnages)
    cleanup = crud_nettoyage.nettoyer_references_orphelines(db)
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Références orphelines corrigées : {cleanup}")
    seeded = crud_personnages.seed_referentiels(db)
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Espèces et classes de personnages ajoutées : {seeded}")
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     -------------------")

    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Application démarrée avec succès.")
    print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     API accessible via: {colors.BColors.LIGHTBLUE}http://{utils.API_IP}:{utils.API_PORT}{colors.BColors.END} (Press CTRL+C to quit)")
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

# CORS preflight support: browsers can send OPTIONS before POST on cross-origin JSON requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

################# Static files #################

app.mount("/assets", StaticFiles(directory=os.path.join(utils.ROOT_DIR, "assets")), name="assets")

################# Include Routers #################

app.include_router(pages_router)

app.include_router(users_router)

app.include_router(bibliotheque_router)

app.include_router(civilisations_router)

app.include_router(religions_router)

app.include_router(commerces_router)

app.include_router(alliances_router)

app.include_router(guerres_router)

app.include_router(personnages_router)

app.include_router(cartographie_router)

app.include_router(monde_router)

################# 404 Handler #################

# -----------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions, including 404 errors"""
    # For 404 errors with HTML accept header, return 404 template
    if exc.status_code == 404:
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header or not request.url.path.startswith("/api"):
            return templates.TemplateResponse("404.html", page_context(request, version=utils.VERSION_SHORT), status_code=404)
    
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