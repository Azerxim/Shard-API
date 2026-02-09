# API Template

Un template d'API moderne construit avec **FastAPI** et **SQLModel**.

## 📋 Table des matières

- [Caractéristiques](#-caractéristiques)
- [Prérequis](#-prérequis)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Démarrage](#-démarrage)
- [Utilisation des scripts](#-utilisation-des-scripts)
- [Structure du projet](#-structure-du-projet)
- [Vérification et synchronisation de la base de données](#-vérification-et-synchronisation-de-la-base-de-données)
- [API Documentation](#-api-documentation)
- [Dépendances principales](#-dépendances-principales)
- [Sécurité](#-sécurité)
- [Architecture](#-architecture)
- [Licence](#-licence)

## ✨ Caractéristiques

- 🚀 **FastAPI** - Framework Web moderne et haute performance
- 🗄️ **SQLModel** - ORM combinant SQLAlchemy et Pydantic
- 🔐 **Authentification OAuth2** - Sécurité intégrée avec tokens JWT
- 📚 **Documentation automatique** - Swagger UI et ReDoc
- 🎨 **Interface Web** - Pages HTML personnalisées avec CSS responsive
- 📦 **Architecture modulaire** - Séparation claire des responsabilités (CRUD, modèles, schémas, routes)
- 🔄 **Vérification des tables** - Synchronisation automatique des schémas BD avec les modèles
- ⚙️ **Configuration flexible** - IP et PORT lus depuis config.json
- 🔁 **Mode développeur** - Hot-reload optionnel avec --reload

## 📦 Prérequis

- Python 3.10+
- pip (gestionnaire de paquets Python)

## 🔧 Installation

1. **Cloner le repository**

   ```bash
   git clone <url-du-repository>
   cd API-template
   ```

2. **Utiliser les scripts de démarrage** (recommandé)

   **Sur Linux/macOS :**

   ```bash
   chmod +x start.sh
   ./start.sh
   # Menu interactif: créer venv, installer dépendances, démarrer l'API
   ```

   **Sur Windows (PowerShell) :**

   ```powershell
   .\start.ps1
   # Menu interactif: créer venv, installer dépendances, démarrer l'API
   ```

3. **Ou installer manuellement**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Sur Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

## ⚙️ Configuration

1. **Copier le fichier de configuration**

   ```bash
   cp config.json.template config.json
   ```

2. **Éditer `config.json`** avec vos paramètres :
   ```json
   {
     "version": "3",
     "api": {
       "name": "Mon API",
       "ip": "0.0.0.0",
       "port": 8000
     },
     "database": {
       "name": "database",
       "debug": false
     },
     "security": {
       "username": "admin",
       "full_name": "Administrateur",
       "email": "admin@example.com",
       "password": "votre_mot_de_passe_securise"
     },
     "oauth2": {
       "client_id": "votre_client_id",
       "client_secret": "votre_client_secret"
     }
   }
   ```

## 🚀 Démarrage

### Avec les scripts (recommandé)

Les scripts `start.sh` (Linux/macOS) et `start.ps1` (Windows) offrent un menu interactif :

1. **Créer/Activer** l'environnement virtuel
2. **Installer** les dépendances
3. **Démarrer** l'API
   - Mode développeur : rechargement automatique lors de modifications
   - Mode production : sans rechargement

### Manuellement

**Mode développeur (avec rechargement automatique) :**

```bash
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

**Mode production (sans rechargement) :**

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## 📝 Utilisation des scripts

Les scripts `start.sh` et `start.ps1` lisent **automatiquement** l'IP et le PORT depuis `config.json` et offrent un choix de mode d'exécution.

**Personnalisation :**

- Modifiez le paramètre `VENV_DIR` au début du script pour changer le répertoire de l'environnement virtuel
- Choisissez entre mode développeur (--reload) et production lors du démarrage

L'API sera accessible à : `http://localhost:8000`

## 📁 Structure du projet

```
.
├── api/                    # Code principal de l'API
│   ├── main.py            # Point d'entrée FastAPI
│   ├── models.py          # Modèles SQLModel
│   ├── schemas.py         # Schémas Pydantic (validation)
│   ├── crud.py            # Opérations base de données + vérification BD
│   ├── database.py        # Configuration base de données
│   ├── utils.py           # Utilitaires et configuration
│   └── routes_users.py    # Routes utilisateur (séparées)
├── html/                   # Pages HTML statiques
│   ├── index.html         # Page d'accueil
│   ├── docs.html          # Documentation personnalisée
│   ├── redoc.html         # Documentation ReDoc
│   └── components/        # Composants réutilisables
├── assets/                # Ressources statiques
│   ├── css/               # Feuilles de style CSS
│   ├── images/            # Images et icônes
│   └── fontawesome/       # Icônes FontAwesome
├── config.json.template   # Template de configuration
├── config.json            # Configuration (à créer)
├── requirements.txt       # Dépendances Python
├── README.md              # Ce fichier
├── start.sh              # Script de démarrage Linux/macOS
└── start.ps1             # Script de démarrage Windows
```

## 🔄 Vérification et synchronisation de la base de données

Au démarrage, l'API :

- **Crée** les tables manquantes automatiquement
- **Ajoute** les colonnes manquantes
- **Corrige** les types de données incompatibles
- **Initialise** l'utilisateur admin avec les credentials de `config.json`

## 📚 API Documentation

Une fois l'API démarrée, accédez à :

- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc
- **Page d'accueil** : http://localhost:8000

## 📄 Dépendances principales

| Package     | Version  | Utilisation               |
| ----------- | -------- | ------------------------- |
| fastapi     | 0.128.0+ | Framework Web             |
| sqlmodel    | 0.0.31   | ORM SQLAlchemy + Pydantic |
| requests    | Latest   | Requêtes HTTP             |
| topazdevsdk | 1.1.0    | Utilitaires et logging    |

## 🔒 Sécurité

**Recommandations pour la production :**

- ✅ Changez les identifiants admin par défaut
- ✅ Utilisez des variables d'environnement pour les secrets
- ✅ Générez des tokens JWT sécurisés
- ✅ Activez HTTPS avec un certificat SSL/TLS
- ✅ Limitez l'accès à la base de données
- ✅ Configurez un mot de passe admin robuste
- ✅ Activez le debug à false dans la configuration

## 🤝 Architecture

L'API suit une architecture modulaire :

- **main.py** : Point d'entrée et configuration FastAPI
- **routes_users.py** : Routes utilisateur (séparées pour meilleure organisation)
- **crud.py** : Opérations base de données et vérification des schémas
- **models.py** : Définition des modèles SQLModel
- **schemas.py** : Schémas Pydantic pour validation
- **database.py** : Configuration et gestion de la base de données
- **utils.py** : Utilitaires et lecture de la configuration

Facile d'ajouter d'autres routes : créez `routes_produits.py`, `routes_commandes.py`, etc.

## 📝 Licence

Ce projet est sous licence. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

**Besoin d'aide ?**

- [Documentation FastAPI](https://fastapi.tiangolo.com)
- [Documentation SQLModel](https://sqlmodel.tiangolo.com)
- [Documentation SQLAlchemy](https://docs.sqlalchemy.org)
