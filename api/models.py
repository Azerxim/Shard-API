from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, BigInteger, Date, DateTime, Float, Interval, Text, Time, Unicode, UnicodeText
from sqlalchemy.orm import relationship
import datetime as dt

from .database import Base

class TableAuth(Base):

    __tablename__ = "auth"

    idAuth = Column(Integer, primary_key=True, index=True)
    platform = Column(String)
    pseudo = Column(String)
    password = Column(String)
    mail = Column(String)
    statut = Column(String)
    image_url = Column(String)
    arrival = Column(String)

    # platform_discord_id = Column(String)
    # platform_discord_name = Column(String)
    # platform_discord_mail = Column(String)
    # platform_discord_image_url = Column(String)

    # platform_github_id = Column(String)
    # platform_github_name = Column(String)
    # platform_github_mail = Column(String)
    # platform_github_image_url = Column(String)

    # platform_microsoft_id = Column(String)
    # platform_microsoft_name = Column(String)
    # platform_microsoft_mail = Column(String)
    # platform_microsoft_image_url = Column(String)

    # param_visible = Column(Integer)
    # param_maillist = Column(Integer)
    # param_beta = Column(Integer)


# class Table(Base):
#
#     __tablename__=""
#
#     playerid = Column(BigInteger, ForeignKey("core.playerid"), primary_key=True)
#
#     owner = relationship("TableCore", back_populates="")


################# Users ########################

class Users(Base):

    __tablename__="Users"

    id = Column(Integer)
    username = Column(String, primary_key=True)
    full_name = Column(String)
    email = Column(String)
    hashed_password = Column(String)
    platform = Column(String)
    arrival = Column(DateTime)
    disabled = Column(Boolean)


################# Security #####################

class SecurityUsers(Base):

    __tablename__="SecurityUsers"

    username = Column(String, primary_key=True)
    full_name = Column(String)
    email = Column(String)
    hashed_password = Column(String)
    disabled = Column(Boolean)