from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, BigInteger, Date, DateTime, Float, Interval, Text, Time, Unicode, UnicodeText
from sqlalchemy.orm import relationship
import datetime as dt

from .database import Base


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

    platform_discord_id = Column(String)
    platform_discord_name = Column(String)
    platform_discord_mail = Column(String)
    platform_discord_image_url = Column(String)


################# Security #####################

class SecurityUsers(Base):

    __tablename__="SecurityUsers"

    username = Column(String, primary_key=True)
    full_name = Column(String)
    email = Column(String)
    hashed_password = Column(String)
    disabled = Column(Boolean)