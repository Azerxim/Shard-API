"""
Liens des livres et des journaux de la bibliothèque avec une civilisation, une religion, un commerce, une alliance, une
guerre ou un personnage.

- Un livre peut avoir plusieurs liens (une chronique peut concerner plusieurs personnages, un traité deux civilisations).
  Seul un lien vers une civilisation donne des droits : ses dirigeants peuvent modifier le livre (crud._check_livre_rights).
- Créer un lien demande des droits sur le livre (crud._check_livre_rights) ET sur l'entité, pour qu'on ne puisse pas
  attribuer un texte à une religion ou au personnage d'un autre :
  civilisation et religion : Fondateur ou Admin ; commerce : Fondateur ou Admin (ou du commerce dirigeant) ; alliance : Fondateur ou
  Admin de la civilisation chef de file ; guerre : modérateur RP ou gestionnaire d'un belligérant engagé ; personnage : son
  joueur. L'administrateur du site peut tout.
- Retirer un lien : droits sur le livre OU sur l'entité (une religion peut refuser un livre qu'on lui attribue).
- Les liens disparaissent avec le livre ou l'entité (crud_nettoyage.supprimer_liens_livres, et au démarrage).
- Journaux : mêmes liens (table journauxliens), mais aucun ne donne de droits sur le journal, qui reste à son auteur
  (crud._check_owner_rights) ; ils disparaissent avec le journal (crud_nettoyage.supprimer_liens_journal) ou l'entité.
"""
from fastapi import HTTPException
from sqlmodel import Session, select

from ..db import models, schemas
from .crud import _check_commerce_rights, _check_livre_rights, _check_owner_rights, get_civilisation_by_id, get_commerce_by_id, get_journal, get_livre, get_religion_by_id
from . import crud_conflits, crud_personnages

ENTITES = ("civilisation", "religion", "commerce", "alliance", "guerre", "personnage")


#region Entités

def _entite(db: Session, entity_type: str, entity_id: int):
    if entity_type == "civilisation":
        return get_civilisation_by_id(db, entity_id)
    if entity_type == "religion":
        return get_religion_by_id(db, entity_id)
    if entity_type == "commerce":
        return get_commerce_by_id(db, entity_id)
    if entity_type == "alliance":
        return db.get(models.Alliances, entity_id)
    if entity_type == "guerre":
        return crud_conflits.get_guerre(db, entity_id)
    if entity_type == "personnage":
        return crud_personnages.get_personnage(db, entity_id)
    raise HTTPException(status_code=400, detail="Un livre ou un journal se lie à une civilisation, une religion, un commerce, une alliance, une guerre ou un personnage")

def _resume(entity_type: str, entite):
    if entity_type == "personnage":
        return {"type": entity_type, "id": entite.id, "title": entite.name, "image_url": entite.image_url, "image_fichier": entite.image_fichier, "user_id": entite.user_id}
    if entity_type == "guerre":
        # Une déclaration pas encore validée (ou refusée) n'est pas publique
        return {"type": entity_type, "id": entite.id, "title": entite.title, "status": entite.status, "is_public": entite.status in crud_conflits.GUERRE_STATUTS_PUBLICS}
    resume = {"type": entity_type, "id": entite.id, "title": entite.title, "is_public": entite.is_public}
    if entity_type in ("religion", "alliance"):
        resume.update(color=entite.color, icon=entite.icon)
    return resume

def peut_gerer_entite(db: Session, user: schemas.Users, entity_type: str, entite) -> bool:
    if not user or user.is_disabled:
        return False
    if user.is_admin:
        return True
    try:
        if entity_type in ("civilisation", "religion"):
            return crud_conflits.can_manage_entity(db, user, entity_type, entite.id)
        if entity_type == "commerce":
            _check_commerce_rights(db, user, entite)
            return True
        if entity_type == "alliance":
            crud_conflits._require_alliance_chef(db, user, entite)
            return True
        if entity_type == "guerre":
            # Modérateur RP, ou gestionnaire d'un belligérant engagé (civilisation ou religion)
            return crud_conflits.is_moderateur(user) or any(
                crud_conflits.can_manage_entity(db, user, b.entity_type, b.entity_id)
                for b in crud_conflits._belligerants(db, entite.id) if b.status == "engage"
            )
        if entity_type == "personnage":
            return crud_personnages.can_manage(user, entite)
    except HTTPException:
        return False
    return False

#endregion
#region Supports

# Ce qu'on lie : livre (table livresliens) ou journal (table journauxliens). Mêmes entités et mêmes règles pour lier
# (droits sur l'écrit ET sur l'entité) ; seuls les droits sur l'écrit diffèrent : un livre suit crud._check_livre_rights
# (auteur, dirigeants d'une civilisation liée), un journal reste à son auteur (crud._check_owner_rights).
SUPPORTS = {
    "livre": {
        "model": models.LivresLiens, "fk": "livre_id", "get": get_livre, "nom": "Le livre",
        "droits": _check_livre_rights,
        "refus": "Seuls les gestionnaires du livre ou de ce qui y est lié peuvent retirer ce lien",
    },
    "journal": {
        "model": models.JournauxLiens, "fk": "journal_id", "get": get_journal, "nom": "Le journal",
        "droits": lambda db, user, journal: _check_owner_rights(user, journal.user_id),
        "refus": "Seuls l'auteur du journal et les gestionnaires de ce qui y est lié peuvent retirer ce lien",
    },
}

