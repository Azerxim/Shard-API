"""
Catalogue des boutiques : articles vendus par chaque magasin, avec leur prix en tetras (1 tetra = 1 diamant).

- Un article est vendu par lot : « 16 pains pour 1 tetra ». Le prix unitaire (prix / quantité) sert au classement.
- Le catalogue d'un magasin est tenu par le Fondateur et les Admins de son commerce (ou un administrateur du site),
  comme le magasin lui-même.
- La recherche « où acheter » ne parcourt que les magasins publics des commerces publics. Elle ignore la casse et les
  accents (« epee » trouve « Épée »), ce que `LIKE` de SQLite ne sait pas faire : le filtre se fait donc en Python.
"""
import datetime as dt
import unicodedata

from fastapi import HTTPException
from sqlmodel import Session, select

from ..db import models, schemas
from .crud import _check_commerce_rights, get_commerce_by_id, get_dimension_by_id, get_magasin_by_id, get_ville_by_id

# Clés reprises par le site (ShardUI-2/src/config/catalogue.js)
CATEGORIES = ("construction", "ressources", "outils", "armes", "nourriture", "alchimie", "services", "divers")
RESULTATS_MAX = 200


#region Outils

def _normaliser(texte: str | None) -> str:
    sans_accents = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(sans_accents.lower().split())

def prix_unitaire(article: models.MagasinArticles) -> float:
    return article.prix / max(article.quantite or 1, 1)

def article_infos(article: models.MagasinArticles):
    return {
        "id": article.id,
        "magasin_id": article.magasin_id,
        "title": article.title,
        "categorie": article.categorie,
        "description": article.description,
        "prix": article.prix,
        "quantite": article.quantite,
        "prix_unitaire": prix_unitaire(article),
        "en_stock": article.en_stock,
        "updated_at": article.updated_at,
    }

def _articles_of_magasin(db: Session, magasinID: int):
    statement = select(models.MagasinArticles).where(models.MagasinArticles.magasin_id == magasinID)
    return db.exec(statement).all()

def _trier(articles):
    # Par catégorie (ordre de CATEGORIES), puis par nom
    rang = {cle: index for index, cle in enumerate(CATEGORIES)}
    return sorted(articles, key=lambda a: (rang.get(a.categorie, len(CATEGORIES)), _normaliser(a.title)))

def _valider(categorie: str | None, prix: int | None, quantite: int | None):
    if categorie is not None and categorie not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Catégorie inconnue : {categorie}")
    if prix is not None and prix < 0:
        raise HTTPException(status_code=400, detail="Le prix ne peut pas être négatif")
    if quantite is not None and quantite < 1:
        raise HTTPException(status_code=400, detail="Un lot contient au moins un article")

#endregion
#region Lecture

def catalogue_magasin(db: Session, magasinID: int):
    # Même visibilité que la liste des magasins : le site masque les magasins privés à qui n'en est pas membre
    if not get_magasin_by_id(db, magasinID):
        raise HTTPException(status_code=404, detail="Le magasin n'existe pas")
    return [article_infos(article) for article in _trier(_articles_of_magasin(db, magasinID))]

