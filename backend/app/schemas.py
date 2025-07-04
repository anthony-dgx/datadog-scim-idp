"""
SCIM Schema Models for Datadog Integration

This module defines Pydantic models that represent SCIM (System for Cross-domain Identity Management)
data structures for Datadog integration. These models serve as both request/response schemas
and documentation for customers implementing SCIM.

The models follow the SCIM 2.0 specification (RFC 7643) and Datadog's specific implementation
requirements. Each model includes examples and validation rules to help customers understand
the expected data formats.

Key SCIM Concepts:
- Users: Individual identities with attributes like email, name, title
- Groups: Collections of users with display names and member lists
- Schemas: URN identifiers that define the structure of SCIM resources
- Patches: Operations for partial updates using SCIM PATCH format

For complete API documentation, see: https://docs.datadoghq.com/api/latest/scim/
"""

from pydantic import BaseModel, EmailStr, Field, validator, computed_field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

# Base schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    formatted_name: Optional[str] = None
    title: Optional[str] = None
    active: bool = True

class UserCreate(UserBase):
    pass

class UserUpdate(UserBase):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    active: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    uuid: str
    external_id: Optional[str] = None
    datadog_user_id: Optional[str] = None
    last_synced: Optional[datetime] = None
    sync_status: str
    sync_error: Optional[str] = None
    idp_roles: List[str] = []
    last_role_sync: Optional[datetime] = None
    roles: List[Dict[str, Any]] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class GroupBase(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

class GroupCreate(GroupBase):
    member_ids: Optional[List[int]] = []

class GroupUpdate(GroupBase):
    display_name: Optional[str] = None
    member_ids: Optional[List[int]] = None

class GroupResponse(GroupBase):
    id: int
    uuid: str
    external_id: Optional[str] = None
    datadog_group_id: Optional[str] = None
    last_synced: Optional[datetime] = None
    sync_status: str
    sync_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    members: List[UserResponse]

    class Config:
        from_attributes = True

# SCIM Schemas
class SCIMEmail(BaseModel):
    """
    SCIM Email attribute for users.
    
    Represents an email address with optional type and primary flags.
    Datadog typically uses the 'work' type for business emails.
    
    Example:
        {
            "value": "john.doe@company.com",
            "type": "work",
            "primary": true
        }
    """
    value: EmailStr = Field(..., description="The email address")
    type: Optional[str] = Field(default="work", description="Email type (work, home, other)")
    primary: Optional[bool] = Field(default=True, description="Whether this is the primary email")
    
    class Config:
        schema_extra = {
            "example": {
                "value": "john.doe@company.com",
                "type": "work",
                "primary": True
            }
        }

class SCIMName(BaseModel):
    """
    SCIM Name attribute for users.
    
    Represents a person's name with individual components.
    The 'formatted' field should contain the full display name.
    
    Example:
        {
            "formatted": "John Doe",
            "givenName": "John",
            "familyName": "Doe",
            "middleName": "Michael",
            "honorificPrefix": "Dr.",
            "honorificSuffix": "Jr."
        }
    """
    formatted: str = Field(..., description="Full display name")
    givenName: Optional[str] = Field(None, description="First name")
    familyName: Optional[str] = Field(None, description="Last name")
    middleName: Optional[str] = Field(None, description="Middle name")
    honorificPrefix: Optional[str] = Field(None, description="Title (Dr., Ms., etc.)")
    honorificSuffix: Optional[str] = Field(None, description="Suffix (Jr., Sr., etc.)")
    
    class Config:
        schema_extra = {
            "example": {
                "formatted": "John Doe",
                "givenName": "John",
                "familyName": "Doe"
            }
        }

class SCIMUser(BaseModel):
    """
    SCIM User resource for creating and updating users in Datadog.
    
    This model represents a complete user with all attributes that can be
    sent to Datadog's SCIM API. Required fields are userName and emails.
    
    Key Points:
    - userName is typically the user's email address
    - emails array should contain at least one email
    - active defaults to True for new users
    - schemas array identifies this as a SCIM User resource
    
    Example Usage:
        user = SCIMUser(
            userName="john.doe@company.com",
            emails=[SCIMEmail(value="john.doe@company.com")],
            name=SCIMName(formatted="John Doe", givenName="John", familyName="Doe"),
            title="Software Engineer",
            active=True
        )
    """
    userName: str = Field(..., description="Unique identifier, typically email address")
    emails: List[SCIMEmail] = Field(..., description="List of email addresses")
    name: Optional[SCIMName] = Field(None, description="User's name components")
    displayName: Optional[str] = Field(None, description="Preferred display name")
    title: Optional[str] = Field(None, description="Job title")
    active: Optional[bool] = Field(default=True, description="Whether user is active")
    locale: Optional[str] = Field(None, description="User's locale (en-US, etc.)")
    timezone: Optional[str] = Field(None, description="User's timezone")
    externalId: Optional[str] = Field(None, description="External system identifier")
    schemas: List[str] = Field(default=["urn:ietf:params:scim:schemas:core:2.0:User"], description="SCIM schema URNs")
    
    @validator('emails')
    def emails_must_not_be_empty(cls, v):
        if not v:
            raise ValueError('At least one email is required')
        return v
    
    @validator('userName')
    def username_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('userName is required and cannot be empty')
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "userName": "john.doe@company.com",
                "emails": [
                    {
                        "value": "john.doe@company.com",
                        "type": "work",
                        "primary": True
                    }
                ],
                "name": {
                    "formatted": "John Doe",
                    "givenName": "John",
                    "familyName": "Doe"
                },
                "displayName": "John Doe",
                "title": "Software Engineer",
                "active": True,
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"]
            }
        }

