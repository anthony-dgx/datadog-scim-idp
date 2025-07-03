from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import logging
import asyncio

from ..database import get_db
from ..models import User, Group
from ..schemas import UserCreate, UserUpdate, UserResponse, SyncResponse, SCIMUser, SCIMEmail, SCIMName
from ..scim_client import scim_client
from ..logging_config import action_logger

router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger(__name__)

def user_to_scim(user: User, base_url: str) -> SCIMUser:
    """Convert a User model to SCIM format"""
    return SCIMUser(
        userName=user.email,
        active=user.active,
        emails=[SCIMEmail(value=user.email, type="work", primary=True)],
        name=SCIMName(
            formatted=user.formatted_name or f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
            givenName=user.first_name,
            familyName=user.last_name
        ),
        title=user.title,
        externalId=user.external_id or user.uuid
    )

@router.get("/", response_model=List[UserResponse])
def get_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all users"""
    users = db.query(User).offset(skip).limit(limit).all()
    return [UserResponse.model_validate(user.to_dict()) for user in users]

@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get a specific user by ID"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user.to_dict())

@router.post("/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user"""
    try:
        # Check if user with same email or username already exists
        existing_user = db.query(User).filter(
            (User.email == user.email) | (User.username == user.username)
        ).first()
        if existing_user:
            # Log failed attempt
            action_logger.log_user_action(
                action="create",
                user_data=user.model_dump(),
                success=False,
                error="User with this email or username already exists"
            )
            raise HTTPException(
                status_code=400, 
                detail="User with this email or username already exists"
            )
        
        # Create formatted name if not provided
        formatted_name = user.formatted_name
        if not formatted_name and (user.first_name or user.last_name):
            formatted_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        
        db_user = User(
            username=user.username,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            formatted_name=formatted_name or user.username,
            title=user.title,
            active=user.active
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        # Log successful creation
        action_logger.log_user_action(
            action="create",
            user_data=db_user.to_dict(),
            user_id=db_user.id,
            success=True
        )
        
        return UserResponse.model_validate(db_user.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        # Log unexpected error
        action_logger.log_user_action(
            action="create",
            user_data=user.model_dump(),
            success=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Internal server error")

async def auto_sync_user_to_datadog(db_user: User, db: Session) -> tuple[bool, str]:
    """Automatically sync a user to Datadog if they have a datadog_user_id"""
    if not db_user.datadog_user_id:
        return False, "User not previously synced to Datadog"
    
    try:
        scim_user = user_to_scim(db_user, scim_client.base_url)
        scim_response = await scim_client.update_user(db_user.datadog_user_id, scim_user)
        
        # Update sync status
        db_user.last_synced = datetime.utcnow()
        db_user.sync_status = "synced"
        db_user.sync_error = None
        db.commit()
        
        # Log successful auto-sync
        action_logger.log_sync_operation(
            operation_type="auto_update",
            entity_type="user",
            entity_id=db_user.id,
            datadog_id=db_user.datadog_user_id,
            success=True,
            sync_data={
                "local_user": db_user.to_dict(),
                "scim_payload": scim_user.model_dump(),
                "context": "automatic_sync_on_update"
            }
        )
        
        return True, "User automatically synced to Datadog"
        
    except ValueError as ve:
        # Handle specific user-friendly errors
        logger.warning(f"Auto-sync validation warning for user {db_user.id}: {ve}")
        
        # Update sync status with warning but don't fail the update
        db_user.sync_status = "warning"
        db_user.sync_error = str(ve)
        db.commit()
        
        # Log warning
        action_logger.log_sync_operation(
            operation_type="auto_update",
            entity_type="user",
            entity_id=db_user.id,
            datadog_id=db_user.datadog_user_id,
            success=False,
            error=str(ve),
            sync_data={
                "local_user": db_user.to_dict(),
                "context": "automatic_sync_on_update",
                "warning": True
            }
        )
        
        return False, f"Auto-sync warning: {str(ve)}"
        
    except Exception as e:
        logger.error(f"Failed to auto-sync user {db_user.id} to Datadog: {e}")
        
        # Update sync status with error but don't fail the update
        db_user.sync_status = "failed"
        db_user.sync_error = str(e)
        db.commit()
        
        # Log failed auto-sync
        action_logger.log_sync_operation(
            operation_type="auto_update",
            entity_type="user",
            entity_id=db_user.id,
            datadog_id=db_user.datadog_user_id,
            success=False,
            error=str(e),
            sync_data={
                "local_user": db_user.to_dict(),
                "context": "automatic_sync_on_update"
            }
        )
        
        return False, f"Auto-sync failed: {str(e)}"

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user: UserUpdate, db: Session = Depends(get_db)):
    """Update an existing user and automatically sync to Datadog if applicable"""
    try:
        db_user = db.query(User).filter(User.id == user_id).first()
        if not db_user:
            # Log failed attempt
            action_logger.log_user_action(
                action="update",
                user_data=user.model_dump(exclude_unset=True),
                user_id=user_id,
                success=False,
                error="User not found"
            )
            raise HTTPException(status_code=404, detail="User not found")
        
        # Store original data for logging
        original_data = db_user.to_dict()
        
        # Update fields if provided
        update_data = user.model_dump(exclude_unset=True)
        
        # Handle formatted name
        if update_data.get('first_name') or update_data.get('last_name'):
            first_name = update_data.get('first_name', db_user.first_name)
            last_name = update_data.get('last_name', db_user.last_name)
            if not update_data.get('formatted_name'):
                update_data['formatted_name'] = f"{first_name or ''} {last_name or ''}".strip()
        
        for field, value in update_data.items():
            setattr(db_user, field, value)
        
        db.commit()
        db.refresh(db_user)
        
        # Automatically sync to Datadog if user was previously synced
        sync_success, sync_message = await auto_sync_user_to_datadog(db_user, db)
        
        # Log successful update with both original and new data
        action_logger.log_user_action(
            action="update",
            user_data={
                "original": original_data,
                "updated": db_user.to_dict(),
                "changes": update_data,
                "auto_sync_result": {
                    "success": sync_success,
                    "message": sync_message
                }
            },
            user_id=user_id,
            success=True
        )
        
        return UserResponse.model_validate(db_user.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update user {user_id}: {e}")
        
        # Log failed update
        action_logger.log_user_action(
            action="update",
            user_data=user.model_dump(exclude_unset=True),
            user_id=user_id,
            success=False,
            error=str(e)
        )
        
        raise HTTPException(status_code=500, detail=f"Failed to update user: {str(e)}")

@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Delete a user"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(db_user)
    db.commit()
    
    return {"message": "User deleted successfully"}

@router.post("/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(user_id: int, db: Session = Depends(get_db)):
    """Deactivate a user"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_user.active = False
    db.commit()
    db.refresh(db_user)
    
    return UserResponse.model_validate(db_user.to_dict())

@router.post("/{user_id}/sync", response_model=SyncResponse)
async def sync_user_to_datadog(user_id: int, db: Session = Depends(get_db)):
    """Sync a user to Datadog via SCIM"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        action_logger.log_sync_operation(
            operation_type="sync",
            entity_type="user",
            entity_id=user_id,
            success=False,
            error="User not found"
        )
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        scim_user = user_to_scim(db_user, scim_client.base_url)
        operation_type = "update" if db_user.datadog_user_id else "create"
        
        if db_user.datadog_user_id:
            # Update existing user
            scim_response = await scim_client.update_user(db_user.datadog_user_id, scim_user)
            message = "User updated in Datadog"
        else:
            # Create new user or link to existing
            scim_response = await scim_client.create_user(scim_user)
            db_user.datadog_user_id = scim_response.id
            
            if "already exists" in str(scim_response.id if hasattr(scim_response, 'id') else ''):
                message = f"User linked to existing Datadog account (ID: {scim_response.id})"
            else:
                message = "User created in Datadog"
        
        # Update sync status
        db_user.last_synced = datetime.utcnow()
        db_user.sync_status = "synced"
        db_user.sync_error = None
        
        db.commit()
        
        # Log successful sync operation
        action_logger.log_sync_operation(
            operation_type=operation_type,
            entity_type="user",
            entity_id=user_id,
            datadog_id=scim_response.id,
            success=True,
            sync_data={
                "local_user": db_user.to_dict(),
                "scim_payload": scim_user.model_dump(),
                "datadog_response": scim_response.model_dump() if hasattr(scim_response, 'model_dump') else str(scim_response)
            }
        )
        
        return SyncResponse(
            success=True,
            message=message,
            datadog_id=scim_response.id
        )
        
    except ValueError as ve:
        # Handle specific user-friendly errors (like existing user conflicts)
        logger.error(f"User sync validation error for user {user_id}: {ve}")
        
        # Update sync status with error
        db_user.sync_status = "failed"
        db_user.sync_error = str(ve)
        db.commit()
        
        # Log failed sync operation
        action_logger.log_sync_operation(
            operation_type=operation_type if 'operation_type' in locals() else "sync",
            entity_type="user",
            entity_id=user_id,
            datadog_id=db_user.datadog_user_id,
            success=False,
            error=str(ve),
            sync_data={
                "local_user": db_user.to_dict(),
                "scim_payload": scim_user.model_dump() if 'scim_user' in locals() else None
            }
        )
        
        return SyncResponse(
            success=False,
            message=str(ve),
            error=str(ve)
        )
        
    except Exception as e:
        logger.error(f"Failed to sync user {user_id} to Datadog: {e}")
        
        # Update sync status with error
        db_user.sync_status = "failed"
        db_user.sync_error = str(e)
        db.commit()
        
        # Log failed sync operation
        action_logger.log_sync_operation(
            operation_type=operation_type if 'operation_type' in locals() else "sync",
            entity_type="user",
            entity_id=user_id,
            datadog_id=db_user.datadog_user_id,
            success=False,
            error=str(e),
            sync_data={
                "local_user": db_user.to_dict(),
                "scim_payload": scim_user.model_dump() if 'scim_user' in locals() else None
            }
        )
        
        return SyncResponse(
            success=False,
            message="Failed to sync user to Datadog",
            error=str(e)
        )

@router.post("/{user_id}/sync-deactivate", response_model=SyncResponse)
async def sync_deactivate_user(user_id: int, db: Session = Depends(get_db)):
    """Deactivate a user in Datadog via SCIM"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        action_logger.log_sync_operation(
            operation_type="deactivate",
            entity_type="user",
            entity_id=user_id,
            success=False,
            error="User not found"
        )
        raise HTTPException(status_code=404, detail="User not found")
    
    if not db_user.datadog_user_id:
        action_logger.log_sync_operation(
            operation_type="deactivate",
            entity_type="user",
            entity_id=user_id,
            datadog_id=db_user.datadog_user_id,
            success=False,
            error="User not synced to Datadog yet"
        )
        raise HTTPException(status_code=400, detail="User not synced to Datadog yet")
    
    try:
        # Deactivate in Datadog first
        await scim_client.deactivate_user(db_user.datadog_user_id)
        
        # Then deactivate locally
        db_user.active = False
        db_user.last_synced = datetime.utcnow()
        db_user.sync_status = "synced"
        db_user.sync_error = None
        
        db.commit()
        
        # Log successful deactivation
        action_logger.log_sync_operation(
            operation_type="deactivate",
            entity_type="user",
            entity_id=user_id,
            datadog_id=db_user.datadog_user_id,
            success=True,
            sync_data={
                "local_user": db_user.to_dict(),
                "action": "deactivated_both_datadog_and_local"
            }
        )
        
        return SyncResponse(
            success=True,
            message="User deactivated in Datadog and locally",
            datadog_id=db_user.datadog_user_id
        )
        
    except Exception as e:
        logger.error(f"Failed to deactivate user {user_id} in Datadog: {e}")
        
        # Update sync status with error but still deactivate locally
        db_user.active = False
        db_user.sync_status = "failed"
        db_user.sync_error = str(e)
        db.commit()
        
        # Log partial failure
        action_logger.log_sync_operation(
            operation_type="deactivate",
            entity_type="user",
            entity_id=user_id,
            datadog_id=db_user.datadog_user_id,
            success=False,
            error=str(e),
            sync_data={
                "local_user": db_user.to_dict(),
                "action": "deactivated_locally_only",
                "datadog_error": str(e)
            }
        )
        
        return SyncResponse(
            success=False,
            message="User deactivated locally but failed to sync to Datadog",
            error=str(e)
        )

@router.post("/bulk-sync", response_model=SyncResponse)
async def bulk_sync_users(db: Session = Depends(get_db)):
    """Sync all pending users to Datadog"""
    pending_users = db.query(User).filter(User.sync_status == "pending").all()
    
    if not pending_users:
        return SyncResponse(
            success=True,
            message="No users to sync"
        )
    
    synced_count = 0
    failed_count = 0
    errors = []
    
    for user in pending_users:
        try:
            scim_user = user_to_scim(user, scim_client.base_url)
            
            if user.datadog_user_id:
                scim_response = await scim_client.update_user(user.datadog_user_id, scim_user)
            else:
                scim_response = await scim_client.create_user(scim_user)
                user.datadog_user_id = scim_response.id
            
            user.last_synced = datetime.utcnow()
            user.sync_status = "synced"
            user.sync_error = None
            synced_count += 1
            
        except Exception as e:
            user.sync_status = "failed"
            user.sync_error = str(e)
            failed_count += 1
            errors.append(f"User {user.username}: {str(e)}")
    
    db.commit()
    
    return SyncResponse(
        success=failed_count == 0,
        message=f"Synced {synced_count} users, {failed_count} failed",
        error="; ".join(errors) if errors else None
    ) 