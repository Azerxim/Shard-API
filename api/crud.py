from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import text
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
            platform_discord_id=result.platform_discord_id,
            platform_discord_name=result.platform_discord_name,
            platform_discord_mail=result.platform_discord_mail,
            platform_discord_image_url=result.platform_discord_image_url
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
            platform_discord_id=one.platform_discord_id,
            platform_discord_name=one.platform_discord_name,
            platform_discord_mail=one.platform_discord_mail,
            platform_discord_image_url=one.platform_discord_image_url
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
# def user_exist_platform(db: Session, user: schemas.Users, platform):
#     db_user_name = db.query(models.Users).filter(models.Users.username == user.username).first()
#     db_user_mail = db.query(models.Users).filter(models.Users.email == user.email).first()

#     if db_user_name:
#         return True, db_user_name
#     elif db_user_mail:
#         return True, db_user_mail
#     else:
#         return False, None


# -------------------------------------------------------------------------------
def check_user_from_name(db: Session, username, password):
    result = db.query(models.Users).filter(models.Users.username == username).first()
    if result is not None:
        user = schemas.rUser(
            id=result.id,
            username=result.username,
            full_name=result.full_name,
            email=result.email,
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
        hashed_password = hash_password(v_user.password),
        platform = utils.CONFIG['api']['platform'],
        arrival = dt.datetime.today(),
        disabled = 0,
        platform_discord_id = None,
        platform_discord_name = None,
        platform_discord_mail = None,
        platform_discord_image_url = None
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def create_user_discord(db: Session, v_user: schemas.iDiscordUser):
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
        hashed_password = hash_password(v_user.password),
        platform = 'discord',
        arrival = dt.datetime.today(),
        disabled = 0,

        platform_discord_id = v_user.platform_discord_id,
        platform_discord_name = v_user.platform_discord_name,
        platform_discord_mail = v_user.platform_discord_mail,
        platform_discord_image_url = v_user.platform_discord_image_url
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# def create_user_platform(db: Session, v_user: schemas.iUser, platform: str):
#     # Platform ID est stocker dans le password et hash dans la DB
#     id = 1
#     boucleID = True
#     while boucleID:
#         if not get_user(db, id):
#             boucleID = False
#         else:
#             id += 1
#     db_user = models.Users(
#         id = id,
#         username = v_user.username,
#         full_name = v_user.full_name,
#         email = v_user.email,
#         hashed_password = hash_password(v_user.password),
#         platform = platform,
#         arrival = dt.datetime.today(),
#         disabled = 0
#     )
    
#     db.add(db_user)
#     db.commit()
#     db.refresh(db_user)
#     return db_user

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
    db_user_name = db.query(models.Users).filter(models.Users.username == v_user.username).first()
    db_user_mail = db.query(models.Users).filter(models.Users.email == v_user.email).first()

    if (not db_user_name) and (v_user.username != ""):
        src_user.username = v_user.username

    if (v_user.full_name != ""):
        src_user.full_name = v_user.full_name

    if (not db_user_mail) and (v_user.email != "" and "@" in v_user.email):
        src_user.email = v_user.email

    if (v_user.disabled is True) or (v_user.disabled is False):
        src_user.disabled = v_user.disabled

    if (v_user.platform_discord_id != ""):
        src_user.platform_discord_id = v_user.platform_discord_id

    if (v_user.platform_discord_name != ""):
        src_user.platform_discord_name = v_user.platform_discord_name

    if (v_user.platform_discord_mail != ""):
        src_user.platform_discord_mail = v_user.platform_discord_mail

    if (v_user.platform_discord_image_url != ""):
        src_user.platform_discord_image_url = v_user.platform_discord_image_url

    db.commit()
    db.refresh(src_user)
    return src_user
