from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime
import logging
import asyncio

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
        # Only include members that have been successfully synced to Datadog
        if member.datadog_user_id and member.sync_status == "synced":
            members.append(SCIMGroupMember(
                **{
                    "$ref": f"{base_url}/Users/{member.datadog_user_id}",
                    "value": member.datadog_user_id,
                    "display": member.formatted_name or member.username,
                    "type": "User"
                }
            ))
        else:
            logger.warning(f"Skipping member {member.username} - not synced to Datadog (status: {member.sync_status})")
    
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

async def auto_sync_group_to_datadog(db_group: Group, db: Session) -> tuple[bool, str]:
    """Automatically sync a group to Datadog if it has a datadog_group_id"""
    if not db_group.datadog_group_id:
        return False, "Group not previously synced to Datadog"
    
    try:
        # Ensure all members are synced first
        member_sync_results = []
        for member in db_group.members:
            if not member.datadog_user_id:
                try:
                    scim_user = user_to_scim(member, scim_client.base_url)
                    scim_response = await scim_client.create_user(scim_user)
                    member.datadog_user_id = scim_response.id
                    member.last_synced = datetime.utcnow()
                    member.sync_status = "synced"
                    member.sync_error = None
                    member_sync_results.append({"user_id": member.id, "success": True})
                except Exception as e:
                    logger.error(f"Failed to auto-sync member {member.username} to Datadog: {e}")
                    member.sync_status = "failed"
                    member.sync_error = str(e)
                    member_sync_results.append({"user_id": member.id, "success": False, "error": str(e)})
        
        # Commit member updates
        db.commit()
        
        # Brief delay for Datadog processing
        if member_sync_results:
            await asyncio.sleep(1)
        
        # Update group metadata and sync members
        synced_member_ids = [
            member.datadog_user_id 
            for member in db_group.members 
            if member.datadog_user_id and member.sync_status == "synced"
        ]
        
        member_display_names = {
            member.datadog_user_id: member.formatted_name or member.username
            for member in db_group.members 
            if member.datadog_user_id and member.sync_status == "synced"
        }
        
        # Use incremental member sync
        member_sync_result = await scim_client.sync_group_members(
            db_group.datadog_group_id, 
            synced_member_ids, 
            member_display_names
        )
        
        # Update group metadata
        scim_response = await scim_client.update_group_metadata(
            db_group.datadog_group_id,
            display_name=db_group.display_name,
            external_id=db_group.external_id or db_group.uuid
        )
        
        # Update sync status
        db_group.last_synced = datetime.utcnow()
        db_group.sync_status = "synced"
        db_group.sync_error = None
        db.commit()
        

        
        message = f"Group automatically synced to Datadog (added: {len(member_sync_result['added'])}, removed: {len(member_sync_result['removed'])})"
        return True, message
        
    except Exception as e:
        logger.error(f"Failed to auto-sync group {db_group.id} to Datadog: {e}")
        
        # Update sync status with error but don't fail the update
        db_group.sync_status = "failed"
        db_group.sync_error = str(e)
        db.commit()
        

        
        return False, f"Auto-sync failed: {str(e)}"

@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(group_id: int, group: GroupUpdate, db: Session = Depends(get_db)):
    """Update an existing group and automatically sync to Datadog if applicable"""
    db_group = db.query(Group).filter(Group.id == group_id).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Store original data for logging
    original_data = db_group.to_dict()
    
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
    
    # Automatically sync to Datadog if group was previously synced
    sync_success, sync_message = await auto_sync_group_to_datadog(db_group, db)
    
    logger.info(f"Group {group_id} updated successfully. Auto-sync result: {sync_message}")
    
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
async def add_member_to_group(group_id: int, user_id: int, db: Session = Depends(get_db)):
    """Add a user to a group and automatically sync to Datadog if applicable"""
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
    
    # Automatically sync to Datadog if group was previously synced
    sync_success, sync_message = await auto_sync_group_to_datadog(db_group, db)
    
    return {
        "message": "User added to group successfully",
        "auto_sync_result": {
            "success": sync_success,
            "message": sync_message
        }
    }

