"""
Catégories des journaux et salons Discord qui les alimentent.

- Catégorie : une des CATEGORIES ci-dessous (« divers » par défaut), affichée et filtrée dans la bibliothèque ;
  « monde » est réservée aux administrateurs du site. Sur Discord,
  le salon d'un journal va dans la catégorie platforms.discord.categories.journaux_<categorie>, ou à défaut dans
  platforms.discord.categories.journaux (voir config.json.template).
- Salon : à la création, le site crée un salon (salon_cree = True) ou, pour un administrateur du site seulement, lie un
  salon texte existant du serveur (salon_cree = False). Un salon n'alimente qu'un journal à la fois.
- À la suppression du journal, le salon créé par le site est supprimé, ou seulement délié sur demande. Un salon lié
  n'est jamais supprimé par le site : il est seulement délié.

Tests : SHARD_FAKE_DISCORD_CHANNELS désigne un fichier JSON { "<id du salon>": { name, category_id, type } } lu et modifié
à la place de Discord (création, déplacement, suppression).
"""
import asyncio
import json
import os
import time

from fastapi import HTTPException
from sqlmodel import Session, select

from ..db import models
from ..integrations import discord_handler
from ..core import utils

# « monde » : récits officiels du monde, catégorie réservée aux administrateurs du site (toujours en tête des listes)
CATEGORIES = {
    "monde": "Monde",
    "gazette": "Gazette",
    "chronique": "Chronique",
    "correspondance": "Correspondance",
    "carnet": "Carnet",
    "proclamation": "Proclamation",
    "divers": "Divers",
}
CATEGORIE_DEFAUT = "divers"
CATEGORIES_ADMIN = {"monde"}


def categorie_valide(categorie: str | None, user=None, actuelle: str | None = None) -> str:
    # actuelle : catégorie du journal modifié ; un joueur garde « Monde » sur un journal qui l'a déjà, sans pouvoir la choisir
    if not categorie:
        return CATEGORIE_DEFAUT
    if categorie not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Catégorie de journal inconnue : choisissez parmi {', '.join(CATEGORIES.values())}")
    if categorie in CATEGORIES_ADMIN and categorie != actuelle and not (user is not None and user.is_admin and not user.is_disabled):
        raise HTTPException(status_code=403, detail=f"Seuls les administrateurs classent un journal dans la catégorie « {CATEGORIES[categorie]} »")
    return categorie


def _categories_discord() -> dict:
    return ((utils.PLATFORMS or {}).get("discord") or {}).get("categories") or {}


def categorie_discord(categorie: str | None) -> int | None:
    # Catégorie Discord du salon d'un journal de cette catégorie ; None : hors catégorie
    configurees = _categories_discord()
    identifiant = configurees.get(f"journaux_{categorie}") or configurees.get("journaux")
    return int(identifiant) if identifiant else None


#region Discord (ou sa simulation)

def _simulation() -> str | None:
    return os.environ.get("SHARD_FAKE_DISCORD_CHANNELS")


def _lire_simulation(fichier: str) -> dict:
    try:
        with open(fichier, encoding="utf-8") as source:
            return json.load(source)
    except FileNotFoundError:
        return {}


def _ecrire_simulation(fichier: str, salons: dict):
    with open(fichier, "w", encoding="utf-8") as destination:
        json.dump(salons, destination, ensure_ascii=False, indent=2)


def _executer(coroutine):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()


def _infos_salon(channel_id: str) -> dict | None:
    # { id, name, category_id, type } ; None si le salon n'est pas sur le serveur
    fichier = _simulation()
    if fichier:
        salon = _lire_simulation(fichier).get(str(channel_id))
        return {"id": str(channel_id), **salon} if salon else None
    return _executer(discord_handler.get_channel_info(channel_id))


