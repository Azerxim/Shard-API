"""Temporalité du RP, miroir de ShardUI-2 (src/config/temporalite.js).

1 semaine réelle = 2 ans dans le RP ; l'an 1 commence à l'ouverture de la saison : config.json, « rp » :
{ "debut": "2026-11-14T14:00:00+01:00", "ans_par_semaine": 2 }, la même date que VITE_SAISON_LANCEMENT du site.
Calendrier RP de 365 jours (mois usuels, sans année bissextile). Sert aux dates RP laissées vides (début et fin d'une
guerre) ; sans « rp.debut » dans la configuration, la date réelle du jour, comme auparavant.
"""
import datetime as dt

from ..core import utils

JOURS_PAR_MOIS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
JOURS_PAR_AN = 365


def _reglage():
    rp = (utils.CONFIG or {}).get("rp") or {}
    try:
        debut = dt.datetime.fromisoformat(rp["debut"]) if rp.get("debut") else None
    except (TypeError, ValueError):
        debut = None
    if debut is not None and debut.tzinfo is None:
        debut = debut.astimezone()  # sans fuseau : heure locale du serveur
    return debut, float(rp.get("ans_par_semaine") or 2)


def date_rp_du_jour(maintenant: dt.datetime | None = None) -> dt.date:
    """Date du jour dans le RP (avant l'ouverture : 1er janvier de l'an 1)."""
    debut, ans_par_semaine = _reglage()
    if debut is None:
        return dt.date.today()
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    ecoule = max((maintenant - debut).total_seconds(), 0)
    duree_an = 7 * 86400 / ans_par_semaine
    ans = int(ecoule // duree_an)
    jour = min(int((ecoule - ans * duree_an) / duree_an * JOURS_PAR_AN), JOURS_PAR_AN - 1)
    mois = 0
    while jour >= JOURS_PAR_MOIS[mois]:
        jour -= JOURS_PAR_MOIS[mois]
        mois += 1
    return dt.date(min(ans + 1, dt.MAXYEAR), mois + 1, jour + 1)


MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")


def date_rp_texte(date: dt.date | None) -> str | None:
    """« 21 juin de l'an 419 » (None sans date)."""
    if not date:
        return None
    return f"{date.day}{'er' if date.day == 1 else ''} {MOIS[date.month - 1]} de l'an {date.year}"
