from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import text, update
import time as t, datetime as dt
from operator import itemgetter
import hashlib

from . import models, schemas
from topazdevsdk import colors
from . import utils


################# Security #####################

def hash_password(password: str):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def secu_decode_token(db: Session, token):
    user = secu_get_user_from_username(db, token)
    return user

def secu_get_user_from_username(db: Session, username: str):
    return db.query(models.SecurityUsers).filter(models.SecurityUsers.username == username).first()

def secu_get_user_from_email(db: Session, email: str):
    return db.query(models.SecurityUsers).filter(models.SecurityUsers.email == email).first()

def loadsecurity(db: Session, json):
    # Gestion du password vide
    if json['password']=="":
        print(f"{colors.BColors.RED}ERROR{colors.BColors.END}:    Security load error, password null")
        return {"result": 'error'}
    try:
        user = secu_get_user_from_username(db, json['username'])     
        user_dict = models.SecurityUsers(
            username = json['username'],
            full_name = json['full_name'],
            hashed_password = hash_password(json['password'])
        )
        if not user:
            db.add(user_dict)
            db.commit()
            db.refresh(user_dict)
            print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Security user created")
            return {"result": 'created'}
        else:
            db.query(models.SecurityUsers).filter(models.SecurityUsers.username == user_dict.username).update({'full_name': user_dict.full_name, 'hashed_password': user_dict.hashed_password})
            print(f"{colors.BColors.GREEN}INFO{colors.BColors.END}:     Security user modified")
            return {"result": 'modified'}
    except:
        print(f"{colors.BColors.RED}ERROR{colors.BColors.END}:    Security load error")
        return {"result": 'error'}


################# USER #####################

# -------------------------------------------------------------------------------
def get_user(db: Session, ID: int):
    result = db.query(models.Users).filter(models.Users.id == ID).first()
    if result is not None:
        user = schemas.rUser(
            id=result.id,
            username=result.username,
            full_name=result.full_name,
            email=result.email,
            arrival=result.arrival,
            disabled=result.disabled,
            platform=result.platform,
            image_url=result.image_url
        )
        return user
    return None


# -------------------------------------------------------------------------------
def get_users(db: Session, skip: int = 0, limit: int = 100):
    result = db.query(models.Users).offset(skip).limit(limit).all()
    users = []
    for one in result:
        user = schemas.rUser(
            id=one.id,
            username=one.username,
            full_name=one.full_name,
            email=one.email,
            arrival=one.arrival,
            disabled=one.disabled,
            platform=one.platform,
            image_url=one.image_url
        )
        users.append(user)
    return users


# -------------------------------------------------------------------------------
def user_exist(db: Session, email: str, username: str):
    db_user_name = db.query(models.Users).filter(models.Users.username == username).first()
    db_user_mail = db.query(models.Users).filter(models.Users.email == email).first()

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
        user = schemas.rUser(
            id=result.id,
            username=result.username,
            full_name=result.full_name,
            email=result.email,
            image_url=result.image_url,
            arrival=result.arrival,
            disabled=result.disabled,
            platform=result.platform
        )
        if result.hashed_password == hash_password(password):
            return True, user
        return False, user
    return False, None


# -------------------------------------------------------------------------------
def check_user_from_email(db: Session, email, password):
    result = db.query(models.Users).filter(models.Users.email == email).first()
    if result is not None:
        user = schemas.rUser(
            id=result.id,
            username=result.username,
            full_name=result.full_name,
            email=result.email,
            image_url=result.image_url,
            arrival=result.arrival,
            disabled=result.disabled,
            platform=result.platform
        )
        if result.hashed_password == hash_password(password):
            return True, user
        return False, user
    return False, None


# -------------------------------------------------------------------------------
def check_user_all(db: Session, username, email, password):
    result = db.query(models.Users).filter(models.Users.username == username).filter(models.Users.email == email).first()
    if result is not None:
        user = schemas.rUser(
            id=result.id,
            username=result.username,
            full_name=result.full_name,
            email=result.email,
            image_url=result.image_url,
            arrival=result.arrival,
            disabled=result.disabled,
            platform=result.platform
        )
        if result.hashed_password == hash_password(password):
            return True, user
        return False, user
    return False, None


# ===============================================================================
# Création
# ===============================================================================
def create_user(db: Session, v_user: schemas.iUser):
    id = 1
    boucleID = True
    while boucleID:
        if not get_user(db, id):
            boucleID = False
        else:
            id += 1
    db_user = models.Users(
        id = id,
        username = v_user.username,
        full_name = v_user.full_name,
        email = v_user.email,
        image_url = None,
        hashed_password = hash_password(v_user.password),
        platform = utils.CONFIG['api']['platform'],
        arrival = dt.datetime.today(),
        disabled = 0
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
def update_user(db: Session, src_user: schemas.Users, v_user: schemas.uUser):
    db_user_name = db.query(models.Users).filter(models.Users.username == src_user.username).first()
    
    if db_user_name:
        db.execute(update(models.Users).where(models.Users.id == src_user.id).values(
            username = v_user.username,
            full_name = v_user.full_name,
            email = v_user.email,
            image_url = v_user.image_url,
            disabled = v_user.disabled
        ))
        db.commit()
        db.refresh(db_user_name)
        return get_user(db=db, ID=src_user.id)
    return {"error": 404, "text": "User not found"}
