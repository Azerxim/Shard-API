from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
import hashlib
import json
import os
import asyncio
import threading
import datetime as dt
import secrets
from ..integrations import discord_handler

from ..core import utils
from ..db import models, schemas
from . import crud_nettoyage
from ..db.database import get_db
from topazdevsdk import colors

#region Security
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
#endregion

#region Users
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
        is_moderateur=user.is_moderateur,
        is_visible=user.is_visible,
        created_at=user.created_at
    )

def create_user(db: Session, user):
    db_user = models.Users(
        username=user.username,
        full_name=(user.full_name or "").strip() or user.username,
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
    # Rôles : la route n'accepte ces champs que d'un administrateur
    if user_update.is_admin is not None:
        user.is_admin = user_update.is_admin
    if user_update.is_moderateur is not None:
        user.is_moderateur = user_update.is_moderateur
    db.add(user)
    db.commit()
    db.refresh(user)
    return build_user_read(user)

def delete_user(db: Session, user_id: int):
    user = get_user_by_id(db, user_id)
    if not user:
        return {"fonction": "delete_user", "erreur": "L'utilisateur n'existe pas"}
    # Un fondateur doit d'abord transmettre son rôle : sinon civilisation, religion ou commerce resteraient sans fondateur
    fondations = crud_nettoyage.fondations_utilisateur(db, user.id)
    if fondations:
        raise HTTPException(status_code=400, detail=f"Ce compte est encore fondateur de {', '.join(fondations)} : transférez d'abord ce rôle")
    crud_nettoyage.detacher_utilisateur(db, user)
    db.delete(user)
    db.commit()
    return {"fonction": "delete_user", "resultat": "Utilisateur supprimé"}
#endregion

################# Bibliothèque #####################

#region Journaux
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

def _channel_messages(channel_id: str, limit: int):
    # Tests : SHARD_FAKE_JOURNAL_MESSAGES désigne un fichier JSON { "<id du salon>": [messages] } lu à la place de Discord
    fake_file = os.environ.get("SHARD_FAKE_JOURNAL_MESSAGES")
    if fake_file:
        try:
            with open(fake_file, encoding="utf-8") as file:
                return (json.load(file).get(str(channel_id)) or [])[:limit]
        except FileNotFoundError:
            return []
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(discord_handler.get_channel_messages(channel_id, limit=limit))
    finally:
        loop.close()

def announce_discord(channel_key: str, content: str):
    # Annonce dans le salon platforms.discord.channels.<channel_key>, en tâche de fond : ne bloque ni ne fait échouer la requête.
    # Sans salon configuré, rien n'est envoyé. Tests : SHARD_FAKE_DISCORD_ANNOUNCEMENTS désigne un fichier (une annonce JSON par ligne).
    fake_file = os.environ.get("SHARD_FAKE_DISCORD_ANNOUNCEMENTS")
    if fake_file:
        with open(fake_file, "a", encoding="utf-8") as file:
            file.write(json.dumps({"channel": channel_key, "content": content}, ensure_ascii=False) + "\n")
        return True
    channel_id = ((utils.PLATFORMS.get("discord") or {}).get("channels") or {}).get(channel_key)
    if not channel_id:
        return False

    def send():
        try:
            asyncio.run(discord_handler.send_channel_message(str(channel_id), content))
        except Exception as error:
            print(f"Annonce Discord ({channel_key}) impossible : {error}")

    threading.Thread(target=send, daemon=True).start()
    return True

def get_channel_message(channel_id: str, message_id: str):
    # Un seul message du salon (association aux personnages) ; None s'il n'existe pas. Même simulation que ci-dessus.
    fake_file = os.environ.get("SHARD_FAKE_JOURNAL_MESSAGES")
    if fake_file:
        return next((message for message in _channel_messages(channel_id, limit=100000) if str(message.get("id")) == str(message_id)), None)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(discord_handler.get_channel_message(channel_id, message_id))
    finally:
        loop.close()

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
        messages = _channel_messages(journal.uid, limit=limit + skip)
        
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
                discord_handler.create_channel(v_journal.title, v_journal.description, category_uid)
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

def _check_owner_rights(user: schemas.Users, owner_id: int | None):
    # Auteur de la ressource ou administrateur du site, jamais un compte désactivé
    if user.is_disabled or not (user.is_admin or (owner_id is not None and owner_id == user.id)):
        raise HTTPException(status_code=403, detail="Accès refusé")

def _check_civilisation_rights(db: Session, user: schemas.Users, civilisationID: int | None):
    # Fondateur ou Admin de la civilisation, ou administrateur du site
    db_members = get_members_of_civilisation(db, civilisationID, limit=10000) if civilisationID else []
    _check_member_rights(user, db_members)

def delete_journal(db: Session, user: schemas.Users, v_journalid: int):
    # Récupérer le journal pour obtenir son UID Discord
    journal = get_journal(db, v_journalid)
    if not journal:
        raise HTTPException(status_code=404, detail="Le journal n'existe pas")
    _check_owner_rights(user, journal.user_id)

    try:
        if journal.uid:
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
        crud_nettoyage.supprimer_liens_journal(db, v_journalid)
        db.delete(journal)
        db.commit()
        return {"fonction": "delete_journal", "resultat": "Journal supprimé"}
    except Exception as e:
        print(f"Erreur lors de la suppression du journal {v_journalid}: {e}")
        return {"fonction": "delete_journal", "erreur": "Une erreur est survenue lors de la suppression du journal", "details": str(e)}

async def update_journal(db: Session, user: schemas.Users, journalID: int, v_journal: schemas.Journal):
    # Vérification de l'existence du journal
    db_journal = get_journal(db, journalID)
    if not db_journal:
        raise HTTPException(status_code=404, detail="Le journal n'existe pas")
    _check_owner_rights(user, db_journal.user_id)

    if db_journal:
        # Mise à jour des informations
        if v_journal.title is not None:
            db_journal.title = v_journal.title
            await discord_handler.update_channel_name(db_journal.uid, v_journal.title)
        if v_journal.author is not None:
            db_journal.author = v_journal.author
        if v_journal.description is not None:
            db_journal.description = v_journal.description
            await discord_handler.update_channel_description(db_journal.uid, v_journal.description)
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
#endregion

#region Livres
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

def get_livres_by_civilisation(db: Session, civilisationID: int, skip: int = 0, limit: int = 100):
    statement = select(models.Livres).where(models.Livres.civilisation_id == civilisationID).offset(skip).limit(limit)
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
        civilisation_id = v_livre.civilisation_id,
        published_date = v_livre.published_date,
        created_at = dt.datetime.today()
    )
    
    db.add(db_livre)
    db.commit()
    db.refresh(db_livre)
    db_livre.link = f"/bibliotheque/livre/{db_livre.id}"
    db.add(db_livre)
    db.commit()
    db.refresh(db_livre)
    return db_livre

def _check_livre_rights(db: Session, user: schemas.Users, livre: models.Livres):
    # Mêmes règles que LivreDetail côté ShardUI-2 : livre d'une civilisation -> Fondateur ou Admin
    # de la civilisation ; sinon -> son auteur. L'administrateur du site a toujours accès.
    if livre.civilisation_id:
        _check_civilisation_rights(db, user, livre.civilisation_id)
    else:
        _check_owner_rights(user, livre.user_id)

def delete_livre(db: Session, user: schemas.Users, livreID: int):
    livre = get_livre(db, livreID)
    if not livre:
        raise HTTPException(status_code=404, detail="Le livre n'existe pas")
    _check_livre_rights(db, user, livre)

    try:
        # Suppression du livre
        
        db.delete(livre)
        db.commit()
        return {"fonction": "delete_livre", "resultat": "Livre supprimé"}
    except Exception as e:
        print(f"Erreur lors de la suppression du livre {livreID}: {e}")
        return {"fonction": "delete_livre", "erreur": "Une erreur est survenue lors de la suppression du livre", "details": str(e)}
    
def update_livre(db: Session, user: schemas.Users, livreID: int, v_livre: schemas.Livre):
    # Vérification de l'existence du livre
    db_livre = get_livre(db, livreID)
    if not db_livre:
        raise HTTPException(status_code=404, detail="Le livre n'existe pas")
    _check_livre_rights(db, user, db_livre)
    # Rattacher le livre à une autre civilisation demande aussi des droits sur celle-ci
    if v_livre.civilisation_id and v_livre.civilisation_id != db_livre.civilisation_id:
        _check_civilisation_rights(db, user, v_livre.civilisation_id)

    if db_livre:
        # Mise à jour des informations
        if v_livre.title is not None:
            db_livre.title = v_livre.title
        if v_livre.author is not None:
            db_livre.author = v_livre.author
        if v_livre.description is not None:
            db_livre.description = v_livre.description
        if v_livre.cover_url is not None:
            db_livre.cover_url = v_livre.cover_url
        if v_livre.cover_icon is not None:
            db_livre.cover_icon = v_livre.cover_icon
        if v_livre.cover_color is not None:
            db_livre.cover_color = v_livre.cover_color
        if v_livre.pages is not None:
            db_livre.pages = v_livre.pages
        if v_livre.language is not None:
            db_livre.language = v_livre.language
        if v_livre.link is not None:
            db_livre.link = v_livre.link
        if v_livre.civilisation_id is not None:
            db_livre.civilisation_id = v_livre.civilisation_id
        if v_livre.published_date is not None:
            db_livre.published_date = v_livre.published_date
        if v_livre.is_public is not None:
            db_livre.is_public = v_livre.is_public
        db.add(db_livre)
        db.commit()
        db.refresh(db_livre)
        return get_livre(db=db, ID=livreID)
    return {"error": 404, "text": "Le livre n'a pas été trouvé"}

def get_livre_contenu(db: Session, ID: int):
    statement = select(models.LivresContenus).where(models.LivresContenus.id == ID)
    results = db.exec(statement)
    return results.first()

def get_livre_contenus(db: Session, livreID: int):
    statement = select(models.LivresContenus).where(models.LivresContenus.livre_id == livreID)
    results = db.exec(statement)
    return results.all()

def create_livre_contenu(db: Session, user: schemas.Users, v_livre: schemas.LivreContenu):
    db_livre = get_livre(db, v_livre.livre_id)
    if not db_livre:
        raise HTTPException(status_code=404, detail="Le livre n'existe pas")
    _check_livre_rights(db, user, db_livre)

    last_ordre_livre = db.exec(
        select(models.LivresContenus).where(models.LivresContenus.livre_id == v_livre.livre_id).order_by(models.LivresContenus.ordre.desc())
    ).first()

    db_livre_contenu = models.LivresContenus(
        livre_id = v_livre.livre_id,
        chapitre = v_livre.chapitre,
        sous_chapitre = v_livre.sous_chapitre,
        ordre= last_ordre_livre.ordre + 1 if last_ordre_livre else 0,
        indent= v_livre.indent,
        content = v_livre.content,
        page_number = v_livre.page_number
    )

    db.add(db_livre_contenu)
    db.commit()
    db.refresh(db_livre_contenu)
    return db_livre_contenu

