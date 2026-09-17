from typing import Annotated
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ..db import schemas
from ..services import crud, crud_monde
from ..db.database import get_db

# Statistiques du monde : relevés du générateur de cartes, réservés aux administrateurs (voir crud_monde)
router = APIRouter(prefix="/api/monde", tags=["Monde"])

CurrentAdmin = Annotated[schemas.Users, Depends(crud.secu_get_current_active_admin)]

def _json(content):
    return JSONResponse(content=jsonable_encoder(content))


async def envoi_autorise(
    x_monde_key: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    """Générateur de cartes (clé partagée platforms.monde.key) ou administrateur connecté."""
    if crud_monde.verifier_cle(x_monde_key):
        return "map-generator"
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = crud.secu_decode_token(db, token) if token else None
    if user and not user.is_disabled and user.is_admin:
        return user.username
    raise HTTPException(status_code=401, detail="Clé du générateur de cartes ou compte administrateur requis")


# -----------------------------------------------
#region Relevés

@router.post("/releves")
def create_releve(payload: schemas.MondeReleveCreate, auteur: Annotated[str, Depends(envoi_autorise)], db: Session = Depends(get_db)):
    resultat = crud_monde.enregistrer_releve(db, payload)
    populations = resultat["populations"]
    text = (f"Le relevé du monde a été enregistré ({populations['villes']} ville(s) et "
            f"{populations['quartiers']} quartier(s) mis à jour)")
    return _json({'code': 200, 'text': text, 'auteur': auteur, **resultat})

@router.get("/releves")
def read_releves(current_user: CurrentAdmin, limit: int = 52, db: Session = Depends(get_db)):
    return _json(crud_monde.liste_releves(db, limit))

@router.get("/resume")
def read_resume(current_user: CurrentAdmin, releve_id: int | None = None, db: Session = Depends(get_db)):
    # { releve, precedent, evolution, dimensions, lieux, zones, joueurs, releves }
    return _json(crud_monde.resume(db, releve_id))

@router.post("/pseudos")
def resoudre_pseudos(current_user: CurrentAdmin, releve_id: int | None = None, db: Session = Depends(get_db)):
    # Cherche sur playerdb.co le pseudo des joueurs que le relevé n'a pas nommés
    resultat = crud_monde.resoudre_pseudos(db, releve_id)
    return _json({'code': 200, 'text': f"{resultat['trouves']} pseudo(s) retrouvé(s) sur {resultat['cherches']}", **resultat})

@router.get("/joueurs")
def read_joueurs(current_user: CurrentAdmin, releve_id: int | None = None, actifs: bool = False, db: Session = Depends(get_db)):
    return _json(crud_monde.joueurs(db, releve_id, actifs))

@router.get("/zones")
def read_zones(current_user: CurrentAdmin, releve_id: int | None = None, limit: int = 50, db: Session = Depends(get_db)):
    return _json(crud_monde.zones(db, releve_id, limit))

@router.get("/lieux")
def read_lieux(current_user: CurrentAdmin, releve_id: int | None = None, db: Session = Depends(get_db)):
    return _json(crud_monde.lieux(db, releve_id))

@router.get("/lieux/{EntityType}/{EntityID}")
def read_historique_lieu(current_user: CurrentAdmin, EntityType: str, EntityID: int, limit: int = 52, db: Session = Depends(get_db)):
    # EntityType : civilisation, ville ou quartier
    return _json(crud_monde.historique_lieu(db, EntityType, EntityID, limit))

@router.delete("/releves/{ReleveID}")
def delete_releve(current_user: CurrentAdmin, ReleveID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, **crud_monde.supprimer_releve(db, ReleveID)})

#endregion