def rechercher(db: Session, q: str | None = None, categorie: str | None = None, ville_id: int | None = None, en_stock: bool = False):
    # Où acheter : articles des magasins publics des commerces publics, du moins cher (à l'unité) au plus cher
    mots = _normaliser(q).split()
    if not mots and not categorie:
        raise HTTPException(status_code=400, detail="Indiquez un article à chercher ou une catégorie")
    _valider(categorie, None, None)

    statement = (
        select(models.MagasinArticles, models.CommerceMagasins, models.Commerces)
        .where(models.CommerceMagasins.id == models.MagasinArticles.magasin_id)
        .where(models.Commerces.id == models.CommerceMagasins.commerce_id)
        .where(models.CommerceMagasins.is_public != False, models.Commerces.is_public != False)  # noqa: E712 (NULL = public)
    )
    if categorie:
        statement = statement.where(models.MagasinArticles.categorie == categorie)
    if ville_id:
        statement = statement.where(models.CommerceMagasins.ville_id == ville_id)
    if en_stock:
        statement = statement.where(models.MagasinArticles.en_stock == True)  # noqa: E712

    trouves = []
    for article, magasin, commerce in db.exec(statement).all():
        texte = _normaliser(f"{article.title} {article.description or ''}")
        if all(mot in texte for mot in mots):
            trouves.append((article, magasin, commerce))
    # En stock d'abord, puis le moins cher à l'unité
    trouves.sort(key=lambda t: (not t[0].en_stock, prix_unitaire(t[0]), _normaliser(t[0].title)))

    villes, dimensions = {}, {}
    resultats = []
    for article, magasin, commerce in trouves[:RESULTATS_MAX]:
        if magasin.ville_id and magasin.ville_id not in villes:
            villes[magasin.ville_id] = get_ville_by_id(db, magasin.ville_id)
        if magasin.dimension_id and magasin.dimension_id not in dimensions:
            dimensions[magasin.dimension_id] = get_dimension_by_id(db, magasin.dimension_id)
        ville = villes.get(magasin.ville_id)
        dimension = dimensions.get(magasin.dimension_id)
        resultats.append({
            **article_infos(article),
            "magasin": {"id": magasin.id, "title": magasin.title, "is_siege": magasin.is_siege, "x": magasin.x, "z": magasin.z},
            "commerce": {"id": commerce.id, "title": commerce.title},
            "ville": {"id": ville.id, "title": ville.title, "civilisation_id": ville.civilisation_id} if ville and ville.is_public is not False else None,
            "dimension": {"id": dimension.id, "title": dimension.title, "link": dimension.link} if dimension else None,
        })
    return {"total": len(trouves), "resultats": resultats}

#endregion
#region Gestion

def _magasin_gere(db: Session, user: schemas.Users, magasinID: int) -> models.CommerceMagasins:
    db_magasin = get_magasin_by_id(db, magasinID)
    if not db_magasin:
        raise HTTPException(status_code=404, detail="Le magasin n'existe pas")
    _check_commerce_rights(db, user, get_commerce_by_id(db, db_magasin.commerce_id))
    return db_magasin

def _require_article(db: Session, user: schemas.Users, ID: int) -> models.MagasinArticles:
    article = db.get(models.MagasinArticles, ID)
    if not article:
        raise HTTPException(status_code=404, detail="Cet article n'existe pas")
    _magasin_gere(db, user, article.magasin_id)
    return article

def create_article(db: Session, user: schemas.Users, body: schemas.ArticleCreate):
    _magasin_gere(db, user, body.magasin_id)
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Un article doit avoir un nom")
    categorie = body.categorie or "divers"
    quantite = 1 if body.quantite is None else body.quantite
    _valider(categorie, body.prix, quantite)
    article = models.MagasinArticles(
        magasin_id=body.magasin_id,
        title=title,
        categorie=categorie,
        description=(body.description or "").strip() or None,
        prix=body.prix,
        quantite=quantite,
        en_stock=body.en_stock is not False,
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article_infos(article)

def update_article(db: Session, user: schemas.Users, ID: int, body: schemas.ArticleUpdate):
    article = _require_article(db, user, ID)
    data = body.model_dump(exclude_unset=True)
    # Un nom, un prix ou une taille de lot ne s'effacent pas ; la description, si
    for key in ("title", "categorie", "prix", "quantite", "en_stock"):
        if data.get(key) is None:
            data.pop(key, None)
    if "title" in data:
        data["title"] = data["title"].strip()
        if not data["title"]:
            raise HTTPException(status_code=400, detail="Un article doit avoir un nom")
    if "description" in data:
        data["description"] = (data["description"] or "").strip() or None
    _valider(data.get("categorie"), data.get("prix"), data.get("quantite"))
    for key, value in data.items():
        setattr(article, key, value)
    article.updated_at = dt.datetime.now()
    db.add(article)
    db.commit()
    db.refresh(article)
    return article_infos(article)

def delete_article(db: Session, user: schemas.Users, ID: int):
    article = _require_article(db, user, ID)
    db.delete(article)
    db.commit()
    return True

def supprimer_articles_magasin(db: Session, magasinID: int):
    # Nettoyage à la suppression du magasin ; le commit reste à l'appelant
    for article in _articles_of_magasin(db, magasinID):
        db.delete(article)

#endregion