def delete_livre_contenu(db: Session, user: schemas.Users, contenuID: int):
    contenu = get_livre_contenu(db, contenuID)
    if not contenu:
        raise HTTPException(status_code=404, detail="Le contenu n'existe pas")
    livre = get_livre(db, contenu.livre_id)
    if not livre:
        raise HTTPException(status_code=404, detail="Le livre n'existe pas")
    _check_livre_rights(db, user, livre)

    try:
        # Suppression du contenu
        
        db.delete(contenu)
        db.commit()
        return {"fonction": "delete_livre_contenu", "resultat": "Contenu supprimé"}
    except Exception as e:
        print(f"Erreur lors de la suppression du contenu {contenuID}: {e}")
        return {"fonction": "delete_livre_contenu", "erreur": "Une erreur est survenue lors de la suppression du contenu", "details": str(e)}
    
def update_livre_contenu(db: Session, user: schemas.Users, contenuID: int, v_livre: schemas.LivreContenu):
    # Vérification de l'existence du livre
    db_contenu = get_livre_contenu(db, contenuID)
    if not db_contenu:
        raise HTTPException(status_code=404, detail="Le contenu n'existe pas")
    db_livre = get_livre(db, db_contenu.livre_id)
    if not db_livre:
        raise HTTPException(status_code=404, detail="Le livre n'existe pas")
    _check_livre_rights(db, user, db_livre)
    # Déplacer le contenu vers un autre livre demande aussi des droits sur celui-ci
    if v_livre.livre_id is not None and v_livre.livre_id != db_contenu.livre_id:
        target_livre = get_livre(db, v_livre.livre_id)
        if not target_livre:
            raise HTTPException(status_code=404, detail="Le livre n'existe pas")
        _check_livre_rights(db, user, target_livre)

    if db_contenu:
        # Mise à jour des informations
        if v_livre.livre_id is not None:
            db_contenu.livre_id = v_livre.livre_id
        if v_livre.chapitre is not None:
            db_contenu.chapitre = v_livre.chapitre
        if v_livre.sous_chapitre is not None:
            db_contenu.sous_chapitre = v_livre.sous_chapitre
        if v_livre.ordre is not None:
            db_contenu.ordre = v_livre.ordre
        if v_livre.indent is not None:
            db_contenu.indent = v_livre.indent
        if v_livre.content is not None:
            db_contenu.content = v_livre.content
        if v_livre.page_number is not None:
            db_contenu.page_number = v_livre.page_number
        db.add(db_contenu)
        db.commit()
        db.refresh(db_contenu)
        return get_livre_contenu(db=db, ID=contenuID)
    return {"error": 404, "text": "Le contenu n'a pas été trouvé"}
#endregion

################# Civilisations #####################
#region Civilisations

def get_civilisations(db: Session, skip: int = 0, limit: int = 100):
    statement = select(models.Civilisations).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_members_of_civilisation(db: Session, civilisationID: int, skip: int = 0, limit: int = 100):
    statement = select(models.CivilisationMembers).where(models.CivilisationMembers.civilisation_id == civilisationID).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_member_of_civilisation(db: Session, civilisationID: int, userID: int):
    statement = select(models.CivilisationMembers).where(
        models.CivilisationMembers.civilisation_id == civilisationID,
        models.CivilisationMembers.user_id == userID
    )
    results = db.exec(statement)
    return results.first()

def get_civilisation_by_id(db: Session, ID: int):
    statement = select(models.Civilisations).where(models.Civilisations.id == ID)
    results = db.exec(statement)
    return results.first()

def get_civilisation_by_title(db: Session, title: str):
    statement = select(models.Civilisations).where(models.Civilisations.title == title)
    results = db.exec(statement)
    return results.first()

def get_dirigees_of_civilisation(db: Session, civilisationID: int, skip: int = 0, limit: int = 100):
    statement = select(models.Civilisations).where(models.Civilisations.dirigeante_civilisation_id == civilisationID).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_all_of_civilisation_by_id(db: Session, ID: int):
    statement = select(models.Civilisations).where(models.Civilisations.id == ID)
    results = db.exec(statement)
    civ = results.first()
    if not civ:
        return None
    
    villes = get_villes_by_civilisation_id(db, civ.id)
    gouvernement = get_gouvernement_by_id(db, civ.gouvernement_id) if civ.gouvernement_id else None
    members = get_members_of_civilisation(db=db, civilisationID=civ.id)
    members_table = []
    villes_table = []
    for ville in villes:
        villeReligions = get_religions_by_ville_id(db=db, villeID=ville.id)
        villes_table.append({
            "id": ville.id,
            "title": ville.title,
            "description": ville.description,
            "population": ville.population,
            "founded_date": ville.founded_date,
            "dimension_id": ville.dimension_id,
            "x": ville.x,
            "z": ville.z,
            "is_public": ville.is_public,
            "is_capital": ville.is_capital,
            "created_at": ville.created_at,
            "civilisation_id": ville.civilisation_id,
            "religions": villeReligions if villeReligions else []
        })
    for member in members:
        user = get_user_by_id(db=db, user_id=member.user_id)
        members_table.append({
            "user_id": member.user_id,
            "role": member.role,
            "joined_at": member.joined_at,
            "username": user.username if user else None
        })
    civ_all = {
        'civilisation': civ,
        'members': members_table if members_table else [],
        'gouvernement': gouvernement if gouvernement else None,
        'villes': villes_table if villes_table else [],
    }
    return civ_all

def create_civilisation(db: Session, user: schemas.Users, v_civilisation: schemas.CivilisationCreate):
    db_civilisation = models.Civilisations(
        title = v_civilisation.title,
        description = v_civilisation.description,
        date_founded = v_civilisation.date_founded,
        is_public = v_civilisation.is_public,
        is_civilisation_dirigeante = v_civilisation.is_civilisation_dirigeante,
        dirigeante_civilisation_id = v_civilisation.dirigeante_civilisation_id,
        created_at = dt.datetime.today()
    )
    
    db.add(db_civilisation)
    db.commit()
    db.refresh(db_civilisation)  # Rafraîchir pour obtenir l'ID généré

    db_member = models.CivilisationMembers(
        user_id=user.id,
        civilisation_id=db_civilisation.id,
        role="Fondateur",
        joined_at=dt.datetime.today()
    )

    db.add(db_member)
    db.commit()
    db.refresh(db_member)

    db_gouv = models.Gouvernements(
        civilisation_id=db_civilisation.id,
        title=f"Gouvernement de {v_civilisation.title}",
        description=f"Gouvernement de la civilisation {v_civilisation.title}",
        created_at=dt.datetime.today(),
        type="Primitif",
    )
    db.add(db_gouv)
    db.commit()
    db.refresh(db_gouv)
    db_civilisation.gouvernement_id = db_gouv.id
    db.add(db_civilisation)
    db.commit()

    return get_civilisation_by_id(db=db, ID=db_civilisation.id), db_member, db_gouv

def delete_civilisation(db: Session, user: schemas.Users, civilisationID: int):
    # Vérification de l'existence de la civilisation
    db_civilisation = get_civilisation_by_id(db, civilisationID)
    if not db_civilisation:
        raise HTTPException(status_code=404, detail="La civilisation n'existe pas")
    _check_civilisation_rights(db, user, civilisationID)
    db_members = get_members_of_civilisation(db, civilisationID, limit=10000)
    db_gouvernement = get_gouvernement_by_id(db, db_civilisation.gouvernement_id) if db_civilisation.gouvernement_id else None
    
    try:
        # Villes et quartiers disparaissent avec la civilisation ; alliances, guerres, personnages… sont détachés
        for db_ville in get_villes_by_civilisation_id(db, civilisationID, limit=10000):
            _delete_ville_tree(db, db_ville)
        crud_nettoyage.detacher_civilisation(db, civilisationID, db_civilisation.title)
        delete_cartographies_by_types(db, "civilisation", civilisationID)
        db.delete(db_civilisation)
        for member in db_members:
            db.delete(member)
        if db_gouvernement:
            db.delete(db_gouvernement)
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
    if not db_civilisation:
        raise HTTPException(status_code=404, detail="La civilisation n'existe pas")

    # print(f"Updating civilisation {civilisationID} with values: {v_civilisation}")

    _check_civilisation_rights(db, user, civilisationID)
    
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
        if v_civilisation.gouvernement_id is not None:
            db_civilisation.gouvernement_id = v_civilisation.gouvernement_id
        if v_civilisation.is_civilisation_dirigeante is not None:
            db_civilisation.is_civilisation_dirigeante = v_civilisation.is_civilisation_dirigeante
            if v_civilisation.is_civilisation_dirigeante:
                db_civilisation.dirigeante_civilisation_id = 0
        if v_civilisation.dirigeante_civilisation_id is not None:
            db_civilisation.dirigeante_civilisation_id = v_civilisation.dirigeante_civilisation_id
        db.add(db_civilisation)
        db.commit()
        db.refresh(db_civilisation)
        return get_civilisation_by_id(db=db, ID=civilisationID)
    return {"error": 404, "text": "La civilisation n'a pas été trouvée"}

def add_member_to_civilisation(db: Session, user: schemas.Users, civilisationID: int, new_member_id: int, role: str):
    # Vérification de l'existence de la civilisation
    db_civilisation = get_civilisation_by_id(db, civilisationID)
    if not db_civilisation:
        return {"fonction": "add_member_to_civilisation", "erreur": "La civilisation n'existe pas"}
    _check_civilisation_rights(db, user, civilisationID)
    
    # Le rôle de Fondateur ne s'obtient que par transfert
    if role == "Fondateur":
        raise HTTPException(status_code=400, detail="Utiliser le transfert pour changer de fondateur")
    if get_member_of_civilisation(db, civilisationID, new_member_id):
        raise HTTPException(status_code=400, detail="Cet utilisateur est déjà membre de la civilisation")

    try:
        db_member = models.CivilisationMembers(
            user_id=new_member_id,
            civilisation_id=civilisationID,
            role=role,
            joined_at=dt.datetime.today()
        )
        db.add(db_member)
        db.commit()
        db.refresh(db_member)
        return {"fonction": "add_member_to_civilisation", "resultat": "Membre ajouté", "member": db_member}
    except Exception as e:
        print(f"Erreur lors de l'ajout du membre {new_member_id} à la civilisation {civilisationID}: {e}")
        return {"fonction": "add_member_to_civilisation", "erreur": "Une erreur est survenue lors de l'ajout du membre à la civilisation", "details": str(e)}
    
