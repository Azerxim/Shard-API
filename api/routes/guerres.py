from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ..db import schemas
from ..services import crud, crud_conflits, crud_troupes
from ..db.database import get_db

# Guerres militaires (civilisations) et de religion (religions), validées par un modérateur RP (voir crud_conflits)
router = APIRouter(prefix="/api/guerres", tags=["Guerres"])

CurrentUser = Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)]
Viewer = Annotated[schemas.Users | None, Depends(crud.secu_get_current_user_optional)]

def _json(content):
    return JSONResponse(content=jsonable_encoder(content))

# -----------------------------------------------
#region Lecture

@router.get("/list")
def read_guerres(db: Session = Depends(get_db)):
    # Guerres publiques (en cours et terminées) : [{ guerre, camps, declarant, moderateur }]
    return _json(crud_conflits.list_guerres_publiques(db))

@router.get("/read/{GuerreID}")
def read_guerre(GuerreID: int, db: Session = Depends(get_db)):
    # Guerre publique ; une déclaration non validée renvoie 404 (voir /prive)
    return _json({'code': 200, **crud_conflits.read_guerre(db, GuerreID)})

@router.get("/prive/{GuerreID}")
def read_guerre_prive(current_user: CurrentUser, GuerreID: int, db: Session = Depends(get_db)):
    # Même réponse, y compris pour une déclaration non validée si l'utilisateur est concerné ou modérateur
    return _json({'code': 200, **crud_conflits.read_guerre(db, GuerreID, current_user)})

@router.get("/cibles/{GuerreID}")
def read_cibles_guerre(GuerreID: int, db: Session = Depends(get_db)):
    # Guerre publique : destructibles des villes des belligérants engagés, camp par camp
    return _json(crud_conflits.cibles_guerre(db, GuerreID))

@router.get("/entite/{EntityType}/{EntityID}")
def read_guerres_of_entity(EntityType: str, EntityID: int, db: Session = Depends(get_db)):
    # EntityType : civilisation ou religion
    return _json(crud_conflits.guerres_of_entity(db, EntityType, EntityID))

@router.get("/mine")
def read_my_guerres(current_user: CurrentUser, db: Session = Depends(get_db)):
    # { a_valider (modérateurs), mes_guerres (non validées), appels (appels aux armes à accepter) }
    return _json(crud_conflits.guerres_for_user(db, current_user))

#endregion
# -----------------------------------------------
#region Déclaration et modération

