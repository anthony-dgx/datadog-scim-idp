from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

# Association table for many-to-many relationship between users and groups
user_group_association = Table(
    'user_groups',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('group_id', Integer, ForeignKey('groups.id'), primary_key=True)
)

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    formatted_name = Column(String, nullable=True)
    title = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    
    # SCIM specific fields
    external_id = Column(String, nullable=True)  # External ID for SCIM
    datadog_user_id = Column(String, nullable=True)  # Datadog user UUID
    last_synced = Column(DateTime, nullable=True)
    sync_status = Column(String, default="pending")  # pending, synced, failed
    sync_error = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    groups = relationship("Group", secondary=user_group_association, back_populates="members")
    
    def to_dict(self):
        return {
            "id": self.id,
            "uuid": self.uuid,
            "username": self.username,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "formatted_name": self.formatted_name,
            "title": self.title,
            "active": self.active,
            "external_id": self.external_id,
            "datadog_user_id": self.datadog_user_id,
            "last_synced": self.last_synced.isoformat() if self.last_synced else None,
            "sync_status": self.sync_status,
            "sync_error": self.sync_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class Group(Base):
    __tablename__ = "groups"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    display_name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # SCIM specific fields
    external_id = Column(String, nullable=True)  # External ID for SCIM
    datadog_group_id = Column(String, nullable=True)  # Datadog group UUID
    last_synced = Column(DateTime, nullable=True)
    sync_status = Column(String, default="pending")  # pending, synced, failed
    sync_error = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    members = relationship("User", secondary=user_group_association, back_populates="groups")
    
    def to_dict(self):
        return {
            "id": self.id,
            "uuid": self.uuid,
            "display_name": self.display_name,
            "description": self.description,
            "external_id": self.external_id,
            "datadog_group_id": self.datadog_group_id,
            "last_synced": self.last_synced.isoformat() if self.last_synced else None,
            "sync_status": self.sync_status,
            "sync_error": self.sync_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "members": [member.to_dict() for member in self.members]
        } 