class SCIMUserResponse(SCIMUser):
    """
    SCIM User response from Datadog API.
    
    This model represents the response received from Datadog when creating,
    updating, or retrieving users. It includes the same fields as SCIMUser
    plus additional metadata from Datadog.
    
    Key Response Fields:
    - id: Datadog's unique identifier for the user (UUID format)
    - meta: Metadata about the resource (created date, etc.)
    - All fields from SCIMUser request
    
    Example Response:
        {
            "id": "12345678-1234-1234-1234-123456789012",
            "userName": "john.doe@company.com",
            "emails": [...],
            "name": {...},
            "active": true,
            "meta": {
                "resourceType": "User",
                "created": "2023-01-01T00:00:00Z",
                "lastModified": "2023-01-01T00:00:00Z",
                "location": "https://api.datadoghq.com/api/v2/scim/Users/12345678-1234-1234-1234-123456789012"
            }
        }
    """
    id: str = Field(..., description="Datadog's unique user identifier")
    userName: str = Field(..., description="User's username/email")
    emails: List[SCIMEmail] = Field(..., description="User's email addresses")
    name: Optional[SCIMName] = Field(None, description="User's name components")
    displayName: Optional[str] = Field(None, description="Display name")
    title: Optional[str] = Field(None, description="Job title")
    active: Optional[bool] = Field(default=True, description="Whether user is active")
    locale: Optional[str] = Field(None, description="User's locale")
    timezone: Optional[str] = Field(None, description="User's timezone")
    externalId: Optional[str] = Field(None, description="External system ID")
    schemas: List[str] = Field(default=["urn:ietf:params:scim:schemas:core:2.0:User"], description="SCIM schema URNs")
    meta: Optional[Dict[str, Any]] = Field(None, description="Resource metadata from Datadog")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "12345678-1234-1234-1234-123456789012",
                "userName": "john.doe@company.com",
                "emails": [
                    {
                        "value": "john.doe@company.com",
                        "type": "work",
                        "primary": True
                    }
                ],
                "name": {
                    "formatted": "John Doe",
                    "givenName": "John",
                    "familyName": "Doe"
                },
                "active": True,
                "meta": {
                    "resourceType": "User",
                    "created": "2023-01-01T00:00:00Z",
                    "lastModified": "2023-01-01T00:00:00Z"
                },
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"]
            }
        }

class SCIMGroupMember(BaseModel):
    """
    SCIM Group Member reference.
    
    Represents a user that belongs to a group. The 'value' field should
    contain the user's Datadog ID (from SCIMUserResponse.id).
    
    Example:
        {
            "$ref": "https://api.datadoghq.com/api/v2/scim/Users/12345678-1234-1234-1234-123456789012",
            "value": "12345678-1234-1234-1234-123456789012",
            "display": "John Doe",
            "type": "User"
        }
    """
    ref: Optional[str] = Field(None, alias="$ref", description="Full URL reference to the user")
    value: str = Field(..., description="User's Datadog ID")
    display: Optional[str] = Field(None, description="User's display name")
    type: Optional[str] = Field(default="User", description="Member type (always 'User')")
    
    class Config:
        allow_population_by_field_name = True
        schema_extra = {
            "example": {
                "$ref": "https://api.datadoghq.com/api/v2/scim/Users/12345678-1234-1234-1234-123456789012",
                "value": "12345678-1234-1234-1234-123456789012",
                "display": "John Doe",
                "type": "User"
            }
        }

