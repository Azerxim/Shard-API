from typing import List, Annotated
from fastapi import Depends
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, FileResponse
from sqlmodel import Session

from ..db import schemas
from ..services import crud, crud_livres, salons_journaux, categories_livres
from ..db.database import get_db

# Créer un routeur pour les routes utilisateur
router = APIRouter(prefix="/api/bibliotheque")

# -----------------------------------------------
#region Journaux
@router.post("/journaux/create", tags=["Journaux"])
def create_journal(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], journal: schemas.Journal, db: Session = Depends(get_db)):
    return crud.create_journal(
        db=db,
        user=current_user,
        v_journal=journal
    )

@router.post("/journaux/create/db", tags=["Journaux"])
def create_journal(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], journal: schemas.Journal, db: Session = Depends(get_db)):
    return crud.create_journal_db(
        db=db,
        user=current_user,
        v_journal=journal
    )

@router.put("/journaux/update/{JournalID}", tags=["Journaux"])
async def update_journal(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], JournalID: int, journal: schemas.Journal, db: Session = Depends(get_db)):
    update=await crud.update_journal(db=db, user=current_user, journalID=JournalID, v_journal=journal)
    if not update:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'code': 400, 'text': f"Une erreur est survenue lors de la mise à jour du journal"}))
    return JSONResponse(content=jsonable_encoder({'code': 200, 'text': f"Le journal a été mis à jour", 'journal': update}))

@router.delete("/journaux/delete/{JournalID}", tags=["Journaux"])
def delete_journal(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], JournalID: int, supprimer_salon: bool = True, db: Session = Depends(get_db)):
    # supprimer_salon=false : le salon Discord est seulement délié (un salon lié n'est jamais supprimé)
    delete=crud.delete_journal(db=db, user=current_user, v_journalid=JournalID, supprimer_salon=supprimer_salon)
    if not delete or 'erreur' in delete:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'code': 400, 'text': f"Une erreur est survenue lors de la suppression du journal"}))
    textes = {
        "supprime": "Le journal et son salon Discord ont été supprimés",
        "introuvable": "Le journal a été supprimé ; son salon Discord n'a pas été trouvé",
        "delie": "Le journal a été supprimé ; son salon Discord est conservé",
    }
    return JSONResponse(content=jsonable_encoder({'code': 200, 'text': textes.get(delete.get("salon"), "Le journal a été supprimé"), 'salon': delete.get("salon")}))

@router.get("/journaux/categories", tags=["Journaux"])
def read_categories_journaux():
    # Catégories des journaux : { clé: libellé } (services/salons_journaux.py)
    return JSONResponse(content=jsonable_encoder(salons_journaux.CATEGORIES))

@router.get("/journaux/list", tags=["Journaux"])
def read_journaux(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    journals = crud.get_journaux(db=db, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(journals))

@router.get("/journaux/read/{JournalID}", tags=["Journaux"])
def read_journal(JournalID: int, db: Session = Depends(get_db)):
    journal = crud.get_journal(db=db, ID=JournalID)
    if journal is None:
        func = {'code': 404, 'journal': journal}
    else:
        func = {'code': 200, 'journal': journal}
    return JSONResponse(content=jsonable_encoder(func))

@router.get("/journaux/user/{UserID}/list", tags=["Journaux"])
def read_journaux_by_user(UserID: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    journals = crud.get_journaux_by_user(db=db, userID=UserID, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(journals))

@router.get("/journaux/contents/{JournalID}", tags=["Journaux"])
def read_journal_contents(JournalID: int, skip: int = 0, limit: int = 100, rafraichir: bool = False, db: Session = Depends(get_db)):
    # Par pages, du plus récent au plus ancien (« Charger plus » : skip = messages déjà reçus), au plus 500 par page ;
    # messages gardés quelques minutes par l'API, rafraichir=true relit le salon (services/messages_journaux.py)
    content = crud.get_journal_contents(db=db, journalID=JournalID, skip=max(0, skip), limit=min(max(1, limit), 500), rafraichir=rafraichir)
    if content is None:
        func = {'code': 404, 'content': content}
    else:
        func = {'code': 200, 'content': content}
    return JSONResponse(content=jsonable_encoder(func))

@router.get("/journaux/liens/{journalID}", tags=["Journaux"])
def read_liens_journal(journalID: int, db: Session = Depends(get_db)):
    # Civilisations, religions, commerces, alliances et personnages liés au journal : [{ id, journal_id, entite: { type, id, title, … } }]
    return JSONResponse(content=jsonable_encoder(crud_livres.liens_de(db, "journal", journalID)))

@router.get("/journaux/entite/{EntityType}/{EntityID}/list", tags=["Journaux"])
def read_journaux_of_entite(EntityType: str, EntityID: int, db: Session = Depends(get_db)):
    # EntityType : civilisation, religion, commerce, alliance, guerre ou personnage ; [{ lien_id, journal }]
    return JSONResponse(content=jsonable_encoder(crud_livres.ecrits_de_entite(db, "journal", EntityType, EntityID)))

@router.post("/journaux/liens", tags=["Journaux"])
def create_lien_journal(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], lien: schemas.JournalLienCreate, db: Session = Depends(get_db)):
    return JSONResponse(content=jsonable_encoder({'code': 200, 'text': "Le journal est lié", 'lien': crud_livres.lier(db, current_user, lien, "journal")}))

@router.delete("/journaux/liens/{lienID}", tags=["Journaux"])
def delete_lien_journal(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], lienID: int, db: Session = Depends(get_db)):
    crud_livres.delier(db, current_user, lienID, "journal")
    return JSONResponse(content=jsonable_encoder({'code': 200, 'text': "Le lien est retiré"}))

