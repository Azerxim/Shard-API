import datetime as dt
import os
import shutil

from sqlmodel import create_engine, Session
from ..core import utils

DATABASE_PATH = f"./{utils.DATABASE['name']}.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Une seule sauvegarde par démarrage, faite juste avant la première modification de colonne
_backup_path = None

engine = create_engine(
    DATABASE_URL, echo=utils.DATABASE['debug']
)

def get_db():
    db = Session(engine)
    try:
        yield db
    finally:
        db.close()

def create_db_and_tables():
    """Crée la base de données et les tables si elles n'existent pas"""
    from sqlmodel import SQLModel
    SQLModel.metadata.create_all(engine)

def migrate_commerces_owner_to_members():
    """
    Ancienne colonne Commerces.owner_id -> ligne "Fondateur" dans CommerceMembers, puis suppression de la colonne.
    À appeler après create_db_and_tables (la table commercemembers doit exister). Sans effet si déjà migré.
    """
    import datetime as dt
    from sqlalchemy import inspect, text, MetaData
    from . import models

    inspector = inspect(engine)
    if "commerces" not in inspector.get_table_names():
        return
    existing_columns = [col['name'] for col in inspector.get_columns("commerces")]
    if "owner_id" not in existing_columns:
        return

    print("Migration : propriétaires des commerces -> membres Fondateur...")
    with engine.begin() as connection:
        commerces = connection.execute(text("SELECT id, owner_id, created_at FROM commerces WHERE owner_id IS NOT NULL")).all()
        for commerce_id, owner_id, created_at in commerces:
            params = {"commerce_id": commerce_id, "user_id": owner_id}
            if connection.execute(text("SELECT 1 FROM commercemembers WHERE commerce_id = :commerce_id AND role = 'Fondateur'"), params).first():
                continue
            if connection.execute(text("SELECT 1 FROM commercemembers WHERE commerce_id = :commerce_id AND user_id = :user_id"), params).first():
                connection.execute(text("UPDATE commercemembers SET role = 'Fondateur' WHERE commerce_id = :commerce_id AND user_id = :user_id"), params)
            else:
                connection.execute(
                    text("INSERT INTO commercemembers (user_id, commerce_id, role, joined_at) VALUES (:user_id, :commerce_id, 'Fondateur', :joined_at)"),
                    {**params, "joined_at": created_at or dt.datetime.now()}
                )

        # SQLite refuse DROP COLUMN sur une colonne à clé étrangère : reconstruction de la table sans owner_id
        columns = ", ".join(col.name for col in models.Commerces.__table__.columns if col.name in existing_columns)
        models.Commerces.__table__.to_metadata(MetaData(), name="commerces_new").create(connection)
        connection.execute(text(f"INSERT INTO commerces_new ({columns}) SELECT {columns} FROM commerces"))
        connection.execute(text("DROP TABLE commerces"))
        connection.execute(text("ALTER TABLE commerces_new RENAME TO commerces"))
    print(f"Migration terminée : {len(commerces)} commerce(s) avec fondateur, colonne owner_id supprimée.")

def backup_database(reason: str):
    """Copie le fichier SQLite avant la première modification de structure du démarrage.
    Renvoie le chemin de la sauvegarde, ou None si elle n'a pas pu être faite."""
    global _backup_path
    from topazdevsdk import colors

    if _backup_path is not None:
        return _backup_path
    if not os.path.exists(DATABASE_PATH):
        return None
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    target = f"{os.path.splitext(DATABASE_PATH)[0]}.backup-{stamp}.db"
    try:
        shutil.copy2(DATABASE_PATH, target)
    except Exception as error:
        print(f"{colors.BColors.RED}  ✗ Sauvegarde impossible ({error}) : aucune modification de colonne ne sera tentée{colors.BColors.END}")
        return None
    _backup_path = target
    print(f"{colors.BColors.CYAN}  → Sauvegarde avant {reason} : {target}{colors.BColors.END}")
    return target