@router.post("/declarer")
def declare_guerre(current_user: CurrentUser, guerre: schemas.GuerreDeclaration, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La déclaration de guerre attend la validation d'un modérateur RP", **crud_conflits.declare_guerre(db, current_user, guerre)})

@router.put("/update/{GuerreID}")
def update_guerre(current_user: CurrentUser, GuerreID: int, guerre: schemas.GuerreUpdate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La déclaration a été modifiée", **crud_conflits.update_guerre(db, current_user, GuerreID, guerre)})

@router.put("/{GuerreID}/valider")
def valider_guerre(current_user: CurrentUser, GuerreID: int, body: schemas.GuerreValidation, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La guerre est déclarée et commence", **crud_conflits.valider_guerre(db, current_user, GuerreID, body)})

@router.put("/{GuerreID}/refuser")
def refuser_guerre(current_user: CurrentUser, GuerreID: int, body: schemas.GuerreRefus, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La déclaration de guerre a été refusée", **crud_conflits.refuser_guerre(db, current_user, GuerreID, body)})

@router.put("/{GuerreID}/terminer")
def terminer_guerre(current_user: CurrentUser, GuerreID: int, body: schemas.GuerreFin, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La guerre est terminée", **crud_conflits.terminer_guerre(db, current_user, GuerreID, body)})

@router.delete("/delete/{GuerreID}")
def annuler_declaration(current_user: CurrentUser, GuerreID: int, db: Session = Depends(get_db)):
    crud_conflits.annuler_declaration(db, current_user, GuerreID)
    return _json({'code': 200, 'text': "La déclaration de guerre a été retirée"})

#endregion
# -----------------------------------------------
#region Camps

@router.post("/{GuerreID}/appels")
def appeler_aux_armes(current_user: CurrentUser, GuerreID: int, body: schemas.GuerreAppel, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "L'appel aux armes a été envoyé", **crud_conflits.appeler_aux_armes(db, current_user, GuerreID, body)})

@router.put("/{GuerreID}/appels/{BelligerantID}/repondre")
def repondre_appel(current_user: CurrentUser, GuerreID: int, BelligerantID: int, body: schemas.ReponseAppel, db: Session = Depends(get_db)):
    text = "Vous avez rejoint la guerre" if body.accepter else "Vous avez décliné l'appel aux armes"
    return _json({'code': 200, 'text': text, **crud_conflits.repondre_appel(db, current_user, GuerreID, BelligerantID, body.accepter)})

@router.delete("/{GuerreID}/belligerants/{BelligerantID}")
def retirer_belligerant(current_user: CurrentUser, GuerreID: int, BelligerantID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "Le belligérant a quitté la guerre", **crud_conflits.retirer_belligerant(db, current_user, GuerreID, BelligerantID)})

#endregion
# -----------------------------------------------
#region Chronologie (zones de conflit : /cartographie, type "guerre")

@router.post("/{GuerreID}/evenements")
def ajouter_evenement(current_user: CurrentUser, GuerreID: int, body: schemas.GuerreEvenementCreate, db: Session = Depends(get_db)):
    # Bataille, siège, traité ou autre fait, raconté par un chef de camp ou un modérateur RP
    return _json({'code': 200, 'text': "L'événement a été ajouté à la chronologie", **crud_conflits.ajouter_evenement(db, current_user, GuerreID, body)})

@router.delete("/{GuerreID}/evenements/{EvenementID}")
def supprimer_evenement(current_user: CurrentUser, GuerreID: int, EvenementID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "L'événement a été retiré de la chronologie", **crud_conflits.supprimer_evenement(db, current_user, GuerreID, EvenementID)})

#endregion
# -----------------------------------------------
#region Troupes (levées ville par ville ; toujours sur un champ de bataille ou en mouvement)

@router.get("/{GuerreID}/troupes")
def read_troupes(viewer: Viewer, GuerreID: int, db: Session = Depends(get_db)):
    # { champs, camps_visibles, troupes: { attaquant, defenseur } (None si le camp est caché), levees }
    return _json(crud_troupes.troupes_guerre(db, viewer, GuerreID))

@router.post("/{GuerreID}/troupes")
def lever_troupe(current_user: CurrentUser, GuerreID: int, body: schemas.GuerreTroupeLevee, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La troupe est levée", **crud_troupes.lever_troupe(db, current_user, GuerreID, body)})

@router.post("/{GuerreID}/mercenaires")
def engager_mercenaires(current_user: CurrentUser, GuerreID: int, body: schemas.GuerreMercenaireEngagement, db: Session = Depends(get_db)):
    # Compagnie de mercenaires engagée par un belligérant : sa civilisation n'entre pas dans un camp (voir /api/mercenaires)
    return _json({'code': 200, 'text': "Les mercenaires rejoignent votre camp", **crud_troupes.engager_mercenaires(db, current_user, GuerreID, body)})

@router.put("/{GuerreID}/troupes/{TroupeID}")
def modifier_troupe(current_user: CurrentUser, GuerreID: int, TroupeID: int, body: schemas.GuerreTroupeUpdate, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La troupe a été modifiée", **crud_troupes.modifier_troupe(db, current_user, GuerreID, TroupeID, body)})

@router.put("/{GuerreID}/troupes/{TroupeID}/deplacer")
def deplacer_troupe(current_user: CurrentUser, GuerreID: int, TroupeID: int, body: schemas.GuerreTroupeMouvement, db: Session = Depends(get_db)):
    text = "La troupe a changé de position (déplacement secret : scellez-le en action secrète)" if body.secret else "La troupe a changé de position"
    return _json({'code': 200, 'text': text, **crud_troupes.deplacer_troupe(db, current_user, GuerreID, TroupeID, body)})

@router.put("/{GuerreID}/troupes/{TroupeID}/demobiliser")
def demobiliser_troupe(current_user: CurrentUser, GuerreID: int, TroupeID: int, db: Session = Depends(get_db)):
    return _json({'code': 200, 'text': "La troupe est démobilisée", **crud_troupes.demobiliser_troupe(db, current_user, GuerreID, TroupeID)})

#endregion
# -----------------------------------------------
