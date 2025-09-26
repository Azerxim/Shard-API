from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import text, update
import time as t, datetime as dt
from operator import itemgetter
import hashlib

from . import models, schemas, crud_security as crudSecu
from topazdevsdk import colors
from . import utils

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
    return db_user


# ===============================================================================
# Suppression
# ===============================================================================
def delete_user(db: Session, v_userid: int):
    script = f'DELETE FROM `Users` WHERE `id` = "{v_userid}"'
    db.execute(script)
    db.commit()
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
    return {"error": 404, "text": "User not found"}