def remove_member_from_civilisation(db: Session, user: schemas.Users, civilisationID: int, member_id: int):
    # Vérification de l'existence de la civilisation
    db_civilisation = get_civilisation_by_id(db, civilisationID)
    if not db_civilisation:
        return {"fonction": "remove_member_from_civilisation", "erreur": "La civilisation n'existe pas"}
    _check_civilisation_rights(db, user, civilisationID)
    
    # Le fondateur ne peut pas être retiré : transférer d'abord la civilisation
    target = get_member_of_civilisation(db, civilisationID, member_id)
    if target and target.role == "Fondateur":
        raise HTTPException(status_code=400, detail="Le fondateur ne peut pas être retiré : transférer d'abord la civilisation")

    try:
        member = db.exec(
            select(models.CivilisationMembers).where(
                models.CivilisationMembers.civilisation_id == civilisationID,
                models.CivilisationMembers.user_id == member_id
            )
        ).first()
        if member:
            db.delete(member)
            db.commit()
            return {"fonction": "remove_member_from_civilisation", "resultat": "Membre retiré"}
        else:
            return {"fonction": "remove_member_from_civilisation", "erreur": "Le membre n'est pas dans la civilisation"}
    except Exception as e:
        print(f"Erreur lors du retrait du membre {member_id} de la civilisation {civilisationID}: {e}")
        return {"fonction": "remove_member_from_civilisation", "erreur": "Une erreur est survenue lors du retrait du membre de la civilisation", "details": str(e)}
    
def update_member_of_civilisation(db: Session, user: schemas.Users, civilisationID: int, member_id: int, member: schemas.CivilisationMemberUpdate):
    # Vérification de l'existence de la civilisation
    db_civilisation = get_civilisation_by_id(db, civilisationID)
    if not db_civilisation:
        return {"fonction": "update_member_of_civilisation", "erreur": "La civilisation n'existe pas"}
    _check_civilisation_rights(db, user, civilisationID)
    
    # Le rôle de Fondateur ne se modifie que par transfert
    target = get_member_of_civilisation(db, civilisationID, member_id)
    if (target and target.role == "Fondateur") or member.role == "Fondateur":
        raise HTTPException(status_code=400, detail="Utiliser le transfert pour changer de fondateur")

    try:
        db_member = db.exec(
            select(models.CivilisationMembers).where(
                models.CivilisationMembers.civilisation_id == civilisationID,
                models.CivilisationMembers.user_id == member_id
            )
        ).first()

        if db_member:
            # Mise à jour des informations
            if member.role is not None:
                db_member.role = member.role
            db.add(db_member)
            db.commit()
            db.refresh(db_member)
            return {"fonction": "update_member_of_civilisation", "resultat": "Membre mis à jour", "member": db_member}
        return {"fonction": "update_member_of_civilisation", "erreur": "Le membre n'est pas dans la civilisation"}
    except Exception as e:
        print(f"Erreur lors de la mise à jour du membre {member_id} de la civilisation {civilisationID}: {e}")
        return {"fonction": "update_member_of_civilisation", "erreur": "Une erreur est survenue lors de la mise à jour du membre de la civilisation", "details": str(e)}

def transfer_founder_of_civilisation(db: Session, user: schemas.Users, civilisationID: int, new_founder_id: int, former_role: str = "Admin"):
    db_civilisation = get_civilisation_by_id(db, civilisationID)
    if not db_civilisation:
        raise HTTPException(status_code=404, detail="La civilisation n'existe pas")

    db_members = get_members_of_civilisation(db, civilisationID, limit=10000)
    db_founder = next((member for member in db_members if member.role == "Fondateur"), None)

    # Seul le fondateur actuel ou un administrateur du site peut transférer
    if not user.is_admin and (db_founder is None or db_founder.user_id != user.id):
        raise HTTPException(status_code=403, detail="Seul le fondateur ou un administrateur peut transférer la civilisation")

    if former_role not in ("Admin", "Membre"):
        raise HTTPException(status_code=400, detail="Le rôle de l'ancien fondateur doit être \"Admin\" ou \"Membre\"")
    if not get_user_by_id(db=db, user_id=new_founder_id):
        raise HTTPException(status_code=404, detail="L'utilisateur n'existe pas")
    if db_founder and db_founder.user_id == new_founder_id:
        raise HTTPException(status_code=400, detail="Cet utilisateur est déjà le fondateur de la civilisation")

    # L'ancien fondateur reste membre avec le rôle choisi
    if db_founder:
        db_founder.role = former_role
        db.add(db_founder)

    # Le nouveau fondateur est ajouté à la civilisation s'il n'en est pas encore membre
    db_new_founder = get_member_of_civilisation(db, civilisationID, new_founder_id)
    if db_new_founder:
        db_new_founder.role = "Fondateur"
    else:
        db_new_founder = models.CivilisationMembers(
            user_id=new_founder_id,
            civilisation_id=civilisationID,
            role="Fondateur",
            joined_at=dt.datetime.today()
        )
    db.add(db_new_founder)
    db.commit()

    return get_members_of_civilisation(db, civilisationID, limit=10000)
#endregion

#region Gouvernements
def get_gouvernements(db: Session, skip: int = 0, limit: int = 100):
    statement = select(models.Gouvernements).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_gouvernement_by_id(db: Session, ID: int):
    statement = select(models.Gouvernements).where(models.Gouvernements.id == ID)
    results = db.exec(statement)
    return results.first()

def create_gouvernement(db: Session, user: schemas.Users, v_gouvernement: schemas.GouvernementCreate):
    _check_civilisation_rights(db, user, v_gouvernement.civilisation_id)
    db_gouvernement = models.Gouvernements(
        civilisation_id = v_gouvernement.civilisation_id,
        title = v_gouvernement.title,
        type = v_gouvernement.type,
        description = v_gouvernement.description,
        devise = v_gouvernement.devise,
        hymne = v_gouvernement.hymne,
        created_at = dt.datetime.today()
    )
    
    db.add(db_gouvernement)
    db.commit()
    db.refresh(db_gouvernement)
    return db_gouvernement

def delete_gouvernement(db: Session, user: schemas.Users, v_gouvernementid: int):
    db_gouvernement = get_gouvernement_by_id(db, v_gouvernementid)
    if not db_gouvernement:
        raise HTTPException(status_code=404, detail="Le gouvernement n'existe pas")
    _check_civilisation_rights(db, user, db_gouvernement.civilisation_id)
    db_civilisation = get_civilisation_by_id(db, db_gouvernement.civilisation_id) if db_gouvernement.civilisation_id else None
    try:
        if db_civilisation:
            db_civilisation.gouvernement_id = None
            db.add(db_civilisation)
        db.delete(db_gouvernement)
        db.commit()
        return {"fonction": "delete_gouvernement", "resultat": "Gouvernement supprimé"}
    except Exception as e:
        print(f"Erreur lors de la suppression du gouvernement {v_gouvernementid}: {e}")
        return {"fonction": "delete_gouvernement", "erreur": "Une erreur est survenue lors de la suppression du gouvernement", "details": str(e)}

def update_gouvernement(db: Session, user: schemas.Users, gouvernementID: int, v_gouvernement: schemas.GouvernementCreate):
    # Vérification de l'existence du gouvernement
    db_gouvernement = get_gouvernement_by_id(db, gouvernementID)
    if not db_gouvernement:
        raise HTTPException(status_code=404, detail="Le gouvernement n'existe pas")
    _check_civilisation_rights(db, user, db_gouvernement.civilisation_id)
    # Rattacher le gouvernement à une autre civilisation demande aussi des droits sur celle-ci
    if v_gouvernement.civilisation_id is not None and v_gouvernement.civilisation_id != db_gouvernement.civilisation_id:
        _check_civilisation_rights(db, user, v_gouvernement.civilisation_id)

    if db_gouvernement:
        # Mise à jour des informations
        if v_gouvernement.civilisation_id is not None:
            db_gouvernement.civilisation_id = v_gouvernement.civilisation_id
        if v_gouvernement.type is not None:
            db_gouvernement.type = v_gouvernement.type
        if v_gouvernement.description is not None:
            db_gouvernement.description = v_gouvernement.description
        if v_gouvernement.devise is not None:
            db_gouvernement.devise = v_gouvernement.devise
        if v_gouvernement.hymne is not None:
            db_gouvernement.hymne = v_gouvernement.hymne
        db.add(db_gouvernement)
        db.commit()
        db.refresh(db_gouvernement)
        return get_gouvernement_by_id(db=db, ID=gouvernementID)
    return {"error": 404, "text": "Le gouvernement n'a pas été trouvé"}

#endregion

#region Villes
def get_villes(db: Session, skip: int = 0, limit: int = 100):
    statement = select(models.Villes).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_ville_by_id(db: Session, ID: int):
    statement = select(models.Villes).where(models.Villes.id == ID)
    results = db.exec(statement)
    return results.first()

def get_villes_by_civilisation_id(db: Session, civilisationID: int, skip: int = 0, limit: int = 100):
    statement = select(models.Villes).where(models.Villes.civilisation_id == civilisationID).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_villes_by_dimension_id(db: Session, dimensionID: int, skip: int = 0, limit: int = 100):
    statement = select(models.Villes).where(models.Villes.dimension_id == dimensionID).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def create_ville(db: Session, user: schemas.Users, v_ville: schemas.VilleCreate):
    if not get_civilisation_by_id(db, v_ville.civilisation_id):
        raise HTTPException(status_code=404, detail="La civilisation n'existe pas")
    _check_civilisation_rights(db, user, v_ville.civilisation_id)
    db_ville = models.Villes(
        civilisation_id = v_ville.civilisation_id,
        title = v_ville.title,
        description = v_ville.description,
        population = v_ville.population,
        dimension_id = v_ville.dimension_id,
        x = v_ville.x,
        z = v_ville.z,
        founded_date = v_ville.founded_date,
        is_capital = v_ville.is_capital,
        is_public = v_ville.is_public,
        created_at = dt.datetime.today()
    )
    
    db.add(db_ville)
    db.commit()
    db.refresh(db_ville)
    return db_ville

def _delete_ville_tree(db: Session, db_ville: models.Villes):
    # Ville, quartiers et leurs dépendances ; le commit reste à l'appelant
    for quartier in get_quartiers_by_ville_id(db, db_ville.id, limit=10000):
        _delete_quartier_dependencies(db, quartier.id)
        db.delete(quartier)
    delete_cartographies_by_types(db, "ville", db_ville.id)
    crud_nettoyage.detacher_ville(db, db_ville.id)
    db.delete(db_ville)

