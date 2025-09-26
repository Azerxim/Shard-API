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

################# Security #####################

class SecurityUsers(Base):

    __tablename__="SecurityUsers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True)
    full_name = Column(String)
    email = Column(String, unique=True)
    hashed_password = Column(String)
    disabled = Column(Boolean)