class SCIMGroup(BaseModel):
    """
    SCIM Group resource for creating and updating groups in Datadog.
    
    This model represents a group/team with members. Groups are used to
    organize users and control access to Datadog resources.
    
    Key Points:
    - displayName is the group's visible name in Datadog
    - externalId links to your internal system's group identifier
    - members array contains user references (Datadog user IDs)
    - schemas array identifies this as a SCIM Group resource
    
    Example Usage:
        group = SCIMGroup(
            displayName="Engineering Team",
            externalId="eng-team-001",
            members=[
                SCIMGroupMember(
                    value="12345678-1234-1234-1234-123456789012",
                    display="John Doe"
                )
            ]
        )
    """
    displayName: str = Field(..., description="Group's display name")
    externalId: Optional[str] = Field(None, description="External system identifier")
    members: Optional[List[SCIMGroupMember]] = Field(default=[], description="Group members")
    schemas: List[str] = Field(default=["urn:ietf:params:scim:schemas:core:2.0:Group"], description="SCIM schema URNs")
    
    @validator('displayName')
    def displayname_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('displayName is required and cannot be empty')
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "displayName": "Engineering Team",
                "externalId": "eng-team-001",
                "members": [
                    {
                        "$ref": "https://api.datadoghq.com/api/v2/scim/Users/12345678-1234-1234-1234-123456789012",
                        "value": "12345678-1234-1234-1234-123456789012",
                        "display": "John Doe",
                        "type": "User"
                    }
                ],
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"]
            }
        }

class SCIMGroupResponse(SCIMGroup):
    """
    SCIM Group response from Datadog API.
    
    This model represents the response received from Datadog when creating,
    updating, or retrieving groups. It includes the same fields as SCIMGroup
    plus additional metadata from Datadog.
    
    Key Response Fields:
    - id: Datadog's unique identifier for the group (UUID format)
    - meta: Metadata about the resource (created date, etc.)
    - All fields from SCIMGroup request
    
    Example Response:
        {
            "id": "87654321-4321-4321-4321-210987654321",
            "displayName": "Engineering Team",
            "externalId": "eng-team-001",
            "members": [...],
            "meta": {
                "resourceType": "Group",
                "created": "2023-01-01T00:00:00Z",
                "lastModified": "2023-01-01T00:00:00Z"
            }
        }
    """
    id: str = Field(..., description="Datadog's unique group identifier")
    displayName: str = Field(..., description="Group's display name")
    externalId: Optional[str] = Field(None, description="External system identifier")
    members: Optional[List[SCIMGroupMember]] = Field(default=[], description="Group members")
    schemas: List[str] = Field(default=["urn:ietf:params:scim:schemas:core:2.0:Group"], description="SCIM schema URNs")
    meta: Optional[Dict[str, Any]] = Field(None, description="Resource metadata from Datadog")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "87654321-4321-4321-4321-210987654321",
                "displayName": "Engineering Team",
                "externalId": "eng-team-001",
                "members": [
                    {
                        "$ref": "https://api.datadoghq.com/api/v2/scim/Users/12345678-1234-1234-1234-123456789012",
                        "value": "12345678-1234-1234-1234-123456789012",
                        "display": "John Doe",
                        "type": "User"
                    }
                ],
                "meta": {
                    "resourceType": "Group",
                    "created": "2023-01-01T00:00:00Z",
                    "lastModified": "2023-01-01T00:00:00Z"
                },
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"]
            }
        }

class SCIMPatchOperation(BaseModel):
    """
    SCIM PATCH operation for partial updates.
    
    PATCH operations allow you to make targeted changes to users or groups
    without sending the entire resource. This is more efficient and reduces
    the chance of conflicts.
    
    Operation Types:
    - "add": Add a new value to an attribute
    - "remove": Remove a value from an attribute
    - "replace": Replace an existing value
    
    Common Paths:
    - "active": Set user active/inactive status
    - "displayName": Update group display name
    - "members": Add/remove group members
    - "members[value eq \"user-id\"]": Target specific group member
    
    Examples:
        # Deactivate a user
        {"op": "replace", "path": "active", "value": False}
        
        # Add user to group
        {"op": "add", "path": "members", "value": [{"value": "user-id", "display": "John Doe"}]}
        
        # Remove user from group
        {"op": "remove", "path": "members[value eq \"user-id\"]"}
        
        # Update group name
        {"op": "replace", "path": "displayName", "value": "New Team Name"}
    """
    op: str = Field(..., description="Operation type: add, remove, replace")
    path: str = Field(..., description="Attribute path to modify")
    value: Optional[Any] = Field(None, description="New value for the attribute")
    
    @validator('op')
    def op_must_be_valid(cls, v):
        valid_ops = ['add', 'remove', 'replace']
        if v not in valid_ops:
            raise ValueError(f'op must be one of {valid_ops}')
        return v
    
    class Config:
        schema_extra = {
            "examples": [
                {
                    "description": "Deactivate a user",
                    "value": {
                        "op": "replace",
                        "path": "active",
                        "value": False
                    }
                },
                {
                    "description": "Add user to group",
                    "value": {
                        "op": "add",
                        "path": "members",
                        "value": [
                            {
                                "value": "12345678-1234-1234-1234-123456789012",
                                "display": "John Doe"
                            }
                        ]
                    }
                },
                {
                    "description": "Remove user from group",
                    "value": {
                        "op": "remove",
                        "path": "members[value eq \"12345678-1234-1234-1234-123456789012\"]"
                    }
                }
            ]
        }

