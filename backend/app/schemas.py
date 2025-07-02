from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
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
    value: str
    type: str = "work"
    primary: bool = True

class SCIMName(BaseModel):
    formatted: str
    familyName: Optional[str] = None
    givenName: Optional[str] = None

class SCIMUser(BaseModel):
    userName: str
    active: bool = True
    emails: List[SCIMEmail]
    name: SCIMName
    title: Optional[str] = None
    schemas: List[str] = ["urn:ietf:params:scim:schemas:core:2.0:User"]
    externalId: Optional[str] = None

class SCIMUserResponse(SCIMUser):
    id: str
    meta: Dict[str, Any] = {}

class SCIMGroupMember(BaseModel):
    ref: str = Field(alias="$ref")
    value: str
    display: str
    type: str = "User"

    class Config:
        populate_by_name = True

class SCIMGroup(BaseModel):
    displayName: str
    externalId: Optional[str] = None
    members: List[SCIMGroupMember] = []
    schemas: List[str] = ["urn:ietf:params:scim:schemas:core:2.0:Group"]

class SCIMGroupResponse(SCIMGroup):
    id: str
    meta: Dict[str, Any] = {}

class SCIMPatchOperation(BaseModel):
    op: str  # "add", "remove", "replace"
    path: Optional[str] = None
    value: Optional[Any] = None

class SCIMPatchRequest(BaseModel):
    schemas: List[str] = ["urn:ietf:params:scim:api:messages:2.0:PatchOp"]
    Operations: List[SCIMPatchOperation]

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