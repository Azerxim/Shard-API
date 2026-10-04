"""
Images envoyées par les joueurs (photos des fermes, portraits et skins des personnages).

- Rangées dans ./uploads/<dossier> (dossier courant de l'API, comme la base ; ignoré par git) sous un nom aléatoire
  de 32 caractères. Ce nom imprévisible tient lieu de droit d'accès : une balise <img> n'envoie pas de jeton.
- Le format est reconnu à la signature du fichier, jamais à son extension ni au type annoncé par le navigateur.
- Ce module ne dépend d'aucun autre service : crud_nettoyage peut l'utiliser.
"""
import os
import secrets
import struct

from fastapi import HTTPException

RACINE = os.path.join(".", "uploads")
IMAGES = ("png", "jpg", "webp")
MAX_OCTETS = 5 * 1024 * 1024


def format_image(contenu: bytes) -> str | None:
    if contenu.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if contenu.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if contenu.startswith(b"RIFF") and contenu[8:12] == b"WEBP":
        return "webp"
    return None

def dimensions_png(contenu: bytes) -> tuple[int, int] | None:
    # Largeur et hauteur lues dans l'en-tête IHDR d'un PNG
    if format_image(contenu) != "png" or len(contenu) < 24 or contenu[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", contenu[16:24])

def enregistrer(dossier: str, contenu: bytes, formats=IMAGES, max_octets: int = MAX_OCTETS, libelle: str = "L'image") -> str:
    # Vérifie puis écrit le fichier ; renvoie son nom. Les formats acceptés sont des clés de format_image.
    if not contenu:
        raise HTTPException(status_code=400, detail="Le fichier est vide")
    if len(contenu) > max_octets:
        raise HTTPException(status_code=413, detail=f"{libelle} dépasse {max_octets // (1024 * 1024)} Mo")
    extension = format_image(contenu)
    if extension not in formats:
        noms = {"png": "PNG", "jpg": "JPEG", "webp": "WebP"}
        raise HTTPException(status_code=400, detail=f"{libelle} doit être une image {' ou '.join(noms[f] for f in formats)}")
    chemin_dossier = os.path.join(RACINE, dossier)
    os.makedirs(chemin_dossier, exist_ok=True)
    nom = f"{secrets.token_hex(16)}.{extension}"
    with open(os.path.join(chemin_dossier, nom), "wb") as fichier:
        fichier.write(contenu)
    return nom

def supprimer(dossier: str, nom: str | None):
    if nom:
        try:
            os.remove(os.path.join(RACINE, dossier, os.path.basename(nom)))
        except OSError:
            pass

def chemin(dossier: str, nom: str) -> str:
    # Nom produit par enregistrer uniquement (pas de chemin, pas de « .. »)
    base = os.path.basename(nom)
    fichier = os.path.join(RACINE, dossier, base)
    if base != nom or not os.path.isfile(fichier):
        raise HTTPException(status_code=404, detail="Ce fichier n'existe pas")
    return fichier