def _rebuild_table(model_class, existing_columns, details: str):
    """Reconstruit une table d'après son modèle en conservant les valeurs des colonnes communes.
    C'est la seule façon, sous SQLite, de corriger un type ou une nullabilité sans perdre de données.
    En cas d'échec (une valeur NULL dans une colonne devenue NOT NULL, par exemple), la transaction
    est annulée et la table reste inchangée."""
    from topazdevsdk import colors
    from sqlalchemy import text, MetaData

    table_name = model_class.__tablename__
    if backup_database(f"correction de '{table_name}'") is None and os.path.exists(DATABASE_PATH):
        return False

    # Colonnes présentes à la fois dans le modèle et dans la table : seules celles-là sont recopiées
    columns = [col.name for col in model_class.__table__.columns if col.name in existing_columns]
    quoted = ", ".join(f'"{name}"' for name in columns)
    temp_name = f"{table_name}__rebuild"
    try:
        with engine.begin() as connection:
            connection.execute(text(f'DROP TABLE IF EXISTS "{temp_name}"'))
            model_class.__table__.to_metadata(MetaData(), name=temp_name).create(connection)
            connection.execute(text(f'INSERT INTO "{temp_name}" ({quoted}) SELECT {quoted} FROM "{table_name}"'))
            connection.execute(text(f'DROP TABLE "{table_name}"'))
            connection.execute(text(f'ALTER TABLE "{temp_name}" RENAME TO "{table_name}"'))
    except Exception as error:
        print(f"{colors.BColors.RED}  ✗ Table '{table_name}' non corrigée ({details}) : {error}{colors.BColors.END}")
        print(f"{colors.BColors.YELLOW}    La table est inchangée et ses données intactes. Correction à faire à la main.{colors.BColors.END}")
        try:
            with engine.begin() as connection:
                connection.execute(text(f'DROP TABLE IF EXISTS "{temp_name}"'))
        except Exception:
            pass
        return False
    print(f"{colors.BColors.GREEN}  ✓ Table '{table_name}' reconstruite ({details}), valeurs conservées{colors.BColors.END}")
    return True