@router.delete("/{group_id}/members/{user_id}")
async def remove_member_from_group(group_id: int, user_id: int, db: Session = Depends(get_db)):
    """Remove a user from a group and automatically sync to Datadog if applicable"""
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
    
    # Automatically sync to Datadog if group was previously synced
    sync_success, sync_message = await auto_sync_group_to_datadog(db_group, db)
    
    return {
        "message": "User removed from group successfully",
        "auto_sync_result": {
            "success": sync_success,
            "message": sync_message
        }
    }

@router.post("/{group_id}/members/{user_id}/sync", response_model=SyncResponse)
async def sync_member_to_datadog_group(group_id: int, user_id: int, db: Session = Depends(get_db)):
    """Sync a specific member to the Datadog group"""
    db_group = db.query(Group).filter(Group.id == group_id).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if not db_group.datadog_group_id:
        raise HTTPException(status_code=400, detail="Group must be synced to Datadog first")
    
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if db_user not in db_group.members:
        raise HTTPException(status_code=400, detail="User is not a member of this group")
    
    try:
        # Ensure user is synced to Datadog first
        if not db_user.datadog_user_id:
            scim_user = user_to_scim(db_user, scim_client.base_url)
            scim_response = await scim_client.create_user(scim_user)
            db_user.datadog_user_id = scim_response.id
            db_user.last_synced = datetime.utcnow()
            db_user.sync_status = "synced"
            db_user.sync_error = None
            db.commit()
            
            # Brief delay for Datadog processing
            import asyncio
            await asyncio.sleep(1)
        
        # Add user to Datadog group
        await scim_client.add_user_to_group(
            db_group.datadog_group_id,
            db_user.datadog_user_id,
            db_user.formatted_name or db_user.username
        )
        
        action_logger.log_sync_operation(
            operation_type="add_member",
            entity_type="group",
            entity_id=group_id,
            datadog_id=db_group.datadog_group_id,
            success=True,
            sync_data={
                "member_user_id": user_id,
                "member_datadog_id": db_user.datadog_user_id,
                "member_name": db_user.username
            }
        )
        
        return SyncResponse(
            success=True,
            message=f"User {db_user.username} added to group {db_group.display_name} in Datadog",
            datadog_id=db_group.datadog_group_id
        )
        
    except Exception as e:
        logger.error(f"Failed to sync member {user_id} to group {group_id}: {e}")
        
        action_logger.log_sync_operation(
            operation_type="add_member",
            entity_type="group",
            entity_id=group_id,
            datadog_id=db_group.datadog_group_id,
            success=False,
            error=str(e)
        )
        
        return SyncResponse(
            success=False,
            message="Failed to sync member to Datadog group",
            error=str(e)
        )

