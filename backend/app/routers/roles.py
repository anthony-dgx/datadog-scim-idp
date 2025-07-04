from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import json

from ..database import get_db
from ..models import Role, User
from ..schemas import RoleCreate, RoleUpdate, RoleResponse, RoleMappingRequest
from ..logging_config import action_logger

router = APIRouter(prefix="/roles", tags=["roles"])
logger = logging.getLogger(__name__)

@router.get("/", response_model=List[RoleResponse])
async def list_roles(db: Session = Depends(get_db)):
    """List all roles"""
    from sqlalchemy.orm import selectinload
    roles = db.query(Role).options(selectinload(Role.users)).order_by(Role.name).all()
    return [RoleResponse.from_orm(role) for role in roles]

@router.post("/", response_model=RoleResponse)
async def create_role(role: RoleCreate, db: Session = Depends(get_db)):
    """Create a new role"""
    
    # Check if role name already exists
    existing_role = db.query(Role).filter(Role.name == role.name).first()
    if existing_role:
        raise HTTPException(
            status_code=400,
            detail=f"Role with name '{role.name}' already exists"
        )
    
    # Check if IdP role value is already mapped (if provided)
    if role.idp_role_value:
        existing_mapping = db.query(Role).filter(Role.idp_role_value == role.idp_role_value).first()
        if existing_mapping:
            raise HTTPException(
                status_code=400,
                detail=f"IdP role value '{role.idp_role_value}' is already mapped to role '{existing_mapping.name}'"
            )
    
    db_role = Role(
        name=role.name,
        description=role.description,
        idp_role_value=role.idp_role_value,
        datadog_role_id=role.datadog_role_id,
        active=role.active,
        is_default=role.is_default
    )
    
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    
    # Log role creation
    action_logger.log_user_action(
        operation="role_created",
        resource_type="role",
        resource_id=db_role.id,
        success=True,
        details={
            "role_name": db_role.name,
            "idp_role_value": db_role.idp_role_value,
            "is_default": db_role.is_default
        }
    )
    
    return RoleResponse.from_orm(db_role)

@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(role_id: int, db: Session = Depends(get_db)):
    """Get a specific role"""
    from sqlalchemy.orm import selectinload
    role = db.query(Role).options(selectinload(Role.users)).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    return RoleResponse.from_orm(role)

@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(role_id: int, role: RoleUpdate, db: Session = Depends(get_db)):
    """Update a role"""
    db_role = db.query(Role).filter(Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check for name conflicts (if name is being changed)
    if role.name and role.name != db_role.name:
        existing_role = db.query(Role).filter(Role.name == role.name).first()
        if existing_role:
            raise HTTPException(
                status_code=400,
                detail=f"Role with name '{role.name}' already exists"
            )
    
    # Check for IdP role value conflicts (if value is being changed)
    if role.idp_role_value and role.idp_role_value != db_role.idp_role_value:
        existing_mapping = db.query(Role).filter(Role.idp_role_value == role.idp_role_value).first()
        if existing_mapping:
            raise HTTPException(
                status_code=400,
                detail=f"IdP role value '{role.idp_role_value}' is already mapped to role '{existing_mapping.name}'"
            )
    
    # Update fields
    for field, value in role.dict(exclude_unset=True).items():
        setattr(db_role, field, value)
    
    db_role.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_role)
    
    # Log role update
    action_logger.log_user_action(
        operation="role_updated",
        resource_type="role",
        resource_id=db_role.id,
        success=True,
        details={
            "role_name": db_role.name,
            "updated_fields": list(role.dict(exclude_unset=True).keys())
        }
    )
    
    return RoleResponse.from_orm(db_role)

@router.delete("/{role_id}")
async def delete_role(role_id: int, db: Session = Depends(get_db)):
    """Delete a role"""
    from sqlalchemy.orm import selectinload
    db_role = db.query(Role).options(selectinload(Role.users)).filter(Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check if role is assigned to any users
    if db_role.users:
        user_count = len(db_role.users)
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete role '{db_role.name}' - it is assigned to {user_count} user(s). Remove role assignments first."
        )
    
    role_name = db_role.name
    db.delete(db_role)
    db.commit()
    
    # Log role deletion
    action_logger.log_user_action(
        operation="role_deleted",
        resource_type="role",
        resource_id=role_id,
        success=True,
        details={"role_name": role_name}
    )
    
    return {"message": f"Role '{role_name}' deleted successfully"}

@router.post("/mappings", response_model=Dict[str, Any])
async def create_role_mappings(mappings: List[RoleMappingRequest], db: Session = Depends(get_db)):
    """Create or update multiple role mappings"""
    
    results = {
        "created": [],
        "updated": [],
        "errors": []
    }
    
    for mapping in mappings:
        try:
            # Check if mapping already exists
            existing_role = db.query(Role).filter(Role.idp_role_value == mapping.idp_role_value).first()
            
            if existing_role:
                # Update existing mapping
                existing_role.name = mapping.role_name
                existing_role.description = mapping.description
                existing_role.active = mapping.active
                existing_role.updated_at = datetime.utcnow()
                
                results["updated"].append({
                    "idp_role_value": mapping.idp_role_value,
                    "role_name": mapping.role_name,
                    "role_id": existing_role.id
                })
            else:
                # Create new mapping
                new_role = Role(
                    name=mapping.role_name,
                    description=mapping.description,
                    idp_role_value=mapping.idp_role_value,
                    active=mapping.active
                )
                
                db.add(new_role)
                db.flush()  # To get the ID
                
                results["created"].append({
                    "idp_role_value": mapping.idp_role_value,
                    "role_name": mapping.role_name,
                    "role_id": new_role.id
                })
                
        except Exception as e:
            results["errors"].append({
                "idp_role_value": mapping.idp_role_value,
                "error": str(e)
            })
    
    db.commit()
    
    # Log bulk role mapping operation
    action_logger.log_user_action(
        operation="role_mappings_created",
        resource_type="role",
        success=len(results["errors"]) == 0,
        details={
            "total_mappings": len(mappings),
            "created": len(results["created"]),
            "updated": len(results["updated"]),
            "errors": len(results["errors"])
        }
    )
    
    return results