def delete_ville(db: Session, user: schemas.Users, v_villeid: int):
    db_ville = get_ville_by_id(db, v_villeid)
    if not db_ville:
        raise HTTPException(status_code=404, detail="La ville n'existe pas")
    _check_civilisation_rights(db, user, db_ville.civilisation_id)
    try:
        _delete_ville_tree(db, db_ville)
        db.commit()
        return {"fonction": "delete_ville", "resultat": "Ville supprimée"}
        # script = f'; DELETE FROM `Cartographie` WHERE `type` = "quartier" AND `type_id` IN (SELECT `id` FROM `Quartiers` WHERE `ville_id` = "{v_villeid}")'
        # script += f'; DELETE FROM `Cartographie` WHERE `type` = "ville" AND `type_id` = "{v_villeid}"'
        # script += f'; DELETE FROM `Quartiers` WHERE `ville_id` = "{v_villeid}"'
        # script += f'; DELETE FROM `Villes` WHERE `id` = "{v_villeid}"'
    except Exception as e:
        print(f"Erreur lors de la suppression de la ville {v_villeid}: {e}")
        return {"fonction": "delete_ville", "erreur": "Une erreur est survenue lors de la suppression de la ville", "details": str(e)}

def update_ville(db: Session, user: schemas.Users, villeID: int, v_ville: schemas.Ville):
    # Vérification de l'existence de la ville
    db_ville = get_ville_by_id(db, villeID)
    if not db_ville:
        raise HTTPException(status_code=404, detail="La ville n'existe pas")
    _check_civilisation_rights(db, user, db_ville.civilisation_id)
    # Déplacer la ville vers une autre civilisation demande aussi des droits sur celle-ci
    if v_ville.civilisation_id is not None and v_ville.civilisation_id != db_ville.civilisation_id:
        if not get_civilisation_by_id(db, v_ville.civilisation_id):
            raise HTTPException(status_code=404, detail="La civilisation n'existe pas")
        _check_civilisation_rights(db, user, v_ville.civilisation_id)

    if db_ville:
        # Mise à jour des informations
        if v_ville.civilisation_id is not None:
            db_ville.civilisation_id = v_ville.civilisation_id
        if v_ville.title is not None:
            db_ville.title = v_ville.title
        if v_ville.description is not None:
            db_ville.description = v_ville.description
        if v_ville.population is not None:
            db_ville.population = v_ville.population
        if v_ville.dimension_id is not None:
            db_ville.dimension_id = v_ville.dimension_id
        if v_ville.x is not None:
            db_ville.x = v_ville.x
        if v_ville.z is not None:
            db_ville.z = v_ville.z
        if v_ville.founded_date is not None:
            db_ville.founded_date = v_ville.founded_date
        if v_ville.is_capital is not None:
            db_ville.is_capital = v_ville.is_capital
        if v_ville.is_public is not None:
            db_ville.is_public = v_ville.is_public
        db.add(db_ville)
        db.commit()
        db.refresh(db_ville)
        return get_ville_by_id(db=db, ID=villeID)
    return {"error": 404, "text": "La ville n'a pas été trouvée"}

#endregion

#region Quartiers
def get_quartiers(db: Session, skip: int = 0, limit: int = 100):
    statement = select(models.Quartiers).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_quartier_by_id(db: Session, ID: int):
    statement = select(models.Quartiers).where(models.Quartiers.id == ID)
    results = db.exec(statement)
    return results.first()

def get_quartiers_by_ville_id(db: Session, villeID: int, skip: int = 0, limit: int = 100):
    statement = select(models.Quartiers).where(models.Quartiers.ville_id == villeID).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def create_quartier(db: Session, user: schemas.Users, v_quartier: schemas.QuartierCreate):
    db_ville = get_ville_by_id(db, v_quartier.ville_id)
    if not db_ville:
        raise HTTPException(status_code=404, detail="La ville n'existe pas")
    _check_civilisation_rights(db, user, db_ville.civilisation_id)
    db_quartier = models.Quartiers(
        ville_id = v_quartier.ville_id,
        title = v_quartier.title,
        description = v_quartier.description,
        population = v_quartier.population,
        # Sans coordonnées, le quartier est placé au centre de sa ville
        x = v_quartier.x if v_quartier.x is not None else db_ville.x,
        z = v_quartier.z if v_quartier.z is not None else db_ville.z,
        founded_date = v_quartier.founded_date,
        is_public = v_quartier.is_public,
        created_at = dt.datetime.today()
    )
    
    db.add(db_quartier)
    db.commit()
    db.refresh(db_quartier)
    return db_quartier

def delete_quartier(db: Session, user: schemas.Users, v_quartierid: int):
    db_quartier = get_quartier_by_id(db, v_quartierid)
    if not db_quartier:
        raise HTTPException(status_code=404, detail="Le quartier n'existe pas")
    db_ville = get_ville_by_id(db, db_quartier.ville_id)
    _check_civilisation_rights(db, user, db_ville.civilisation_id if db_ville else None)

    try:
        _delete_quartier_dependencies(db, v_quartierid)
        db.delete(db_quartier)
        db.commit()
        return {"fonction": "delete_quartier", "resultat": "Quartier supprimé"}
        # script = f'; DELETE FROM `Cartographie` WHERE `type` = "quartier" AND `type_id` = "{v_quartierid}"'
        # script += f'; DELETE FROM `Quartiers` WHERE `id` = "{v_quartierid}"'
        # db.execute(script)
    except Exception as e:
        print(f"Erreur lors de la suppression du quartier {v_quartierid}: {e}")
        return {"fonction": "delete_quartier", "erreur": "Une erreur est survenue lors de la suppression du quartier", "details": str(e)}

def update_quartier(db: Session, user: schemas.Users, quartierID: int, v_quartier: schemas.Quartier):
    # Vérification de l'existence du quartier
    db_quartier = get_quartier_by_id(db, quartierID)
    if not db_quartier:
        raise HTTPException(status_code=404, detail="Le quartier n'existe pas")
    db_ville = get_ville_by_id(db, db_quartier.ville_id)
    _check_civilisation_rights(db, user, db_ville.civilisation_id if db_ville else None)
    # Déplacer le quartier vers une autre ville demande aussi des droits sur la civilisation de celle-ci
    if v_quartier.ville_id is not None and v_quartier.ville_id != db_quartier.ville_id:
        target_ville = get_ville_by_id(db, v_quartier.ville_id)
        if not target_ville:
            raise HTTPException(status_code=404, detail="La ville n'existe pas")
        _check_civilisation_rights(db, user, target_ville.civilisation_id)

    if db_quartier:
        # Mise à jour des informations
        if v_quartier.ville_id is not None:
            db_quartier.ville_id = v_quartier.ville_id
        if v_quartier.title is not None:
            db_quartier.title = v_quartier.title
        if v_quartier.description is not None:
            db_quartier.description = v_quartier.description
        if v_quartier.population is not None:
            db_quartier.population = v_quartier.population
        if v_quartier.x is not None:
            db_quartier.x = v_quartier.x
        if v_quartier.z is not None:
            db_quartier.z = v_quartier.z
        if v_quartier.founded_date is not None:
            db_quartier.founded_date = v_quartier.founded_date
        if v_quartier.is_public is not None:
            db_quartier.is_public = v_quartier.is_public
        db.add(db_quartier)
        db.commit()
        db.refresh(db_quartier)
        return get_quartier_by_id(db=db, ID=quartierID)
    return {"error": 404, "text": "Le quartier n'a pas été trouvé"}

def _delete_quartier_dependencies(db: Session, quartierID: int):
    # Frontières, religions et habitants du quartier ; la suppression du quartier et le commit restent à l'appelant
    delete_cartographies_by_types(db, "quartier", quartierID)
    crud_nettoyage.detacher_quartier(db, quartierID)
    links = db.exec(select(models.QuartiersReligions).where(models.QuartiersReligions.quartier_id == quartierID)).all()
    for db_link in links:
        db.delete(db_link)

def get_all_of_quartier_by_id(db: Session, ID: int):
    db_quartier = get_quartier_by_id(db, ID)
    if not db_quartier:
        return None
    return {
        'quartier': db_quartier,
        'ville': get_ville_by_id(db, db_quartier.ville_id),
        'religions': get_religions_by_quartier_id(db, ID),
    }

def _check_quartier_rights(db: Session, user: schemas.Users, quartierID: int):
    # Fondateur ou Admin de la civilisation de la ville du quartier, ou administrateur du site
    db_quartier = get_quartier_by_id(db, quartierID)
    if not db_quartier:
        raise HTTPException(status_code=404, detail="Le quartier n'existe pas")
    db_ville = get_ville_by_id(db, db_quartier.ville_id)
    _check_civilisation_rights(db, user, db_ville.civilisation_id if db_ville else None)
    return db_quartier

def _quartier_religion_link(db: Session, quartierID: int, religionID: int):
    statement = select(models.QuartiersReligions).where(
        models.QuartiersReligions.quartier_id == quartierID,
        models.QuartiersReligions.religion_id == religionID
    )
    return db.exec(statement).first()

def _religion_with_influence(db_religion: models.Religions, influence: float | None):
    # Même format que les religions d'une ville (get_religions_by_ville_id)
    return {
        "id": db_religion.id,
        "title": db_religion.title,
        "color": db_religion.color,
        "icon": db_religion.icon,
        "description": db_religion.description,
        "date_founded": db_religion.date_founded,
        "created_at": db_religion.created_at,
        "is_public": db_religion.is_public,
        "influence": influence
    }

def add_religion_to_quartier(db: Session, user: schemas.Users, quartierID: int, religionID: int, influence: float):
    _check_quartier_rights(db, user, quartierID)
    db_religion = get_religion_by_id(db, religionID)
    if not db_religion:
        raise HTTPException(status_code=404, detail="La religion n'existe pas")
    if _quartier_religion_link(db, quartierID, religionID):
        raise HTTPException(status_code=400, detail="Cette religion est déjà présente dans le quartier")

    db.add(models.QuartiersReligions(quartier_id=quartierID, religion_id=religionID, influence=influence))
    db.commit()
    return {"resultat": "Religion ajoutée au quartier", "religion": _religion_with_influence(db_religion, influence)}