#endregion
#region Lecture

def lien_infos(db: Session, lien, support: str = "livre"):
    fk = SUPPORTS[support]["fk"]
    entite = _entite(db, lien.entity_type, lien.entity_id)
    return {"id": lien.id, fk: getattr(lien, fk), "entite": _resume(lien.entity_type, entite) if entite else None}

def liens_de(db: Session, support: str, ID: int):
    # Liens dont l'entité existe encore, par type puis par nom
    conf = SUPPORTS[support]
    if not conf["get"](db, ID):
        raise HTTPException(status_code=404, detail=f"{conf['nom']} n'existe pas")
    model = conf["model"]
    liens = db.exec(select(model).where(getattr(model, conf["fk"]) == ID)).all()
    infos = [info for info in (lien_infos(db, lien, support) for lien in liens) if info["entite"]]
    return sorted(infos, key=lambda info: (ENTITES.index(info["entite"]["type"]), info["entite"]["title"].lower()))

def ecrits_de_entite(db: Session, support: str, entity_type: str, entity_id: int):
    # Écrits liés à l'entité : [{ lien_id, <support> }] ; le site masque les écrits privés comme ailleurs
    if entity_type not in ENTITES:
        raise HTTPException(status_code=400, detail="Un livre ou un journal se lie à une civilisation, une religion, un commerce, une alliance, une guerre ou un personnage")
    conf = SUPPORTS[support]
    model = conf["model"]
    liens = db.exec(select(model).where(model.entity_type == entity_type, model.entity_id == entity_id)).all()
    resultats = []
    for lien in liens:
        ecrit = conf["get"](db, getattr(lien, conf["fk"]))
        if ecrit:
            resultats.append({"lien_id": lien.id, support: ecrit})
    return sorted(resultats, key=lambda r: r[support].title.lower())

def tous_les_liens(db: Session):
    # Tous les liens des livres et des journaux, pour la recherche de la bibliothèque :
    # [{ support, ecrit_id, entite: { type, id, title, … } }] ; les entités disparues sont omises
    resumes = {}
    def resume(entity_type, entity_id):
        cle = (entity_type, entity_id)
        if cle not in resumes:
            entite = _entite(db, entity_type, entity_id) if entity_type in ENTITES else None
            resumes[cle] = _resume(entity_type, entite) if entite else None
        return resumes[cle]
    resultats = []
    for support, conf in SUPPORTS.items():
        for lien in db.exec(select(conf["model"])).all():
            entite = resume(lien.entity_type, lien.entity_id)
            if entite:
                resultats.append({"support": support, "ecrit_id": getattr(lien, conf["fk"]), "entite": entite})
    return resultats

def liens_du_livre(db: Session, livreID: int):
    return liens_de(db, "livre", livreID)

def livres_de_entite(db: Session, entity_type: str, entity_id: int):
    return ecrits_de_entite(db, "livre", entity_type, entity_id)

#endregion
#region Gestion

def lier(db: Session, user: schemas.Users, body, support: str = "livre"):
    # body : LivreLienCreate (livre_id) ou JournalLienCreate (journal_id)
    conf = SUPPORTS[support]
    model, fk = conf["model"], conf["fk"]
    ecrit = conf["get"](db, getattr(body, fk))
    if not ecrit:
        raise HTTPException(status_code=404, detail=f"{conf['nom']} n'existe pas")
    conf["droits"](db, user, ecrit)
    entite = _entite(db, body.entity_type, body.entity_id)
    if not entite:
        raise HTTPException(status_code=404, detail="Cette entité n'existe pas")
    if not peut_gerer_entite(db, user, body.entity_type, entite):
        raise HTTPException(status_code=403, detail=f"Lier un {support} demande aussi des droits sur ce que vous liez (dirigeant, chef de file ou joueur du personnage)")
    deja = db.exec(select(model).where(
        getattr(model, fk) == ecrit.id, model.entity_type == body.entity_type, model.entity_id == entite.id,
    )).first()
    if deja:
        raise HTTPException(status_code=400, detail=f"{conf['nom']} y est déjà lié")
    lien = model(**{fk: ecrit.id}, entity_type=body.entity_type, entity_id=entite.id, created_by=user.id)
    db.add(lien)
    db.commit()
    db.refresh(lien)
    return lien_infos(db, lien, support)

def delier(db: Session, user: schemas.Users, lienID: int, support: str = "livre"):
    conf = SUPPORTS[support]
    lien = db.get(conf["model"], lienID)
    if not lien:
        raise HTTPException(status_code=404, detail="Ce lien n'existe pas")
    ecrit = conf["get"](db, getattr(lien, conf["fk"]))
    entite = _entite(db, lien.entity_type, lien.entity_id)
    try:
        if not ecrit:
            raise HTTPException(status_code=404)
        conf["droits"](db, user, ecrit)
    except HTTPException:
        if not (entite and peut_gerer_entite(db, user, lien.entity_type, entite)):
            raise HTTPException(status_code=403, detail=conf["refus"])
    db.delete(lien)
    db.commit()
    return True

#endregion
