from sqlmodel import create_engine, Session
from . import utils

DATABASE_URL = f"sqlite:///./{utils.DATABASE['name']}.db"

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
                        has_type_mismatch = False
                        has_nullable_mismatch = False
                        
                        if expected_type_normalized != actual_type_normalized:
                            mismatch_details.append(f"type ({actual_type} vs {expected_type})")
                            has_type_mismatch = True
                        if expected_nullable != actual_nullable:
                            nullable_str = "NULL" if actual_nullable else "NOT NULL"
                            expected_nullable_str = "NULL" if expected_nullable else "NOT NULL"
                            mismatch_details.append(f"nullable ({nullable_str} vs {expected_nullable_str})")
                            has_nullable_mismatch = True
                        
                        details_str = ", ".join(mismatch_details)
                        print(f"{colors.BColors.RED}  ✗ Colonne '{column_name}' : incohérence détectée ({details_str}){colors.BColors.END}")
                        
                        # CORRECTION : Supprimer et recréer la colonne
                        print(f"{colors.BColors.YELLOW}  → Correction en cours...{colors.BColors.END}")
                        try:
                            # Construire le type SQL correct
                            col_type = str(column.type.compile(engine.dialect))
                            
                            # Déterminer si la colonne accepte NULL
                            nullable = "NULL" if column.nullable else "NOT NULL"
                            
                            # Construire la clause DEFAULT si nécessaire
                            default_clause = ""
                            if column.default is not None:
                                if callable(column.default.arg):
                                    default_clause = ""
                                else:
                                    default_clause = f"DEFAULT {column.default.arg}"
                            
                            # Supprimer la colonne
                            drop_stmt = f"ALTER TABLE {table_name} DROP COLUMN {column_name}"
                            connection.execute(text(drop_stmt))
                            
                            # Recréer la colonne avec le bon type
                            add_stmt = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {col_type} {nullable} {default_clause}".strip()
                            connection.execute(text(add_stmt))
                            
                            print(f"{colors.BColors.GREEN}  ✓ Colonne '{column_name}' corrigée : {col_type} {nullable}{colors.BColors.END}")
                        except Exception as e:
                            print(f"{colors.BColors.YELLOW}  ⚠ Impossible de corriger '{column_name}': {str(e)}{colors.BColors.END}")
    
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