def update_influence_of_religion_in_quartier(db: Session, user: schemas.Users, quartierID: int, religionID: int, influence: float):
    _check_quartier_rights(db, user, quartierID)
    db_link = _quartier_religion_link(db, quartierID, religionID)
    if not db_link:
        raise HTTPException(status_code=404, detail="La religion n'est pas associée au quartier")

    db_link.influence = influence
    db.add(db_link)
    db.commit()
    db.refresh(db_link)
    return {"resultat": "Influence mise à jour", "religion": _religion_with_influence(get_religion_by_id(db, religionID), db_link.influence)}

def delete_religion_from_quartier(db: Session, user: schemas.Users, quartierID: int, religionID: int):
    _check_quartier_rights(db, user, quartierID)
    db_link = _quartier_religion_link(db, quartierID, religionID)
    if not db_link:
        raise HTTPException(status_code=404, detail="La religion n'est pas associée au quartier")

    db.delete(db_link)
    db.commit()
    return {"resultat": "Religion retirée du quartier"}
#endregion

################# Religions #####################
#region Religions

def _check_member_rights(user: schemas.Users, db_members):
    # Mêmes règles que checkMemberAuth côté ShardUI-2 : Fondateur ou Admin, ou administrateur du site
    if user.is_disabled:
        raise HTTPException(status_code=403, detail="Accès refusé")
    if user.is_admin:
        return
    if not any(member.user_id == user.id and member.role in ("Fondateur", "Admin") for member in db_members):
        raise HTTPException(status_code=403, detail="Accès refusé")

# --- Membres (religions, commerces) : model = table des membres, fk = colonne de l'entité ---
MEMBER_ROLES = ("Admin", "Membre")

def members_table(db: Session, members):
    # Même format que les membres de /civilisations/read
    table = []
    for member in members:
        member_user = get_user_by_id(db=db, user_id=member.user_id)
        table.append({
            "user_id": member.user_id,
            "role": member.role,
            "joined_at": member.joined_at,
            "username": member_user.username if member_user else None
        })
    return table

def _get_member(db: Session, model, fk: str, entityID: int, userID: int):
    statement = select(model).where(getattr(model, fk) == entityID, model.user_id == userID)
    return db.exec(statement).first()

def _check_member_role(role: str):
    # Le rôle de Fondateur ne s'obtient que par transfert
    if role == "Fondateur":
        raise HTTPException(status_code=400, detail="Utiliser le transfert pour changer de fondateur")
    if role not in MEMBER_ROLES:
        raise HTTPException(status_code=400, detail="Le rôle doit être \"Admin\" ou \"Membre\"")

def _add_member(db: Session, model, fk: str, entityID: int, new_member_id: int, role: str):
    _check_member_role(role)
    if not get_user_by_id(db=db, user_id=new_member_id):
        raise HTTPException(status_code=404, detail="L'utilisateur n'existe pas")
    if _get_member(db, model, fk, entityID, new_member_id):
        raise HTTPException(status_code=400, detail="Cet utilisateur est déjà membre")

    db_member = model(user_id=new_member_id, role=role, joined_at=dt.datetime.today(), **{fk: entityID})
    db.add(db_member)
    db.commit()
    db.refresh(db_member)
    return {"resultat": "Membre ajouté", "member": db_member}

def _remove_member(db: Session, model, fk: str, entityID: int, member_id: int):
    db_member = _get_member(db, model, fk, entityID, member_id)
    if not db_member:
        raise HTTPException(status_code=404, detail="Cet utilisateur n'est pas membre")
    if db_member.role == "Fondateur":
        raise HTTPException(status_code=400, detail="Le fondateur ne peut pas être retiré : le transférer d'abord")
    db.delete(db_member)
    db.commit()
    return {"resultat": "Membre retiré"}

def _update_member(db: Session, model, fk: str, entityID: int, member_id: int, role: str):
    db_member = _get_member(db, model, fk, entityID, member_id)
    if not db_member:
        raise HTTPException(status_code=404, detail="Cet utilisateur n'est pas membre")
    if db_member.role == "Fondateur":
        raise HTTPException(status_code=400, detail="Utiliser le transfert pour changer de fondateur")
    _check_member_role(role)
    db_member.role = role
    db.add(db_member)
    db.commit()
    db.refresh(db_member)
    return {"resultat": "Membre mis à jour", "member": db_member}

def _transfer_founder(db: Session, user: schemas.Users, model, fk: str, entityID: int, new_founder_id: int, former_role: str, label: str):
    # label : "la religion", "le commerce"… (messages d'erreur)
    db_members = db.exec(select(model).where(getattr(model, fk) == entityID)).all()
    db_founder = next((member for member in db_members if member.role == "Fondateur"), None)

    # Seul le fondateur actuel ou un administrateur du site peut transférer
    if not user.is_admin and (db_founder is None or db_founder.user_id != user.id):
        raise HTTPException(status_code=403, detail=f"Seul le fondateur ou un administrateur peut transférer {label}")

    if former_role not in MEMBER_ROLES:
        raise HTTPException(status_code=400, detail="Le rôle de l'ancien fondateur doit être \"Admin\" ou \"Membre\"")
    if not get_user_by_id(db=db, user_id=new_founder_id):
        raise HTTPException(status_code=404, detail="L'utilisateur n'existe pas")
    if db_founder and db_founder.user_id == new_founder_id:
        raise HTTPException(status_code=400, detail="Cet utilisateur est déjà le fondateur")

    # L'ancien fondateur reste membre avec le rôle choisi
    if db_founder:
        db_founder.role = former_role
        db.add(db_founder)

    # Le nouveau fondateur est ajouté s'il n'est pas encore membre
    db_new_founder = _get_member(db, model, fk, entityID, new_founder_id)
    if db_new_founder:
        db_new_founder.role = "Fondateur"
    else:
        db_new_founder = model(user_id=new_founder_id, role="Fondateur", joined_at=dt.datetime.today(), **{fk: entityID})
    db.add(db_new_founder)
    db.commit()

    return db.exec(select(model).where(getattr(model, fk) == entityID)).all()

def get_religions(db: Session, skip: int = 0, limit: int = 100):
    statement = select(models.Religions).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_members_of_religion(db: Session, religionID: int, skip: int = 0, limit: int = 100):
    statement = select(models.ReligionMembers).where(models.ReligionMembers.religion_id == religionID).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_member_of_religion(db: Session, religionID: int, userID: int):
    statement = select(models.ReligionMembers).where(
        models.ReligionMembers.religion_id == religionID,
        models.ReligionMembers.user_id == userID
    )
    results = db.exec(statement)
    return results.first()

def get_religion_by_id(db: Session, ID: int):
    statement = select(models.Religions).where(models.Religions.id == ID)
    results = db.exec(statement)
    return results.first()

def get_ville_religion_by_id(db: Session, villeID: int, religionID: int):
    statement = select(models.VillesReligions).where(models.VillesReligions.ville_id == villeID, models.VillesReligions.religion_id == religionID)
    results = db.exec(statement)
    return results.first()

def get_religions_by_ville_id(db: Session, villeID: int, skip: int = 0, limit: int = 100):
    statement = select(models.VillesReligions, models.Religions).join(models.Religions, models.VillesReligions.religion_id == models.Religions.id).where(models.VillesReligions.ville_id == villeID).offset(skip).limit(limit)
    results = db.exec(statement)
    resultlist = list()
    for ville_religion, religion in results.all():
        resultlist.append({
            "id": religion.id,
            "title": religion.title,
            "color": religion.color,
            "icon": religion.icon,
            "description": religion.description,
            "date_founded": religion.date_founded,
            "created_at": religion.created_at,
            "is_public": religion.is_public,
            "influence": ville_religion.influence
        })
    return resultlist

def get_villes_by_religion_id(db: Session, religionID: int, skip: int = 0, limit: int = 100):
    statement = select(models.VillesReligions, models.Villes).join(models.Villes, models.VillesReligions.ville_id == models.Villes.id).where(models.VillesReligions.religion_id == religionID).offset(skip).limit(limit)
    results = db.exec(statement)
    return [{"villes_religions": ville_religion, "ville": ville} for ville_religion, ville in results.all()]

def get_religions_by_quartier_id(db: Session, quartierID: int, skip: int = 0, limit: int = 100):
    statement = select(models.QuartiersReligions, models.Religions).join(models.Religions, models.QuartiersReligions.religion_id == models.Religions.id).where(models.QuartiersReligions.quartier_id == quartierID).offset(skip).limit(limit)
    results = db.exec(statement)
    return [_religion_with_influence(religion, quartier_religion.influence) for quartier_religion, religion in results.all()]

def get_quartiers_by_religion_id(db: Session, religionID: int, skip: int = 0, limit: int = 100):
    statement = select(models.QuartiersReligions, models.Quartiers).join(models.Quartiers, models.QuartiersReligions.quartier_id == models.Quartiers.id).where(models.QuartiersReligions.religion_id == religionID).offset(skip).limit(limit)
    results = db.exec(statement)
    return [{"quartiers_religions": quartier_religion, "quartier": quartier} for quartier_religion, quartier in results.all()]

def get_all_of_religion_by_id(db: Session, ID: int):
    statement = select(models.Religions).where(models.Religions.id == ID)
    results = db.exec(statement)
    religion = results.first()
    if not religion:
        return None
    
    villes = get_villes_by_religion_id(db, religion.id)
    quartiers = get_quartiers_by_religion_id(db, religion.id)
    religion_all = {
        'religion': religion,
        'members': members_table(db, get_members_of_religion(db, religion.id)),
        'villes': villes if villes else [],
        'quartiers': quartiers if quartiers else [],
    }
    return religion_all

def create_religion(db: Session, user: schemas.Users, v_religion: schemas.ReligionCreate):
    db_religion = models.Religions(
        title = v_religion.title,
        description = v_religion.description,
        date_founded = v_religion.date_founded,
        is_public = v_religion.is_public,
        color = v_religion.color,
        icon = v_religion.icon,
        created_at = dt.datetime.today()
    )
    
    db.add(db_religion)
    db.commit()
    db.refresh(db_religion) # Rafraîchir pour obtenir l'ID généré

    db_member = models.ReligionMembers(
        user_id=user.id,
        religion_id=db_religion.id,
        role="Fondateur",
        joined_at=dt.datetime.today()
    )
    db.add(db_member)
    db.commit()
    db.refresh(db_member)

    return get_religion_by_id(db=db, ID=db_religion.id), db_member

