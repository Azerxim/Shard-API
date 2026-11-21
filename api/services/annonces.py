"""Annonces Discord en embed : un titre (le type d'annonce), la phrase de l'annonce, des champs détaillés et le lien vers
la page du site (platforms.discord.site_url).

Chaque salon a sa couleur ; les limites de Discord (256 caractères pour un titre, 1 024 pour un champ, 25 champs) sont
respectées en tronquant. Les tests (SHARD_FAKE_DISCORD_ANNOUNCEMENTS) reçoivent aussi la version texte de l'embed, dans
« content » : titre, phrase, champs puis lien.
"""
import datetime as dt

from ..core import utils
from .crud import announce_discord

COULEURS = {
    "guerres": 0xB3261E,     # rouge
    "actions": 0x6B3FA0,     # violet
    "evenements": 0x2F5BB7,  # bleu
    "marches": 0xD98A1C,     # orange
    "lignees": 0xC9A227,     # or
    "fermes": 0x3E8E41,      # vert
}
GRIS = 0x6B7280  # annulations


def _tronquer(texte, limite: int) -> str:
    texte = str(texte)
    return texte if len(texte) <= limite else texte[: limite - 1].rstrip() + "…"


def lien_site(chemin: str | None) -> str | None:
    site = ((utils.PLATFORMS or {}).get("discord") or {}).get("site_url")
    return f"{str(site).rstrip('/')}{chemin}" if site and chemin else None


def champ(nom: str, valeur, en_ligne: bool = True):
    """Champ d'embed, ou None quand la valeur est vide (il est alors omis)."""
    if valeur is None or str(valeur).strip() == "":
        return None
    return {"name": _tronquer(nom, 256), "value": _tronquer(valeur, 1024), "inline": en_ligne}


def couleur_hex(valeur: str | None) -> int | None:
    """« #c98a12 » → entier pour Discord (None si la couleur est absente ou mal écrite)."""
    try:
        return int(str(valeur).lstrip("#"), 16) if valeur else None
    except ValueError:
        return None


def embed(salon: str, titre: str, description: str | None = None, chemin: str | None = None, champs=(),
          couleur: int | None = None, pied: str | None = None) -> dict:
    donnees = {
        "title": _tronquer(titre, 256),
        "color": couleur if couleur is not None else COULEURS.get(salon, COULEURS["evenements"]),
        "footer": {"text": _tronquer(pied or "Tetrago", 2048)},
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    if description:
        # L'emoji du titre n'est pas répété en tête de la phrase (« 🎪 Nouvelle foire » puis « **Foire aux chevaux**… »)
        emoji = titre.split(" ", 1)[0]
        if not emoji.isalnum() and description.startswith(f"{emoji} "):
            description = description[len(emoji) + 1:]
        donnees["description"] = _tronquer(description, 4096)
    url = lien_site(chemin)
    if url:
        donnees["url"] = url
    champs = [c for c in champs if c][:25]
    if champs:
        donnees["fields"] = champs
    return donnees


def texte_brut(donnees: dict) -> str:
    """Version texte d'un embed : titre, phrase, « champ : valeur », lien en dernier."""
    lignes = [donnees.get("title"), donnees.get("description")]
    lignes += [f"{c['name']} : {c['value']}" for c in donnees.get("fields", [])]
    lignes.append(donnees.get("url"))
    return "\n".join(ligne for ligne in lignes if ligne)


def annoncer(salon: str, titre: str, description: str | None = None, chemin: str | None = None, champs=(),
             couleur: int | None = None, pied: str | None = None):
    """Annonce dans le salon platforms.discord.channels.<salon> (en tâche de fond, sans bloquer la requête)."""
    donnees = embed(salon, titre, description, chemin, champs, couleur, pied)
    return announce_discord(salon, embed=donnees, texte=texte_brut(donnees))