def creer_salon(titre: str, description: str | None, categorie: str | None) -> str | None:
    # Identifiant du salon créé, ou None si Discord est injoignable (le journal est créé sans salon)
    category_id = categorie_discord(categorie)
    fichier = _simulation()
    try:
        if fichier:
            salons = _lire_simulation(fichier)
            channel_id = str(int(time.time() * 1000))
            while channel_id in salons:
                channel_id = str(int(channel_id) + 1)
            salons[channel_id] = {"name": titre.lower().replace(" ", "-")[:32], "category_id": str(category_id) if category_id else None, "type": "text"}
            _ecrire_simulation(fichier, salons)
            return channel_id
        channel_id = _executer(discord_handler.create_channel(titre, description, category_id))
        print(f"\033[92mSalon Discord créé avec l'ID: {channel_id}\033[0m")
        return channel_id
    except Exception as error:
        print(f"Avertissement: Impossible de créer le salon Discord: {error}")
        return None


def supprimer_salon(channel_id: str) -> bool:
    fichier = _simulation()
    try:
        if fichier:
            salons = _lire_simulation(fichier)
            existait = salons.pop(str(channel_id), None) is not None
            _ecrire_simulation(fichier, salons)
            return existait
        return _executer(discord_handler.delete_channel(channel_id))
    except Exception as error:
        print(f"Avertissement: Erreur suppression salon Discord {channel_id}: {error}")
        return False


async def mettre_a_jour_salon(journal, titre: str | None = None, description: str | None = None, categorie: str | None = None):
    # Modification du journal reportée sur le salon créé par le site (nom, sujet, catégorie Discord). Un salon lié
    # appartient à son serveur : le site n'y touche pas. Un échec Discord ne fait pas échouer la modification.
    if not journal.uid or journal.salon_cree is False:
        return
    category_id = categorie_discord(categorie) if categorie else None
    fichier = _simulation()
    try:
        if fichier:
            salons = _lire_simulation(fichier)
            salon = salons.get(str(journal.uid))
            if salon is None:
                return
            if titre:
                salon["name"] = titre.lower().replace(" ", "-")[:32]
            if description is not None:
                salon["topic"] = description
            if category_id:
                salon["category_id"] = str(category_id)
            _ecrire_simulation(fichier, salons)
            return
        if titre:
            await discord_handler.update_channel_name(journal.uid, titre)
        if description is not None:
            await discord_handler.update_channel_description(journal.uid, description)
        if category_id:
            await discord_handler.move_channel(journal.uid, category_id)
    except Exception as error:
        print(f"Avertissement: Salon Discord {journal.uid} non mis à jour: {error}")

#endregion


def verifier_salon_a_lier(db: Session, user, channel_id: str | None, journal_id: int | None = None) -> str:
    # Identifiant du salon existant à lier à un journal, ou erreur expliquée. Réservé aux administrateurs du site : un
    # journal publie les messages du salon sur le site.
    if user.is_disabled or not user.is_admin:
        raise HTTPException(status_code=403, detail="Seuls les administrateurs lient un salon Discord existant à un journal")
    channel_id = str(channel_id or "").strip()
    if not channel_id.isdigit():
        raise HTTPException(status_code=400, detail="Indiquez l'identifiant du salon Discord à lier (clic droit sur le salon, « Copier l'identifiant du salon »)")
    deja = db.exec(select(models.Journaux).where(models.Journaux.uid == channel_id)).first()
    if deja and deja.id != journal_id:
        raise HTTPException(status_code=409, detail=f"Ce salon alimente déjà le journal « {deja.title} »")
    try:
        salon = _infos_salon(channel_id)
    except Exception as error:
        print(f"Salon Discord {channel_id} non vérifié : {error}")
        raise HTTPException(status_code=503, detail="Discord est injoignable : le salon n'a pas pu être vérifié, réessayez plus tard")
    if not salon:
        raise HTTPException(status_code=404, detail="Ce salon n'existe pas sur le serveur Discord de Tetrago")
    if salon.get("type") != "text":
        raise HTTPException(status_code=400, detail="Seul un salon textuel peut alimenter un journal")
    return channel_id