def delete_religion(db: Session, user: schemas.Users, v_religionid: int):
    db_religion = get_religion_by_id(db, v_religionid)
    db_villes_religions = get_villes_by_religion_id(db, v_religionid, skip=0, limit=1000)
    db_quartiers_religions = get_quartiers_by_religion_id(db, v_religionid, skip=0, limit=1000)
    if not db_religion:
        raise HTTPException(status_code=404, detail="La religion n'existe pas")
    db_members = get_members_of_religion(db, v_religionid, limit=10000)

    # Fondateur ou Admin de la religion, ou administrateur du site
    _check_member_rights(user, db_members)
    
    try:
        for villereligion in db_villes_religions:
            db.delete(villereligion["villes_religions"])
        for quartierreligion in db_quartiers_religions:
            db.delete(quartierreligion["quartiers_religions"])
        for member in db_members:
            db.delete(member)
        crud_nettoyage.detacher_religion(db, v_religionid, db_religion.title)
        db.delete(db_religion)
        db.commit()
        return {"fonction": "delete_religion", "resultat": "Religion supprimée"}
    except Exception as e:
        print(f"Erreur lors de la suppression de la religion {v_religionid}: {e}")
        return {"fonction": "delete_religion", "erreur": "Une erreur est survenue lors de la suppression de la religion", "details": str(e)}

def update_religion(db: Session, user: schemas.Users, religionID: int, v_religion: schemas.Religions):
    # Vérification de l'existence de la religion
    db_religion = get_religion_by_id(db, religionID)
    if not db_religion:
        raise HTTPException(status_code=404, detail="La religion n'existe pas")
    db_members = get_members_of_religion(db, religionID, limit=10000)

    # Fondateur ou Admin de la religion, ou administrateur du site
    _check_member_rights(user, db_members)

    if db_religion:
        # Mise à jour des informations
        if v_religion.title is not None:
            db_religion.title = v_religion.title
        if v_religion.description is not None:
            db_religion.description = v_religion.description
        if v_religion.date_founded is not None:
            db_religion.date_founded = v_religion.date_founded
        if v_religion.color is not None:
            db_religion.color = v_religion.color
        if v_religion.icon is not None:
            db_religion.icon = v_religion.icon
        if v_religion.is_public is not None:
            db_religion.is_public = v_religion.is_public
        db.add(db_religion)
        db.commit()
        db.refresh(db_religion)
        return get_religion_by_id(db=db, ID=religionID)
    return {"error": 404, "text": "La religion n'a pas été trouvée"}

def add_religion_to_ville(db: Session, user: schemas.Users, villeID: int, v_religionid: int, influence: float): 
    db_ville = get_ville_by_id(db, villeID)
    db_civilisation = get_civilisation_by_id(db, db_ville.civilisation_id) if db_ville else None
    db_members = get_members_of_civilisation(db, db_civilisation.id) if db_civilisation else []
    db_religion = get_religion_by_id(db, v_religionid)

    if not db_ville:
        return {"error": 404, "text": "La ville n'a pas été trouvée"}

    # Fondateur ou Admin de la civilisation de la ville, ou administrateur du site
    _check_member_rights(user, db_members)
    if not db_religion:
        return {"error": 404, "text": "La religion n'a pas été trouvée"}
    else:
        religion = {
            "id": db_religion.id,
            "title": db_religion.title,
            "description": db_religion.description,
            "created_at": db_religion.created_at,
            "date_founded": db_religion.date_founded,
            "color": db_religion.color,
            "icon": db_religion.icon,
            "is_public": db_religion.is_public,
            "influence": influence
        }

    try:
        db_ville_religion = models.VillesReligions(
            ville_id=villeID,
            religion_id=v_religionid,
            influence=influence
        )
        db.add(db_ville_religion)
        db.commit()
        db.refresh(db_ville_religion)
        return {"fonction": "add_religion_to_ville", "resultat": "Religion ajoutée à la ville", "religion": religion}
    except Exception as e:
        print(f"Erreur lors de l'ajout de la religion {v_religionid} à la ville {villeID}: {e}")
        return {"fonction": "add_religion_to_ville", "erreur": "Une erreur est survenue lors de l'ajout de la religion à la ville", "details": str(e)}

def update_influence_of_religion_in_ville(db: Session, user: schemas.Users, villeID: int, v_religionid: int, influence: float):
    db_ville = get_ville_by_id(db, villeID)
    db_civilisation = get_civilisation_by_id(db, db_ville.civilisation_id) if db_ville else None
    db_members = get_members_of_civilisation(db, db_civilisation.id) if db_civilisation else []
    db_religion = get_religion_by_id(db, v_religionid)

    if not db_ville:
        return {"error": 404, "text": "La ville n'a pas été trouvée"}

    # Fondateur ou Admin de la civilisation de la ville, ou administrateur du site
    _check_member_rights(user, db_members)
    if not db_religion:
        return {"error": 404, "text": "La religion n'a pas été trouvée"}
    else:
        religion = {
            "id": db_religion.id,
            "title": db_religion.title,
            "description": db_religion.description,
            "created_at": db_religion.created_at,
            "date_founded": db_religion.date_founded,
            "color": db_religion.color,
            "icon": db_religion.icon,
            "is_public": db_religion.is_public,
            "influence": None
        }

    try:
        db_ville_religion = db.exec(
            select(models.VillesReligions).where(
                models.VillesReligions.ville_id == villeID,
                models.VillesReligions.religion_id == v_religionid
            )
        ).first()
        if not db_ville_religion:
            return {"error": 404, "text": "La religion n'est pas associée à la ville"}
        db_ville_religion.influence = influence
        db.add(db_ville_religion)
        db.commit()
        db.refresh(db_ville_religion)
        religion["influence"] = db_ville_religion.influence
        return {"fonction": "update_influence_of_religion_in_ville", "resultat": "Influence mise à jour", "religion": religion}
    except Exception as e:
        print(f"Erreur lors de la mise à jour de l'influence de la religion {v_religionid} dans la ville {villeID}: {e}")
        return {"fonction": "update_influence_of_religion_in_ville", "erreur": "Une erreur est survenue lors de la mise à jour de l'influence", "details": str(e)}

def delete_religion_from_ville(db: Session, user: schemas.Users, villeID: int, v_religionid: int):
    db_ville = get_ville_by_id(db, villeID)
    db_civilisation = get_civilisation_by_id(db, db_ville.civilisation_id) if db_ville else None
    db_members = get_members_of_civilisation(db, db_civilisation.id) if db_civilisation else []
    db_religion = get_religion_by_id(db, v_religionid)

    if not db_ville:
        return {"error": 404, "text": "La ville n'a pas été trouvée"}

    # Fondateur ou Admin de la civilisation de la ville, ou administrateur du site
    _check_member_rights(user, db_members)
    if not db_religion:
        return {"error": 404, "text": "La religion n'a pas été trouvée"}

    try:
        db_ville_religion = db.exec(
            select(models.VillesReligions).where(
                models.VillesReligions.ville_id == villeID,
                models.VillesReligions.religion_id == v_religionid
            )
        ).first()
        if not db_ville_religion:
            return {"fonction": "delete_religion_from_ville", "erreur": "La relation ville-religion n'existe pas"}
        db.delete(db_ville_religion)
        db.commit()
        return {"fonction": "delete_religion_from_ville", "resultat": "Relation supprimée"}
    except Exception as e:
        print(f"Erreur lors de la suppression de la religion {v_religionid} de la ville {villeID}: {e}")
        return {"fonction": "delete_religion_from_ville", "erreur": "Une erreur est survenue lors de la suppression de la relation ville-religion", "details": str(e)}

def transfer_founder_of_religion(db: Session, user: schemas.Users, religionID: int, new_founder_id: int, former_role: str = "Admin"):
    db_religion = get_religion_by_id(db, religionID)
    if not db_religion:
        raise HTTPException(status_code=404, detail="La religion n'existe pas")

    return _transfer_founder(db, user, models.ReligionMembers, "religion_id", religionID, new_founder_id, former_role, "la religion")

def _check_religion_member_rights(db: Session, user: schemas.Users, religionID: int):
    if not get_religion_by_id(db, religionID):
        raise HTTPException(status_code=404, detail="La religion n'existe pas")
    # Fondateur ou Admin de la religion, ou administrateur du site
    _check_member_rights(user, get_members_of_religion(db, religionID, limit=10000))

def add_member_to_religion(db: Session, user: schemas.Users, religionID: int, new_member_id: int, role: str):
    _check_religion_member_rights(db, user, religionID)
    return _add_member(db, models.ReligionMembers, "religion_id", religionID, new_member_id, role)

def remove_member_from_religion(db: Session, user: schemas.Users, religionID: int, member_id: int):
    _check_religion_member_rights(db, user, religionID)
    return _remove_member(db, models.ReligionMembers, "religion_id", religionID, member_id)

def update_member_of_religion(db: Session, user: schemas.Users, religionID: int, member_id: int, member: schemas.ReligionMemberUpdate):
    _check_religion_member_rights(db, user, religionID)
    return _update_member(db, models.ReligionMembers, "religion_id", religionID, member_id, member.role)
#endregion

################# Commerces #####################
#region Commerces

def _commerce_fondateur(db: Session, db_members):
    # Informations publiques du fondateur (jamais le mot de passe haché)
    db_founder = next((member for member in db_members if member.role == "Fondateur"), None)
    user = get_user_by_id(db=db, user_id=db_founder.user_id) if db_founder else None
    if not user:
        return None
    return {"id": user.id, "username": user.username, "full_name": user.full_name, "image_url": user.image_url}

def _check_commerce_rights(db: Session, user: schemas.Users, db_commerce: models.Commerces):
    # Comme les religions : Fondateur ou Admin du commerce, ou administrateur du site
    _check_member_rights(user, get_members_of_commerce(db, db_commerce.id))

def get_members_of_commerce(db: Session, commerceID: int, skip: int = 0, limit: int = 1000):
    statement = select(models.CommerceMembers).where(models.CommerceMembers.commerce_id == commerceID).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_member_of_commerce(db: Session, commerceID: int, userID: int):
    return _get_member(db, models.CommerceMembers, "commerce_id", commerceID, userID)

def _get_commerce_for_members(db: Session, user: schemas.Users, commerceID: int):
    db_commerce = get_commerce_by_id(db, commerceID)
    if not db_commerce:
        raise HTTPException(status_code=404, detail="Le commerce n'existe pas")
    _check_commerce_rights(db, user, db_commerce)
    return db_commerce

def add_member_to_commerce(db: Session, user: schemas.Users, commerceID: int, new_member_id: int, role: str):
    _get_commerce_for_members(db, user, commerceID)
    return _add_member(db, models.CommerceMembers, "commerce_id", commerceID, new_member_id, role)

def remove_member_from_commerce(db: Session, user: schemas.Users, commerceID: int, member_id: int):
    _get_commerce_for_members(db, user, commerceID)
    return _remove_member(db, models.CommerceMembers, "commerce_id", commerceID, member_id)