@router.delete("/{group_id}/members/{user_id}/sync", response_model=SyncResponse)
async def remove_member_from_datadog_group(group_id: int, user_id: int, db: Session = Depends(get_db)):
    """Remove a specific member from the Datadog group"""
    db_group = db.query(Group).filter(Group.id == group_id).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if not db_group.datadog_group_id:
        raise HTTPException(status_code=400, detail="Group is not synced to Datadog")
    
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not db_user.datadog_user_id:
        return SyncResponse(
            success=True,
            message="User is not synced to Datadog, nothing to remove"
        )
    
    try:
        # Remove user from Datadog group
        await scim_client.remove_user_from_group(
            db_group.datadog_group_id,
            db_user.datadog_user_id
        )
        
        action_logger.log_sync_operation(
            operation_type="remove_member",
            entity_type="group",
            entity_id=group_id,
            datadog_id=db_group.datadog_group_id,
            success=True,
            sync_data={
                "member_user_id": user_id,
                "member_datadog_id": db_user.datadog_user_id,
                "member_name": db_user.username
            }
        )
        
        return SyncResponse(
            success=True,
            message=f"User {db_user.username} removed from group {db_group.display_name} in Datadog",
            datadog_id=db_group.datadog_group_id
        )
        
    except Exception as e:
        logger.error(f"Failed to remove member {user_id} from group {group_id}: {e}")
        
        action_logger.log_sync_operation(
            operation_type="remove_member",
            entity_type="group",
            entity_id=group_id,
            datadog_id=db_group.datadog_group_id,
            success=False,
            error=str(e)
        )
        
        return SyncResponse(
            success=False,
            message="Failed to remove member from Datadog group",
            error=str(e)
        )

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
        
        # Add a brief delay to allow Datadog to process user creations
        if member_sync_results:
            import asyncio
            await asyncio.sleep(2)  # 2 second delay for Datadog processing
        
        # Now sync the group
        operation_type = "update" if db_group.datadog_group_id else "create"
        
        if db_group.datadog_group_id:
            # Update existing group using member sync instead of full replacement
            synced_member_ids = [
                member.datadog_user_id 
                for member in db_group.members 
                if member.datadog_user_id and member.sync_status == "synced"
            ]
            
            member_display_names = {
                member.datadog_user_id: member.formatted_name or member.username
                for member in db_group.members 
                if member.datadog_user_id and member.sync_status == "synced"
            }
            
            # Use incremental member sync instead of full group update
            member_sync_result = await scim_client.sync_group_members(
                db_group.datadog_group_id, 
                synced_member_ids, 
                member_display_names
            )
            
            # Update group metadata (name, description) using PATCH to avoid member conflicts
            scim_response = await scim_client.update_group_metadata(
                db_group.datadog_group_id,
                display_name=db_group.display_name,
                external_id=db_group.external_id or db_group.uuid
            )
            message = f"Group updated in Datadog (added: {len(member_sync_result['added'])}, removed: {len(member_sync_result['removed'])})"
            
            # Store member sync results for logging
            member_sync_results.extend([
                {"action": "added", "user_id": uid} for uid in member_sync_result["added"]
            ] + [
                {"action": "removed", "user_id": uid} for uid in member_sync_result["removed"]
            ])
            
        else:
            # Create new group with initial members
            scim_group = group_to_scim(db_group, scim_client.base_url)
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
                "group_metadata": {
                    "displayName": db_group.display_name,
                    "externalId": db_group.external_id or db_group.uuid
                },
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
                "group_metadata": {
                    "displayName": db_group.display_name,
                    "externalId": db_group.external_id or db_group.uuid
                } if db_group else None,
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
            
            # Sync the group using the improved approach
            if group.datadog_group_id:
                # Use incremental member sync for existing groups
                synced_member_ids = [
                    member.datadog_user_id 
                    for member in group.members 
                    if member.datadog_user_id and member.sync_status == "synced"
                ]
                
                member_display_names = {
                    member.datadog_user_id: member.formatted_name or member.username
                    for member in group.members 
                    if member.datadog_user_id and member.sync_status == "synced"
                }
                
                await scim_client.sync_group_members(
                    group.datadog_group_id, 
                    synced_member_ids, 
                    member_display_names
                )
                
                # Update group metadata using PATCH to avoid member conflicts
                scim_response = await scim_client.update_group_metadata(
                    group.datadog_group_id,
                    display_name=group.display_name,
                    external_id=group.external_id or group.uuid
                )
            else:
                # Create new group with initial members
                scim_group = group_to_scim(group, scim_client.base_url)
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

@router.patch("/{group_id}/metadata", response_model=SyncResponse)
async def update_group_metadata_only(group_id: int, db: Session = Depends(get_db)):
    """Test endpoint: Update only group metadata in Datadog without affecting members"""
    db_group = db.query(Group).filter(Group.id == group_id).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if not db_group.datadog_group_id:
        raise HTTPException(status_code=400, detail="Group must be synced to Datadog first")
    
    try:
        # Update only metadata using PATCH operations
        scim_response = await scim_client.update_group_metadata(
            db_group.datadog_group_id,
            display_name=db_group.display_name,
            external_id=db_group.external_id or db_group.uuid
        )
        
        action_logger.log_sync_operation(
            operation_type="update_metadata",
            entity_type="group",
            entity_id=group_id,
            datadog_id=db_group.datadog_group_id,
            success=True,
            sync_data={
                "updated_metadata": {
                    "displayName": db_group.display_name,
                    "externalId": db_group.external_id or db_group.uuid
                }
            }
        )
        
        return SyncResponse(
            success=True,
            message=f"Group metadata updated in Datadog: {db_group.display_name}",
            datadog_id=db_group.datadog_group_id
        )
        
    except Exception as e:
        logger.error(f"Failed to update group metadata {group_id}: {e}")
        
        action_logger.log_sync_operation(
            operation_type="update_metadata",
            entity_type="group",
            entity_id=group_id,
            datadog_id=db_group.datadog_group_id,
            success=False,
            error=str(e)
        )
        
        return SyncResponse(
            success=False,
            message="Failed to update group metadata in Datadog",
            error=str(e)
        )

