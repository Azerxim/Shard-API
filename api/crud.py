from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import text, update
import time as t, datetime as dt
from operator import itemgetter
import hashlib
import asyncio

from . import models, schemas, crud_security as crudSecu
from topazdevsdk import colors
from . import utils
from . import discord_handler

################# USER #####################

# -------------------------------------------------------------------------------
def get_user(db: Session, ID: int):
    return db.query(models.Users).filter(models.Users.id == ID).first()

# -------------------------------------------------------------------------------
def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Users).offset(skip).limit(limit).all()

# -------------------------------------------------------------------------------
def get_read_user(db: Session, ID: int):
    result = get_user(db=db, ID=ID)
    if result is not None:
        user = schemas.readUser(
            id=result.id,
            username=result.username,
            email=result.email,
            pseudo=result.pseudo,
            image_url=result.image_url,
            arrival=result.arrival,
            is_disabled=result.is_disabled,
            is_admin=result.is_admin,
        )
        return user
    return None


# -------------------------------------------------------------------------------
def get_read_users(db: Session, skip: int = 0, limit: int = 100):
    result = get_users(db=db, skip=skip, limit=limit)
    users = []
    for one in result:
        user = schemas.readUser(
            id=one.id,
            username=one.username,
            email=one.email,
            pseudo=one.pseudo,
            image_url=one.image_url,
            arrival=one.arrival,
            is_disabled=one.is_disabled,
            is_admin=one.is_admin,
        )
        users.append(user)
    return users


# -------------------------------------------------------------------------------
def user_exist(db: Session, email: str = "", username: str = ""):
    if username != "" and username is not None:
        db_user_name = db.query(models.Users).filter(models.Users.username == username).first()
    else:
        db_user_name = None
    if email != "" and email is not None:
        db_user_mail = db.query(models.Users).filter(models.Users.email == email).first()
    else:
        db_user_mail = None

    if db_user_name:
        return True, db_user_name
    elif db_user_mail:
        return True, db_user_mail
    else:
        return False, None


# -------------------------------------------------------------------------------
def check_user_from_name(db: Session, username, password):
    result = db.query(models.Users).filter(models.Users.username == username).first()
    if result is not None:
        user = schemas.readUser(
            id=result.id,
            username=result.username,
            email=result.email,
            pseudo=result.pseudo,
            image_url=result.image_url,
            arrival=result.arrival,
            is_disabled=result.is_disabled,
            is_admin=result.is_admin,
        )
        if result.hashed_password == crudSecu.hash_password(password):
            return True, user
        return False, user
    return False, None


# -------------------------------------------------------------------------------
def check_user_from_email(db: Session, email, password):
    result = db.query(models.Users).filter(models.Users.email == email).first()
    if result is not None:
        user = schemas.readUser(
            id=result.id,
            username=result.username,
            email=result.email,
            pseudo=result.pseudo,
            image_url=result.image_url,
            arrival=result.arrival,
            is_disabled=result.is_disabled,
            is_admin=result.is_admin,
        )
        if result.hashed_password == crudSecu.hash_password(password):
            return True, user
        return False, user
    return False, None


# -------------------------------------------------------------------------------
def check_user_all(db: Session, username, email, password):
    result = db.query(models.Users).filter(models.Users.username == username).filter(models.Users.email == email).first()
    if result is not None:
        user = schemas.readUser(
            id=result.id,
            username=result.username,
            email=result.email,
            pseudo=result.pseudo,
            image_url=result.image_url,
            arrival=result.arrival,
            is_disabled=result.is_disabled,
            is_admin=result.is_admin,
        )
        if result.hashed_password == crudSecu.hash_password(password):
            return True, user
        return False, user
    return False, None

################# Bibliothèque #####################

# Journaux
def get_journaux(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Journaux).offset(skip).limit(limit).all()

def get_journal(db: Session, ID: int):
    return db.query(models.Journaux).filter(models.Journaux.id == ID).first()

def get_journaux_by_user(db: Session, userID: int, skip: int = 0, limit: int = 100):
    return db.query(models.Journaux).filter(models.Journaux.user_id == userID).offset(skip).limit(limit).all()

def get_journaux_count(db: Session):
    return db.query(func.count(models.Journaux.id)).scalar()

def get_journaux_count_by_user(db: Session, userID: int):
    return db.query(func.count(models.Journaux.id)).filter(models.Journaux.user_id == userID).scalar()