def update_member_of_commerce(db: Session, user: schemas.Users, commerceID: int, member_id: int, member: schemas.CommerceMemberUpdate):
    _get_commerce_for_members(db, user, commerceID)
    return _update_member(db, models.CommerceMembers, "commerce_id", commerceID, member_id, member.role)

def transfer_founder_of_commerce(db: Session, user: schemas.Users, commerceID: int, new_founder_id: int, former_role: str = "Admin"):
    if not get_commerce_by_id(db, commerceID):
        raise HTTPException(status_code=404, detail="Le commerce n'existe pas")
    return _transfer_founder(db, user, models.CommerceMembers, "commerce_id", commerceID, new_founder_id, former_role, "le commerce")

def get_commerces(db: Session, skip: int = 0, limit: int = 100):
    statement = select(models.Commerces).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_commerce_by_id(db: Session, ID: int):
    statement = select(models.Commerces).where(models.Commerces.id == ID)
    results = db.exec(statement)
    return results.first()

def get_commerces_by_member_id(db: Session, userID: int, skip: int = 0, limit: int = 100):
    statement = (
        select(models.Commerces)
        .join(models.CommerceMembers, models.CommerceMembers.commerce_id == models.Commerces.id)
        .where(models.CommerceMembers.user_id == userID)
        .offset(skip).limit(limit)
    )
    results = db.exec(statement)
    return results.all()

def get_magasins(db: Session, skip: int = 0, limit: int = 100):
    statement = select(models.CommerceMagasins).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_magasin_by_id(db: Session, ID: int):
    statement = select(models.CommerceMagasins).where(models.CommerceMagasins.id == ID)
    results = db.exec(statement)
    return results.first()

def get_magasins_by_commerce_id(db: Session, commerceID: int, skip: int = 0, limit: int = 1000):
    # Le siège en premier
    statement = (
        select(models.CommerceMagasins)
        .where(models.CommerceMagasins.commerce_id == commerceID)
        .order_by(models.CommerceMagasins.is_siege.desc(), models.CommerceMagasins.title)
        .offset(skip).limit(limit)
    )
    results = db.exec(statement)
    return results.all()

def get_magasins_by_ville_id(db: Session, villeID: int, skip: int = 0, limit: int = 100):
    statement = select(models.CommerceMagasins).where(models.CommerceMagasins.ville_id == villeID).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_all_of_commerce_by_id(db: Session, ID: int):
    db_commerce = get_commerce_by_id(db, ID)
    if not db_commerce:
        return None
    db_members = get_members_of_commerce(db, db_commerce.id)
    return {
        'commerce': db_commerce,
        'fondateur': _commerce_fondateur(db, db_members),
        'members': members_table(db, db_members),
        'magasins': get_magasins_by_commerce_id(db, db_commerce.id),
    }

def get_diriges_of_commerce(db: Session, commerceID: int, skip: int = 0, limit: int = 1000):
    statement = select(models.Commerces).where(models.Commerces.dirigeant_commerce_id == commerceID).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_commerce_links(db: Session, db_commerce: models.Commerces):
    # Commerce dirigeant (résumé) et commerces dirigés (avec fondateur, membres et magasins)
    dirigeant = get_commerce_by_id(db, db_commerce.dirigeant_commerce_id) if db_commerce.dirigeant_commerce_id else None
    return {
        'dirigeant': {"id": dirigeant.id, "title": dirigeant.title, "is_public": dirigeant.is_public} if dirigeant else None,
        'diriges': [get_all_of_commerce_by_id(db, dirige.id) for dirige in get_diriges_of_commerce(db, db_commerce.id) if dirige.id != db_commerce.id],
    }

def _apply_commerce_dirigeant(db: Session, user: schemas.Users, db_commerce: models.Commerces, is_dirigeant: bool, dirigeant_id: int | None):
    # Un commerce dirigeant n'a pas de dirigeant. Un commerce dirigé est rattaché à un commerce dirigeant
    # existant (pas de chaîne), autre que lui-même, sur lequel l'utilisateur a des droits.
    if is_dirigeant:
        db_commerce.is_commerce_dirigeant = True
        db_commerce.dirigeant_commerce_id = 0
        return

    if db_commerce.id and get_diriges_of_commerce(db, db_commerce.id, limit=1):
        raise HTTPException(status_code=400, detail="Ce commerce dirige d'autres commerces : il ne peut pas être rattaché à un commerce dirigeant")
    if dirigeant_id:
        if db_commerce.id and dirigeant_id == db_commerce.id:
            raise HTTPException(status_code=400, detail="Un commerce ne peut pas se diriger lui-même")
        db_dirigeant = get_commerce_by_id(db, dirigeant_id)
        if not db_dirigeant:
            raise HTTPException(status_code=404, detail="Le commerce dirigeant n'existe pas")
        if db_dirigeant.is_commerce_dirigeant is False:
            raise HTTPException(status_code=400, detail="Le commerce choisi n'est pas un commerce dirigeant")
        dirigeant_members = get_members_of_commerce(db, db_dirigeant.id)
        if not (user.is_admin or any(member.user_id == user.id and member.role in ("Fondateur", "Admin") for member in dirigeant_members)):
            raise HTTPException(status_code=403, detail="Rattacher un commerce demande les droits sur le commerce dirigeant")

    db_commerce.is_commerce_dirigeant = False
    db_commerce.dirigeant_commerce_id = dirigeant_id or 0

def create_commerce(db: Session, user: schemas.Users, v_commerce: schemas.CommerceCreate):
    if user.is_disabled:
        raise HTTPException(status_code=403, detail="Accès refusé")

    db_commerce = models.Commerces(
        title = v_commerce.title,
        description = v_commerce.description,
        date_founded = v_commerce.date_founded,
        is_public = v_commerce.is_public if v_commerce.is_public is not None else True,
        created_at = dt.datetime.today()
    )
    _apply_commerce_dirigeant(db, user, db_commerce, v_commerce.is_commerce_dirigeant is not False, v_commerce.dirigeant_commerce_id)
    db.add(db_commerce)
    db.commit()
    db.refresh(db_commerce)

    # Le créateur devient Fondateur du commerce
    db.add(models.CommerceMembers(
        user_id=user.id,
        commerce_id=db_commerce.id,
        role="Fondateur",
        joined_at=dt.datetime.today()
    ))
    db.commit()
    db.refresh(db_commerce)
    return db_commerce

def update_commerce(db: Session, user: schemas.Users, commerceID: int, v_commerce: schemas.CommerceUpdate):
    db_commerce = get_commerce_by_id(db, commerceID)
    if not db_commerce:
        raise HTTPException(status_code=404, detail="Le commerce n'existe pas")
    _check_commerce_rights(db, user, db_commerce)

    data = v_commerce.model_dump(exclude_unset=True)
    is_dirigeant = data.pop("is_commerce_dirigeant", None)
    dirigeant_id = data.pop("dirigeant_commerce_id", None)
    if data.get("title") is None:
        data.pop("title", None)
    for key, value in data.items():
        setattr(db_commerce, key, value)

    # Lien dirigeant : revalidé seulement s'il change (le formulaire renvoie aussi les valeurs actuelles)
    if is_dirigeant is not None or dirigeant_id is not None:
        current_is = db_commerce.is_commerce_dirigeant is not False
        current_id = db_commerce.dirigeant_commerce_id or 0
        new_is = current_is if is_dirigeant is None else is_dirigeant
        new_id = current_id if dirigeant_id is None else (dirigeant_id or 0)
        if new_is != current_is or (not new_is and new_id != current_id):
            _apply_commerce_dirigeant(db, user, db_commerce, new_is, new_id)

    db.add(db_commerce)
    db.commit()
    db.refresh(db_commerce)
    return db_commerce

def delete_commerce(db: Session, user: schemas.Users, commerceID: int):
    db_commerce = get_commerce_by_id(db, commerceID)
    if not db_commerce:
        raise HTTPException(status_code=404, detail="Le commerce n'existe pas")
    # Comme les religions : Fondateur ou Admin du commerce, ou administrateur du site
    _check_commerce_rights(db, user, db_commerce)

    # Les commerces dirigés redeviennent indépendants
    for db_dirige in get_diriges_of_commerce(db, commerceID):
        db_dirige.is_commerce_dirigeant = True
        db_dirige.dirigeant_commerce_id = 0
        db.add(db_dirige)
    for db_magasin in get_magasins_by_commerce_id(db, commerceID):
        db.delete(db_magasin)
    for db_member in get_members_of_commerce(db, commerceID):
        db.delete(db_member)
    db.delete(db_commerce)
    db.commit()
    return True

def _check_magasin_references(db: Session, dimension_id: int | None, ville_id: int | None):
    if dimension_id is not None and not get_dimension_by_id(db, dimension_id):
        raise HTTPException(status_code=404, detail="La dimension n'existe pas")
    if ville_id is not None and not get_ville_by_id(db, ville_id):
        raise HTTPException(status_code=404, detail="La ville n'existe pas")

def _keep_single_siege(db: Session, db_magasin: models.CommerceMagasins):
    # Un seul siège par commerce : le magasin désigné remplace l'ancien siège
    if not db_magasin.is_siege:
        return
    for other in get_magasins_by_commerce_id(db, db_magasin.commerce_id):
        if other.id != db_magasin.id and other.is_siege:
            other.is_siege = False
            db.add(other)
    db.commit()

def create_magasin(db: Session, user: schemas.Users, v_magasin: schemas.MagasinCreate):
    db_commerce = get_commerce_by_id(db, v_magasin.commerce_id)
    if not db_commerce:
        raise HTTPException(status_code=404, detail="Le commerce n'existe pas")
    _check_commerce_rights(db, user, db_commerce)
    _check_magasin_references(db, v_magasin.dimension_id, v_magasin.ville_id)

    db_magasin = models.CommerceMagasins(
        commerce_id = v_magasin.commerce_id,
        title = v_magasin.title,
        description = v_magasin.description,
        founded_date = v_magasin.founded_date,
        dimension_id = v_magasin.dimension_id,
        x = v_magasin.x,
        z = v_magasin.z,
        is_siege = bool(v_magasin.is_siege),
        is_public = v_magasin.is_public if v_magasin.is_public is not None else True,
        ville_id = v_magasin.ville_id,
        created_at = dt.datetime.today()
    )
    db.add(db_magasin)
    db.commit()
    db.refresh(db_magasin)
    _keep_single_siege(db, db_magasin)
    return get_magasin_by_id(db, db_magasin.id)