@router.get("/mappings/idp-values", response_model=List[str])
async def get_idp_role_values(db: Session = Depends(get_db)):
    """Get all unique IdP role values"""
    values = db.query(Role.idp_role_value).filter(Role.idp_role_value.isnot(None)).distinct().all()
    return [value[0] for value in values if value[0]]

@router.post("/{role_id}/users/{user_id}")
async def assign_role_to_user(role_id: int, user_id: int, db: Session = Depends(get_db)):
    """Assign a role to a user"""
    
    from sqlalchemy.orm import selectinload
    
    # Verify role exists
    role = db.query(Role).options(selectinload(Role.users)).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Verify user exists
    user = db.query(User).options(selectinload(User.roles)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user already has this role
    if role in user.roles:
        raise HTTPException(
            status_code=400,
            detail=f"User '{user.email}' already has role '{role.name}'"
        )
    
    # Assign role
    user.roles.append(role)
    user.last_role_sync = datetime.utcnow()
    
    # Update IdP roles JSON
    current_idp_roles = json.loads(user.idp_roles) if user.idp_roles else []
    if role.idp_role_value and role.idp_role_value not in current_idp_roles:
        current_idp_roles.append(role.idp_role_value)
        user.idp_roles = json.dumps(current_idp_roles)
    
    db.commit()
    
    # Log role assignment
    action_logger.log_user_action(
        operation="role_assigned",
        resource_type="user",
        resource_id=user.id,
        success=True,
        details={
            "user_email": user.email,
            "role_name": role.name,
            "role_id": role.id
        }
    )
    
    return {
        "message": f"Role '{role.name}' assigned to user '{user.email}'",
        "user_id": user.id,
        "role_id": role.id
    }

@router.delete("/{role_id}/users/{user_id}")
async def remove_role_from_user(role_id: int, user_id: int, db: Session = Depends(get_db)):
    """Remove a role from a user"""
    
    from sqlalchemy.orm import selectinload
    
    # Verify role exists
    role = db.query(Role).options(selectinload(Role.users)).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Verify user exists
    user = db.query(User).options(selectinload(User.roles)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user has this role
    if role not in user.roles:
        raise HTTPException(
            status_code=400,
            detail=f"User '{user.email}' does not have role '{role.name}'"
        )
    
    # Remove role
    user.roles.remove(role)
    user.last_role_sync = datetime.utcnow()
    
    # Update IdP roles JSON
    current_idp_roles = json.loads(user.idp_roles) if user.idp_roles else []
    if role.idp_role_value and role.idp_role_value in current_idp_roles:
        current_idp_roles.remove(role.idp_role_value)
        user.idp_roles = json.dumps(current_idp_roles)
    
    db.commit()
    
    # Log role removal
    action_logger.log_user_action(
        operation="role_removed",
        resource_type="user",
        resource_id=user.id,
        success=True,
        details={
            "user_email": user.email,
            "role_name": role.name,
            "role_id": role.id
        }
    )
    
    return {
        "message": f"Role '{role.name}' removed from user '{user.email}'",
        "user_id": user.id,
        "role_id": role.id
    }

@router.get("/{role_id}/users", response_model=List[Dict[str, Any]])
async def get_role_users(role_id: int, db: Session = Depends(get_db)):
    """Get all users assigned to a role"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    users = [
        {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "active": user.active,
            "last_role_sync": user.last_role_sync.isoformat() if user.last_role_sync else None
        }
        for user in role.users
    ]
    
    return users

@router.post("/sync-user-roles/{user_id}")
async def sync_user_roles_from_idp(user_id: int, idp_roles: List[str], db: Session = Depends(get_db)):
    """Sync user roles based on IdP role values"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get all roles that match the IdP role values
    matching_roles = db.query(Role).filter(
        Role.idp_role_value.in_(idp_roles),
        Role.active == True
    ).all()
    
    # Get default role if no matching roles and user has no roles
    default_role = None
    if not matching_roles and not user.roles:
        default_role = db.query(Role).filter(Role.is_default == True, Role.active == True).first()
    
    # Clear existing roles and assign new ones
    user.roles.clear()
    
    if matching_roles:
        user.roles.extend(matching_roles)
        assigned_roles = [role.name for role in matching_roles]
    elif default_role:
        user.roles.append(default_role)
        assigned_roles = [default_role.name]
    else:
        assigned_roles = []
    
    # Update IdP roles and sync timestamp
    user.idp_roles = json.dumps(idp_roles)
    user.last_role_sync = datetime.utcnow()
    
    db.commit()
    
    # Log role sync
    action_logger.log_user_action(
        operation="roles_synced",
        resource_type="user",
        resource_id=user.id,
        success=True,
        details={
            "user_email": user.email,
            "idp_roles": idp_roles,
            "assigned_roles": assigned_roles,
            "default_role_used": bool(default_role)
        }
    )
    
    return {
        "message": "User roles synced successfully",
        "user_email": user.email,
        "idp_roles": idp_roles,
        "assigned_roles": assigned_roles,
        "sync_timestamp": user.last_role_sync.isoformat()
    } 