"""
Import des données historiques des dumps SQL mbu-s1 / mbu-tetrago vers les tables
préfixées s1-/s2- (voir models_shards.py).

Les fichiers dump ne sont pas exécutés tels quels (syntaxe MariaDB, moteur différent) :
on extrait uniquement le contenu des clauses `INSERT INTO ... VALUES (...);` avec un
petit analyseur dédié, puis on instancie les modèles SQLModel correspondants.
"""
import datetime as dt
import types
import typing
from functools import lru_cache
from pathlib import Path

from sqlmodel import Session, select

from . import models_shards as shards

# Les dumps sont à la racine du workspace, un niveau au-dessus de Shard-API/
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DUMP_FILES = {
    "s1": WORKSPACE_ROOT / "mbu-s1-2026-07-31_083120-dump.sql",
    "s2": WORKSPACE_ROOT / "mbu-tetrago-2026-07-31_083102-dump.sql",
}

# (clé du dump, nom de la table dans le dump, modèle SQLModel cible)
TABLE_SPECS = [
    # mbu-s1 -> préfixe s1-
    ("s1", "civilisations", shards.S1Civilisations),
    ("s1", "commerces", shards.S1Commerces),
    ("s1", "personnages", shards.S1Personnages),
    ("s1", "presses", shards.S1Presses),
    ("s1", "structures", shards.S1Structures),
    ("s1", "villes", shards.S1Villes),
    ("s1", "zones_commerciale", shards.S1ZonesCommerciale),
    # mbu-tetrago -> préfixe s2-
    ("s2", "_datapacks", shards.S2Datapacks),
    ("s2", "_mods", shards.S2Mods),
    ("s2", "_params", shards.S2Params),
    ("s2", "_plugins", shards.S2Plugins),
    ("s2", "_regles", shards.S2Regles),
    ("s2", "_saves", shards.S2Saves),
    ("s2", "_structures", shards.S2Structures),
    ("s2", "alliance_commerces", shards.S2AllianceCommerces),
    ("s2", "alliance_partisants", shards.S2AlliancePartisants),
    ("s2", "alliances", shards.S2Alliances),
    ("s2", "auth", shards.S2Auth),
    ("s2", "bibliotheque", shards.S2Bibliotheque),
    ("s2", "cartographie", shards.S2Cartographie),
    ("s2", "cartographie_quartiers", shards.S2CartographieQuartiers),
    ("s2", "civ_membres", shards.S2CivMembres),
    ("s2", "civilisations", shards.S2Civilisations),
    ("s2", "commerces", shards.S2Commerces),
    ("s2", "guerre_opposants", shards.S2GuerreOpposants),
    ("s2", "guerres", shards.S2Guerres),
    ("s2", "journaux", shards.S2Journaux),
    ("s2", "magasins", shards.S2Magasins),
    ("s2", "niveau_type", shards.S2NiveauType),
    ("s2", "niveau_villes", shards.S2NiveauVilles),
    ("s2", "perso_classes", shards.S2PersoClasses),
    ("s2", "perso_especes", shards.S2PersoEspeces),
    ("s2", "personnages", shards.S2Personnages),
    ("s2", "religions", shards.S2Religions),
    ("s2", "salons", shards.S2Salons),
    ("s2", "villes", shards.S2Villes),
    ("s2", "villes_quartiers", shards.S2VillesQuartiers),
    ("s2", "zones_commerciale", shards.S2ZonesCommerciale),
]

#region Parsing SQL brut

_MYSQL_ESCAPES = {
    "n": "\n", "r": "\r", "t": "\t", "0": "\0",
    "\\": "\\", "'": "'", '"': '"', "Z": "\x1a", "b": "\b",
}

def _convert_token(token: str, is_string: bool):
    """Convertit un token brut de la clause VALUES en valeur Python (str/int/float/None)."""
    if is_string:
        return token
    token = token.strip()
    if token == "NULL":
        return None
    if token.lstrip("-").isdigit():
        return int(token)
    try:
        return float(token)
    except ValueError:
        return token

