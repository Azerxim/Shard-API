"""
Description longue (Markdown) d'une civilisation, d'un commerce, d'une religion, d'une alliance ou d'un personnage.

Affichée sous la première carte de la fiche et modifiée sur place (ShardUI-2, DescriptionLongue). La modifier demande
les mêmes droits que lier un écrit à l'entité (crud_livres.peut_gerer_entite) : Fondateur ou Admin de la civilisation,
de la religion ou du commerce, chef de file de l'alliance, joueur du personnage ; l'administrateur du site peut tout.
"""
from fastapi import HTTPException
from sqlmodel import Session

from ..db import schemas
from . import crud_livres

ENTITES = ("civilisation", "commerce", "religion", "alliance", "personnage")
TAILLE_MAX = 50000  # caractères


def _require_entite(db: Session, entity_type: str, entity_id: int):
    if entity_type not in ENTITES:
        raise HTTPException(status_code=400, detail="Une description longue s'ajoute à une civilisation, un commerce, une religion, une alliance ou un personnage")
    entite = crud_livres._entite(db, entity_type, entity_id)
    if not entite:
        raise HTTPException(status_code=404, detail="Cette fiche n'existe pas")
    return entite

def lire(db: Session, entity_type: str, entity_id: int):
    entite = _require_entite(db, entity_type, entity_id)
    return {"type": entity_type, "id": entite.id, "description_longue": entite.description_longue}

def modifier(db: Session, user: schemas.Users, entity_type: str, entity_id: int, body: schemas.DescriptionLongue):
    entite = _require_entite(db, entity_type, entity_id)
    if not crud_livres.peut_gerer_entite(db, user, entity_type, entite):
        raise HTTPException(status_code=403, detail="Seuls les gestionnaires de cette fiche peuvent modifier sa description longue")
    texte = (body.description_longue or "").strip()
    if len(texte) > TAILLE_MAX:
        raise HTTPException(status_code=400, detail=f"La description longue est limitée à {TAILLE_MAX} caractères")
    entite.description_longue = texte or None
    db.add(entite)
    db.commit()
    db.refresh(entite)
    return {"type": entity_type, "id": entite.id, "description_longue": entite.description_longue}
