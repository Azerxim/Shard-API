# Shard-API — Documentation

API du serveur Minecraft RP **Tetrago** (projet Shard-2). Elle stocke les comptes, la bibliothèque, les
civilisations, religions, commerces, alliances, guerres, personnages, la cartographie et les statistiques du monde.
Elle est utilisée par [ShardUI-2](../ShardUI-2) (le site) et [ShardUI-2-Maps](../ShardUI-2-Maps) (la carte).

Version actuelle : `2.0.15` (champ `version` de `package.json`, lu par `api/core/version.py`).

Ce document est aussi servi en HTML par l'API sur `/documentation`
(source brute sur `/documentation.md`).

## Sommaire

- [Vue d'ensemble](#vue-densemble)
- [Installation et lancement](#installation-et-lancement)
- [Configuration](#configuration)
- [Démarrage de l'API](#démarrage-de-lapi)
- [Authentification et droits](#authentification-et-droits)
- [Organisation du code](#organisation-du-code)
- [Modèle de données](#modèle-de-données)
- [Référence des routes](#référence-des-routes)
- [Règles métier](#règles-métier)
- [Intégrations externes](#intégrations-externes)
- [Tests](#tests)
- [Points d'attention](#points-dattention)

## Vue d'ensemble

| Élément | Choix |
| --- | --- |
| Langage | Python 3.10+ (le `.venv` actuel utilise 3.11) |
| Framework | FastAPI 0.128 |
| ORM | SQLModel 0.0.31 (SQLAlchemy + Pydantic) |
| Base de données | SQLite, fichier `<database.name>.db` à la racine (`ShardDB.db` en production) |
| Discord | `discord.py` 2.3.2 (salons des journaux, annonces des guerres) |
| HTTP sortant | `httpx` (OAuth), `urllib` (playerdb.co) |
| Pages HTML | Jinja2 (`templates/`) et fichiers statiques (`assets/`) |

```
             ┌────────────────────┐
 ShardUI-2 ──┤                    ├── Discord (bot, OAuth)
             │     Shard-API      ├── Microsoft / Xbox / Minecraft (OAuth)
 Maps ───────┤  FastAPI + SQLite  ├── playerdb.co (pseudos)
             │                    │
 Générateur ─┘ POST /api/monde/releves (clé X-Monde-Key)
 de cartes   └────────────────────┘
```

## Installation et lancement

Prérequis : Python 3.10 ou plus, `npm` (pour les scripts), `pm2` pour la production.

```bash
npm run init        # crée .venv et installe requirements.txt
cp config.json.template config.json                              # puis renseigner les valeurs
cp config.development.json.template config.development.json      # facultatif, pour le développement
```

Depuis la racine de Shard-2, `npm run api:init` fait la même chose.

Les scripts interactifs `start.sh` (Linux/macOS) et `start.ps1` (Windows) proposent aussi de créer le venv,
d'installer les dépendances et de lancer l'API.

### Scripts npm

| Commande | Effet |
| --- | --- |
| `npm run init` | Crée `.venv` et installe les dépendances |
| `npm run dev` | `API_ENV=development`, rechargement automatique, IP/port de `api.development` |
| `npm run verbose` | Comme `dev`, avec `--log-level debug` |
| `npm run start` | Production : IP/port de `api.production`, `config.json` seul |
| `npm run pm2:start` / `pm2:stop` / `pm2:restart` / `pm2:logs` / `pm2:delete` | Processus pm2 `shard-api` |

## Configuration

La configuration est lue par `api/core/utils.py` au chargement du module.

- `config.json` est toujours lu. S'il n'existe pas, il est créé à partir de `config.json.template`.
- Si `API_ENV=development` (`npm run dev`, `npm run verbose`), `config.development.json` est fusionné
  par-dessus : les objets sont fusionnés clé par clé, les autres valeurs sont remplacées.
- Les fichiers chargés sont affichés au démarrage (`Configuration: config.json + config.development.json`).

Aucun de ces deux fichiers n'est versionné : ils contiennent des secrets.

### Clés

| Clé | Rôle |
| --- | --- |
| `version` | Version du format de configuration |
| `api.name` | Nom affiché (titre OpenAPI, pages HTML) |
| `api.mode` | `production` ou `development` : choisit le bloc IP/port hors `API_ENV` |
| `api.production.ip` / `.port` | Adresse d'écoute en production (`0.0.0.0:8000`) |
| `api.development.ip` / `.port` | Adresse d'écoute en développement (`127.0.0.1:8001` dans la configuration actuelle) |
| `database.name` | Nom du fichier SQLite, sans `.db` (`ShardDB`, `ShardDB-dev` en développement) |
| `database.debug` | Affiche les requêtes SQL (`echo` SQLAlchemy) |
| `security.username` / `full_name` / `email` / `password` | Compte administrateur recréé ou mis à jour à chaque démarrage |
| `oauth2.client_id` / `client_secret` | Réservés (vérification désactivée dans `/api/users/token`) |
| `oauth2.discord.client_id` / `client_secret` / `redirect_uri` | Connexion et liaison Discord |
| `oauth2.microsoft.client_id` / `client_secret` / `redirect_uri` | Connexion et liaison Microsoft (profil Minecraft Java) |
| `platforms.local` | Plateforme par défaut (nom et clé) |
| `platforms.discord.token` | Jeton du bot Discord |
| `platforms.discord.guild_id` | Serveur Discord |
| `platforms.discord.site_url` | URL du site, pour les liens des annonces |
| `platforms.discord.channels.guerres` | Salon des annonces de guerre |
| `platforms.discord.channels.actions` | Salon des révélations d'actions secrètes (facultatif) |
| `platforms.discord.channels.marches` / `.fermes` | Salons des foires et des déclarations de fermes (facultatifs) |
| `platforms.discord.channels.lignees` | Salon des fondations de maisons nobles et des mariages (facultatif) |
| `platforms.discord.channels.evenements` | Salon des annonces du calendrier (facultatif) ; les événements programmés du serveur demandent au bot la permission « Gérer les événements » |
| `platforms.discord.categories.journaux` | Catégorie où `crud.create_journal` crée les salons de journaux (hors catégorie si absente) |
| `platforms.monde.key` | Clé partagée avec le générateur de cartes (`MAP_STATS_API_KEY` côté Maps) |

`oauth2.<fournisseur>.client_secret` doit être le *Client Secret* OAuth2 du fournisseur, pas le jeton du bot.
Chaque `redirect_uri` pointe vers la page `/auth/<fournisseur>/callback` de ShardUI-2 et doit être déclarée
chez le fournisseur (Discord Developer Portal, Azure).

### Variables d'environnement

| Variable | Rôle |
| --- | --- |
| `API_ENV` | `development` active `config.development.json` et le bloc `api.development` |
| `DISCORD_OAUTH_CLIENT_ID`, `DISCORD_OAUTH_CLIENT_SECRET`, `DISCORD_OAUTH_REDIRECT_URI` | Remplacent `oauth2.discord.*` |
| `DISCORD_API_BASE_URL` | Autre adresse pour l'API Discord (tests) |
| `MICROSOFT_OAUTH_CLIENT_ID`, `MICROSOFT_OAUTH_CLIENT_SECRET`, `MICROSOFT_OAUTH_REDIRECT_URI` | Remplacent `oauth2.microsoft.*` |
| `MICROSOFT_API_BASE_URL` | Remplace tous les services Microsoft, Xbox et Minecraft (tests) |
| `SHARD_MONDE_KEY` | Remplace `platforms.monde.key` |
| `SHARD_PLAYERDB_URL` | Autre service que playerdb.co pour les pseudos |
| `SHARD_FAKE_JOURNAL_MESSAGES` | Lit les messages des journaux dans ce fichier JSON au lieu de Discord |
| `SHARD_FAKE_DISCORD_ANNOUNCEMENTS` | Écrit les annonces dans ce fichier (une ligne JSON par annonce) au lieu de Discord |
| `SHARD_FAKE_DISCORD_EVENTS` | Écrit les opérations sur les événements programmés Discord (`create`, `edit`, `delete`) dans ce fichier |

## Démarrage de l'API

La fonction `lifespan` de `api/main.py` exécute, dans l'ordre :

1. `create_db_and_tables()` : crée les tables manquantes.
2. `migrate_commerces_owner_to_members()` : migration unique de l'ancienne colonne `commerces.owner_id` vers une
   ligne `Fondateur` dans `commercemembers` (sans effet une fois faite).
3. `check_database_tables()` : compare chaque table aux modèles, ajoute les colonnes manquantes et corrige une
   colonne dont le type ou la nullabilité diffère **en reconstruisant la table**, valeurs conservées (voir
   ci-dessous).
4. `crud.loadsecurity()` : crée ou met à jour le compte administrateur de `security` (admin, actif, masqué).
5. `crud_nettoyage.nettoyer_references_orphelines()` : corrige les références laissées par d'anciennes suppressions.
6. `crud_personnages.seed_referentiels()` : ajoute les espèces et classes de personnages par défaut.

#### Correction des colonnes incohérentes

Avant la **première** modification de structure d'un démarrage, `backup_database()` copie le fichier SQLite en
`<database.name>.backup-<AAAA-MM-JJ_hhmmss>.db`. Le chemin est rappelé à la fin de la vérification.

SQLite ne sait pas changer le type ni la nullabilité d'une colonne en place : `_rebuild_table()` recrée donc la
table d'après son modèle, y recopie les colonnes communes, supprime l'ancienne et renomme la nouvelle — la même
méthode que la migration des commerces. Si la copie échoue (une valeur `NULL` dans une colonne devenue `NOT NULL`,
par exemple), la transaction est annulée : **la table et ses données restent intactes** et un message indique la
correction à faire à la main.

> Les sauvegardes `*.backup-*.db` ne sont pas supprimées automatiquement : les purger de temps en temps.

### Pages servies

| Chemin | Contenu |
| --- | --- |
| `/` | Page d'accueil (`templates/landing.html`) |
| `/documentation` | Ce document rendu en HTML (`templates/documentation.html`), relu dès que `DOCUMENTATION.md` change |
| `/documentation.md` | Ce document au format Markdown |
| `/docs` | Swagger UI dans le gabarit du site |
| `/redoc` | ReDoc |
| `/openapi.json` | Schéma OpenAPI |
| `/assets/...` | Fichiers statiques |
| `/robots.txt`, `/sitemap.xml`, `/favicon_shard.ico` | Fichiers techniques |
| `/api/version/` | `{ name, version, version_dev, version_short, hostname }` |

Toute autre adresse renvoie une 404 : page HTML hors `/api`, JSON `{"detail": ...}` pour l'API.

CORS : toutes les origines, méthodes et en-têtes sont acceptés, sans cookies (`allow_credentials=False`).

## Authentification et droits

### Jetons

L'authentification suit le schéma OAuth2 « password » de FastAPI, avec des jetons opaques stockés en base.

1. `POST /api/users/token` (formulaire `username`, `password`, paramètre `expiry_hours`, 24 par défaut).
2. L'API vérifie le mot de passe, supprime les sessions précédentes de l'utilisateur et crée
   une `ActiveSession` avec un jeton aléatoire de 64 caractères hexadécimaux.
3. Réponse : `{ "access_token": "...", "token_type": "bearer" }`.
4. Les appels protégés envoient `Authorization: Bearer <jeton>`.

Une nouvelle connexion invalide donc les jetons précédents du même utilisateur (y compris celui de l'éditeur de carte,
qui en redemande un au site).

### Mots de passe

Les mots de passe sont stockés en **scrypt salé**, via `hashlib` (aucune dépendance externe). Le format en base est
`scrypt$<n>$<r>$<p>$<sel hex>$<clé hex>` ; les paramètres de coût sont les constantes `SCRYPT_*` de
`api/services/crud.py` (n = 2¹⁴, r = 8, p = 1, clé de 32 octets, sel de 16 octets).

`crud.verify_password` accepte aussi les empreintes de l'ancien schéma (SHA-256 sans sel, 64 caractères
hexadécimaux) et signale qu'elles doivent être renouvelées ; `crud.check_password` s'en charge alors dans la foulée.
Une empreinte héritée est donc remplacée par une empreinte scrypt **à la connexion suivante de son utilisateur**,
sans intervention ni migration de la base. Relever les paramètres de coût provoque le même renouvellement
progressif.

`POST /api/users/login` vérifie seulement les identifiants (par nom, par e-mail ou les deux) et renvoie le profil
dans `{ code, user }` ; il ne délivre pas de jeton. ShardUI-2 appelle `/login` puis `/token`.

### Dépendances FastAPI

| Dépendance (`api/services/crud.py`) | Exige |
| --- | --- |
| `secu_get_current_user` | Jeton valide et non expiré (sinon 401) |
| `secu_get_current_active_user` | Idem, et compte non désactivé (sinon 400) |
| `secu_get_current_active_admin` | Idem, et `is_admin` (sinon 403) |
| `secu_get_current_user_optional` | Rien : renvoie l'utilisateur si un jeton valide est fourni, sinon `None` |

`secu_get_current_user_optional` sert aux routes publiques dont la réponse dépend du demandeur : `/api/users/id/{id}`
et `/api/users/name/{username}` ne joignent l'e-mail du profil que pour son propriétaire ou un administrateur
(`crud.viewer_sees_private`). Les autres appelants reçoivent `email: null`.

### Rôles

| Rôle | Portée | Obtention |
| --- | --- | --- |
| Administrateur (`Users.is_admin`) | Tout le site | Compte `security` ou attribution par un administrateur |
| Modérateur RP (`Users.is_moderateur`) | Guerres, référentiels des personnages | Attribution par un administrateur |
| Fondateur | Une civilisation, religion ou un commerce | Création, puis transfert uniquement |
| Admin | Une civilisation, religion ou un commerce | Ajout ou modification par un Fondateur/Admin |
| Membre | Une civilisation, religion ou un commerce | Idem |
| Chef de file / Membre / Observateur | Une alliance (rôle d'une civilisation) | Création, invitation, transfert |

Règle générale : **agir au nom d'une entité demande d'en être Fondateur ou Admin, ou d'être administrateur du site.**
La même règle est appliquée côté site par `checkMemberAuth` (ShardUI-2), mais c'est l'API qui fait foi.

## Organisation du code

```
Shard-API/
├── api/
│   ├── main.py                  # Application, démarrage (lifespan), fichiers statiques, 404, inclusion des routeurs
│   ├── core/                    # Socle commun
│   │   ├── utils.py             # Lecture et fusion de la configuration, ROOT_DIR
│   │   ├── version.py           # Version, lue dans package.json
│   │   └── documentation.py     # Rendu HTML de DOCUMENTATION.md
│   ├── db/                      # Données
│   │   ├── database.py          # Moteur SQLite, session, création/vérification des tables, migration commerces
│   │   ├── models.py            # Tables SQLModel
│   │   └── schemas.py           # Corps de requête et réponses (Pydantic)
│   ├── services/                # Logique métier
│   │   ├── crud.py              # Sécurité, utilisateurs, bibliothèque, civilisations, villes, quartiers,
│   │   │                        # religions, commerces, magasins, dimensions, cartographie, annonces Discord
│   │   ├── crud_conflits.py     # Alliances et guerres
│   │   ├── crud_personnages.py  # Personnages, espèces, classes, messages attribués
│   │   ├── crud_monde.py        # Statistiques du monde
│   │   ├── crud_catalogue.py    # Catalogue des boutiques (articles, recherche « où acheter »)
│   │   ├── crud_marches.py      # Jours de marché des zones commerciales, foires des villes
│   │   ├── crud_fermes.py       # Déclaration des fermes, photo, validation
│   │   ├── crud_calendrier.py   # Calendrier des événements RP, inscriptions, événements Discord programmés
│   │   ├── crud_chroniques.py   # Chroniques : frise déduite des données, faits marquants
│   │   ├── crud_lignees.py      # Liens de parenté, maisons nobles et leur arbre
│   │   ├── crud_notifications.py # Notifications du site (cloche) : destinataires, envoi, lecture
│   │   ├── fichiers.py          # Images envoyées (./uploads) : format, taille, nom aléatoire
│   │   ├── crud_livres.py       # Liens des livres (religion, commerce, alliance, personnage)
│   │   └── crud_nettoyage.py    # Cohérence des suppressions et références orphelines
│   ├── integrations/            # Services externes
│   │   ├── oauth.py             # Discord et Microsoft (liaison et connexion)
│   │   └── discord_handler.py   # Bot Discord (salons, messages, événements programmés)
│   └── routes/                  # Routeurs FastAPI
│       ├── pages.py             # /, /documentation, /docs, /redoc, /api/version/, robots, sitemap, favicon
│       ├── users.py             # /api/users
│       ├── bibliotheque.py      # /api/bibliotheque
│       ├── civilisations.py     # /api/civilisations (+ gouvernements, villes, quartiers)
│       ├── religions.py         # /api/religions
│       ├── commerces.py         # /api/commerces (+ magasins)
│       ├── catalogue.py         # /api/catalogue
│       ├── marches.py           # /api/marches
│       ├── fermes.py            # /api/fermes
│       ├── calendrier.py        # /api/calendrier
│       ├── chroniques.py        # /api/chroniques
│       ├── lignees.py           # /api/lignees
│       ├── notifications.py     # /api/notifications
│       ├── alliances.py         # /api/alliances
│       ├── guerres.py           # /api/guerres
│       ├── personnages.py       # /api/personnages
│       ├── cartographie.py      # /api/cartographie (+ dimensions)
│       ├── monde.py             # /api/monde
│       └── _template.py         # Modèle vide pour un nouveau routeur (non inclus)
├── templates/                   # Pages Jinja2 (accueil, documentation, docs, redoc, 404, version)
├── assets/                      # CSS (dont documentation.css), images
├── DOCUMENTATION.md             # Ce document (servi sur /documentation)
├── config.json(.template)       # Configuration
├── config.development.json(.template)
├── requirements.txt
├── start.sh / start.ps1         # Menus interactifs
└── ShardDB.db                   # Base de production (non versionnée)
```

### Ajouter un domaine

1. Déclarer les tables dans `db/models.py` (elles sont créées au démarrage suivant).
2. Déclarer les corps de requête dans `db/schemas.py`.
3. Écrire la logique dans un module `services/crud_<domaine>.py` : lever des `HTTPException` avec un message en français,
   lisible tel quel par le site.
4. Créer `routes/<domaine>.py` à partir de `routes/_template.py` et l'inclure dans `main.py`.
5. Si des entités en référencent d'autres, compléter `services/crud_nettoyage.py`.

Les imports restent relatifs : depuis un sous-paquet, `from ..db import models, schemas`,
`from ..services import crud`, `from ..core import utils`.

## Modèle de données

Toutes les tables ont une clé `id` entière. Les dates de création sont remplies par l'API.

### Comptes

| Table | Contenu |
| --- | --- |
| `users` | `username` et `email` uniques, `hashed_password` (scrypt salé, voir [Mots de passe](#mots-de-passe)), `full_name`, `image_url`, `arrival`, `is_disabled`, `is_admin`, `is_moderateur`, `is_visible` (profil public) |
| `userplatforms` | Compte externe lié : `platform` (`discord`, `microsoft`), `uid`, `username`, `avatar_url`. Un par plateforme et par utilisateur ; un compte externe n'appartient qu'à un utilisateur |
| `oauthstates` | Paramètre `state` d'une autorisation en cours (usage unique, 10 minutes), `mode` `login` ou `link` |
| `activesession` | Jeton d'accès, utilisateur, date d'expiration |
| `notifications` | Notification du site : `user_id` (destinataire), `type`, `title`, `text`, `link` (chemin du site), `created_at`, `read_at` (vide tant qu'elle n'est pas lue) |

### Bibliothèque

| Table | Contenu |
| --- | --- |
| `journaux` | Journal RP adossé à un salon Discord (`uid` = identifiant du salon), couverture (`cover_url`, `cover_icon`, `cover_color`), `link` (`/bibliotheque/journal/<id>`), `is_public` |
| `livres` | Livre : auteur, couverture, `pages`, `language`, `is_public` (ses civilisations et autres liens : `livresliens`) |
| `livresliens` | Lien d'un livre avec une civilisation, une religion, un commerce, une alliance ou un personnage : `livre_id`, `entity_type`, `entity_id` (plusieurs par livre). Remplace l'ancienne colonne `livres.civilisation_id`, reprise au démarrage par `migrate_livres_civilisation_to_liens` |
| `livrescontenus` | Contenu d'un livre : `chapitre`, `sous_chapitre`, `ordre`, `indent`, `content`, `page_number` |

### Géopolitique

| Table | Contenu |
| --- | --- |
| `civilisations` | `title`, `description`, `date_founded`, `gouvernement_id`, `is_public`, vassalité (`is_civilisation_dirigeante`, `dirigeante_civilisation_id`) |
| `civilisationmembers` | `user_id`, `civilisation_id`, `role` (Fondateur, Admin, Membre) |
| `gouvernements` | `title`, `type`, `description`, `devise`, `hymne`, `civilisation_id` |
| `villes` | `title`, `population`, `founded_date`, `dimension_id`, `x`, `z`, `is_public`, `is_capital`, `civilisation_id` |
| `quartiers` | `title`, `population`, `x`, `z`, `is_public`, `ville_id` |
| `religions` | `title`, `color`, `icon` (FontAwesome), `is_public` |
| `religionmembers` | Membres d'une religion (mêmes rôles) |
| `villesreligions` / `quartiersreligions` | Présence d'une religion et `influence` (nombre décimal) |
| `commerces` | `title`, `is_public`, filiale (`is_commerce_dirigeant`, `dirigeant_commerce_id`) |
| `commercemembers` | Membres d'un commerce (mêmes rôles) |
| `commercemagasins` | Magasin : `dimension_id`, `x`, `z`, `ville_id`, `is_siege`, `is_public` |
| `magasinarticles` | Article du catalogue d'un magasin : `title`, `categorie`, `description`, `prix` (tetras, pour le lot), `quantite` (taille du lot), `en_stock` |
| `marchejours` | Jours d'ouverture d'une zone commerciale : `cartographie_id` (unique), `jours` (« 2,5 », 0 = lundi), `horaires` |
| `foires` | Foire d'une ville : `ville_id`, `title`, `date_debut`, `date_fin` (dates réelles), `horaires`, `zone_id`, position (`dimension_id`, `x`, `z`) |
| `fermes` | Ferme déclarée : `user_id`, `title`, `type`, `production`, `justification`, `habillage`, position, `ville_id`, `photo`, `status` (`en_attente`, `validee`, `a_corriger`), décision du modérateur |

### Alliances et guerres

| Table | Contenu |
| --- | --- |
| `alliances` | `title`, `type` (`Militaire`, `Diplomatique`), `color`, `icon`, `flag_url`, `is_public` |
| `alliancemembres` | Civilisation membre et `role` (`Chef de file`, `Membre`, `Observateur`) |
| `allianceinvitations` | `direction` (invitation de l'alliance ou demande de la civilisation), `status` (`en_attente`, …), `created_by`, `answered_at` |
| `guerres` | `title`, `type` (`Militaire`, `Religion`), `casus_belli`, `status` (`en_attente`, `en_cours`, `terminee`, `refusee`), `issue`, `moderation_note`, dates RP et techniques, `declared_by`, `moderator_id` |
| `guerrebelligerants` | `camp` (`attaquant`, `defenseur`), `entity_type` (`civilisation`, `religion`), `entity_id`, `entity_title` (nom archivé), `is_leader`, `status` (`appele`, `engage`), `alliance_id` |
| `guerreevenements` | Chronologie : `type` (`declaration`, `validation`, `refus`, `ralliement`, `retrait`, `fin`, `bataille`, `siege`, `traite`, `autre`), `camp`, `date_rp`, `is_auto` |

### Calendrier et chroniques

| Table | Contenu |
| --- | --- |
| `evenements` | Événement RP : `title`, `type` (`bataille`, `fete`, `couronnement`, `ceremonie`, `tournoi`, `conseil`, `autre`), `date_debut`, `date_fin` (heures réelles), `lieu`, `ville_id`, organisateur (`organisateur_type` : `joueur`, `civilisation`, `religion`, `commerce`, `alliance` ; `organisateur_id`, `organisateur_title` archivé), `guerre_id`, `places`, `status` (`prevu`, `annule`), `motif_annulation`, `discord_event_id`, `created_by` |
| `evenementinscriptions` | Inscription d'un joueur (`user_id`) à un événement, avec `personnage_id` facultatif |
| `chroniquesfaits` | Fait marquant inscrit par un modérateur RP : `title`, `description`, `date_rp` (place le fait dans la frise), `date` (jour réel de l'inscription) |

### Personnages

| Table | Contenu |
| --- | --- |
| `personnageespeces` / `personnageclasses` | Référentiels (`title`, `description`) |
| `personnages` | `user_id`, `name` (80 car.), `status` (`vivant`, `mort`, `disparu`), `espece_id`, `classe_id`, `grade`, portrait (`image_url` ou `image_fichier`, prioritaire), skin (`skin_source` : `aucun`, `minecraft`, `lien`, `fichier` ; `skin_url`, `skin_fichier`, `minecraft_uuid`), dates de naissance et de décès, résidence (`civilisation_id`, `ville_id`, `quartier_id`), `maison_id` |
| `maisons` | Maison noble : `title`, `devise`, `description`, blason (`couleur`, `icon`), `civilisation_id`, `chef_id` (personnage, sans clé étrangère : `personnages.maison_id` référence déjà la table), `date_fondation` (RP), `created_by` |
| `personnageliens` | Lien de parenté : `type` (`parent` : source parent de cible ; `conjoint` ; `heritier` : cible hérite de source), `source_id`, `cible_id`, `rang` (héritier), `date_rp`, `status` (`en_attente`, `accepte`), `en_attente_de` (personnage dont le joueur doit accepter), `demande_par` |
| `personnagemessages` | Message Discord d'un journal attribué à un personnage : `message_id`, `author_uid`, `excerpt` (280 car.), `message_timestamp` |

### Carte

| Table | Contenu |
| --- | --- |
| `dimensions` | `title`, `link` (nom de la carte dans ShardUI-2-Maps, ex. `tetrago`), `description` |
| `cartographie` | Forme sur la carte : `type` (`civilisation`, `ville`, `quartier`, `guerre`), `type_id`, `dimension_id`, `shape_type`, `coordinates` (JSON, format Leaflet `[-z, x]`), `color`, `text` |

### Statistiques du monde

| Table | Contenu |
| --- | --- |
| `mondereleves` | Un relevé : monde, durée, taille, totaux (chunks, heures de présence, lits, villageois, entités, joueurs) et seuils utilisés |
| `mondedimensionsstats` | Totaux par dimension |
| `mondelieux` | Mesure par civilisation, ville ou quartier : `methode` (frontières ou rayon), `population`, `population_declaree` (valeur avant le relevé), `personnages` domiciliés, joueurs présents |
| `mondezones` | Zones les plus fréquentées et lieu déclaré le plus proche |
| `mondejoueurs` | Joueur par UUID : pseudo, `user_id` lié, temps de jeu, morts, distance, dernière position, lit, lieu |

Les 104 derniers relevés sont conservés (deux ans à raison d'un par semaine).

## Référence des routes

Légende des droits : **—** public ; **U** utilisateur connecté ; **A** administrateur ; **règle** : voir
[Règles métier](#règles-métier). Le détail des corps de requête est visible sur `/docs`.

Les réponses n'ont pas toutes le même format : selon les routes, le statut est dans `code` ou `error`
(avec la valeur HTTP : 200, 404…), ou seule l'erreur HTTP est levée avec `detail`.

### Utilisateurs — `/api/users`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| POST | `/create` | — | Inscription (`username`, `email`, `password`) ; nom et e-mail uniques |
| PUT | `/update/{user_id}` | U (soi-même ou A) | Modifie un profil ; seul un administrateur change `is_admin` / `is_moderateur` |
| DELETE | `/delete/{user_id}` | U (soi-même ou A) | Refusé tant que l'utilisateur est fondateur d'une entité |
| GET | `/name/{username}` | — | Profil par nom ; e-mail seulement pour lui-même ou un administrateur |
| GET | `/id/{user_id}` | — | Profil par identifiant ; e-mail seulement pour lui-même ou un administrateur |
| GET | `/list` | A | Liste des utilisateurs, e-mails compris |
| POST | `/login` | — | Vérifie les identifiants, renvoie `{ code, user }` |
| POST | `/token` | — | Délivre un jeton (formulaire OAuth2) |
| GET | `/me` | U | Profil de l'utilisateur connecté |
| GET | `/verify` | U | `{ valid: true, user }` |
| GET | `/oauth/providers` | — | `[{ provider, label, enabled }]` |
| GET | `/oauth/{provider}/login` | — | `{ url }` d'autorisation pour se connecter |
| GET | `/oauth/{provider}/link` | U | `{ url }` d'autorisation pour lier un compte |
| GET | `/oauth/{provider}/callback?code=&state=` | — | Termine l'autorisation : `{ mode: "login", access_token, user }` ou `{ mode: "link", platform }` |
| GET | `/platforms` | U | Comptes liés de l'utilisateur |
| DELETE | `/platforms/{provider}` | U | Délie un compte |
| GET | `/id/{user_id}/platforms` | — | Comptes publics (Microsoft uniquement) d'un profil visible |

### Bibliothèque — `/api/bibliotheque`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| POST | `/journaux/create` | U | Crée le journal **et** son salon Discord |
| POST | `/journaux/create/db` | U | Crée le journal en base seulement (salon existant, `uid` fourni) |
| PUT | `/journaux/update/{JournalID}` | Auteur ou A | Met à jour (renomme aussi le salon et change sa description) |
| DELETE | `/journaux/delete/{JournalID}` | Auteur ou A | Supprime le journal, son salon Discord et ses attributions de messages |
| GET | `/journaux/list` | — | Liste (`skip`, `limit`) |
| GET | `/journaux/read/{JournalID}` | — | Détail |
| GET | `/journaux/user/{UserID}/list` | — | Journaux d'un utilisateur |
| GET | `/journaux/contents/{JournalID}` | — | Messages du salon Discord |
| POST | `/livres/create` | U (F/A de la civilisation si `civilisation_id`) | Crée un livre ; `civilisation_id` crée aussitôt le lien (ignoré à la mise à jour) |
| PUT | `/livres/update/{livreID}` | règle livre | Met à jour |
| DELETE | `/livres/delete/{livreID}` | règle livre | Supprime, avec ses chapitres et ses liens |
| GET | `/livres/list` | — | Liste |
| GET | `/livres/read/{livreID}` | — | Détail |
| GET | `/livres/user/{userID}/list` | — | Livres d'un utilisateur |
| GET | `/livres/civilisation/{civilisationID}/list` | — | Livres liés à une civilisation |
| GET | `/livres/liens/{livreID}` | — | Religions, commerces, alliances et personnages liés : `[{ id, livre_id, entite }]` |
| GET | `/livres/entite/{EntityType}/{EntityID}/list` | — | Livres liés à une entité : `[{ lien_id, livre }]` |
| POST | `/livres/liens` | règle livre + droits sur l'entité | `{ livre_id, entity_type, entity_id }` (civilisation, religion, commerce, alliance, personnage) |
| DELETE | `/livres/liens/{lienID}` | règle livre ou droits sur l'entité | Retire le lien |
| POST | `/livres/content/create` | règle livre | Ajoute un contenu |
| PUT | `/livres/content/update/{contenuID}` | règle livre | Modifie un contenu |
| DELETE | `/livres/content/delete/{contenuID}` | règle livre | Supprime un contenu |

Règle livre : son auteur, le Fondateur ou un Admin de l'une des civilisations liées, ou un administrateur. Les autres
liens (religion, commerce, alliance, personnage) ne donnent aucun droit sur le livre.
L'administrateur du site a toujours accès.

| GET | `/livres/contents/read/{livreID}` | — | `{ livre, contents }` |
| GET | `/livres/content/read/{contenuID}` | — | Un contenu |

### Civilisations — `/api/civilisations`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| GET | `/list` | — | Civilisations avec membres, gouvernement et villes |
| GET | `/read/{CivilisationID}` | — | `{ civilisation, members, gouvernement, villes }` |
| GET | `/get/{CivilisationID}/dirigees` | — | Civilisations vassales |
| POST | `/create` | U | Crée la civilisation, son gouvernement et le créateur comme Fondateur |
| PUT | `/update/{CivilisationID}` | Fondateur/Admin | Met à jour |
| DELETE | `/delete/{CivilisationID}` | Fondateur/Admin | Supprime avec ses dépendances (voir [cohérence](#cohérence-des-suppressions)) |
| GET | `/members/{CivilisationID}/list` | — | `[{ user_id, role, joined_at, username }]` |
| GET | `/members/{CivilisationID}/{MemberID}/read` | — | Un membre |
| POST | `/members/{CivilisationID}/add` | Fondateur/Admin | Ajoute un membre (`Admin` ou `Membre`) |
| PUT | `/members/{CivilisationID}/{MemberID}/update` | Fondateur/Admin | Change le rôle |
| DELETE | `/members/{CivilisationID}/remove?member_id=` | Fondateur/Admin | Retire un membre |
| PUT | `/members/{CivilisationID}/transfer` | Fondateur/A | Transfère le rôle de Fondateur (`user_id`, `former_role`) |
| GET | `/gouvernement/list` | — | Gouvernements |
| GET | `/gouvernement/read/{GouvernementID}` | — | Un gouvernement |
| POST | `/gouvernement/create` | Fondateur/Admin | Crée |
| PUT | `/gouvernement/update/{GouvernementID}` | Fondateur/Admin | Met à jour |
| DELETE | `/gouvernement/delete?GouvernementID=` | Fondateur/Admin | Supprime |
| GET | `/villes/list` | — | Villes |
| GET | `/villes/id/{VilleID}` | — | Une ville |
| POST | `/villes/create` | Fondateur/Admin | Crée une ville |
| PUT | `/villes/update/{VilleID}` | Fondateur/Admin | Met à jour |
| DELETE | `/villes/delete?VilleID=` | Fondateur/Admin | Supprime avec ses quartiers |
| GET | `/quartiers/list` | — | Quartiers |
| GET | `/quartiers/id/{QuartierID}` | — | Un quartier |
| GET | `/quartiers/read/{QuartierID}` | — | Quartier, ville et religions |
| GET | `/quartiers/ville/{VilleID}` | — | Quartiers d'une ville |
| POST | `/quartiers/create` | Fondateur/Admin | Crée |
| PUT | `/quartiers/update/{QuartierID}` | Fondateur/Admin | Met à jour |
| DELETE | `/quartiers/delete?QuartierID=` | Fondateur/Admin | Supprime |

### Religions — `/api/religions`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| GET | `/list` | — | Religions avec membres, villes et quartiers |
| GET | `/id/{ReligionID}` | — | `{ religion: {...} }` |
| GET | `/read/{ReligionID}` | — | `{ religion, members, villes, quartiers }` |
| POST | `/create` | U | Crée ; le créateur devient Fondateur |
| PUT | `/update/{ReligionID}` | Fondateur/Admin | Met à jour |
| DELETE | `/delete/{ReligionID}` | Fondateur/Admin | Supprime |
| GET | `/members/{ReligionID}/list` | — | Membres |
| GET | `/members/{ReligionID}/{MemberID}/read` | — | Un membre |
| POST | `/members/{ReligionID}/add` | Fondateur/Admin | Ajoute |
| PUT | `/members/{ReligionID}/{MemberID}/update` | Fondateur/Admin | Change le rôle |
| DELETE | `/members/{ReligionID}/remove?member_id=` | Fondateur/Admin | Retire |
| PUT | `/members/{ReligionID}/transfer` | Fondateur/A | Transfère le rôle de Fondateur |
| GET | `/ville/{VilleID}` | — | Religions d'une ville |
| GET | `/ville/{VilleID}/read/{ReligionID}` | — | Présence d'une religion dans une ville |
| POST | `/ville/{VilleID}/add` | civ. de la ville | Ajoute une religion (`ReligionID`, `influence`) |
| PUT | `/ville/{VilleID}/update/influence` | civ. de la ville | Change l'influence |
| DELETE | `/ville/{VilleID}/delete/{religionID}` | civ. de la ville | Retire la religion |
| GET | `/quartier/{QuartierID}` | — | Religions d'un quartier |
| POST | `/quartier/{QuartierID}/add` | civ. de la ville | Ajoute |
| PUT | `/quartier/{QuartierID}/update/influence` | civ. de la ville | Change l'influence |
| DELETE | `/quartier/{QuartierID}/delete/{religionID}` | civ. de la ville | Retire |

« civ. de la ville » : Fondateur/Admin de la civilisation à laquelle appartient la ville (ou la ville du quartier),
ou administrateur du site. La religion elle-même n'a pas à donner son accord.


### Commerces — `/api/commerces`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| GET | `/list` | — | Commerces complets |
| GET | `/id/{CommerceID}` | — | Le commerce seul |
| GET | `/read/{CommerceID}` | — | Commerce, membres, magasins, `dirigeant` et `diriges` |
| GET | `/get/{CommerceID}/diriges` | — | Filiales |
| GET | `/user/{UserID}` | — | Commerces dont l'utilisateur est membre |
| POST | `/create` | U | Crée ; le créateur devient Fondateur |
| PUT | `/update/{CommerceID}` | Fondateur/Admin | Met à jour |
| DELETE | `/delete/{CommerceID}` | Fondateur/Admin | Supprime avec ses magasins |
| GET / POST / PUT / DELETE | `/members/...` | comme les religions | Membres et transfert |
| GET | `/magasins/list` | — | Magasins |
| GET | `/magasins/id/{MagasinID}` | — | Un magasin |
| GET | `/magasins/commerce/{CommerceID}` | — | Magasins d'un commerce |
| GET | `/magasins/ville/{VilleID}` | — | Magasins d'une ville |
| POST | `/magasins/create` | Fondateur/Admin | Crée |
| PUT | `/magasins/update/{MagasinID}` | Fondateur/Admin | Met à jour |
| DELETE | `/magasins/delete/{MagasinID}` | Fondateur/Admin | Supprime, avec son catalogue |

### Catalogue — `/api/catalogue`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| GET | `/magasin/{MagasinID}` | — | Articles du magasin : `{ id, title, categorie, description, prix, quantite, prix_unitaire, en_stock, updated_at }` |
| GET | `/recherche?q=&categorie=&ville_id=&en_stock=` | — | Où acheter : `{ total, resultats }` (200 au plus), chaque article avec `magasin`, `commerce`, `ville`, `dimension` |
| POST | `/articles` | Fondateur/Admin du commerce | Ajoute `{ magasin_id, title, categorie?, description?, prix, quantite?, en_stock? }` |
| PUT | `/articles/{ArticleID}` | Fondateur/Admin du commerce | Met à jour (champs envoyés seulement) |
| DELETE | `/articles/{ArticleID}` | Fondateur/Admin du commerce | Retire l'article |

Un article est vendu par lot (« 16 flèches pour 1 tetra ») : `prix` entier ≥ 0 (0 : offert), `quantite` ≥ 1. Catégories :
`construction`, `ressources`, `outils`, `armes`, `nourriture`, `alchimie`, `services`, `divers` (défaut), reprises par
le site dans `src/config/catalogue.js`. La recherche exige un texte ou une catégorie ; elle ne parcourt que les
magasins publics des commerces publics, ignore la casse et les accents (filtre en Python, `LIKE` de SQLite ne le fait
pas), et classe les articles en stock d'abord, puis du moins cher au plus cher à l'unité (`prix / quantite`).

### Alliances — `/api/alliances`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| GET | `/list` | — | `[{ alliance, membres, chef_de_file }]` |
| GET | `/read/{AllianceID}` | — | Avec invitations en attente et guerres publiques des membres |
| GET | `/civilisation/{CivilisationID}` | — | Alliances d'une civilisation |
| POST | `/create` | Fondateur/Admin de la civilisation fondatrice | Fonde l'alliance ; la civilisation devient chef de file |
| PUT | `/update/{AllianceID}` | Chef de file | Met à jour |
| DELETE | `/delete/{AllianceID}` | Chef de file | Dissout |
| GET | `/invitations/mine` | U | Invitations et demandes auxquelles l'utilisateur peut répondre |
| POST | `/{AllianceID}/invitations` | Chef de file | Invite une civilisation (`civilisation_id`) |
| POST | `/{AllianceID}/demandes` | Fondateur/Admin de la civilisation | Demande à entrer |
| PUT | `/invitations/{InvitationID}/repondre` | L'autre partie | `{ accepter: bool }` |
| DELETE | `/invitations/{InvitationID}` | L'une ou l'autre partie | Annule une invitation ou une demande en attente |
| PUT | `/{AllianceID}/membres/{CivilisationID}` | Chef de file | Change le rôle (`Membre`, `Observateur`) |
| PUT | `/{AllianceID}/transfert` | Chef de file | Transfère le rôle de chef de file |
| DELETE | `/{AllianceID}/membres/{CivilisationID}` | Chef de file ou la civilisation | Retire ou quitte (le chef de file doit d'abord transférer son rôle) |

### Guerres — `/api/guerres`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| GET | `/list` | — | Guerres publiques (`en_cours`, `terminee`) |
| GET | `/read/{GuerreID}` | — | Guerre publique ; 404 pour une déclaration non validée |
| GET | `/prive/{GuerreID}` | U concerné ou modérateur | Même réponse, y compris non validée |
| GET | `/entite/{EntityType}/{EntityID}` | — | Guerres d'une civilisation ou religion |
| GET | `/cibles/{GuerreID}` | — | Guerre publique : destructibles des villes publiques des belligérants engagés, `{ attaquant, defenseur }` → `[{ entite, villes: [{ …, destructibles }] }]` (religion : villes où elle est implantée) |
| GET | `/mine` | U | `{ a_valider, mes_guerres, appels }` |
| POST | `/declarer` | Fondateur/Admin de l'attaquant | Déclaration (`title`, `type`, `attaquant_id`, `defenseur_id`, `casus_belli`, `description`) |
| PUT | `/update/{GuerreID}` | Attaquant avant validation, ou modérateur | Modifie |
| PUT | `/{GuerreID}/valider` | Modérateur RP | Commence la guerre (`date_debut`, `note`) |
| PUT | `/{GuerreID}/refuser` | Modérateur RP | Refuse (`note`) |
| PUT | `/{GuerreID}/terminer` | Modérateur RP | Termine (`issue` obligatoire, `date_fin`) |
| DELETE | `/delete/{GuerreID}` | Attaquant ou modérateur | Retire une déclaration en attente ou refusée |
| POST | `/{GuerreID}/appels` | Chef de camp | Appel aux armes d'une civilisation ou d'une alliance (`camp`, `civilisation_id` ou `alliance_id`) |
| PUT | `/{GuerreID}/appels/{BelligerantID}/repondre` | Fondateur/Admin de l'appelé | `{ accepter: bool }` |
| DELETE | `/{GuerreID}/belligerants/{BelligerantID}` | L'allié ou son chef de camp | Retrait d'un allié |
| POST | `/{GuerreID}/evenements` | Chef de camp (guerre en cours) ou modérateur | Ajoute une bataille, un siège, un traité ou un autre fait |
| DELETE | `/{GuerreID}/evenements/{EvenementID}` | Auteur (guerre en cours) ou modérateur | Retire un fait raconté |
| GET | `/{GuerreID}/troupes` | — (jeton facultatif) | `{ champs, camps_visibles, troupes: { attaquant, defenseur }, levees }` : un camp caché vaut `null` (visible de ses belligérants engagés et des modérateurs, de tous une fois la guerre terminée) ; `levees` : villes que l'utilisateur peut mobiliser (`armee`, `mobilises`, `disponibles`) |
| POST | `/{GuerreID}/troupes` | Fondateur/Admin d'une civilisation engagée (guerre en cours) | Lève une troupe dans une de ses villes (`ville_id`, `title`, `effectif`, `position` : `champ_de_bataille` avec `zone_id`, ou `en_mouvement` avec destination facultative) ; un soldat pour dix habitants, guerres en cours confondues |
| PUT | `/{GuerreID}/troupes/{TroupeID}` | Sa civilisation ou modérateur | Nom, pertes ou renforts (`title`, `effectif`) |
| PUT | `/{GuerreID}/troupes/{TroupeID}/deplacer` | Sa civilisation ou modérateur | Nouvelle position (`position`, `zone_id`, `secret`) ; public : inscrit dans la chronologie (type `deplacement`) |
| POST | `/{GuerreID}/mercenaires` | Fondateur/Admin d'un belligérant engagé (guerre en cours) | Engage une compagnie disponible (`mercenaire_id`, `employeur_type`, `employeur_id`, `position`, `zone_id`) : troupe de son camp, sa civilisation n'entre pas dans la guerre |
| PUT | `/{GuerreID}/troupes/{TroupeID}/demobiliser` | Sa civilisation ou modérateur | Démobilise (archivée, soldats rendus à la ville) ; aussi au retrait de la civilisation et à la fin de la guerre |

### Mercenaires — `/api/mercenaires`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| GET | `/list` | — | Marché : compagnies disponibles ou sous contrat des civilisations publiques (sans dire où elles servent) |
| GET | `/civilisation/{CivilisationID}` | — (jeton facultatif) | `{ compagnies, gere, villes }` ; `contrat` (guerre, troupe) et soldats disponibles des villes pour ses dirigeants et les modérateurs |
| POST | `/create` | Fondateur/Admin de la civilisation de la ville | Déclare une compagnie (`ville_id`, `title`, `effectif`, `tarif`, `description`) ; effectif pris sur l'armée autorisée de la ville |
| PUT | `/{MercenaireID}` | Idem, compagnie disponible | Modifie |
| PUT | `/{MercenaireID}/rompre` | Idem, ou modérateur | Rompt le contrat : la troupe est démobilisée, la compagnie revient disponible |
| DELETE | `/{MercenaireID}` | Idem, compagnie disponible | Dissout (soldats rendus à la ville) |

### Modération — `/api/moderation`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| GET | `/tableau` | Modérateur RP | `{ a_traiter: { guerres, ajustements, fermes, pieges }, suivi: { guerres, fermes, actions_scellees }, historique }` ; `propre` marque une demande ou un piège du modérateur lui-même ; historique : 200 dernières décisions et lectures tracées |

### Notifications — `/api/notifications`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| GET | `/mine?limite=30` | U | `{ non_lues, notifications: [{ id, type, title, text, link, created_at, lue }] }`, plus récentes d'abord (200 au plus) ; purge au passage les notifications lues depuis plus de 30 jours |
| PUT | `/lue/{NotificationID}` | Destinataire (404 sinon) | Marque une notification comme lue |
| PUT | `/lues` | U | Marque toutes ses notifications comme lues |

### Personnages — `/api/personnages`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| GET | `/list` | — | `[{ personnage, joueur, civilisation, ville, quartier, espece, classe, messages_count }]` |
| GET | `/read/{PersonnageID}` | — | Fiche et messages attribués |
| GET | `/user/{UserID}` | — | Personnages d'un joueur |
| GET | `/residence/{Residence}/{ID}` | — | Habitants d'une civilisation, ville ou quartier |
| GET | `/habitants/{Residence}` | — | `{ id du lieu: nombre }` (popups de la carte) |
| POST | `/create` | U | Crée un personnage |
| PUT | `/update/{PersonnageID}` | Propriétaire ou A | Met à jour |
| DELETE | `/delete/{PersonnageID}` | Propriétaire ou A | Supprime, avec ses fichiers |
| POST | `/portrait/{PersonnageID}` | Propriétaire ou A | Multipart, champ `image` : PNG, JPEG ou WebP, 5 Mo au plus ; remplace le lien |
| DELETE | `/portrait/{PersonnageID}` | Propriétaire ou A | Retire le portrait envoyé |
| POST | `/skin/{PersonnageID}` | Propriétaire ou A | Multipart, champ `skin` : PNG 64 × 64 ou 64 × 32, 1 Mo au plus ; source « fichier » |
| GET | `/fichier/{Nom}` | — | Portrait ou skin envoyé (nom aléatoire) |
| GET | `/referentiel` | — | `{ especes, classes }` |
| POST | `/referentiel/{Kind}` | A ou modérateur RP | Ajoute (`Kind` : `especes` ou `classes`) |
| PUT | `/referentiel/{Kind}/{ID}` | A ou modérateur RP | Modifie |
| DELETE | `/referentiel/{Kind}/{ID}` | A ou modérateur RP | Supprime |
| GET | `/journal/{JournalID}` | — | Attributions des messages d'un journal |
| POST | `/messages` | Auteur Discord du message | Attribue un message à l'un de ses personnages |
| DELETE | `/messages/{LienID}` | Auteur du message, joueur du personnage ou A | Retire l'attribution |

### Cartographie — `/api/cartographie`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| GET | `/list` | — | Formes (`skip`, `limit`) |
| GET | `/id/{CartographieID}` | — | Une forme |
| GET | `/entity/{Type}/{TypeID}` | — | Formes d'une entité |
| GET | `/types` | — | `["civilisation", "ville", "quartier", "guerre", "destructible", "commerciale"]` |
| POST | `/create` | règle | Crée (`coordinates` doit être du JSON valide, `dimension_id` doit exister) |
| PUT | `/update/{CartographieID}` | règle | Met à jour ; changer d'entité exige aussi les droits sur la nouvelle |
| DELETE | `/delete/{CartographieID}` | règle | Supprime |
| GET | `/dimensions/read` | — | Dimensions |
| GET | `/dimensions/id/{DimensionID}` | — | Une dimension |
| GET | `/dimensions/title/{DimensionTitle}` | — | Par nom |
| POST | `/dimensions/create` | A | Crée |
| PUT | `/dimensions/update` | A | Met à jour (`id` dans le corps) |
| DELETE | `/dimensions/delete?DimensionID=` | A | Supprime |

Droits de la cartographie : Fondateur/Admin de la civilisation propriétaire (celle de la ville ou du quartier),
ou administrateur ; pour `guerre`, chefs de camp et modérateurs RP d'une guerre **en cours** ; pour `destructible`
(bâtiments en `Marker`, zones en `Polygon`, qu'une guerre RP autorise à détruire ; `type_id` = ville), les modérateurs
RP en plus des dirigeants de la civilisation. Ces formes sont supprimées avec la ville. `commerciale` : marchés et
quartiers marchands d'une ville (`type_id` = ville, polygones nommés), mêmes droits que les frontières de la ville,
supprimés avec elle ; leurs boutiques sont les magasins situés à l'intérieur (calculées par le site et la carte).

### Marchés et foires — `/api/marches`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| GET | `/list` | — | Villes publiques : `{ jours, foires }` (foires à venir ou en cours) |
| GET | `/ville/{VilleID}` | — | `{ jours, a_venir, passees }` (les 5 dernières passées) |
| PUT | `/zones/{CartographieID}/jours` | F/A de la civilisation de la ville | `{ jours: [0…6], horaires? }` |
| POST | `/foires` | F/A de la civilisation de la ville | `{ ville_id, title, date_debut, date_fin?, horaires?, zone_id?, description? }` |
| PUT | `/foires/{FoireID}` | Idem | Met à jour (un changement de dates est annoncé) |
| DELETE | `/foires/{FoireID}` | Idem | Annule (annoncé si la foire n'est pas passée) |

Jours de la semaine réelle (le serveur se joue en temps réel). Une foire dure au plus 31 jours, ne s'annonce pas une
fois passée, et se place au centre de sa zone commerciale ou, à défaut, de la ville. Création, report et annulation
sont annoncés dans le salon `platforms.discord.channels.marches` (villes publiques), avec le lien `…/ville/{id}#marches`.
Supprimer une zone efface ses jours et replace ses foires au centre de la ville ; supprimer la ville efface ses foires.

### Fermes — `/api/fermes`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| GET | `/mine` | Connecté | Fermes déclarées par l'utilisateur |
| GET | `/list?status=` | Modérateur RP | Toutes les fermes, en attente d'abord |
| GET | `/read/{FermeID}` | Déclarant ou modérateur RP | Une ferme (404 pour les autres) |
| GET | `/photo/{Nom}` | — | La photo ; son nom aléatoire tient lieu de droit d'accès |
| POST | `/create` | Connecté | `{ title, type?, production?, justification, habillage?, dimension_id?, x, y?, z, ville_id? }` |
| PUT | `/update/{FermeID}` | Déclarant ou modérateur RP | Modifiée par son déclarant, la ferme repasse en attente |
| POST | `/photo/{FermeID}` | Déclarant ou modérateur RP | Multipart, champ `photo` : PNG, JPEG ou WebP (signature vérifiée), 5 Mo au plus |
| PUT | `/decision/{FermeID}` | Modérateur RP, sauf le déclarant | `{ status: validee \| a_corriger, note? }` (note obligatoire pour `a_corriger`) |
| DELETE | `/delete/{FermeID}` | Déclarant ou modérateur RP | Retire la déclaration et sa photo |

Types : `cultures`, `elevage`, `mobs`, `ressources`, `automatique`, `autre`. Les photos sont rangées dans
`./uploads/fermes` (dossier courant de l'API, comme la base ; ignoré par git ; voir `services/fichiers.py`, qui range
aussi les portraits et skins des personnages dans `./uploads/personnages`). Chaque déclaration nouvelle ou rouverte
est signalée dans `platforms.discord.channels.fermes`. Les fermes d'un utilisateur supprimé le sont avec lui ; une
ville supprimée est simplement détachée.

### Calendrier — `/api/calendrier`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| GET | `/list?debut=&fin=` | — | `{ evenements, foires }` qui touchent la période (400 jours au plus ; par défaut du mois passé à l'an prochain), annulés compris |
| GET | `/read/{EvenementID}` | — | Un événement, avec ses inscrits |
| POST | `/create` | Connecté ; F/A de l'organisateur | `{ title, type?, date_debut, date_fin?, lieu?, ville_id?, organisateur_type?, organisateur_id?, guerre_id?, places?, description? }` |
| PUT | `/update/{EvenementID}` | Créateur, F/A de l'organisateur, modérateur RP | Mêmes champs, sauf l'organisateur ; un changement de date est annoncé |
| POST | `/{EvenementID}/annuler` | Idem | `{ motif? }` : annonce l'annulation et supprime l'événement Discord |
| POST | `/{EvenementID}/inscription` | Connecté | `{ personnage_id? }` : s'inscrire, ou changer de personnage |
| DELETE | `/{EvenementID}/inscription` | Connecté | Se désinscrire |

### Lignées — `/api/lignees`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| GET | `/personnage/{PersonnageID}` | — | `{ maison, parents, enfants, conjoints, fratrie, heritiers, heritier_de }` (liens acceptés) |
| GET | `/demandes` | Connecté | `{ recues, envoyees }` : demandes en attente qui concernent ses personnages |
| POST | `/liens` | Joueur de l'un des deux personnages (de la source pour un héritier) ; modérateur RP | `{ type, source_id, cible_id, rang?, date_rp? }` ; en attente si l'autre personnage est à un autre joueur |
| POST | `/liens/{LienID}/accepter` / `refuser` | Joueur du personnage attendu, modérateur RP | Refuser supprime la demande |
| DELETE | `/liens/{LienID}` | Joueur de l'un des deux personnages, demandeur, modérateur RP | Retire le lien |
| GET | `/maisons` | — | Maisons, avec chef, civilisation et nombre de membres |
| GET | `/maisons/{MaisonID}` | — | `{ maison, membres, allies, liens }` : de quoi dessiner l'arbre |
| POST | `/maisons` | Connecté | `{ title, chef_id (un de ses personnages), devise?, description?, couleur?, icon?, civilisation_id?, date_fondation? }` |
| PUT | `/maisons/{MaisonID}` | Créateur, joueur du chef, modérateur RP | Mêmes champs ; le chef est un membre |
| DELETE | `/maisons/{MaisonID}` | Idem | Dissout la maison (ses membres restent, sans maison) |
| POST | `/maisons/{MaisonID}/membres` | Joueur du personnage | `{ personnage_id }` : il y entre (et quitte son ancienne maison, sauf s'il en est le chef) |
| DELETE | `/maisons/{MaisonID}/membres/{PersonnageID}` | Joueur du personnage, gestionnaires | Sortie ou exclusion ; pas le chef |

### Chroniques — `/api/chroniques`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| GET | `/list` | — | Frise par date RP, la plus récente d'abord (sans date RP, une entrée n'y figure pas) : `[{ id, categorie, date, date_rp, title, description, lien, fait_id? }]` |
| POST | `/faits` | Modérateur RP | `{ title, date_rp, description? }` |
| PUT | `/faits/{FaitID}` | Modérateur RP | Mêmes champs |
| DELETE | `/faits/{FaitID}` | Modérateur RP | Retire le fait |

### Population — `/api/population`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| GET | `/ville/{VilleID}` | — | `{ mesuree, mesure: { releve_at, methode, rayon }, ajustements, en_attente, officielle }` |
| GET | `/civilisation/{CivilisationID}` | — | `{ officielle, armee, habitants_par_soldat, villes }` (somme des villes, un soldat pour dix habitants) |
| GET | `/ajustements/en-attente` | Modérateur RP | Demandes à valider, avec leur ville |
| POST | `/ajustements` | F/A de la civilisation | Demande `{ ville_id, ecart, motif }` (écart non nul, motif obligatoire) |
| PUT | `/ajustements/{ID}/decision` | Modérateur RP, sauf le demandeur | `{ accepte, note? }` |
| DELETE | `/ajustements/{ID}` | Demandeur (en attente) ou modérateur RP | Retire l'ajustement |

Population officielle d'une ville : `villes.population` (écrite par chaque relevé, modifiable directement par un
administrateur seulement) + somme des écarts acceptés, jamais négative. Les ajustements sont supprimés avec la ville.

### Actions secrètes — `/api/actions`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| GET | `/list` | — | Registre : `{ id, code, created_at, empreinte, revealed }` pour une action scellée, tout pour une révélée |
| GET | `/read/{ActionID}` | — | Une action, sous la même forme |
| GET | `/guerre/{GuerreID}` | — | Actions révélées rattachées à la guerre |
| GET | `/mine` | Connecté | Actions dont on est l'auteur, en entier, avec les lectures tracées |
| POST | `/lire/{ActionID}` | Auteur, ou A / modérateur RP (lecture enregistrée) | Contenu d'une action scellée |
| POST | `/create` | Joueur du personnage, F/A de la civilisation ou religion | Scelle `{ title, content, entity_type, entity_id, guerre_id?, reveal_at? }` |
| POST | `/{ActionID}/reveler` | Auteur, ou modérateur RP avec `motif` | Révèle l'action |
| PUT | `/{ActionID}/piege` | Modérateur RP, pas l'auteur | Juge un piège révélé, déclaré au dépôt (`piege: true`) : `{ mortel, note }`, `note` obligatoire pour une blessure ; annoncé sur Discord |

### Monde — `/api/monde`

| Méthode | Chemin | Droits | Description |
| --- | --- | --- | --- |
| POST | `/releves` | En-tête `X-Monde-Key` ou jeton A | Enregistre un relevé et met à jour les populations |
| GET | `/releves?limit=52` | A | Liste des relevés |
| GET | `/resume?releve_id=` | A | `{ releve, precedent, evolution, dimensions, lieux, zones, joueurs, releves }` (dernier relevé par défaut) |
| POST | `/pseudos?releve_id=` | A | Cherche sur playerdb.co les pseudos manquants |
| GET | `/joueurs?releve_id=&actifs=` | A | Joueurs |
| GET | `/zones?releve_id=&limit=50` | A | Zones les plus fréquentées |
| GET | `/lieux?releve_id=` | A | Mesures par lieu |
| GET | `/lieux/{EntityType}/{EntityID}` | A | Historique d'un lieu |
| DELETE | `/releves/{ReleveID}` | A | Supprime un relevé |

## Règles métier

### Membres (civilisations, religions, commerces)

- Le créateur devient **Fondateur**. Ce rôle ne s'obtient que par transfert
  (`/members/{id}/transfer`), qui donne à l'ancien fondateur le rôle `former_role` (`Admin` par défaut).
- Les rôles ajoutables sont `Admin` et `Membre`. Un utilisateur n'est membre qu'une fois.
- Gérer les membres demande d'être Fondateur ou Admin de l'entité, ou administrateur du site.
- **Commerce dirigé** : le Fondateur et les Admins de son commerce dirigeant ont les mêmes droits que les siens
  (fiche, suppression, membres, magasins, catalogue ; `_check_commerce_rights`). L'inverse est faux, et le transfert
  du rôle de Fondateur reste réservé au Fondateur lui-même. `/commerces/read` joint donc les `members` du dirigeant
  pour que le site affiche les mêmes boutons.

### Alliances

- Types : `Militaire` ou `Diplomatique`. Rôles : `Chef de file` (un seul), `Membre`, `Observateur`.
- On entre par **invitation** de l'alliance ou par **demande** de la civilisation, acceptée par l'autre partie.
- La gestion de l'alliance revient au Fondateur et aux Admins de la civilisation chef de file.

### Guerres

- `Militaire` : entre civilisations. `Religion` : entre religions, que des civilisations peuvent rejoindre.
- Cycle de vie :

  ```
  déclarer ──► en_attente ──valider──► en_cours ──terminer──► terminee
                   │
                   └──refuser──► refusee
  ```

- Une déclaration reste **privée** tant qu'un modérateur RP ne l'a pas validée. Deux guerres ouvertes ne peuvent
  pas opposer les mêmes chefs de camp.
- Une guerre validée est **archivée, jamais supprimée** ; seule une déclaration en attente ou refusée peut être retirée.
- Appel aux armes : le chef de camp appelle une civilisation ou tous les membres (hors observateurs) d'une alliance
  dont il fait partie ; chaque appelé accepte ou décline. Un chef de camp ne peut pas se retirer.
- La chronologie s'écrit automatiquement (déclaration, validation, refus, ralliement, retrait, fin). Les chefs de
  camp (guerre en cours) et les modérateurs RP y ajoutent batailles, sièges, traités et autres faits ; les étapes
  automatiques ne peuvent pas être retirées.
- Annonces Discord (salon `platforms.discord.channels.guerres`) : début, batailles, sièges, traités et fin.

### Actions secrètes

- Déposée au nom d'un personnage (son joueur), d'une civilisation ou d'une religion (Fondateur ou Admin), avec une
  guerre **en cours** facultative. Scellée à l'heure du serveur ; aucune modification ni suppression.
- Empreinte SHA-256 de « sel\ntitre\ncontenu », publiée au dépôt ; le sel n'est publié qu'à la révélation, ce qui
  permet à chacun de recalculer l'empreinte (le site le fait et affiche « Intacte »).
- Avant révélation, le public ne voit que le code (`AS-0001`), la date de dépôt et l'empreinte.
- **Lecture tracée** (conflit d'intérêts de l'équipe, qui joue aussi) : un administrateur ou modérateur RP qui n'est
  pas l'auteur peut lire une action scellée, mais chaque lecture est enregistrée (table `actionsecretelectures`),
  visible de l'auteur aussitôt et de tous à la révélation. Être administrateur du site ne fait pas de vous l'auteur.
- Révélation par l'auteur, par un modérateur RP (motif obligatoire, publié) ou à la date `reveal_at` fixée au dépôt
  (appliquée à la première lecture qui suit, sans tâche planifiée). Annonce Discord dans `platforms.discord.channels.actions`.

### Notifications

Écrites par `crud_notifications.notifier` au moment des faits, après l'enregistrement de l'action, et relevées par le
site (cloche de la barre) toutes les minutes. Jamais adressées à celui qui agit, ni à un compte désactivé. Les
« gestionnaires » d'une civilisation ou d'une religion sont son Fondateur et ses Admins ; ceux d'un personnage, son joueur.

| Type | Fait | Destinataires |
| --- | --- | --- |
| `appel` | Appel aux armes | Gestionnaires de chaque civilisation appelée |
| `appel` | Réponse à un appel (rejoint ou décline) | Gestionnaires des belligérants engagés du camp qui appelait |
| `invitation` | Invitation d'une alliance / demande d'une civilisation | Gestionnaires de la civilisation invitée / du chef de file |
| `invitation` | Réponse à l'invitation ou à la demande | L'autre partie |
| `lien` | Lien de parenté en attente | Joueur du personnage dont l'accord est attendu |
| `lien` | Lien accepté ou refusé | Joueur qui l'avait demandé |
| `lecture` | Lecture tracée d'une action scellée | Auteurs de l'action (déposant et gestionnaires de l'entité) |
| `revelation` | Révélation d'une action | Ses auteurs (sauf celui qui la révèle), et les gestionnaires des belligérants de sa guerre |
| `moderation` | Déclaration de guerre, ferme déclarée ou retouchée, ajustement de population, piège révélé | Modérateurs RP et administrateurs (l'auteur exclu) |
| `decision` | Déclaration refusée, ferme validée ou à corriger, ajustement accepté ou refusé, piège jugé | Le demandeur (ou les auteurs de l'action) |
| `guerre` | Guerre validée, guerre terminée | Gestionnaires des belligérants engagés (et le déclarant à la validation) |
| `evenement` | Événement du calendrier annulé | Joueurs inscrits |
| `mercenaires` | Compagnie engagée / contrat rompu | Gestionnaires de la civilisation qui loue / de l'employeur |

Une notification lue est supprimée après 30 jours ; au-delà de 200 par joueur, les plus anciennes disparaissent.

### Calendrier

- Heures réelles du serveur (le serveur se joue en temps réel). Un événement s'annonce avant de commencer, dure au plus
  31 jours, et ne se modifie ni ne s'annule une fois terminé.
- Organisateur : le joueur lui-même, ou une civilisation, une religion, un commerce (Fondateur ou Admin, y compris du
  commerce dirigeant) ou une alliance (Fondateur ou Admin de la civilisation chef de file). Il ne change plus ensuite.
- Une bataille se rattache à une guerre **en cours** par un chef de camp ou un modérateur RP (`crud_conflits.can_raconter`).
- Gèrent l'événement : son créateur, les dirigeants de l'organisateur, les modérateurs RP.
- Inscriptions jusqu'au début, dans la limite des places, sous les traits d'un de ses personnages (pas d'un mort) ou
  sans personnage ; on ne réduit pas les places sous le nombre d'inscrits.
- Discord : annonce dans `platforms.discord.channels.evenements` (création, changement de date, annulation), avec le
  lien `…/calendrier?mois=AAAA-MM#evenement-{id}` ; reproduction en événement programmé du serveur (type « lieu
  externe », lieu = lieu + ville, deux heures sans heure de fin), créé, mis à jour tant qu'il n'a pas commencé, supprimé à
  l'annulation. En tâche de fond, une synchronisation à la fois ; un échec n'empêche rien sur le site.
- Les foires des villes publiques figurent au calendrier (lecture seule, voir Marchés et foires).

### Lignées

- Liens `parent`, `conjoint`, `heritier`. Au plus deux parents ; pas de boucle (nul n'est son propre ancêtre, demandes
  en attente comprises) ; deux personnages ne sont liés qu'une fois (pas de mariage entre parent et enfant).
- Entre deux personnages du même joueur, ou par un administrateur ou modérateur RP : lien établi aussitôt. Vers le
  personnage d'un autre joueur : demande, que ce joueur accepte ou refuse. Seul le joueur de la source désigne ses héritiers.
- Maisons : chaque joueur y fait entrer ses propres personnages (comme la résidence) ; les gestionnaires (créateur, joueur
  du chef, modérateurs RP) modifient la maison, en excluent des membres, la dissolvent. Le chef ne quitte pas sa maison
  tant qu'un autre n'est pas désigné.
- Arbre : membres, liens parent et conjoint acceptés entre eux, conjoints venus d'autres maisons (`allies`).
- Annonces Discord dans `platforms.discord.channels.lignees` : fondation d'une maison (chef, date RP, devise) et
  mariage, dès que le lien est établi (aussitôt, ou à l'accord de l'autre joueur), avec le lien de la page.

### Chroniques

- Calculées à chaque lecture, sans table : fondations (civilisations, villes de civilisations publiques, religions,
  commerces), alliances conclues, début et fin des guerres validées et faits racontés de leur chronologie, et lignées
  (fondation des maisons, naissances et morts de leurs membres, mariages datés). Les modérateurs RP ajoutent des faits
  marquants (`chroniquesfaits`).
- Seulement ce qui est public et daté dans le monde. Classées par date RP (fondation, début et fin de guerre, fait
  raconté, fait marquant), la plus récente d'abord. Sans date RP, une entrée n'y figure pas : les révélations d'actions
  secrètes, les adhésions et les événements du calendrier, datés en heure réelle seulement, n'y entrent donc pas.

### Personnages

- Nombre illimité, sans validation. Seuls le joueur et les administrateurs les modifient.
- Résidence cohérente : le quartier appartient à la ville, la ville à la civilisation ; les niveaux supérieurs sont
  complétés automatiquement.
- Skin `minecraft` : l'UUID du compte Microsoft lié est copié à l'enregistrement.
- Attribution d'un message : l'utilisateur doit être l'auteur Discord du message (compte Discord lié). Seul ce
  message est relu sur Discord et un extrait de 280 caractères est conservé.

### Statistiques du monde

- Le calcul est fait par le générateur de cartes (`ShardUI-2-Maps/scripts/map-generator/world_stats.py`) ;
  l'API reçoit, complète et conserve.
- À l'arrivée : totaux recalculés à partir des dimensions, population actuelle des villes et quartiers conservée dans
  `population_declaree`, personnages domiciliés ajoutés, joueurs reliés à leur compte par l'UUID Minecraft.
- **La population mesurée remplace celle des villes et quartiers.** Les lieux d'une dimension absente du relevé ne
  sont pas modifiés.
- Pseudos : compte Minecraft lié, sinon celui fourni par le relevé, sinon playerdb.co (en tâche de fond après
  l'envoi, ou à la demande).

### Cohérence des suppressions

Implémentée dans `services/crud_nettoyage.py`, et rejouée au démarrage pour les références orphelines.

| Suppression | Conséquences |
| --- | --- |
| Civilisation | Villes et quartiers supprimés ; quitte ses alliances (chef de file remplacé ou alliance dissoute) ; déclarations non validées retirées ; guerres commencées archivées sous son nom (relève du chef de camp, sinon fin) ; vassales rendues indépendantes ; liens des livres supprimés ; résidence des personnages vidée |
| Ville / quartier | Résidence des personnages vidée ; religions et magasins détachés ; formes de la carte supprimées |
| Commerce / magasin | Articles du catalogue supprimés avec le magasin |
| Livre | Chapitres et liens supprimés |
| Religion, commerce, alliance, personnage | Liens des livres supprimés |
| Zone commerciale | Jours de marché supprimés ; ses foires replacées au centre de la ville |
| Ville (en plus) | Foires supprimées ; fermes détachées |
| Utilisateur (en plus) | Fermes et photos supprimées ; inscriptions aux événements et notifications supprimées ; événements et faits marquants conservés sans auteur |
| Ville (calendrier) | Événements détachés (leur lieu en texte reste) |
| Personnage (calendrier) | Inscriptions conservées, sans personnage |
| Personnage (lignées) | Liens de parenté supprimés ; la maison qu'il dirigeait n'a plus de chef |
| Maison | Ses membres restent, sans maison |
| Civilisation (lignées) | Maisons détachées de la civilisation |
| Organisateur d'un événement | L'événement garde son nom archivé (`organisateur_title`) |
| Religion | Mêmes règles pour les guerres de religion |
| Utilisateur | Refusée tant qu'il est Fondateur ; sinon personnages, adhésions, sessions et comptes liés supprimés, écrits conservés sans auteur |
| Journal | Attributions des messages supprimées |

## Intégrations externes

### Discord (bot)

`integrations/discord_handler.py` démarre un bot `discord.py` (intents par défaut + contenu des messages) à la première utilisation,
avec `platforms.discord.token` et `guild_id`.

| Fonction | Usage |
| --- | --- |
| `create_channel` | Création d'un journal (catégorie fixée dans `crud.create_journal`) |
| `update_channel_name` / `update_channel_description` | Modification d'un journal |
| `delete_channel` | Suppression d'un journal |
| `get_channel_messages` | Contenu d'un journal |
| `get_channel_message` | Un message (attribution à un personnage) |
| `send_channel_message` | Annonces (`crud.announce_discord`, en tâche de fond : un échec ne fait pas échouer la requête) |
| `create_scheduled_event` / `edit_scheduled_event` / `delete_scheduled_event` | Événements programmés du serveur, reflets du calendrier (`crud_calendrier`) |

### Comptes externes (OAuth)

`integrations/oauth.py` gère Discord (`scope identify`) et Microsoft. Aucun compte n'est créé depuis un fournisseur :
l'utilisateur crée d'abord un compte Tetrago, lie son compte externe depuis son profil, puis peut s'en servir pour
se connecter. Les jetons des fournisseurs ne sont jamais conservés.

```
Site                         Shard-API                      Fournisseur
 │ GET /oauth/discord/link ──►│ crée OAuthStates (10 min)     │
 │◄── { url } ────────────────│                               │
 │ redirection ───────────────┼──────────────────────────────►│
 │◄── /auth/discord/callback?code&state ──────────────────────│
 │ GET /oauth/discord/callback ►│ échange le code, lit l'identité ─►│
 │◄── { mode, ... } ──────────│                               │
```

Microsoft suit la chaîne Microsoft → Xbox Live → XSTS → profil Minecraft Java et renvoie un message clair pour un
compte sans Xbox, un compte enfant ou un compte sans le jeu. L'application Azure doit être approuvée par Mojang
(formulaire sur https://aka.ms/AppRegInfo) ; en attendant, la liaison indique que la validation est en attente.

### playerdb.co

Utilisé par `crud_monde` pour convertir en pseudo les UUID des joueurs (10 s de délai maximal par appel).

## Tests

Il n'y a pas de tests unitaires dans ce dépôt. Les parcours de bout en bout sont couverts par les tests Playwright de
ShardUI-2 (`npm run test:ux`), qui lancent cette API sur une copie jetable de `ShardDB.db` avec les variables de
[simulation](#variables-denvironnement) (faux Discord, faux Microsoft, faux playerdb.co, clé du monde).

## Points d'attention

Les cinq constats relevés lors de la rédaction de ce document ont été traités :

| Constat | Traitement |
| --- | --- |
| `GET /api/users/list` n'exigeait pas de connexion et renvoyait tous les e-mails | La route dépend de `secu_get_current_active_admin` (401 sans jeton, 403 sans le rôle). `/users/id/{id}` et `/users/name/{username}` ne joignent l'e-mail que pour le propriétaire du profil ou un administrateur — voir [Dépendances FastAPI](#dépendances-fastapi) |
| Mots de passe en SHA-256 sans sel | scrypt salé, empreintes héritées migrées à la connexion suivante — voir [Mots de passe](#mots-de-passe) |
| La vérification des tables supprimait et recréait une colonne incohérente | Reconstruction de la table avec conservation des valeurs, après sauvegarde du fichier SQLite — voir [Correction des colonnes incohérentes](#correction-des-colonnes-incohérentes) |
| Catégorie Discord des journaux codée en dur | Lue dans `platforms.discord.categories.journaux` (`crud.discord_category`) |
| `README.md` encore celui du modèle « API Template » | Réécrit pour Shard-API ; ce document reste la référence complète |

Restent ouverts, sans urgence :

- **Empreintes SHA-256 encore en base** : elles ne disparaissent qu'au fur et à mesure des connexions. Un compte
  jamais reconnecté conserve son ancienne empreinte, vérifiable mais sans sel.
- **`oauth2.client_id` / `client_secret`** ne sont pas vérifiés par `/api/users/token` (code commenté).
- **Format des réponses inégal** : selon les routes, le statut est dans `code`, dans `error`, ou seulement dans
  l'erreur HTTP `detail` (voir [Référence des routes](#référence-des-routes)).
- **Sauvegardes `*.backup-*.db`** jamais purgées automatiquement.