class SCIMPatchRequest(BaseModel):
    """
    SCIM PATCH request containing multiple operations.
    
    A PATCH request can contain multiple operations that are applied in sequence.
    This allows you to make complex changes in a single API call.
    
    Example Multi-Operation PATCH:
        patch_request = SCIMPatchRequest(
            Operations=[
                SCIMPatchOperation(op="replace", path="active", value=False),
                SCIMPatchOperation(op="replace", path="title", value="Former Employee")
            ]
        )
    
    Common Use Cases:
    - Deactivate user and update title
    - Add multiple users to a group
    - Update multiple group attributes
    - Remove user from multiple groups
    """
    schemas: List[str] = Field(default=["urn:ietf:params:scim:api:messages:2.0:PatchOp"], description="SCIM PATCH schema URN")
    Operations: List[SCIMPatchOperation] = Field(..., description="List of operations to perform")
    
    @validator('Operations')
    def operations_must_not_be_empty(cls, v):
        if not v:
            raise ValueError('At least one operation is required')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [
                    {
                        "op": "replace",
                        "path": "active",
                        "value": False
                    },
                    {
                        "op": "replace",
                        "path": "title",
                        "value": "Former Employee"
                    }
                ]
            }
        }

# API Response schemas
class SyncResponse(BaseModel):
    success: bool
    message: str
    datadog_id: Optional[str] = None
    error: Optional[str] = None

class SyncStatus(str, Enum):
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"

class BulkSyncResponse(BaseModel):
    total: int
    synced: int
    failed: int
    errors: List[str] = []

# SAML Schemas
class SAMLMetadataCreate(BaseModel):
    entity_id: str
    metadata_xml: str

class SAMLMetadataResponse(BaseModel):
    id: int
    entity_id: str
    acs_url: Optional[str] = None
    acs_binding: Optional[str] = None
    sls_url: Optional[str] = None
    sls_binding: Optional[str] = None
    name_id_formats: List[str] = []
    required_attributes: List[str] = []
    active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SAMLLoginRequest(BaseModel):
    SAMLRequest: str
    RelayState: Optional[str] = None

class SAMLValidateRequest(BaseModel):
    email: EmailStr
    SAMLRequest: str
    RelayState: Optional[str] = None

class SAMLResponseData(BaseModel):
    SAMLResponse: str
    RelayState: Optional[str] = None
    acs_url: str

# Role Schemas for SAML Role Mapping
class RoleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    idp_role_value: Optional[str] = Field(None, description="IdP role value that maps to this role")
    datadog_role_id: Optional[str] = Field(None, description="Datadog role UUID if synced")
    active: bool = True
    is_default: bool = False

class RoleCreate(RoleBase):
    """Schema for creating a new role"""
    pass

class RoleUpdate(BaseModel):
    """Schema for updating a role"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    idp_role_value: Optional[str] = None
    datadog_role_id: Optional[str] = None
    active: Optional[bool] = None
    is_default: Optional[bool] = None

class RoleResponse(RoleBase):
    """Schema for role responses"""
    id: int
    uuid: str
    created_at: datetime
    updated_at: datetime
    
    @computed_field
    @property
    def user_count(self) -> int:
        """Calculate the number of users assigned to this role"""
        # If we have a users relationship loaded, count them
        if hasattr(self, '_users') and self._users:
            return len(self._users)
        # Otherwise return 0 as fallback
        return 0
    
    @classmethod
    def from_orm(cls, obj):
        """Custom from_orm method to handle user_count calculation"""
        # Store the users relationship for the computed field
        instance = super().from_orm(obj)
        if hasattr(obj, 'users') and obj.users is not None:
            instance._users = obj.users
        else:
            instance._users = []
        return instance

    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "id": 1,
                "uuid": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Administrator",
                "description": "Full system access",
                "idp_role_value": "admin",
                "datadog_role_id": "datadog-admin-role-id",
                "active": True,
                "is_default": False,
                "user_count": 5,
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z"
            }
        }

class RoleMappingRequest(BaseModel):
    """Schema for creating role mappings"""
    idp_role_value: str = Field(..., description="Role value from IdP")
    role_name: str = Field(..., description="Local role name")
    description: Optional[str] = None
    active: bool = True

    class Config:
        schema_extra = {
            "example": {
                "idp_role_value": "admin",
                "role_name": "Administrator",
                "description": "Full access administrator role",
                "active": True
            }
        } 