def parse_values_clause(values_str: str) -> list[tuple]:
    """Parse une clause `(a,b,'c'),(d,e,'f')` en liste de tuples de valeurs Python."""
    rows: list[tuple] = []
    row: list = []
    buf: list[str] = []
    depth = 0
    in_string = False
    token_is_string = False
    i, n = 0, len(values_str)
    while i < n:
        ch = values_str[i]
        if in_string:
            if ch == "\\" and i + 1 < n:
                buf.append(_MYSQL_ESCAPES.get(values_str[i + 1], values_str[i + 1]))
                i += 2
                continue
            if ch == "'":
                if i + 1 < n and values_str[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                in_string = False
                i += 1
                continue
            buf.append(ch)
            i += 1
            continue

        if ch == "'":
            in_string = True
            token_is_string = True
            i += 1
            continue
        if ch == "(":
            depth += 1
            if depth == 1:
                row = []
                buf = []
                token_is_string = False
            else:
                buf.append(ch)
            i += 1
            continue
        if ch == ")":
            depth -= 1
            if depth == 0:
                row.append(_convert_token("".join(buf), token_is_string))
                rows.append(tuple(row))
            else:
                buf.append(ch)
            i += 1
            continue
        if ch == "," and depth == 1:
            row.append(_convert_token("".join(buf), token_is_string))
            buf = []
            token_is_string = False
            i += 1
            continue
        if depth >= 1:
            buf.append(ch)
        i += 1
    return rows

def extract_insert_values(sql_text: str, table_name: str) -> list[tuple]:
    """Trouve `INSERT INTO \\`table_name\\` VALUES ...;` et retourne les lignes parsées."""
    marker = f"INSERT INTO `{table_name}` VALUES "
    start = sql_text.find(marker)
    if start == -1:
        return []
    pos = start + len(marker)
    depth = 0
    in_string = False
    i, n = pos, len(sql_text)
    while i < n:
        ch = sql_text[i]
        if in_string:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == "'":
                if i + 1 < n and sql_text[i + 1] == "'":
                    i += 2
                    continue
                in_string = False
            i += 1
            continue
        if ch == "'":
            in_string = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == ";" and depth == 0:
            break
        i += 1
    return parse_values_clause(sql_text[pos:i])

@lru_cache(maxsize=None)
def _dump_text(shard_key: str) -> str:
    return DUMP_FILES[shard_key].read_text(encoding="utf-8")

#endregion
# -----------------------------------------------
#region Conversion / insertion

def _unwrap_optional(annotation):
    if typing.get_origin(annotation) in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        if args:
            return args[0]
    return annotation

def _coerce_value(annotation, value):
    if value is None:
        return None
    annotation = _unwrap_optional(annotation)
    if annotation is bool:
        return bool(value)
    if annotation is dt.date and isinstance(value, str):
        return dt.date.fromisoformat(value)
    return value

def import_all(db: Session) -> dict:
    """Importe chaque table du dump dans son modèle préfixé si la table est vide."""
    results = {}
    for shard_key, table_name, model_cls in TABLE_SPECS:
        label = model_cls.__tablename__
        if db.exec(select(model_cls)).first():
            results[label] = "déjà présent, import ignoré"
            continue

        rows = extract_insert_values(_dump_text(shard_key), table_name)
        if not rows:
            results[label] = "aucune donnée trouvée dans le dump"
            continue

        columns = list(model_cls.model_fields.keys())
        inserted = 0
        for row in rows:
            kwargs = {
                col: _coerce_value(model_cls.model_fields[col].annotation, value)
                for col, value in zip(columns, row)
            }
            db.add(model_cls(**kwargs))
            inserted += 1
        db.commit()
        results[label] = f"{inserted} lignes importées"
    return results

#endregion