def get_journal_contents(db: Session, journalID: int, skip: int = 0, limit: int = 10000):
    """
    Récupère les messages Discord associés à un journal.
    
    Args:
        db: Session de la base de données
        journalID: L'ID du journal
        skip: Nombre de messages à sauter
        limit: Nombre maximum de messages à récupérer
    
    Returns:
        dict: Les messages du canal Discord ou erreur
    """
    try:
        # Récupérer le journal
        journal = get_journal(db, journalID)
        if not journal:
            return {"error": 404, "message": "Journal non trouvé"}
        
        # Vérifier que le journal a un UID Discord
        if not journal.uid:
            return {"error": 400, "message": "Ce journal n'a pas de canal Discord associé"}
        
        # Récupérer les messages du canal Discord
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        messages = loop.run_until_complete(
            discord_handler.get_channel_messages(journal.uid, limit=limit + skip)
        )
        loop.close()
        
        # Appliquer skip et limit
        paginated_messages = messages[skip:skip + limit]
        
        return {
            "journal_id": journalID,
            "journal_title": journal.title,
            "channel_id": journal.uid,
            "total_messages": len(messages),
            "messages_count": len(paginated_messages),
            "skip": skip,
            "limit": limit,
            "messages": paginated_messages
        }
    
    except Exception as e:
        print(f"Erreur lors de la récupération des messages du journal {journalID}: {e}")
        return {"error": 500, "message": f"Erreur serveur: {str(e)}"}

# Livres
def get_livres(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Livres).offset(skip).limit(limit).all()

def get_livre(db: Session, ID: int):
    return db.query(models.Livres).filter(models.Livres.id == ID).first()

def get_livres_by_user(db: Session, userID: int, skip: int = 0, limit: int = 100):
    return db.query(models.Livres).filter(models.Livres.user_id == userID).offset(skip).limit(limit).all()

def get_livres_count(db: Session):
    return db.query(func.count(models.Livres.id)).scalar()

def get_livres_count_by_user(db: Session, userID: int):
    return db.query(func.count(models.Livres.id)).filter(models.Livres.user_id == userID).scalar()


# ===============================================================================
# Création
# ===============================================================================
def create_user(db: Session, v_user: schemas.createUser):
    db_user = models.Users(
        username = v_user.username.lower(),
        email = v_user.email,
        hashed_password = crudSecu.hash_password(v_user.password),
        pseudo = v_user.pseudo,
        image_url = None,
        arrival = dt.datetime.today(),
        is_disabled = 0,
        is_admin = 0
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"error": 200, "text": "Utilisateur créé avec succès", "user": db_user}

def create_journal(db: Session, v_journal: schemas.Journal):
    # Créer le salon Discord si le titre est fourni
    channel_uid = None
    category_uid = 1444691218234605700
    if v_journal.title:
        try:
            # Utiliser asyncio pour exécuter la fonction asynchrone
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            channel_uid = loop.run_until_complete(
                discord_handler.create_channel(v_journal.title, category_uid)
            )
            loop.close()
            print(f"\033[92mSalon Discord créé avec l'ID: {channel_uid}\033[0m")
        except Exception as e:
            print(f"Avertissement: Impossible de créer le salon Discord: {e}")
            channel_uid = None
    
    db_journal = models.Journaux(
        user_id = v_journal.user_id,
        author = v_journal.author,
        title = v_journal.title,
        description = v_journal.description,
        cover_url = v_journal.cover_url,
        cover_icon = v_journal.cover_icon,
        cover_color = v_journal.cover_color,
        link = v_journal.link,
        uid = channel_uid if channel_uid else v_journal.uid,
        published_date = v_journal.published_date,
        created_at = dt.datetime.today()
    )
    
    db.add(db_journal)
    db.commit()
    db.refresh(db_journal)
    return db_journal

def create_livre(db: Session, v_livre: schemas.Livre):
    db_livre = models.Livres(
        user_id = v_livre.user_id,
        author = v_livre.author,
        title = v_livre.title,
        description = v_livre.description,
        cover_url = v_livre.cover_url,
        cover_icon = v_livre.cover_icon,
        cover_color = v_livre.cover_color,
        pages = v_livre.pages,
        language = v_livre.language,
        link = v_livre.link,
        published_date = v_livre.published_date,
        created_at = dt.datetime.today()
    )
    
    db.add(db_livre)
    db.commit()
    db.refresh(db_livre)
    return db_livre


# ===============================================================================
# Suppression
# ===============================================================================
def delete_user(db: Session, v_userid: int):
    try:
        script = f'DELETE FROM `Users` WHERE `id` = "{v_userid}"'
        db.execute(script)
        db.commit()
        return True
    except Exception as e:
        print(f"Erreur lors de la suppression de l'utilisateur {v_userid}: {e}")
    return False

def delete_journal(db: Session, v_journalid: int):
    try:
        # Récupérer le journal pour obtenir son UID Discord
        journal = get_journal(db, v_journalid)
        if journal and journal.uid:
            try:
                # Supprimer le salon Discord associé
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    discord_handler.delete_channel(journal.uid)
                )
                loop.close()
                if result:
                    print(f"Salon Discord {journal.uid} supprimé avec succès")
                else:
                    print(f"Avertissement: Impossible de supprimer le salon Discord {journal.uid}")
            except Exception as e:
                print(f"Avertissement: Erreur suppression salon Discord {journal.uid}: {e}")
        
        # Supprimer le journal de la base de données
        script = f'DELETE FROM `Journaux` WHERE `id` = "{v_journalid}"'
        db.execute(script)
        db.commit()
        return True
    except Exception as e:
        print(f"Erreur lors de la suppression du journal {v_journalid}: {e}")
    return False