def check_database_tables():
    """
    Vérifie et met à jour la structure des tables par rapport aux modèles SQLModel
    Ajoute les nouvelles colonnes si elles sont manquantes
    Vérifie les types de données et signale les incohérences
    """
    from topazdevsdk import colors
    from sqlalchemy import inspect, text
    from . import models
    import inspect as inspect_module

    print(f"{colors.BColors.CYAN}Vérification de la structure des tables...{colors.BColors.END}")
    
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    # Découvrir dynamiquement tous les modèles SQLModel avec une table
    import inspect as inspect_module
    model_classes = [
        obj for name, obj in inspect_module.getmembers(models)
        if (inspect_module.isclass(obj) and 
            issubclass(obj, models.SQLModel) and 
            hasattr(obj, '__table__') and
            obj is not models.SQLModel)
    ]
    
    for model_class in model_classes:
        # Obtenir le nom de la table à partir du modèle SQLModel
        table_name = model_class.__tablename__
        print(f"{colors.BColors.YELLOW}  Vérification de la table '{table_name}'...{colors.BColors.END}")
        
        # Si la table n'existe pas encore, elle sera créée par SQLModel
        if table_name not in existing_tables:
            print(f"{colors.BColors.GREEN}  ✓ Table '{table_name}' sera créée{colors.BColors.END}")
            continue
        
        # Obtenir les colonnes existantes dans la base de données
        existing_columns = {col['name']: col for col in inspector.get_columns(table_name)}
        
        # Obtenir les colonnes du modèle SQLModel
        # SQLModel utilise __table__ pour accéder à la table SQLAlchemy
        model_table = model_class.__table__
        
        # Incohérences de type ou de nullabilité relevées sur cette table, corrigées après la boucle
        mismatched_columns = []

        # Vérifier et ajouter les colonnes manquantes et vérifier les types
        with engine.begin() as connection:
            for column in model_table.columns:
                column_name = column.name
                
                if column_name not in existing_columns:
                    # COLONNE MANQUANTE - L'ajouter
                    # Construire le type SQL
                    col_type = str(column.type.compile(engine.dialect))
                    
                    # Déterminer si la colonne accepte NULL
                    nullable = "NULL" if column.nullable else "NOT NULL"
                    
                    # Construire la clause DEFAULT si nécessaire
                    default_clause = ""
                    if column.default is not None:
                        if callable(column.default.arg):
                            default_clause = ""  # Les defaults callable (comme now()) sont gérés par la DB
                        else:
                            default_clause = f"DEFAULT {column.default.arg}"
                    
                    # Construire la requête ALTER TABLE
                    alter_stmt = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {col_type} {nullable} {default_clause}".strip()
                    
                    try:
                        backup_database(f"ajout de '{column_name}' à '{table_name}'")
                        connection.execute(text(alter_stmt))
                        print(f"{colors.BColors.GREEN}  ✓ Colonne '{column_name}' ajoutée à '{table_name}'{colors.BColors.END}")
                    except Exception as e:
                        print(f"{colors.BColors.YELLOW}  ⚠ Impossible d'ajouter '{column_name}': {str(e)}{colors.BColors.END}")
                else:
                    # COLONNE EXISTE - Vérifier le type de données
                    existing_col = existing_columns[column_name]
                    expected_type = str(column.type.compile(engine.dialect)).upper()
                    actual_type = str(existing_col['type']).upper() if existing_col['type'] else 'UNKNOWN'
                    
                    # Normaliser les types pour la comparaison
                    expected_type_normalized = _normalize_sql_type(expected_type)
                    actual_type_normalized = _normalize_sql_type(actual_type)
                    
                    # Vérifier la nullabilité
                    expected_nullable = column.nullable
                    actual_nullable = existing_col['nullable']
                    
                    # Afficher les détails
                    if expected_type_normalized == actual_type_normalized and expected_nullable == actual_nullable:
                        print(f"{colors.BColors.GREEN}  ✓ Colonne '{column_name}' : {actual_type} (correct){colors.BColors.END}")
                    else:
                        mismatch_details = []
                        if expected_type_normalized != actual_type_normalized:
                            mismatch_details.append(f"type ({actual_type} vs {expected_type})")
                        if expected_nullable != actual_nullable:
                            nullable_str = "NULL" if actual_nullable else "NOT NULL"
                            expected_nullable_str = "NULL" if expected_nullable else "NOT NULL"
                            mismatch_details.append(f"nullable ({nullable_str} vs {expected_nullable_str})")
                        
                        details_str = ", ".join(mismatch_details)
                        print(f"{colors.BColors.RED}  ✗ Colonne '{column_name}' : incohérence détectée ({details_str}){colors.BColors.END}")
                        # La correction se fait après la boucle, par reconstruction de la table :
                        # supprimer puis recréer la colonne effacerait toutes ses valeurs.
                        mismatched_columns.append(f"{column_name} : {details_str}")

        # Correction des incohérences relevées : reconstruction de la table, valeurs conservées
        if mismatched_columns:
            print(f"{colors.BColors.YELLOW}  → Correction de '{table_name}' par reconstruction ({len(mismatched_columns)} colonne(s))...{colors.BColors.END}")
            _rebuild_table(model_class, existing_columns, "; ".join(mismatched_columns))

    if _backup_path:
        print(f"{colors.BColors.CYAN}Sauvegarde de la base avant correction : {_backup_path}{colors.BColors.END}")
    print(f"{colors.BColors.GREEN}Vérification des tables terminée{colors.BColors.END}")


def _normalize_sql_type(sql_type: str) -> str:
    """
    Normalise les types SQL pour la comparaison
    Exemple: VARCHAR(255) et VARCHAR sont considérés comme équivalents
    """
    # Supprimer les paramètres de type (VARCHAR(255) -> VARCHAR)
    base_type = sql_type.split('(')[0].strip().upper()
    
    # Créer des mappings d'équivalence
    type_equivalence = {
        'INT': ['INT', 'INTEGER'],
        'VARCHAR': ['VARCHAR', 'STRING', 'TEXT'],
        'BOOLEAN': ['BOOLEAN', 'BOOL'],
        'DATETIME': ['DATETIME', 'TIMESTAMP'],
    }
    
    # Trouver la catégorie équivalente
    for category, types in type_equivalence.items():
        if base_type in types:
            return category
    
    return base_type