#endregion
# -----------------------------------------------
#region Livres
@router.post("/livres/create", tags=["Livres"])
def create_livre(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], livre: schemas.Livre, db: Session = Depends(get_db)):
    return crud.create_livre(
        db=db,
        user=current_user,
        v_livre=livre
    )

@router.get("/livres/categories", tags=["Livres"])
def read_categories_livres():
    # Catégories des livres : { clé: libellé } (services/categories_livres.py)
    return JSONResponse(content=jsonable_encoder(categories_livres.CATEGORIES))

@router.put("/livres/update/{livreID}", tags=["Livres"])
def update_livre(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], livreID: int, livre: schemas.Livre, db: Session = Depends(get_db)):
    update=crud.update_livre(db=db, user=current_user, livreID=livreID, v_livre=livre)
    if not update:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'code': 400, 'text': f"Une erreur est survenue lors de la mise à jour du livre"}))
    return JSONResponse(content=jsonable_encoder({'code': 200, 'text': f"Le livre a été mis à jour", 'livre': update}))

@router.delete("/livres/delete/{livreID}", tags=["Livres"])
def delete_livre(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], livreID: int, db: Session = Depends(get_db)):
    delete=crud.delete_livre(db=db, user=current_user, livreID=livreID)
    if not delete:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'code': 400, 'text': f"Une erreur est survenue lors de la suppression du livre"}))
    return JSONResponse(content=jsonable_encoder({'code': 200, 'text': f"Le livre a été supprimé"}))

