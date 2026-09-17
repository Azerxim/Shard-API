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
router = APIRouter(prefix="/api/templates", tags=["Templates"])

# -----------------------------------------------
#region Templates

#endregion
# -----------------------------------------------
