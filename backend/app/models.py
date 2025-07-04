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

# Association table for many-to-many relationship between users and roles
user_role_association = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True)
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
    
    # SAML Role mapping fields
    idp_roles = Column(Text, nullable=True)  # JSON array of roles from IdP
    last_role_sync = Column(DateTime, nullable=True)  # When roles were last synced
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    groups = relationship("Group", secondary=user_group_association, back_populates="members")
    roles = relationship("Role", secondary=user_role_association, back_populates="users")
    
    def to_dict(self):
        import json
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
            "idp_roles": json.loads(self.idp_roles) if self.idp_roles else [],
            "last_role_sync": self.last_role_sync.isoformat() if self.last_role_sync else None,
            "roles": [role.to_dict() for role in self.roles] if self.roles else [],
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

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # Role mapping fields
    idp_role_value = Column(String, nullable=True)  # Value from IdP that maps to this role
    datadog_role_id = Column(String, nullable=True)  # Datadog role UUID if synced
    
    # Status fields
    active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # Default role for new users
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    users = relationship("User", secondary=user_role_association, back_populates="roles")
    
    def to_dict(self):
        return {
            "id": self.id,
            "uuid": self.uuid,
            "name": self.name,
            "description": self.description,
            "idp_role_value": self.idp_role_value,
            "datadog_role_id": self.datadog_role_id,
            "active": self.active,
            "is_default": self.is_default,
            "user_count": len(self.users) if self.users else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class SAMLMetadata(Base):
    __tablename__ = "saml_metadata"
    
    id = Column(Integer, primary_key=True, index=True)
    entity_id = Column(String, unique=True, index=True, nullable=False)
    metadata_xml = Column(Text, nullable=False)
    
    # Parsed metadata fields for easy access
    acs_url = Column(String, nullable=True)  # Primary AssertionConsumerService URL
    acs_binding = Column(String, nullable=True)  # ACS binding type
    sls_url = Column(String, nullable=True)  # SingleLogoutService URL
    sls_binding = Column(String, nullable=True)  # SLS binding type
    
    # Additional metadata
    name_id_formats = Column(Text, nullable=True)  # JSON array of supported NameID formats
    required_attributes = Column(Text, nullable=True)  # JSON array of required attributes
    
    # Status fields
    active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        import json
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "acs_url": self.acs_url,
            "acs_binding": self.acs_binding,
            "sls_url": self.sls_url,
            "sls_binding": self.sls_binding,
            "name_id_formats": json.loads(self.name_id_formats) if self.name_id_formats else [],
            "required_attributes": json.loads(self.required_attributes) if self.required_attributes else [],
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        } 