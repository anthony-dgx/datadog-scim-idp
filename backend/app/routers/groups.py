from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import logging

from ..database import get_db
from ..models import Group, User
from ..schemas import GroupCreate, GroupUpdate, GroupResponse, SyncResponse, SCIMGroup, SCIMGroupMember
from ..scim_client import scim_client
from .users import user_to_scim
from ..logging_config import action_logger

router = APIRouter(prefix="/groups", tags=["groups"])
logger = logging.getLogger(__name__)

def group_to_scim(group: Group, base_url: str) -> SCIMGroup:
    """Convert a Group model to SCIM format"""
    members = []
    for member in group.members:
        members.append(SCIMGroupMember(
            **{
                "$ref": f"{base_url}/Users/{member.datadog_user_id or member.uuid}",
                "value": member.datadog_user_id or member.uuid,
                "display": member.formatted_name or member.username,
                "type": "User"
            }
        ))
    
    return SCIMGroup(
        displayName=group.display_name,
        externalId=group.external_id or group.uuid,
        members=members
    )

@router.get("/", response_model=List[GroupResponse])
def get_groups(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all groups"""
    groups = db.query(Group).offset(skip).limit(limit).all()
    return [GroupResponse.model_validate(group.to_dict()) for group in groups]

@router.get("/{group_id}", response_model=GroupResponse)
def get_group(group_id: int, db: Session = Depends(get_db)):
    """Get a specific group by ID"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return GroupResponse.model_validate(group.to_dict())

@router.post("/", response_model=GroupResponse)
def create_group(group: GroupCreate, db: Session = Depends(get_db)):
    """Create a new group"""
    # Check if group with same name already exists
    existing_group = db.query(Group).filter(Group.display_name == group.display_name).first()
    if existing_group:
        raise HTTPException(
            status_code=400, 
            detail="Group with this name already exists"
        )
    
    db_group = Group(
        display_name=group.display_name,
        description=group.description
    )
    
    # Add members if provided
    if group.member_ids:
        members = db.query(User).filter(User.id.in_(group.member_ids)).all()
        if len(members) != len(group.member_ids):
            raise HTTPException(status_code=400, detail="Some user IDs are invalid")
        db_group.members = members
    
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    
    return GroupResponse.model_validate(db_group.to_dict())

@router.put("/{group_id}", response_model=GroupResponse)
def update_group(group_id: int, group: GroupUpdate, db: Session = Depends(get_db)):
    """Update an existing group"""
    db_group = db.query(Group).filter(Group.id == group_id).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Update fields if provided
    update_data = group.model_dump(exclude_unset=True)
    
    # Handle member updates
    if 'member_ids' in update_data:
        member_ids = update_data.pop('member_ids')
        if member_ids is not None:
            members = db.query(User).filter(User.id.in_(member_ids)).all()
            if len(members) != len(member_ids):
                raise HTTPException(status_code=400, detail="Some user IDs are invalid")
            db_group.members = members
    
    # Update other fields
    for field, value in update_data.items():
        setattr(db_group, field, value)
    
    db.commit()
    db.refresh(db_group)
    
    return GroupResponse.model_validate(db_group.to_dict())

@router.delete("/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db)):
    """Delete a group"""
    db_group = db.query(Group).filter(Group.id == group_id).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    db.delete(db_group)
    db.commit()
    
    return {"message": "Group deleted successfully"}

@router.post("/{group_id}/members/{user_id}")
def add_member_to_group(group_id: int, user_id: int, db: Session = Depends(get_db)):
    """Add a user to a group"""
    db_group = db.query(Group).filter(Group.id == group_id).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if db_user in db_group.members:
        raise HTTPException(status_code=400, detail="User is already a member of this group")
    
    db_group.members.append(db_user)
    db.commit()
    
    return {"message": "User added to group successfully"}

@router.delete("/{group_id}/members/{user_id}")
def remove_member_from_group(group_id: int, user_id: int, db: Session = Depends(get_db)):
    """Remove a user from a group"""
    db_group = db.query(Group).filter(Group.id == group_id).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if db_user not in db_group.members:
        raise HTTPException(status_code=400, detail="User is not a member of this group")
    
    db_group.members.remove(db_user)
    db.commit()
    
    return {"message": "User removed from group successfully"}

@router.post("/{group_id}/sync", response_model=SyncResponse)
async def sync_group_to_datadog(group_id: int, db: Session = Depends(get_db)):
    """Sync a group to Datadog via SCIM"""
    db_group = db.query(Group).filter(Group.id == group_id).first()
    if not db_group:
        action_logger.log_sync_operation(
            operation_type="sync",
            entity_type="group",
            entity_id=group_id,
            success=False,
            error="Group not found"
        )
        raise HTTPException(status_code=404, detail="Group not found")
    
    try:
        # Store original state for logging
        original_group_state = db_group.to_dict()
        member_sync_results = []
        
        # First, ensure all group members are synced to Datadog
        for member in db_group.members:
            if not member.datadog_user_id:
                try:
                    scim_user = user_to_scim(member, scim_client.base_url)
                    scim_response = await scim_client.create_user(scim_user)
                    member.datadog_user_id = scim_response.id
                    member.last_synced = datetime.utcnow()
                    member.sync_status = "synced"
                    member.sync_error = None
                    
                    # Log successful member sync
                    action_logger.log_sync_operation(
                        operation_type="create",
                        entity_type="user",
                        entity_id=member.id,
                        datadog_id=scim_response.id,
                        success=True,
                        sync_data={
                            "context": "group_member_auto_sync",
                            "parent_group_id": group_id,
                            "user_data": member.to_dict(),
                            "scim_payload": scim_user.model_dump()
                        }
                    )
                    member_sync_results.append({"user_id": member.id, "success": True})
                    
                except Exception as e:
                    logger.error(f"Failed to sync member {member.username} to Datadog: {e}")
                    member.sync_status = "failed"
                    member.sync_error = str(e)
                    
                    # Log failed member sync
                    action_logger.log_sync_operation(
                        operation_type="create",
                        entity_type="user",
                        entity_id=member.id,
                        success=False,
                        error=str(e),
                        sync_data={
                            "context": "group_member_auto_sync",
                            "parent_group_id": group_id,
                            "user_data": member.to_dict()
                        }
                    )
                    member_sync_results.append({"user_id": member.id, "success": False, "error": str(e)})
        
        # Commit member updates
        db.commit()
        
        # Now sync the group
        scim_group = group_to_scim(db_group, scim_client.base_url)
        operation_type = "update" if db_group.datadog_group_id else "create"
        
        if db_group.datadog_group_id:
            # Update existing group
            scim_response = await scim_client.update_group(db_group.datadog_group_id, scim_group)
            message = "Group updated in Datadog"
        else:
            # Create new group
            scim_response = await scim_client.create_group(scim_group)
            db_group.datadog_group_id = scim_response.id
            message = "Group created in Datadog"
        
        # Update sync status
        db_group.last_synced = datetime.utcnow()
        db_group.sync_status = "synced"
        db_group.sync_error = None
        
        db.commit()
        
        # Log successful group sync with comprehensive data
        action_logger.log_sync_operation(
            operation_type=operation_type,
            entity_type="group",
            entity_id=group_id,
            datadog_id=scim_response.id,
            success=True,
            sync_data={
                "original_state": original_group_state,
                "updated_state": db_group.to_dict(),
                "scim_payload": scim_group.model_dump(),
                "datadog_response": scim_response.model_dump() if hasattr(scim_response, 'model_dump') else str(scim_response),
                "member_sync_results": member_sync_results,
                "member_count": len(db_group.members)
            }
        )
        
        return SyncResponse(
            success=True,
            message=message,
            datadog_id=scim_response.id
        )
        
    except Exception as e:
        logger.error(f"Failed to sync group {group_id} to Datadog: {e}")
        
        # Update sync status with error
        db_group.sync_status = "failed"
        db_group.sync_error = str(e)
        db.commit()
        
        # Log failed group sync
        action_logger.log_sync_operation(
            operation_type=operation_type if 'operation_type' in locals() else "sync",
            entity_type="group",
            entity_id=group_id,
            datadog_id=db_group.datadog_group_id,
            success=False,
            error=str(e),
            sync_data={
                "original_state": original_group_state if 'original_group_state' in locals() else None,
                "scim_payload": scim_group.model_dump() if 'scim_group' in locals() else None,
                "member_sync_results": member_sync_results if 'member_sync_results' in locals() else []
            }
        )
        
        return SyncResponse(
            success=False,
            message="Failed to sync group to Datadog",
            error=str(e)
        )

@router.post("/bulk-sync", response_model=SyncResponse)
async def bulk_sync_groups(db: Session = Depends(get_db)):
    """Sync all pending groups to Datadog"""
    pending_groups = db.query(Group).filter(Group.sync_status == "pending").all()
    
    if not pending_groups:
        return SyncResponse(
            success=True,
            message="No groups to sync"
        )
    
    synced_count = 0
    failed_count = 0
    errors = []
    
    for group in pending_groups:
        try:
            # Ensure all members are synced first
            for member in group.members:
                if not member.datadog_user_id:
                    scim_user = user_to_scim(member, scim_client.base_url)
                    scim_response = await scim_client.create_user(scim_user)
                    member.datadog_user_id = scim_response.id
                    member.last_synced = datetime.utcnow()
                    member.sync_status = "synced"
                    member.sync_error = None
            
            # Sync the group
            scim_group = group_to_scim(group, scim_client.base_url)
            
            if group.datadog_group_id:
                scim_response = await scim_client.update_group(group.datadog_group_id, scim_group)
            else:
                scim_response = await scim_client.create_group(scim_group)
                group.datadog_group_id = scim_response.id
            
            group.last_synced = datetime.utcnow()
            group.sync_status = "synced"
            group.sync_error = None
            synced_count += 1
            
        except Exception as e:
            group.sync_status = "failed"
            group.sync_error = str(e)
            failed_count += 1
            errors.append(f"Group {group.display_name}: {str(e)}")
    
    db.commit()
    
    return SyncResponse(
        success=failed_count == 0,
        message=f"Synced {synced_count} groups, {failed_count} failed",
        error="; ".join(errors) if errors else None
    ) 