@router.get("/{group_id}/debug", response_model=Dict[str, Any])
async def debug_group_state(group_id: int, db: Session = Depends(get_db)):
    """Debug endpoint: Get detailed group state from both local DB and Datadog"""
    db_group = db.query(Group).filter(Group.id == group_id).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    result = {
        "local_group": db_group.to_dict(),
        "datadog_group": None,
        "member_comparison": None
    }
    
    if db_group.datadog_group_id:
        try:
            # Get current state from Datadog
            datadog_group = await scim_client.get_group(db_group.datadog_group_id)
            result["datadog_group"] = {
                "id": datadog_group.id,
                "displayName": datadog_group.displayName,
                "externalId": datadog_group.externalId,
                "members": [
                    {
                        "value": getattr(member, 'value', None),
                        "display": getattr(member, 'display', None),
                        "$ref": getattr(member, 'ref', None)
                    } for member in datadog_group.members
                ]
            }
            
            # Compare local vs Datadog members
            local_members = [
                {
                    "user_id": member.id,
                    "username": member.username,
                    "datadog_user_id": member.datadog_user_id,
                    "sync_status": member.sync_status
                } for member in db_group.members
            ]
            
            datadog_member_ids = [getattr(member, 'value', None) for member in datadog_group.members]
            local_datadog_ids = [member.datadog_user_id for member in db_group.members if member.datadog_user_id]
            
            result["member_comparison"] = {
                "local_members": local_members,
                "datadog_member_ids": datadog_member_ids,
                "local_synced_ids": local_datadog_ids,
                "members_in_datadog_not_local": [mid for mid in datadog_member_ids if mid not in local_datadog_ids],
                "members_in_local_not_datadog": [mid for mid in local_datadog_ids if mid not in datadog_member_ids]
            }
            
        except Exception as e:
            result["datadog_error"] = str(e)
    
    return result

@router.delete("/{group_id}/cleanup/{datadog_user_id}", response_model=SyncResponse)
async def cleanup_remove_user_from_datadog_group(group_id: int, datadog_user_id: str, db: Session = Depends(get_db)):
    """Cleanup endpoint: Remove a user from Datadog group by their Datadog user ID (for orphaned users)"""
    db_group = db.query(Group).filter(Group.id == group_id).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if not db_group.datadog_group_id:
        raise HTTPException(status_code=400, detail="Group must be synced to Datadog first")
    
    try:
        success = await scim_client.remove_user_from_group_by_datadog_id(
            db_group.datadog_group_id, 
            datadog_user_id
        )
        
        if success:
            action_logger.log_sync_operation(
                operation_type="cleanup_remove_member",
                entity_type="group",
                entity_id=group_id,
                datadog_id=db_group.datadog_group_id,
                success=True,
                sync_data={
                    "removed_datadog_user_id": datadog_user_id,
                    "context": "cleanup_orphaned_user"
                }
            )
            
            return SyncResponse(
                success=True,
                message=f"Successfully removed user {datadog_user_id} from Datadog group",
                datadog_id=db_group.datadog_group_id
            )
        else:
            return SyncResponse(
                success=False,
                message=f"Failed to remove user {datadog_user_id} from Datadog group",
                datadog_id=db_group.datadog_group_id
            )
            
    except Exception as e:
        logger.error(f"Failed to cleanup remove user {datadog_user_id} from group {group_id}: {e}")
        
        action_logger.log_sync_operation(
            operation_type="cleanup_remove_member",
            entity_type="group",
            entity_id=group_id,
            datadog_id=db_group.datadog_group_id,
            success=False,
            error=str(e),
            sync_data={
                "datadog_user_id": datadog_user_id,
                "context": "cleanup_orphaned_user"
            }
        )
        
        return SyncResponse(
            success=False,
            message="Failed to remove user from Datadog group",
            error=str(e)
        ) 