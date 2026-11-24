"""
Messages des journaux, gardés quelques minutes en mémoire au lieu d'être relus sur Discord à chaque visite.

Lire un salon demande de connecter un bot Discord (plusieurs secondes) et compte dans la limite de requêtes de Discord :
- les messages lus sont gardés CACHE_SECONDES par salon, du plus récent au plus ancien ;
- la lecture se fait par pages (« Charger plus » sur le site) : on ne demande à Discord que les messages plus anciens
  qui manquent, à partir du plus ancien déjà gardé ;
- « Rafraîchir » (rafraichir=True) relit le salon, mais pas plus d'une fois toutes les RAFRAICHIR_SECONDES, pour qu'un
  visiteur ne puisse pas épuiser la limite de Discord.

Tests : SHARD_FAKE_JOURNAL_MESSAGES désigne un fichier JSON { "<id du salon>": [messages, du plus récent au plus ancien] }
lu à la place de Discord ; le cache s'y applique aussi.
"""
import asyncio
import json
import os
import threading
import time

from ..integrations import discord_handler

CACHE_SECONDES = 300
# Tests : SHARD_JOURNAL_RAFRAICHIR_SECONDES=0 pour relire aussitôt
RAFRAICHIR_SECONDES = float(os.environ.get("SHARD_JOURNAL_RAFRAICHIR_SECONDES", 10))

# { id du salon : { "messages": [...], "complet": bool, "lu_le": time.monotonic() } }
_cache: dict[str, dict] = {}
_verrous: dict[str, threading.Lock] = {}
_verrou_global = threading.Lock()


class LectureImpossible(Exception):
    """Discord n'a pas pu être lu (bot non connecté, configuration absente…)."""


def _verrou(channel_id: str) -> threading.Lock:
    with _verrou_global:
        return _verrous.setdefault(channel_id, threading.Lock())


def _lire_discord(channel_id: str, limit: int, before: str | None = None) -> list:
    # Messages du salon, du plus récent au plus ancien ; before : seulement ceux antérieurs à ce message
    fake_file = os.environ.get("SHARD_FAKE_JOURNAL_MESSAGES")
    if fake_file:
        try:
            with open(fake_file, encoding="utf-8") as file:
                messages = json.load(file).get(str(channel_id)) or []
        except FileNotFoundError:
            messages = []
        if before is not None:
            index = next((i for i, message in enumerate(messages) if str(message.get("id")) == str(before)), None)
            messages = messages[index + 1:] if index is not None else []
        return messages[:limit]
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        messages = loop.run_until_complete(discord_handler.get_channel_messages(channel_id, limit=limit, before=before))
    finally:
        loop.close()
    if messages is None:
        raise LectureImpossible("Discord n'a pas pu être lu")
    return messages


def oublier(channel_id: str | None):
    # Salon supprimé, délié ou remplacé : ses messages ne sont plus gardés
    if channel_id:
        _cache.pop(str(channel_id), None)


def page(channel_id: str, skip: int = 0, limit: int = 100, rafraichir: bool = False) -> dict:
    """Messages skip à skip + limit du salon (du plus récent au plus ancien), lus dans le cache ou sur Discord.

    Retourne { messages, plus_anciens (il en reste après cette page), complet (tout le salon est lu), lu_le (secondes
    depuis la lecture sur Discord), en_cache (aucune lecture sur Discord pour cette page) }.
    """
    channel_id = str(channel_id)
    skip = max(0, int(skip))
    limit = max(1, int(limit))
    voulu = skip + limit + 1  # un de plus : savoir s'il en reste après la page
    with _verrou(channel_id):
        maintenant = time.monotonic()
        entree = _cache.get(channel_id)
        if entree is not None:
            age = maintenant - entree["lu_le"]
            if age > CACHE_SECONDES or (rafraichir and age >= RAFRAICHIR_SECONDES):
                entree = None
        en_cache = True
        if entree is None:
            messages = _lire_discord(channel_id, voulu)
            entree = {"messages": messages, "complet": len(messages) < voulu, "lu_le": maintenant}
            _cache[channel_id] = entree
            en_cache = False
        elif not entree["complet"] and len(entree["messages"]) < voulu:
            # Messages plus anciens que ceux déjà gardés
            manquants = voulu - len(entree["messages"])
            plus_ancien = entree["messages"][-1].get("id") if entree["messages"] else None
            suite = _lire_discord(channel_id, manquants, before=plus_ancien)
            connus = {str(message.get("id")) for message in entree["messages"]}
            entree["messages"].extend(message for message in suite if str(message.get("id")) not in connus)
            entree["complet"] = len(suite) < manquants
            en_cache = False
        messages = entree["messages"]
        return {
            "messages": messages[skip:skip + limit],
            "plus_anciens": len(messages) > skip + limit,
            "complet": entree["complet"],
            "lu_le": round(maintenant - entree["lu_le"]),
            "en_cache": en_cache,
            "gardes": len(messages),
        }


def message_garde(channel_id: str, message_id: str) -> dict | None:
    # Message déjà gardé en cache (signature par un personnage) ; None : à lire sur Discord
    entree = _cache.get(str(channel_id))
    if entree is None or time.monotonic() - entree["lu_le"] > CACHE_SECONDES:
        return None
    return next((message for message in entree["messages"] if str(message.get("id")) == str(message_id)), None)