def update_magasin(db: Session, user: schemas.Users, magasinID: int, v_magasin: schemas.MagasinUpdate):
    db_magasin = get_magasin_by_id(db, magasinID)
    if not db_magasin:
        raise HTTPException(status_code=404, detail="Le magasin n'existe pas")
    _check_commerce_rights(db, user, get_commerce_by_id(db, db_magasin.commerce_id))

    # Seuls les champs envoyés sont modifiés (null permet d'effacer une ville ou une description)
    data = v_magasin.model_dump(exclude_unset=True)
    if data.get("title") is None:
        data.pop("title", None)
    _check_magasin_references(db, data.get("dimension_id"), data.get("ville_id"))
    for key, value in data.items():
        setattr(db_magasin, key, value)

    db.add(db_magasin)
    db.commit()
    db.refresh(db_magasin)
    _keep_single_siege(db, db_magasin)
    return get_magasin_by_id(db, magasinID)

def delete_magasin(db: Session, user: schemas.Users, magasinID: int):
    db_magasin = get_magasin_by_id(db, magasinID)
    if not db_magasin:
        raise HTTPException(status_code=404, detail="Le magasin n'existe pas")
    _check_commerce_rights(db, user, get_commerce_by_id(db, db_magasin.commerce_id))

    db.delete(db_magasin)
    db.commit()
    return True
#endregion

#region Cartographie
################# Cartographie #####################

# Dimensions
def get_dimensions(db: Session, skip: int = 0, limit: int = 100):
    statement = select(models.Dimensions).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_dimension_by_id(db: Session, ID: int):
    statement = select(models.Dimensions).where(models.Dimensions.id == ID)
    results = db.exec(statement)
    return results.first()

def get_dimension_by_name(db: Session, name: str):
    statement = select(models.Dimensions).where(models.Dimensions.title == name)
    results = db.exec(statement)
    return results.first()

def get_dimensions_by_title(db: Session, title: str, skip: int = 0, limit: int = 100):
    statement = select(models.Dimensions).where(models.Dimensions.title.like(f"%{title}%")).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def create_dimension(db: Session, user: schemas.Users, v_dimension: schemas.DimensionCreate):
    db_dimension = models.Dimensions(
        title = v_dimension.title,
        link = v_dimension.link,
        description = v_dimension.description
    )
    
    db.add(db_dimension)
    db.commit()
    db.refresh(db_dimension)
    return db_dimension

def delete_dimension(db: Session, user: schemas.Users, v_dimensionid: int):
    db_dimension = get_dimension_by_id(db, v_dimensionid)

    # Vérifier de l'utilisateur actuel
    if not user.is_admin or user.is_disabled:
        raise HTTPException(status_code=403, detail="Accès refusé")

    if not db_dimension:
        return {"fonction": "delete_dimension", "erreur": "La dimension n'existe pas"}

    # Une dimension encore référencée ne peut pas être supprimée
    nb_villes = len(get_villes_by_dimension_id(db, v_dimensionid, limit=1))
    nb_marqueurs = len(get_cartographies_by_dimension(db, v_dimensionid, limit=1))
    if nb_villes or nb_marqueurs:
        return {"fonction": "delete_dimension", "erreur": "La dimension est encore utilisée par des villes ou des marqueurs de cartographie"}
    try:
        db.delete(db_dimension)
        db.commit()
        return {"fonction": "delete_dimension", "resultat": "Dimension supprimée"}
    except Exception as e:
        print(f"Erreur lors de la suppression de la dimension {v_dimensionid}: {e}")
        return {"fonction": "delete_dimension", "erreur": "Une erreur est survenue lors de la suppression de la dimension", "details": str(e)}

def update_dimension(db: Session, user: schemas.Users, dimensionID: int, v_dimension: schemas.Dimension):
    # Vérification de l'existence de la dimension
    db_dimension = get_dimension_by_id(db, dimensionID)

    # Vérifier de l'utilisateur actuel
    if not user.is_admin or user.is_disabled:
        raise HTTPException(status_code=403, detail="Accès refusé")

    if db_dimension:
        # Mise à jour des informations
        if v_dimension.title is not None:
            db_dimension.title = v_dimension.title
        if v_dimension.link is not None:
            db_dimension.link = v_dimension.link
        if v_dimension.description is not None:
            db_dimension.description = v_dimension.description
        db.add(db_dimension)
        db.commit()
        db.refresh(db_dimension)
        return get_dimension_by_id(db=db, ID=dimensionID)
    return {"error": 404, "text": "La dimension n'a pas été trouvée"}

# Cartographie Markers
def get_cartographies(db: Session, skip: int = 0, limit: int = 100):
    statement = select(models.Cartographie).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_cartographie_by_id(db: Session, ID: int):
    statement = select(models.Cartographie).where(models.Cartographie.id == ID)
    results = db.exec(statement)
    return results.first()

def get_cartographies_by_dimension(db: Session, dimensionID: int, skip: int = 0, limit: int = 100):
    statement = select(models.Cartographie).where(models.Cartographie.dimension_id == dimensionID).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_cartographies_by_type(db: Session, type: str, skip: int = 0, limit: int = 100):
    statement = select(models.Cartographie).where(models.Cartographie.type == type).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_cartographies_by_type_and_dimension(db: Session, type: str, dimensionID: int, skip: int = 0, limit: int = 100):
    statement = select(models.Cartographie).where(models.Cartographie.type == type).where(models.Cartographie.dimension_id == dimensionID).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_cartographies_type(db: Session):
    types = ["civilisation", "ville", "quartier", "guerre"]
    return types

def get_cartographies_by_types(db: Session, type: str, id: int, skip: int = 0, limit: int = 100):
    statement = select(models.Cartographie).where(models.Cartographie.type == type).where(models.Cartographie.type_id == id).offset(skip).limit(limit)
    results = db.exec(statement)
    return results.all()

def get_cartographie_civilisation_id(db: Session, type: str, type_id: int):
    # Retrouve la civilisation propriétaire d'une entité cartographiée
    if type == "civilisation":
        db_civilisation = get_civilisation_by_id(db, type_id)
        return db_civilisation.id if db_civilisation else None
    if type == "ville":
        db_ville = get_ville_by_id(db, type_id)
        return db_ville.civilisation_id if db_ville else None
    if type == "quartier":
        db_quartier = get_quartier_by_id(db, type_id)
        db_ville = get_ville_by_id(db, db_quartier.ville_id) if db_quartier else None
        return db_ville.civilisation_id if db_ville else None
    return None

def check_cartographie_authorisation(db: Session, user: schemas.Users, type: str, type_id: int):
    if type not in get_cartographies_type(db):
        raise HTTPException(status_code=400, detail=f"Type de cartographie inconnu : {type}")
    if type == "guerre":
        # Zones de conflit : guerre en cours, chefs de camp ou modérateurs RP (import local : crud_conflits importe crud)
        from . import crud_conflits
        db_guerre = crud_conflits.get_guerre(db, type_id)
        if not db_guerre:
            raise HTTPException(status_code=404, detail=f"L'entité {type} {type_id} n'existe pas")
        if not crud_conflits.can_edit_zones(db, user, db_guerre):
            raise HTTPException(status_code=403, detail="Seuls les chefs de camp et les modérateurs RP tracent les zones d'une guerre en cours")
        return
    civilisationID = get_cartographie_civilisation_id(db, type, type_id)
    if civilisationID is None:
        raise HTTPException(status_code=404, detail=f"L'entité {type} {type_id} n'existe pas")
    if user.is_admin:
        return
    # Mêmes règles que checkMemberAuth côté ShardUI-2 : Fondateur ou Admin de la civilisation
    db_members = get_members_of_civilisation(db, civilisationID)
    if not any(member.user_id == user.id and member.role in ("Fondateur", "Admin") for member in db_members):
        raise HTTPException(status_code=403, detail="Accès refusé")

def check_cartographie_coordinates(coordinates: str):
    try:
        json.loads(coordinates)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Les coordonnées doivent être au format JSON")

def create_cartographie(db: Session, user: schemas.Users, v_cartographie: schemas.CartographieCreate):
    check_cartographie_authorisation(db, user, v_cartographie.type, v_cartographie.type_id)
    check_cartographie_coordinates(v_cartographie.coordinates)
    if not get_dimension_by_id(db, v_cartographie.dimension_id):
        raise HTTPException(status_code=404, detail="La dimension n'existe pas")

    db_cartographie = models.Cartographie(
        title = v_cartographie.title or "",
        description = v_cartographie.description,
        text = v_cartographie.text,
        color = v_cartographie.color,
        dimension_id = v_cartographie.dimension_id,
        shape_type = v_cartographie.shape_type,
        coordinates = v_cartographie.coordinates,
        type = v_cartographie.type,
        type_id = v_cartographie.type_id
    )

    db.add(db_cartographie)
    db.commit()
    db.refresh(db_cartographie)
    return db_cartographie

def delete_cartographie(db: Session, user: schemas.Users, cartographieID: int):
    db_cartographie = get_cartographie_by_id(db, cartographieID)
    if not db_cartographie:
        raise HTTPException(status_code=404, detail="La cartographie n'a pas été trouvée")
    check_cartographie_authorisation(db, user, db_cartographie.type, db_cartographie.type_id)

    db.delete(db_cartographie)
    db.commit()
    return True

def delete_cartographies_by_types(db: Session, type: str, id: int):
    # Nettoyage des marqueurs / frontières lors de la suppression de l'entité associée
    for db_cartographie in get_cartographies_by_types(db, type, id, limit=10000):
        db.delete(db_cartographie)

def update_cartographie(db: Session, user: schemas.Users, cartographieID: int, v_cartographie: schemas.CartographieUpdate):
    db_cartographie = get_cartographie_by_id(db, cartographieID)
    if not db_cartographie:
        raise HTTPException(status_code=404, detail="La cartographie n'a pas été trouvée")
    check_cartographie_authorisation(db, user, db_cartographie.type, db_cartographie.type_id)

    # Déplacement vers une autre entité : il faut aussi les droits sur la nouvelle
    new_type = v_cartographie.type if v_cartographie.type is not None else db_cartographie.type
    new_type_id = v_cartographie.type_id if v_cartographie.type_id is not None else db_cartographie.type_id
    if (new_type, new_type_id) != (db_cartographie.type, db_cartographie.type_id):
        check_cartographie_authorisation(db, user, new_type, new_type_id)
    if v_cartographie.coordinates is not None:
        check_cartographie_coordinates(v_cartographie.coordinates)
    if v_cartographie.dimension_id is not None and not get_dimension_by_id(db, v_cartographie.dimension_id):
        raise HTTPException(status_code=404, detail="La dimension n'existe pas")

    for field, value in v_cartographie.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(db_cartographie, field, value)
    db.add(db_cartographie)
    db.commit()
    db.refresh(db_cartographie)
    return db_cartographie
#endregion