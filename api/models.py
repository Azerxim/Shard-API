from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, BigInteger, Date, DateTime, Float, Interval, Text, Time, Unicode, UnicodeText
from sqlalchemy.orm import relationship
import datetime as dt

from .database import Base


################# Users ########################

class Users(Base):

    __tablename__="Users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True)
    email = Column(String, unique=True)
    hashed_password = Column(String)
    pseudo = Column(String)
    image_url = Column(String)
    arrival = Column(DateTime)
    is_disabled = Column(Boolean)
    is_admin = Column(Boolean)

    platforms = relationship("UserPlatforms", back_populates="user", cascade="all, delete-orphan")

class UserPlatforms(Base):

    __tablename__="UserPlatforms"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("Users.id"))
    platform = Column(String)
    uid = Column(String)

    user = relationship("Users", back_populates="platforms")


############### Bibliothèque ####################

class Journaux(Base):

    __tablename__="Journaux"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("Users.id"))
    author = Column(String)
    title = Column(String)
    description = Column(Text)
    
    cover_url = Column(String)
    cover_icon = Column(String)
    cover_color = Column(String)

    link = Column(String)
    uid = Column(String)

    published_date = Column(Date)
    created_at = Column(DateTime)


class Livres(Base):

    __tablename__="Livres"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("Users.id"))
    author = Column(String)
    title = Column(String)
    description = Column(Text)
    
    cover_url = Column(String)
    cover_icon = Column(String)
    cover_color = Column(String)

    pages = Column(Integer)
    language = Column(String)

    link = Column(String)

    published_date = Column(Date)
    created_at = Column(DateTime)


################# Security #####################

class SecurityUsers(Base):

    __tablename__="SecurityUsers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True)
    full_name = Column(String)
    email = Column(String, unique=True)
    hashed_password = Column(String)
    disabled = Column(Boolean)