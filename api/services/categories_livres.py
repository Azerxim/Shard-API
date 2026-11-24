"""
Catégories des livres, sur le modèle de celles des journaux (services/salons_journaux.py), sans salon Discord.

- Catégorie : une des CATEGORIES ci-dessous (« divers » par défaut), affichée et filtrée dans la bibliothèque ;
- « officiel » (textes officiels du serveur, Codex) est réservée aux administrateurs du site et toujours en tête des listes.
"""
from fastapi import HTTPException

# Ordre d'affichage (même ordre que config/livres.js de ShardUI-2)
CATEGORIES = {
    "officiel": "Textes officiels",
    "lois": "Lois",
    "histoire": "Histoire",
    "legendes": "Légendes",
    "religion": "Religion",
    "traites": "Traités",
    "recits": "Récits",
    "savoirs": "Savoirs",
    "divers": "Divers",
}
CATEGORIE_DEFAUT = "divers"
CATEGORIES_ADMIN = {"officiel"}


def categorie_valide(categorie: str | None, user=None, actuelle: str | None = None) -> str:
    # actuelle : catégorie du livre modifié ; un auteur garde « Textes officiels » sur un livre qui l'a déjà, sans pouvoir la choisir
    if not categorie:
        return CATEGORIE_DEFAUT
    if categorie not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Catégorie de livre inconnue : choisissez parmi {', '.join(CATEGORIES.values())}")
    if categorie in CATEGORIES_ADMIN and categorie != actuelle and not (user is not None and user.is_admin and not user.is_disabled):
        raise HTTPException(status_code=403, detail=f"Seuls les administrateurs classent un livre dans la catégorie « {CATEGORIES[categorie]} »")
    return categorie
