# Shard-API

> Documentation complète et à jour : [DOCUMENTATION.md](DOCUMENTATION.md), aussi servie sur `/documentation`.

API du serveur **Tetrago** : comptes utilisateurs, bibliothèque de récits et de journaux, civilisations, villes et
quartiers, religions, commerces, alliances, guerres, personnages, cartographie et statistiques du monde.
Elle est consommée par [ShardUI-2](../ShardUI-2) (le site) et [ShardUI-2-Maps](../ShardUI-2-Maps) (la carte).

## Stack technique

- [Python](https://www.python.org/) 3.10+ (le `.venv` actuel utilise 3.11)
- [FastAPI](https://fastapi.tiangolo.com/) — routes, validation, OpenAPI
- [SQLModel](https://sqlmodel.tiangolo.com/) (SQLAlchemy + Pydantic) sur **SQLite**
- [discord.py](https://discordpy.readthedocs.io/) — salons des journaux, annonces des guerres
- [Jinja2](https://jinja.palletsprojects.com/) pour les pages HTML servies (`templates/`)
- `httpx` (OAuth Discord et Microsoft), `urllib` (playerdb.co)

## Prérequis

- Python 3.10 ou plus
- `npm` (les scripts de lancement passent par `package.json`)
- `pm2` pour la production

## Installation

```bash
npm run init                                                   # crée .venv et installe requirements.txt
cp config.json.template config.json                            # puis renseigner les valeurs
cp config.development.json.template config.development.json    # facultatif, pour le développement
```

Depuis la racine de Shard-2, `npm run api:init` fait la même chose. Les scripts interactifs `start.sh` (Linux/macOS)
et `start.ps1` (Windows) proposent aussi de créer le venv, d'installer les dépendances et de lancer l'API.

## Configuration

`config.json` est toujours lu ; avec `API_ENV=development`, `config.development.json` est fusionné par-dessus
(objets fusionnés clé par clé). Aucun des deux n'est versionné : ils contiennent des secrets.

| Clé | Rôle |
| --- | --- |
| `api.mode`, `api.production`, `api.development` | Adresse et port d'écoute |
| `database.name` | Nom du fichier SQLite, sans `.db` (`ShardDB`, `ShardDB-dev` en développement) |
| `security.*` | Compte administrateur recréé ou mis à jour à chaque démarrage |
| `oauth2.discord.*`, `oauth2.microsoft.*` | Connexion et liaison des comptes externes |
| `platforms.discord.token`, `.guild_id`, `.site_url` | Bot Discord |
| `platforms.discord.channels.guerres` | Salon des annonces de guerre |
| `platforms.discord.categories.journaux` | Catégorie où sont créés les salons de journaux |
| `platforms.monde.key` | Clé partagée avec le générateur de cartes |

Le détail de chaque clé et les variables d'environnement (dont celles de simulation utilisées par les tests) sont
dans [DOCUMENTATION.md](DOCUMENTATION.md#configuration).

## Scripts disponibles

```bash
npm run init       # Crée .venv et installe les dépendances
npm run dev        # Développement : API_ENV=development, rechargement automatique
npm run verbose    # Comme dev, avec --log-level debug
npm run start      # Production : IP/port de api.production, config.json seul
npm run pm2:start  # Lance le processus pm2 « shard-api » (pm2:stop, pm2:restart, pm2:logs, pm2:delete)
```

## Structure du projet

```
Shard-API/
├── api/
│   ├── main.py            # Application, démarrage (lifespan), statiques, 404, inclusion des routeurs
│   ├── core/              # Configuration (utils.py), version, rendu HTML de la documentation
│   ├── db/                # database.py (moteur, vérification des tables), models.py, schemas.py
│   ├── services/          # Logique métier : crud.py, crud_conflits, crud_personnages, crud_monde, crud_nettoyage
│   ├── integrations/      # oauth.py (Discord, Microsoft), discord_handler.py (bot)
│   └── routes/            # Un routeur par domaine (+ _template.py comme point de départ)
├── templates/             # Pages Jinja2 (accueil, documentation, docs, redoc, 404)
├── assets/                # CSS et images
├── config.json(.template) # Configuration (non versionnée)
├── requirements.txt
├── start.sh / start.ps1   # Menus interactifs
└── ShardDB.db             # Base de production (non versionnée)
```

Pour ajouter un domaine : modèles dans `db/models.py`, corps de requête dans `db/schemas.py`, logique dans
`services/crud_<domaine>.py`, routeur copié depuis `routes/_template.py` puis inclus dans `main.py`.
Détail dans [DOCUMENTATION.md](DOCUMENTATION.md#ajouter-un-domaine).

## Points d'entrée

| Chemin | Contenu |
| --- | --- |
| `/api/...` | L'API (référence complète des routes dans la documentation) |
| `/documentation` | `DOCUMENTATION.md` rendu en HTML, relu dès que le fichier change |
| `/docs`, `/redoc`, `/openapi.json` | Swagger UI, ReDoc, schéma OpenAPI |
| `/api/version/` | `{ name, version, version_dev, version_short, hostname }` |

## Authentification

OAuth2 « password » avec des jetons opaques stockés en base : `POST /api/users/token` renvoie un `access_token`
à envoyer en `Authorization: Bearer <jeton>`. Les mots de passe sont stockés en **scrypt salé**. Une nouvelle
connexion invalide les jetons précédents du même utilisateur. Voir
[DOCUMENTATION.md](DOCUMENTATION.md#authentification-et-droits) pour les rôles et les dépendances FastAPI.

## Tests

Il n'y a pas de tests unitaires ici : les parcours de bout en bout sont couverts par les tests Playwright de
ShardUI-2 (`npm run test:ux`), qui lancent cette API sur une copie jetable de `ShardDB.db`.

## Déploiement

```bash
npm run pm2:start     # ou npm run start
```

La base `ShardDB.db` est sauvegardée automatiquement (`ShardDB.backup-<date>.db`) avant toute modification de
structure au démarrage.

## Projets liés

- [ShardUI-2](../ShardUI-2) — site web consommant cette API
- [ShardUI-2-Maps](../ShardUI-2-Maps) — application de cartographie

## Licence

Voir [LICENSE](LICENSE).
