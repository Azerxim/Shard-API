from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
import hashlib
import asyncio
import datetime as dt
import secrets
from . import discord_handler

from . import models, schemas
from .database import get_db
from topazdevsdk import colors

################# Security #####################

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/token")

# -----------------------------------------------
async def secu_get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)):
    user = secu_decode_token(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def secu_get_current_active_user(current_user: Annotated[schemas.Users, Depends(secu_get_current_user)]):
    if current_user.is_disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def secu_get_current_active_admin(current_user: Annotated[schemas.Users, Depends(secu_get_current_user)]):
    if current_user.is_disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    return current_user

# -----------------------------------------------
def hash_password(password: str):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def secu_decode_token(db: Session, token: str):
    now = dt.datetime.now()
    statement = select(models.ActiveSession).where(
        models.ActiveSession.access_token == token
    ).where(models.ActiveSession.expiry_time > now)
    session = db.exec(statement).first()
    if not session:
        return None
    return get_user_by_username(db, session.username)

def create_active_session(db: Session, username: str, expiry_hours: int = 24):
    """Crée une session active pour l'utilisateur, supprime les anciennes sessions"""
    # Supprimer les sessions précédentes de cet utilisateur
    old_sessions = db.exec(
        select(models.ActiveSession).where(models.ActiveSession.username == username)
    ).all()
    for s in old_sessions:
        db.delete(s)
    db.commit()

    token = secrets.token_hex(32)
    session = models.ActiveSession(
        username=username,
        access_token=token,
        expiry_time=dt.datetime.now() + dt.timedelta(hours=expiry_hours)
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

# def secu_get_user_by_username(db: Session, username: str):
#     statement = select(models.Users).where(models.Users.username == username).where(models.Users.is_disabled == False)
#     results = db.exec(statement)
#     return results.first()

# def secu_get_user_by_email(db: Session, email: str):
#     statement = select(models.Users).where(models.Users.email == email).where(models.Users.is_disabled == False)
#     results = db.exec(statement)
#     return results.first()

def loadsecurity(db: Session, json):
    # Gestion du password vide
    if json['password']=="":
        print(f"{colors.BColors.RED}ERROR{colors.BColors.END}:    Security load error, password null")
        return {"fonction": "loadsecurity", "erreur": 'Le mot de passe ne peut pas être vide'}
    try:
        user = get_user_by_username(db, json['username'])     
        user_dict = models.Users(
            username = json['username'],
            full_name = json['full_name'],
            email = json.get('email', json['username'] + '@admin.local'),
            hashed_password = hash_password(json['password']),
            is_admin = True,
            is_disabled = False,
            is_visible = False
        )
        if not user:
            db.add(user_dict)
            db.commit()
            db.refresh(user_dict)
            print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Utilisateur de sécurité créé")
            return {"result": 'Utilisateur de sécurité créé'}
        else:
            statement = select(models.Users).where(models.Users.username == user_dict.username)
            result = db.exec(statement).one()
            result.username = user_dict.username
            result.full_name = user_dict.full_name
            result.email = user_dict.email
            result.hashed_password = user_dict.hashed_password
            result.is_admin = True
            result.is_disabled = False
            result.is_visible = False
            db.add(result)
            db.commit()
            db.refresh(result)
            
            print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Utilisateur de sécurité modifié")
            return {"result": 'Utilisateur de sécurité modifié'}
    except:
        print(f"{colors.BColors.RED}ERROR{colors.BColors.END}:    Erreur lors du chargement de la sécurité")
        return {"fonction": "loadsecurity", "erreur": 'Erreur lors du chargement de la sécurité'}

    
############### Users #############

# ------------------------------------------ 
def check_user_from_name(db: Session, username, password):
    statement = select(models.Users).where(models.Users.username == username)
    results = db.exec(statement)
    result = results.first()
    if result is not None:
        user = build_user_read(result)
        if result.hashed_password == hash_password(password):
            return True, user
        return False, user
    return False, None

def check_user_from_email(db: Session, email, password):
    statement = select(models.Users).where(models.Users.email == email)
    results = db.exec(statement)
    result = results.first()
    if result is not None:
        user = build_user_read(result)
        if result.hashed_password == hash_password(password):
            return True, user
        return False, user
    return False, None

def check_user_all(db: Session, username, email, password):
    statement = select(models.Users).where(models.Users.username == username).where(models.Users.email == email)
    results = db.exec(statement)
    result = results.first()
    if result is not None:
        user = build_user_read(result)
        if result.hashed_password == hash_password(password):
            return True, user
        return False, user
    return False, None

# ------------------------------------------ 
def get_user_by_username(db: Session, username: str):
    statement = select(models.Users).where(models.Users.username == username)
    results = db.exec(statement)
    return results.first()

def get_user_by_email(db: Session, email: str):
    statement = select(models.Users).where(models.Users.email == email)
    results = db.exec(statement)
    return results.first()

def get_user_by_id(db: Session, user_id: int):
    statement = select(models.Users).where(models.Users.id == user_id)
    results = db.exec(statement)
    return results.first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    statement = select(models.Users).where(models.Users.is_disabled == False).where(models.Users.is_visible == True).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def build_user_read(user: models.Users):
    return schemas.UserRead(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        image_url=user.image_url,
        arrival=user.arrival,
        is_disabled=user.is_disabled,
        is_admin=user.is_admin,
        is_visible=user.is_visible,
        created_at=user.created_at
    )

def create_user(db: Session, user):
    db_user = models.Users(
        username=user.username,
        full_name=user.username,
        email=user.email,
        hashed_password=hash_password(user.password),
        is_admin=False,
        is_disabled=False,
        is_visible=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return build_user_read(db_user)

def update_user(db: Session, user_id: int, user_update: schemas.UserUpdate):
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    if user_update.username is not None:
        user.username = user_update.username
    if user_update.full_name is not None:
        user.full_name = user_update.full_name
    if user_update.email is not None:
        user.email = user_update.email
    if user_update.password is not None:
        user.hashed_password = hash_password(user_update.password)
    if user_update.is_disabled is not None:
        user.is_disabled = user_update.is_disabled
    if user_update.is_visible is not None:
        user.is_visible = user_update.is_visible
    if user_update.image_url is not None:
        user.image_url = user_update.image_url
    db.add(user)
    db.commit()
    db.refresh(user)
    return build_user_read(user)

def delete_user(db: Session, user_id: int):
    user = get_user_by_id(db, user_id)
    if not user:
        return {"fonction": "delete_user", "erreur": "L'utilisateur n'existe pas"}
    db.delete(user)
    db.commit()
    return {"fonction": "delete_user", "resultat": "Utilisateur supprimé"}

################# Bibliothèque #####################

# --------------- Journaux ---------------
def get_journaux(db: Session, skip: int = 0, limit: int = 100):
    statement = select(models.Journaux).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_journal(db: Session, ID: int):
    statement = select(models.Journaux).where(models.Journaux.id == ID)
    results = db.exec(statement)
    return results.first()

def get_journaux_by_user(db: Session, userID: int, skip: int = 0, limit: int = 100):
    statement = select(models.Journaux).where(models.Journaux.user_id == userID).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

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

def create_journal(db: Session, user: schemas.Users, v_journal: schemas.Journal):
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
        user_id = user.id,
        author = v_journal.author,
        title = v_journal.title,
        description = v_journal.description,
        cover_url = v_journal.cover_url,
        cover_icon = v_journal.cover_icon,
        cover_color = v_journal.cover_color,
        link = "",
        uid = channel_uid if channel_uid else v_journal.uid,
        published_date = v_journal.published_date,
        created_at = dt.datetime.today()
    )
    
    db.add(db_journal)
    db.commit()
    db.refresh(db_journal)
    db_journal.link = f"/bibliotheque/journal/{db_journal.id}"
    db.add(db_journal)
    db.commit()
    db.refresh(db_journal)
    return db_journal

def create_journal_db(db: Session, user: schemas.Users, v_journal: schemas.Journal):   
    db_journal = models.Journaux(
        user_id = user.id,
        author = v_journal.author,
        title = v_journal.title,
        description = v_journal.description,
        cover_url = v_journal.cover_url,
        cover_icon = v_journal.cover_icon,
        cover_color = v_journal.cover_color,
        link = v_journal.link,
        uid = v_journal.uid,
        published_date = v_journal.published_date,
        created_at = dt.datetime.today()
    )

    db.add(db_journal)
    db.commit()
    db.refresh(db_journal)
    return db_journal

def delete_journal(db: Session, user: schemas.Users, v_journalid: int):
    try:
        # Récupérer le journal pour obtenir son UID Discord
        journal = get_journal(db, v_journalid)

        # Vérifier de l'utilisateur actuel
        if user.id != journal.user_id and not user.is_admin and not user.is_disabled:
            raise HTTPException(status_code=403, detail="Accès refusé")

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
        journal = get_journal(db, v_journalid)
        db.delete(journal)
        db.commit()
        return {"fonction": "delete_journal", "resultat": "Journal supprimé"}
    except Exception as e:
        print(f"Erreur lors de la suppression du journal {v_journalid}: {e}")
        return {"fonction": "delete_journal", "erreur": "Une erreur est survenue lors de la suppression du journal", "details": str(e)}

def update_journal(db: Session, user: schemas.Users, journalID: int, v_journal: schemas.Journal):
    # Vérification de l'existence du journal
    db_journal = get_journal(db, journalID)

    # Vérifier de l'utilisateur actuel
    if user.id != db_journal.user_id and not user.is_admin and not user.is_disabled:
        raise HTTPException(status_code=403, detail="Accès refusé")

    if db_journal:
        # Mise à jour des informations
        if v_journal.title is not None:
            db_journal.title = v_journal.title
        if v_journal.author is not None:
            db_journal.author = v_journal.author
        if v_journal.description is not None:
            db_journal.description = v_journal.description
        if v_journal.cover_url is not None:
            db_journal.cover_url = v_journal.cover_url
        if v_journal.cover_icon is not None:
            db_journal.cover_icon = v_journal.cover_icon
        if v_journal.cover_color is not None:
            db_journal.cover_color = v_journal.cover_color
        if v_journal.published_date is not None:
            db_journal.published_date = v_journal.published_date
        if v_journal.is_public is not None:
            db_journal.is_public = v_journal.is_public
        db.add(db_journal)
        db.commit()
        db.refresh(db_journal)
        return get_journal(db=db, ID=journalID)
    return {"error": 404, "text": "Le journal n'a pas été trouvé"}

# --------------- Livres ---------------
def get_livres(db: Session, skip: int = 0, limit: int = 100):
    statement = select(models.Livres).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_livre(db: Session, ID: int):
    statement = select(models.Livres).where(models.Livres.id == ID)
    results = db.exec(statement)
    return results.first()

def get_livres_by_user(db: Session, userID: int, skip: int = 0, limit: int = 100):
    statement = select(models.Livres).where(models.Livres.user_id == userID).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def create_livre(db: Session, user: schemas.Users, v_livre: schemas.Livre):
    db_livre = models.Livres(
        user_id = user.id,
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

def delete_livre(db: Session, user: schemas.Users, livreID: int):
    try:
        livre = get_livre(db, livreID)

        # Vérifier de l'utilisateur actuel
        if user.id != livre.user_id and not user.is_admin and not user.is_disabled:
            raise HTTPException(status_code=403, detail="Accès refusé")
        
        db.delete(livre)
        db.commit()
        return {"fonction": "delete_livre", "resultat": "Livre supprimé"}
    except Exception as e:
        print(f"Erreur lors de la suppression du livre {livreID}: {e}")
        return {"fonction": "delete_livre", "erreur": "Une erreur est survenue lors de la suppression du livre", "details": str(e)}

################# Civilisations #####################

def get_civilisations(db: Session, skip: int = 0, limit: int = 100):
    statement = select(models.Civilisations).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_civilisation_by_id(db: Session, ID: int):
    statement = select(models.Civilisations).where(models.Civilisations.id == ID)
    results = db.exec(statement)
    return results.first()

def get_civilisation_by_title(db: Session, title: str):
    statement = select(models.Civilisations).where(models.Civilisations.title == title)
    results = db.exec(statement)
    return results.first()

def create_civilisation(db: Session, user: schemas.Users, v_civilisation: schemas.CivilisationCreate):
    db_civilisation = models.Civilisations(
        user_id=user.id,
        title = v_civilisation.title,
        description = v_civilisation.description,
        is_public = v_civilisation.is_public,
        created_at = dt.datetime.today()
    )
    
    db.add(db_civilisation)
    db.commit()
    db.refresh(db_civilisation)
    return db_civilisation

def delete_civilisation(db: Session, user: schemas.Users, civilisationID: int):
    # Vérification de l'existence de la civilisation
    db_civilisation = get_civilisation_by_id(db, civilisationID)

    # Vérifier de l'utilisateur actuel
    if user.id != db_civilisation.user_id and not user.is_admin and not user.is_disabled:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    try:
        db.delete(db_civilisation)
        db.commit()
        return {"fonction": "delete_civilisation", "resultat": "Civilisation supprimée"}
    except Exception as e:
        print(f"Erreur lors de la suppression de la civilisation {civilisationID}: {e}")
        return {"fonction": "delete_civilisation", "erreur": "Une erreur est survenue lors de la suppression de la civilisation", "details": str(e)}

    # script = ''
    # try:
    #     script += f'; DELETE FROM `Cartographie` WHERE `type` = "quartier" AND `type_id` IN (SELECT `id` FROM `Quartiers` WHERE `ville_id` IN (SELECT `id` FROM `Villes` WHERE `civilisation_id` = "{civilisationID}"))'
    #     script += f'; DELETE FROM `Cartographie` WHERE `type` = "ville" AND `type_id` IN (SELECT `id` FROM `Villes` WHERE `civilisation_id` = "{civilisationID}")'
    #     script += f'; DELETE FROM `Cartographie` WHERE `type` = "civilisation" AND `type_id` = "{civilisationID}"'
    #     script += f'; DELETE FROM `Gouvernements` WHERE `civilisation_id` = "{civilisationID}"'
    #     script += f'; DELETE FROM `Quartiers` WHERE `ville_id` IN (SELECT `id` FROM `Villes` WHERE `civilisation_id` = "{civilisationID}")'
    #     script += f'; DELETE FROM `Villes` WHERE `civilisation_id` = "{civilisationID}"'
    #     script += f'; DELETE FROM `CivilisationMembers` WHERE `civilisation_id` = "{civilisationID}"'
    #     script += f'; DELETE FROM `Civilisations` WHERE `id` = "{civilisationID}"'
    #     db.execute(script)
    #     db.commit()
    #     return True
    # except Exception as e:
    #     print(f"Erreur lors de la suppression de la civilisation {civilisationID}: {e}")
    # return False

def update_civilisation(db: Session, user: schemas.Users, civilisationID: int, v_civilisation: schemas.Civilisation):
    # Vérification de l'existence de la civilisation
    db_civilisation = get_civilisation_by_id(db, civilisationID)

    # Vérifier de l'utilisateur actuel
    if user.id != db_civilisation.user_id and not user.is_admin and not user.is_disabled:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    if db_civilisation:
        # Mise à jour des informations
        if v_civilisation.title is not None:
            db_civilisation.title = v_civilisation.title
        if v_civilisation.description is not None:
            db_civilisation.description = v_civilisation.description
        if v_civilisation.date_founded is not None:
            db_civilisation.date_founded = v_civilisation.date_founded
        if v_civilisation.is_public is not None:
            db_civilisation.is_public = v_civilisation.is_public
        db.add(db_civilisation)
        db.commit()
        db.refresh(db_civilisation)
        return get_civilisation_by_id(db=db, ID=civilisationID)
    return {"error": 404, "text": "La civilisation n'a pas été trouvée"}

# Gouvernements
# def get_gouvernements(db: Session, skip: int = 0, limit: int = 100):
#     statement = select(models.Gouvernements).offset(skip).limit(limit)
#     results = db.exec(statement)
#     return results.all()

# def get_gouvernement_by_id(db: Session, ID: int):
#     statement = select(models.Gouvernements).where(models.Gouvernements.id == ID)
#     results = db.exec(statement)
#     return results.first()

# def create_gouvernement(db: Session, v_gouvernement: schemas.GouvernementCreate):
#     db_gouvernement = models.Gouvernements(
#         civilisation_id = v_gouvernement.civilisation_id,
#         type = v_gouvernement.type,
#         description = v_gouvernement.description,
#         devise = v_gouvernement.devise,
#         hymne = v_gouvernement.hymne,
#         created_at = dt.datetime.today()
#     )
    
#     db.add(db_gouvernement)
#     db.commit()
#     db.refresh(db_gouvernement)
#     return db_gouvernement

# def delete_gouvernement(db: Session, v_gouvernementid: int):
#     try:
#         db_gouvernement = get_gouvernement_by_id(db, v_gouvernementid)
#         script = f'; UPDATE `Civilisations` SET `gouvernement_id` = NULL WHERE `id` = "{db_gouvernement.civilisation_id}"'
#         script += f'; DELETE FROM `Gouvernements` WHERE `id` = "{v_gouvernementid}"'
#         db.execute(script)
#         db.commit()
#         return True
#     except Exception as e:
#         print(f"Erreur lors de la suppression du gouvernement {v_gouvernementid}: {e}")
#     return False

# def update_gouvernement(db: Session, gouvernementID: int, v_gouvernement: schemas.Gouvernement):
#     # Vérification de l'existence du gouvernement
#     db_gouvernement = get_gouvernement_by_id(db, gouvernementID)

#     if db_gouvernement:
#         # Mise à jour des informations
#         if v_gouvernement.civilisation_id is not None:
#             db_gouvernement.civilisation_id = v_gouvernement.civilisation_id
#         if v_gouvernement.type is not None:
#             db_gouvernement.type = v_gouvernement.type
#         if v_gouvernement.description is not None:
#             db_gouvernement.description = v_gouvernement.description
#         if v_gouvernement.devices is not None:
#             db_gouvernement.devices = v_gouvernement.devices
#         if v_gouvernement.hymne is not None:
#             db_gouvernement.hymne = v_gouvernement.hymne
#         db.add(db_gouvernement)
#         db.commit()
#         db.refresh(db_gouvernement)
#         return get_gouvernement_by_id(db=db, ID=gouvernementID)
#     return {"error": 404, "text": "Le gouvernement n'a pas été trouvé"}

# Villes
# def get_villes(db: Session, skip: int = 0, limit: int = 100):
#     statement = select(models.Villes).offset(skip).limit(limit)
#     results = db.exec(statement)
#     return results.all()

# def get_ville_by_id(db: Session, ID: int):
#     statement = select(models.Villes).where(models.Villes.id == ID)
#     results = db.exec(statement)
#     return results.first()

# def get_villes_by_civilisation_id(db: Session, civilisationID: int, skip: int = 0, limit: int = 100):
#     statement = select(models.Villes).where(models.Villes.civilisation_id == civilisationID).offset(skip).limit(limit)
#     results = db.exec(statement)
#     return results.all()

# def create_ville(db: Session, v_ville: schemas.VilleCreate):
#     db_ville = models.Villes(
#         civilisation_id = v_ville.civilisation_id,
#         title = v_ville.title,
#         description = v_ville.description,
#         population = v_ville.population,
#         dimension_id = v_ville.dimension_id,
#         x = v_ville.x,
#         z = v_ville.z,
#         founded_date = v_ville.founded_date,
#         is_capital = v_ville.is_capital,
#         is_public = v_ville.is_public,
#         created_at = dt.datetime.today()
#     )
    
#     db.add(db_ville)
#     db.commit()
#     db.refresh(db_ville)
#     return db_ville

# def delete_ville(db: Session, v_villeid: int):
#     try:
#         script = f'; DELETE FROM `Cartographie` WHERE `type` = "quartier" AND `type_id` IN (SELECT `id` FROM `Quartiers` WHERE `ville_id` = "{v_villeid}")'
#         script += f'; DELETE FROM `Cartographie` WHERE `type` = "ville" AND `type_id` = "{v_villeid}"'
#         script += f'; DELETE FROM `Quartiers` WHERE `ville_id` = "{v_villeid}"'
#         script += f'; DELETE FROM `Villes` WHERE `id` = "{v_villeid}"'
#         db.execute(script)
#         db.commit()
#         return True
#     except Exception as e:
#         print(f"Erreur lors de la suppression de la ville {v_villeid}: {e}")
#     return False

# def update_ville(db: Session, villeID: int, v_ville: schemas.Ville):
#     # Vérification de l'existence de la ville
#     db_ville = get_ville_by_id(db, villeID)

#     if db_ville:
#         # Mise à jour des informations
#         if v_ville.civilisation_id is not None:
#             db_ville.civilisation_id = v_ville.civilisation_id
#         if v_ville.title is not None:
#             db_ville.title = v_ville.title
#         if v_ville.description is not None:
#             db_ville.description = v_ville.description
#         if v_ville.population is not None:
#             db_ville.population = v_ville.population
#         if v_ville.dimension_id is not None:
#             db_ville.dimension_id = v_ville.dimension_id
#         if v_ville.x is not None:
#             db_ville.x = v_ville.x
#         if v_ville.z is not None:
#             db_ville.z = v_ville.z
#         if v_ville.founded_date is not None:
#             db_ville.founded_date = v_ville.founded_date
#         if v_ville.is_capital is not None:
#             db_ville.is_capital = v_ville.is_capital
#         if v_ville.is_public is not None:
#             db_ville.is_public = v_ville.is_public
#         db.add(db_ville)
#         db.commit()
#         db.refresh(db_ville)
#         return get_ville_by_id(db=db, ID=villeID)
#     return {"error": 404, "text": "La ville n'a pas été trouvée"}

# Quartiers
# def get_quartiers(db: Session, skip: int = 0, limit: int = 100):
#     statement = select(models.Quartiers).offset(skip).limit(limit)
#     results = db.exec(statement)
#     return results.all()

# def get_quartier_by_id(db: Session, ID: int):
#     statement = select(models.Quartiers).where(models.Quartiers.id == ID)
#     results = db.exec(statement)
#     return results.first()

# def get_quartiers_by_ville_id(db: Session, villeID: int, skip: int = 0, limit: int = 100):
#     statement = select(models.Quartiers).where(models.Quartiers.ville_id == villeID).offset(skip).limit(limit)
#     results = db.exec(statement)
#     return results.all()

# def create_quartier(db: Session, v_quartier: schemas.QuartierCreate):
#     db_quartier = models.Quartiers(
#         ville_id = v_quartier.ville_id,
#         title = v_quartier.title,
#         description = v_quartier.description,
#         population = v_quartier.population,
#         x = v_quartier.x,
#         z = v_quartier.z,
#         founded_date = v_quartier.founded_date,
#         is_public = v_quartier.is_public,
#         created_at = dt.datetime.today()
#     )
    
#     db.add(db_quartier)
#     db.commit()
#     db.refresh(db_quartier)
#     return db_quartier

# def delete_quartier(db: Session, v_quartierid: int):
#     try:
#         script = f'; DELETE FROM `Cartographie` WHERE `type` = "quartier" AND `type_id` = "{v_quartierid}"'
#         script += f'; DELETE FROM `Quartiers` WHERE `id` = "{v_quartierid}"'
#         db.execute(script)
#         db.commit()
#         return True
#     except Exception as e:
#         print(f"Erreur lors de la suppression du quartier {v_quartierid}: {e}")
#     return False

# def update_quartier(db: Session, quartierID: int, v_quartier: schemas.Quartier):
#     # Vérification de l'existence du quartier
#     db_quartier = get_quartier_by_id(db, quartierID)

#     if db_quartier:
#         # Mise à jour des informations
#         if v_quartier.ville_id is not None:
#             db_quartier.ville_id = v_quartier.ville_id
#         if v_quartier.title is not None:
#             db_quartier.title = v_quartier.title
#         if v_quartier.description is not None:
#             db_quartier.description = v_quartier.description
#         if v_quartier.population is not None:
#             db_quartier.population = v_quartier.population
#         if v_quartier.x is not None:
#             db_quartier.x = v_quartier.x
#         if v_quartier.z is not None:
#             db_quartier.z = v_quartier.z
#         if v_quartier.founded_date is not None:
#             db_quartier.founded_date = v_quartier.founded_date
#         if v_quartier.is_public is not None:
#             db_quartier.is_public = v_quartier.is_public
#         db.add(db_quartier)
#         db.commit()
#         db.refresh(db_quartier)
#         return get_quartier_by_id(db=db, ID=quartierID)
#     return {"error": 404, "text": "Le quartier n'a pas été trouvé"}

################# Religions #####################

# def get_religions(db: Session, skip: int = 0, limit: int = 100):
#     statement = select(models.Religions).offset(skip).limit(limit)
#     results = db.exec(statement)
#     return results.all()

# def get_religion_by_id(db: Session, ID: int):
#     statement = select(models.Religions).where(models.Religions.id == ID)
#     results = db.exec(statement)
#     return results.first()

# def create_religion(db: Session, v_religion: schemas.ReligionCreate):
#     db_religion = models.Religions(
#         title = v_religion.title,
#         description = v_religion.description,
#         founder = v_religion.founder,
#         date_founded = v_religion.date_founded,
#         is_public = v_religion.is_public,
#         created_at = dt.datetime.today()
#     )
    
#     db.add(db_religion)
#     db.commit()
#     db.refresh(db_religion)
#     return db_religion

# def delete_religion(db: Session, v_religionid: int):
#     try:
#         script = f'UPDATE `Civilisations` SET `religion_id` = NULL WHERE `religion_id` = "{v_religionid}"'
#         script += f'; DELETE FROM `Religions` WHERE `id` = "{v_religionid}"'
#         db.execute(script)
#         db.commit()
#         return True
#     except Exception as e:
#         print(f"Erreur lors de la suppression de la religion {v_religionid}: {e}")
#     return False

# def update_religion(db: Session, religionID: int, v_religion: schemas.Religions):
#     # Vérification de l'existence de la religion
#     db_religion = get_religion_by_id(db, religionID)

#     if db_religion:
#         # Mise à jour des informations
#         if v_religion.title is not None:
#             db_religion.title = v_religion.title
#         if v_religion.description is not None:
#             db_religion.description = v_religion.description
#         if v_religion.founder is not None:
#             db_religion.founder = v_religion.founder
#         if v_religion.date_founded is not None:
#             db_religion.date_founded = v_religion.date_founded
#         if v_religion.is_public is not None:
#             db_religion.is_public = v_religion.is_public
#         db.add(db_religion)
#         db.commit()
#         db.refresh(db_religion)
#         return get_religion_by_id(db=db, ID=religionID)
#     return {"error": 404, "text": "La religion n'a pas été trouvée"}

################# Cartographie #####################

# Dimensions
# def get_dimensions(db: Session, skip: int = 0, limit: int = 100):
#     statement = select(models.Dimensions).offset(skip).limit(limit)
#     results = db.exec(statement)
#     return results.all()

# def get_dimension_by_id(db: Session, ID: int):
#     statement = select(models.Dimensions).where(models.Dimensions.id == ID)
#     results = db.exec(statement)
#     return results.first()

# def get_dimension_by_name(db: Session, name: str):
#     statement = select(models.Dimensions).where(models.Dimensions.title == name)
#     results = db.exec(statement)
#     return results.first()

# def get_dimensions_by_title(db: Session, title: str, skip: int = 0, limit: int = 100):
#     statement = select(models.Dimensions).where(models.Dimensions.title.like(f"%{title}%")).offset(skip).limit(limit)
#     results = db.exec(statement)
#     return results.all()

# def create_dimension(db: Session, v_dimension: schemas.DimensionCreate):
#     db_dimension = models.Dimensions(
#         title = v_dimension.title,
#         link = v_dimension.link,
#         description = v_dimension.description
#     )
    
#     db.add(db_dimension)
#     db.commit()
#     db.refresh(db_dimension)
#     return db_dimension

# def delete_dimension(db: Session, v_dimensionid: int):
#     try:
#         script = f'DELETE FROM `Dimensions` WHERE `id` = "{v_dimensionid}"'
#         db.execute(script)
#         db.commit()
#         return True
#     except Exception as e:
#         print(f"Erreur lors de la suppression de la dimension {v_dimensionid}: {e}")
#     return False

# def update_dimension(db: Session, dimensionID: int, v_dimension: schemas.Dimension):
#     # Vérification de l'existence de la dimension
#     db_dimension = get_dimension_by_id(db, dimensionID)

#     if db_dimension:
#         # Mise à jour des informations
#         if v_dimension.title is not None:
#             db_dimension.title = v_dimension.title
#         if v_dimension.link is not None:
#             db_dimension.link = v_dimension.link
#         if v_dimension.description is not None:
#             db_dimension.description = v_dimension.description
#         db.add(db_dimension)
#         db.commit()
#         db.refresh(db_dimension)
#         return get_dimension_by_id(db=db, ID=dimensionID)
#     return {"error": 404, "text": "La dimension n'a pas été trouvée"}

# Cartographie Markers
# def get_cartographies(db: Session, skip: int = 0, limit: int = 100):
#     statement = select(models.Cartographie).offset(skip).limit(limit)
#     results = db.exec(statement)
#     return results.all()

# def get_cartographie_by_id(db: Session, ID: int):
#     statement = select(models.Cartographie).where(models.Cartographie.id == ID)
#     results = db.exec(statement)
#     return results.first()

# def get_cartographies_by_dimension(db: Session, dimensionID: int, skip: int = 0, limit: int = 100):
#     statement = select(models.Cartographie).where(models.Cartographie.dimension_id == dimensionID).offset(skip).limit(limit)
#     results = db.exec(statement)
#     return results.all()

# def get_cartographies_by_type(db: Session, type: str, skip: int = 0, limit: int = 100):
#     statement = select(models.Cartographie).where(models.Cartographie.type == type).offset(skip).limit(limit)
#     results = db.exec(statement)
#     return results.all()

# def get_cartographies_by_type_and_dimension(db: Session, type: str, dimensionID: int, skip: int = 0, limit: int = 100):
#     statement = select(models.Cartographie).where(models.Cartographie.type == type).where(models.Cartographie.dimension_id == dimensionID).offset(skip).limit(limit)
#     results = db.exec(statement)
#     return results.all()

# def get_cartographies_type(db: Session):
#     types = ["civilisation", "ville", "quartier"]
#     return types

# def get_cartographies_by_types(db: Session, type: str, id: int, skip: int = 0, limit: int = 100):
#     statement = select(models.Cartographie).where(models.Cartographie.type == type).where(models.Cartographie.type_id == id).offset(skip).limit(limit)
#     results = db.exec(statement)
#     return results.all()

# def create_cartographie(db: Session, v_cartographie: schemas.CartographieCreate):
#     db_cartographie = models.Cartographie(
#         title = v_cartographie.title,
#         description = v_cartographie.description,
#         text = v_cartographie.text,
#         color = v_cartographie.color,
#         dimension_id = v_cartographie.dimension_id,
#         shape_type = v_cartographie.shape_type,
#         coordinates = v_cartographie.coordinates,
#         type = v_cartographie.type,
#         type_id = v_cartographie.type_id
#     )
    
#     db.add(db_cartographie)
#     db.commit()
#     db.refresh(db_cartographie)
#     return db_cartographie

# def delete_cartographie(db: Session, v_cartographieid: int):
#     try:
#         script = f"DELETE FROM `Cartographie` WHERE `id` = '{v_cartographieid}'"
#         db.execute(script)
#         db.commit()
#         return True
#     except Exception as e:
#         print(f"Erreur lors de la suppression de la cartographie {v_cartographieid}: {e}")
#     return False

# def update_cartographie(db: Session, cartographieID: int, v_cartographie: schemas.Cartographie):
#     # Vérification de l'existence de la cartographie
#     db_cartographie = get_cartographie_by_id(db, cartographieID)

#     if db_cartographie:
#         # Mise à jour des informations
#         if v_cartographie.title is not None:
#             db_cartographie.title = v_cartographie.title
#         if v_cartographie.description is not None:
#             db_cartographie.description = v_cartographie.description
#         if v_cartographie.text is not None:
#             db_cartographie.text = v_cartographie.text
#         if v_cartographie.color is not None:
#             db_cartographie.color = v_cartographie.color
#         if v_cartographie.type is not None:
#             db_cartographie.type = v_cartographie.type
#         if v_cartographie.type_id is not None:
#             db_cartographie.type_id = v_cartographie.type_id
#         if v_cartographie.dimension_id is not None:
#             db_cartographie.dimension_id = v_cartographie.dimension_id
#         if v_cartographie.shape_type is not None:
#             db_cartographie.shape_type = v_cartographie.shape_type
#         if v_cartographie.coordinates is not None:
#             db_cartographie.coordinates = v_cartographie.coordinates
#         db.add(db_cartographie)
#         db.commit()
#         db.refresh(db_cartographie)
#         return get_cartographie_by_id(db=db, ID=cartographieID)
#     return {"error": 404, "text": "La cartographie n'a pas été trouvée"}

################# Templates #####################