def delete_livre(db: Session, v_livreid: int):
    try:
        script = f'DELETE FROM `Livres` WHERE `id` = "{v_livreid}"'
        db.execute(script)
        db.commit()
        return True
    except Exception as e:
        print(f"Erreur lors de la suppression du livre {v_livreid}: {e}")
    return False


# ===============================================================================
# Update
# ===============================================================================
def update_user(db: Session, userID: int, v_user: schemas.updateUser):
    # Vérification de l'existence de l'utilisateur
    db_user = get_user(db, userID)

    if db_user:
        # Vérification des modifications
        if user_exist(db, v_user.username)[0]:
            v_user.username = None
        if user_exist(db, v_user.email)[0]:
            v_user.email = None

        # Mise à jour des informations
        db.execute(update(models.Users).where(models.Users.id == userID).values(
            username = (v_user.username if v_user.username is not None else db_user.username),
            email = (v_user.email if v_user.email is not None else db_user.email),
            hashed_password = (crudSecu.hash_password(v_user.password) if v_user.password is not None else db_user.hashed_password),
            pseudo = (v_user.pseudo if v_user.pseudo is not None else db_user.pseudo),
            image_url = (v_user.image_url if v_user.image_url is not None else db_user.image_url),
            is_disabled = (v_user.is_disabled if v_user.is_disabled is not None else db_user.is_disabled),
            is_admin = (v_user.is_admin if v_user.is_admin is not None else db_user.is_admin)
        ))
        db.commit()
        db.refresh(db_user)
        return get_read_user(db=db, ID=userID)
    return {"error": 404, "text": "L'utilisateur n'a pas été trouvé"}

def update_journal(db: Session, journalID: int, v_journal: schemas.Journal):
    # Vérification de l'existence du journal
    db_journal = get_journal(db, journalID)

    if db_journal:
        # Mise à jour des informations
        db.execute(update(models.Journaux).where(models.Journaux.id == journalID).values(
            user_id = (v_journal.user_id if v_journal.user_id is not None else db_journal.user_id),
            author = (v_journal.author if v_journal.author is not None else db_journal.author),
            title = (v_journal.title if v_journal.title is not None else db_journal.title),
            description = (v_journal.description if v_journal.description is not None else db_journal.description),
            cover_url = (v_journal.cover_url if v_journal.cover_url is not None else db_journal.cover_url),
            cover_icon = (v_journal.cover_icon if v_journal.cover_icon is not None else db_journal.cover_icon),
            cover_color = (v_journal.cover_color if v_journal.cover_color is not None else db_journal.cover_color),
            link = (v_journal.link if v_journal.link is not None else db_journal.link),
            uid = (v_journal.uid if v_journal.uid is not None else db_journal.uid),
            published_date = (v_journal.published_date if v_journal.published_date is not None else db_journal.published_date)
        ))
        db.commit()
        db.refresh(db_journal)
        return get_journal(db=db, ID=journalID)
    return {"error": 404, "text": "Le journal n'a pas été trouvé"}

def update_livre(db: Session, livreID: int, v_livre: schemas.Livre):
    # Vérification de l'existence du livre
    db_livre = get_livre(db, livreID)

    if db_livre:
        # Mise à jour des informations
        db.execute(update(models.Livres).where(models.Livres.id == livreID).values(
            user_id = (v_livre.user_id if v_livre.user_id is not None else db_livre.user_id),
            author = (v_livre.author if v_livre.author is not None else db_livre.author),
            title = (v_livre.title if v_livre.title is not None else db_livre.title),
            description = (v_livre.description if v_livre.description is not None else db_livre.description),
            cover_url = (v_livre.cover_url if v_livre.cover_url is not None else db_livre.cover_url),
            cover_icon = (v_livre.cover_icon if v_livre.cover_icon is not None else db_livre.cover_icon),
            cover_color = (v_livre.cover_color if v_livre.cover_color is not None else db_livre.cover_color),
            pages = (v_livre.pages if v_livre.pages is not None else db_livre.pages),
            language = (v_livre.language if v_livre.language is not None else db_livre.language),
            link = (v_livre.link if v_livre.link is not None else db_livre.link),
            published_date = (v_livre.published_date if v_livre.published_date is not None else db_livre.published_date)
        ))
        db.commit()
        db.refresh(db_livre)
        return get_livre(db=db, ID=livreID)
    return {"error": 404, "text": "Le livre n'a pas été trouvé"}
