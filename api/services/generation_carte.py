"""Génération de la carte à la demande, depuis la page des statistiques du monde (administrateurs).

L'API lance le générateur de Shard-Maps (scripts/map-generator/run.sh) en tâche détachée, sans aucun argument venu du
navigateur : téléchargement du monde, cartes, monde téléchargeable et relevé des statistiques, comme la tâche cron du
lundi. Il faut donc que l'API et Shard-Maps soient sur la même machine.

- Chemin du lanceur : config.json « platforms.monde.generateur » ; par défaut ../Shard-Maps/scripts/map-generator/run.sh
  à côté de Shard-API.
- En cours : run.sh tient un verrou (flock) sur .cache/run.lock, que l'on teste sans le prendre.
- État : date de maps.json (dernière carte publiée) et fin du dernier journal (logs/map-generator).
- Tests : SHARD_FAKE_MAP_GENERATION désigne un fichier où chaque lancement est écrit au lieu d'être exécuté.
"""
import datetime as dt
import fcntl
import json
import os
import subprocess

from fastapi import HTTPException

from ..core import utils

LIGNES_JOURNAL = 20


def _lanceur() -> str | None:
    chemin = ((utils.PLATFORMS or {}).get("monde") or {}).get("generateur")
    if not chemin:
        chemin = os.path.join(utils.ROOT_DIR, "..", "Shard-Maps", "scripts", "map-generator", "run.sh")
    chemin = os.path.realpath(chemin if os.path.isabs(chemin) else os.path.join(utils.ROOT_DIR, chemin))
    return chemin if os.path.isfile(chemin) else None


def _dossiers(lanceur: str):
    dossier = os.path.dirname(lanceur)
    maps = os.path.realpath(os.path.join(dossier, "..", ".."))
    return {
        "verrou": os.path.join(dossier, ".cache", "run.lock"),
        "journaux": os.path.join(maps, "logs", "map-generator"),
        "maps_json": os.path.join(maps, "assets", "data", "maps.json"),
    }


def _en_cours(verrou: str) -> bool:
    if not os.path.exists(verrou):
        return False
    with open(verrou, "a") as fichier:
        try:
            fcntl.flock(fichier, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fichier, fcntl.LOCK_UN)
    return False


def _dernier_journal(dossier: str):
    try:
        journaux = sorted(nom for nom in os.listdir(dossier) if nom.endswith(".log"))
    except OSError:
        return None
    if not journaux:
        return None
    chemin = os.path.join(dossier, journaux[-1])
    with open(chemin, encoding="utf-8", errors="replace") as fichier:
        lignes = fichier.read().splitlines()
    # [DONE] clôt une génération (« en erreur : … » si une carte a échoué) ; un relevé seul (--stats-only) finit par l'envoi
    erreur = any("[ERROR]" in ligne or ("[DONE]" in ligne and "en erreur" in ligne) for ligne in lignes)
    termine = any("[DONE]" in ligne or "[STATS] Relevé envoyé" in ligne for ligne in lignes)
    return {
        "fichier": journaux[-1],
        "debut": dt.datetime.fromtimestamp(os.path.getctime(chemin)).isoformat(timespec="seconds"),
        "modifie": dt.datetime.fromtimestamp(os.path.getmtime(chemin)).isoformat(timespec="seconds"),
        "resultat": "erreur" if erreur else "termine" if termine else "inconnu",
        "lignes": lignes[-LIGNES_JOURNAL:],
    }


def _date_carte(maps_json: str):
    try:
        with open(maps_json, encoding="utf-8") as fichier:
            return json.load(fichier).get("date") or None
    except (OSError, ValueError):
        return None


def etat():
    if os.environ.get("SHARD_FAKE_MAP_GENERATION"):
        return {"disponible": True, "en_cours": False, "date_carte": None, "journal": None}
    lanceur = _lanceur()
    if not lanceur:
        return {"disponible": False, "en_cours": False, "date_carte": None, "journal": None,
                "raison": "Générateur introuvable : indiquer le chemin de run.sh dans platforms.monde.generateur (config.json)."}
    dossiers = _dossiers(lanceur)
    return {
        "disponible": True,
        "en_cours": _en_cours(dossiers["verrou"]),
        "date_carte": _date_carte(dossiers["maps_json"]),
        "journal": _dernier_journal(dossiers["journaux"]),
    }


def lancer(auteur: str):
    fichier_simule = os.environ.get("SHARD_FAKE_MAP_GENERATION")
    if fichier_simule:
        with open(fichier_simule, "a", encoding="utf-8") as fichier:
            fichier.write(json.dumps({"auteur": auteur, "date": dt.datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False) + "\n")
        return {**etat(), "lance": True}
    lanceur = _lanceur()
    if not lanceur:
        raise HTTPException(status_code=503, detail="Générateur de cartes introuvable sur ce serveur (platforms.monde.generateur)")
    if _en_cours(_dossiers(lanceur)["verrou"]):
        raise HTTPException(status_code=409, detail="Une génération de la carte est déjà en cours")
    # Détaché : la génération (plusieurs minutes) survit à la requête ; run.sh écrit son propre journal
    subprocess.Popen(["bash", lanceur], cwd=os.path.dirname(lanceur), stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    print(f"Génération de la carte lancée par {auteur}")
    # Le verrou n'est pris qu'au démarrage de run.sh : la génération est annoncée en cours dès maintenant
    return {**etat(), "lance": True, "en_cours": True}