@router.get("/livres/list", tags=["Livres"])
def read_livres(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    livres = crud.get_livres(db=db, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(livres))

@router.get("/livres/read/{livreID}", tags=["Livres"])
def read_livre(livreID: int, db: Session = Depends(get_db)):
    livre = crud.get_livre(db=db, ID=livreID)
    if livre is None:
        func = {'code': 404, 'livre': livre}
    else:
        func = {'code': 200, 'livre': livre}
    return JSONResponse(content=jsonable_encoder(func))

@router.get("/livres/user/{userID}/list", tags=["Livres"])
def read_livres_by_user(userID: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    livres = crud.get_livres_by_user(db=db, userID=userID, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(livres))

@router.get("/livres/civilisation/{civilisationID}/list", tags=["Livres"])
def read_livres_by_civilisation(civilisationID: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    livres = crud.get_livres_by_civilisation(db=db, civilisationID=civilisationID, skip=skip, limit=limit)
    return JSONResponse(content=jsonable_encoder(livres))

@router.get("/liens/list", tags=["Livres", "Journaux"])
def read_tous_les_liens(db: Session = Depends(get_db)):
    # Tous les liens des livres et des journaux (recherche de la bibliothèque) : [{ support, ecrit_id, entite }]
    return JSONResponse(content=jsonable_encoder(crud_livres.tous_les_liens(db)))

@router.get("/livres/liens/{livreID}", tags=["Livres"])
def read_liens_livre(livreID: int, db: Session = Depends(get_db)):
    # Religions, commerces, alliances et personnages liés au livre : [{ id, livre_id, entite: { type, id, title, … } }]
    return JSONResponse(content=jsonable_encoder(crud_livres.liens_du_livre(db, livreID)))

@router.get("/livres/entite/{EntityType}/{EntityID}/list", tags=["Livres"])
def read_livres_of_entite(EntityType: str, EntityID: int, db: Session = Depends(get_db)):
    # EntityType : civilisation, religion, commerce, alliance, guerre ou personnage ; [{ lien_id, livre }]
    return JSONResponse(content=jsonable_encoder(crud_livres.livres_de_entite(db, EntityType, EntityID)))

@router.post("/livres/liens", tags=["Livres"])
def create_lien_livre(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], lien: schemas.LivreLienCreate, db: Session = Depends(get_db)):
    return JSONResponse(content=jsonable_encoder({'code': 200, 'text': "Le livre est lié", 'lien': crud_livres.lier(db, current_user, lien)}))

@router.delete("/livres/liens/{lienID}", tags=["Livres"])
def delete_lien_livre(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], lienID: int, db: Session = Depends(get_db)):
    crud_livres.delier(db, current_user, lienID)
    return JSONResponse(content=jsonable_encoder({'code': 200, 'text': "Le lien est retiré"}))

@router.post("/livres/content/create", tags=["Livres"])
def create_livre_contenu(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], contenu: schemas.LivreContenu, db: Session = Depends(get_db)):
    create = crud.create_livre_contenu(
        db=db,
        user=current_user,
        v_livre=contenu
    )
    if not create:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'code': 400, 'text': f"Une erreur est survenue lors de la création du contenu"}))
    return JSONResponse(content=jsonable_encoder({'code': 200, 'text': f"Le contenu a été créé", 'content': create}))

@router.put("/livres/content/update/{contenuID}", tags=["Livres"])
def update_livre_contenu(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], contenuID: int, contenu: schemas.LivreContenu, db: Session = Depends(get_db)):
    update=crud.update_livre_contenu(db=db, user=current_user, contenuID=contenuID, v_livre=contenu)
    if not update:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'code': 400, 'text': f"Une erreur est survenue lors de la mise à jour du contenu"}))
    return JSONResponse(content=jsonable_encoder({'code': 200, 'text': f"Le contenu a été mis à jour", 'content': update}))

@router.delete("/livres/content/delete/{contenuID}", tags=["Livres"])
def delete_livre_contenu(current_user: Annotated[schemas.Users, Depends(crud.secu_get_current_active_user)], contenuID: int, db: Session = Depends(get_db)):
    delete=crud.delete_livre_contenu(db=db, user=current_user, contenuID=contenuID)
    if not delete:
        raise HTTPException(status_code=400, detail=jsonable_encoder({'code': 400, 'text': f"Une erreur est survenue lors de la suppression du contenu"}))
    return JSONResponse(content=jsonable_encoder({'code': 200, 'text': f"Le contenu a été supprimé"}))

@router.get("/livres/contents/read/{livreID}", tags=["Livres"])
def read_livre_contenus(livreID: int, db: Session = Depends(get_db)):
    livre = crud.get_livre(db=db, ID=livreID)
    contenus = crud.get_livre_contenus(db=db, livreID=livreID)
    if livre is None:
        func = {'code': 404, 'livre': livre, 'contents': contenus}
    else:
        func = {'code': 200, 'livre': livre, 'contents': contenus}
    return JSONResponse(content=jsonable_encoder(func))

@router.get("/livres/content/read/{contenuID}", tags=["Livres"])
def read_livre_contenu(contenuID: int, db: Session = Depends(get_db)):
    contenu = crud.get_livre_contenu(db=db, ID=contenuID)
    if contenu is None:
        func = {'code': 404, 'content': contenu}
    else:
        func = {'code': 200, 'content': contenu}
    return JSONResponse(content=jsonable_encoder(func))

#endregion
# -----------------------------------------------