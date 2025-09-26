from sqlalchemy.orm import Session
import hashlib

from . import models
from topazdevsdk import colors

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