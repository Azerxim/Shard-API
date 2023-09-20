from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import text
import time as t, datetime as dt
from operator import itemgetter
from . import models, schemas



# -------------------------------------------------------------------------------
def user_exist(db: Session, platform: str, mail: str, pseudo: str, id: str):
    if platform == "Discord":
        db_user_id = db.query(models.TableAuth).filter(models.TableAuth.platform_discord_id == id).first()
        db_user_mail = db.query(models.TableAuth).filter(models.TableAuth.platform_discord_mail == mail).first()
    elif platform == "Github":
        db_user_id = db.query(models.TableAuth).filter(models.TableAuth.platform_github_id == id).first()
        db_user_mail = db.query(models.TableAuth).filter(models.TableAuth.platform_github_mail == mail).first()
    elif platform == "Microsoft":
        db_user_id = db.query(models.TableAuth).filter(models.TableAuth.platform_microsoft_id == id).first()
        db_user_mail = db.query(models.TableAuth).filter(models.TableAuth.platform_microsoft_mail == mail).first()
    else:
        db_user_id = db.query(models.TableAuth).filter(models.TableAuth.idAuth == id).first()
        db_user_mail = db.query(models.TableAuth).filter(models.TableAuth.mail == mail).first()

    if not db_user_id and not db_user_mail:
        return False
    return True


# -------------------------------------------------------------------------------
def get_user(db: Session, ID: int):
    return db.query(models.TableAuth).filter(models.TableAuth.idAuth == ID).first()


# -------------------------------------------------------------------------------
def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.TableAuth).offset(skip).limit(limit).all()


# ===============================================================================
# Création
# ===============================================================================
def create_user(db: Session, v_platform: str, v_mail: str, v_pseudo: str, v_mdp: str, v_id_platform: str, v_img_platform: str):
    id = 1
    boucleID = True
    while boucleID:
        if not get_user(db, id):
            boucleID = False
        else:
            id += 1
    # print(f'ID: {id}')
    db_user = models.TableAuth(
        idAuth = id,
        platform = v_platform,
        pseudo = v_pseudo,
        password = v_mdp,
        mail = v_mail,
        statut = "Standard",
        image_url = "https://www.topazdev.fr/images/image_profil_white.png",
        arrival = str(dt.date.today()),

        platform_discord_id = "",
        platform_discord_mail = "",
        platform_discord_image_url = "",

        platform_github_id = "",
        platform_github_mail = "",
        platform_github_image_url = "",
        
        platform_microsoft_id = "",
        platform_microsoft_mail = "",
        platform_microsoft_image_url = "",

        param_visible = 1,
        param_maillist = 1,
        param_beta = 0
    )

    if v_platform == "Discord":
        db_user.platform_discord_id = v_id_platform
        db_user.platform_discord_mail = v_mail
        db_user.platform_discord_image_url = v_img_platform

    elif v_platform == "Github":
        db_user.platform_github_id = v_id_platform
        db_user.platform_github_mail = v_mail
        db_user.platform_github_image_url = v_img_platform

    elif v_platform == "Microsoft":
        db_user.platform_microsoft_id = v_id_platform
        db_user.platform_microsoft_mail = v_mail
        db_user.platform_microsoft_image_url = v_img_platform
    
    # print(f'DB user: {db_user}')
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user