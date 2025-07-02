import httpx
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
from .schemas import SCIMUser, SCIMGroup, SCIMPatchRequest, SCIMUserResponse, SCIMGroupResponse
from .logging_config import action_logger, TimingContext

logger = logging.getLogger(__name__)

class DatadogSCIMClient:
    def __init__(self):
        self.base_url = os.getenv("DD_SCIM_BASE_URL", "https://api.datadoghq.com/api/v2/scim")
        self.bearer_token = os.getenv("DD_BEARER_TOKEN")
        
        if not self.bearer_token:
            raise ValueError("DD_BEARER_TOKEN environment variable is required")
        
        self.headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make an HTTP request to the Datadog SCIM API with comprehensive logging"""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        with TimingContext(f"scim_{method.lower()}_{endpoint}") as timing:
            try:
                logger.info(f"Making SCIM API request: {method} {endpoint}")
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=self.headers,
                        json=data
                    )
                    
                    # Parse response data
                    response_data = response.json() if response.content else {}
                    
                    # Log the API call with full details
                    action_logger.log_scim_request(
                        method=method,
                        endpoint=endpoint,
                        request_payload=data,
                        response_payload=response_data,
                        status_code=response.status_code,
                        duration_ms=timing.duration_ms,
                        success=response.status_code < 400,
                        error=response.text if response.status_code >= 400 else None
                    )
                    
                    logger.info(f"SCIM API {method} {url} - Status: {response.status_code}")
                    
                    if response.status_code >= 400:
                        error_text = response.text
                        logger.error(f"SCIM API Error: {response.status_code} - {error_text}")
                        raise httpx.HTTPStatusError(
                            f"SCIM API returned {response.status_code}: {error_text}",
                            request=response.request,
                            response=response
                        )
                    
                    return response_data
                    
            except httpx.RequestError as e:
                error_msg = str(e)
                logger.error(f"Request error: {error_msg}")
                
                # Log the failed API call
                action_logger.log_scim_request(
                    method=method,
                    endpoint=endpoint,
                    request_payload=data,
                    duration_ms=timing.duration_ms,
                    success=False,
                    error=error_msg
                )
                raise
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Unexpected error: {error_msg}")
                
                # Log the failed API call
                action_logger.log_scim_request(
                    method=method,
                    endpoint=endpoint,
                    request_payload=data,
                    duration_ms=timing.duration_ms,
                    success=False,
                    error=error_msg
                )
                raise

    # User operations
    async def create_user(self, user_data: SCIMUser) -> SCIMUserResponse:
        """Create a user in Datadog via SCIM"""
        response_data = await self._make_request("POST", "/Users", user_data.model_dump())
        return SCIMUserResponse(**response_data)
    
    async def get_user(self, user_id: str) -> SCIMUserResponse:
        """Get a user from Datadog via SCIM"""
        response_data = await self._make_request("GET", f"/Users/{user_id}")
        return SCIMUserResponse(**response_data)
    
    async def update_user(self, user_id: str, user_data: SCIMUser) -> SCIMUserResponse:
        """Update a user in Datadog via SCIM"""
        response_data = await self._make_request("PUT", f"/Users/{user_id}", user_data.model_dump())
        return SCIMUserResponse(**response_data)
    
    async def patch_user(self, user_id: str, patch_data: SCIMPatchRequest) -> SCIMUserResponse:
        """Patch a user in Datadog via SCIM"""
        response_data = await self._make_request("PATCH", f"/Users/{user_id}", patch_data.model_dump())
        return SCIMUserResponse(**response_data)
    
    async def deactivate_user(self, user_id: str) -> SCIMUserResponse:
        """Deactivate a user in Datadog via SCIM"""
        patch_data = SCIMPatchRequest(
            Operations=[
                {
                    "op": "replace",
                    "path": "active",
                    "value": False
                }
            ]
        )
        return await self.patch_user(user_id, patch_data)
    
    async def delete_user(self, user_id: str) -> bool:
        """Delete a user from Datadog via SCIM"""
        await self._make_request("DELETE", f"/Users/{user_id}")
        return True
    
    async def list_users(self, start_index: int = 1, count: int = 100, filter_expr: Optional[str] = None) -> Dict[str, Any]:
        """List users from Datadog via SCIM"""
        params = f"?startIndex={start_index}&count={count}"
        if filter_expr:
            params += f"&filter={filter_expr}"
        
        return await self._make_request("GET", f"/Users{params}")

    # Group operations
    async def create_group(self, group_data: SCIMGroup) -> SCIMGroupResponse:
        """Create a group in Datadog via SCIM"""
        response_data = await self._make_request("POST", "/Groups", group_data.model_dump())
        return SCIMGroupResponse(**response_data)
    
    async def get_group(self, group_id: str) -> SCIMGroupResponse:
        """Get a group from Datadog via SCIM"""
        response_data = await self._make_request("GET", f"/Groups/{group_id}")
        return SCIMGroupResponse(**response_data)
    
    async def update_group(self, group_id: str, group_data: SCIMGroup) -> SCIMGroupResponse:
        """Update a group in Datadog via SCIM"""
        response_data = await self._make_request("PUT", f"/Groups/{group_id}", group_data.model_dump())
        return SCIMGroupResponse(**response_data)
    
    async def patch_group(self, group_id: str, patch_data: SCIMPatchRequest) -> SCIMGroupResponse:
        """Patch a group in Datadog via SCIM"""
        response_data = await self._make_request("PATCH", f"/Groups/{group_id}", patch_data.model_dump())
        return SCIMGroupResponse(**response_data)
    
    async def delete_group(self, group_id: str) -> bool:
        """Delete a group from Datadog via SCIM"""
        await self._make_request("DELETE", f"/Groups/{group_id}")
        return True
    
    async def list_groups(self, start_index: int = 1, count: int = 100, filter_expr: Optional[str] = None) -> Dict[str, Any]:
        """List groups from Datadog via SCIM"""
        params = f"?startIndex={start_index}&count={count}"
        if filter_expr:
            params += f"&filter={filter_expr}"
        
        return await self._make_request("GET", f"/Groups{params}")
    
    # Utility methods
    async def validate_user_exists(self, user_id: str) -> bool:
        """Check if a user exists in Datadog SCIM"""
        try:
            await self.get_user(user_id)
            return True
        except Exception:
            return False
    
    async def get_group_current_members(self, group_id: str) -> List[str]:
        """Get current member IDs from a group in Datadog"""
        try:
            group = await self.get_group(group_id)
            return [getattr(member, 'value', None) for member in group.members if getattr(member, 'value', None)]
        except Exception:
            return []
    
    async def add_user_to_group(self, group_id: str, user_id: str, user_display_name: str) -> SCIMGroupResponse:
        """Add a user to a group via SCIM PATCH"""
        # First validate the user exists
        if not await self.validate_user_exists(user_id):
            raise ValueError(f"User {user_id} does not exist in Datadog")
        
        # Check if user is already a member
        current_members = await self.get_group_current_members(group_id)
        if user_id in current_members:
            logger.info(f"User {user_id} is already a member of group {group_id}")
            return await self.get_group(group_id)
        
        patch_data = SCIMPatchRequest(
            Operations=[
                {
                    "op": "add",
                    "path": "members",
                    "value": [
                        {
                            "$ref": f"{self.base_url}/Users/{user_id}",
                            "value": user_id,
                            "display": user_display_name,
                            "type": "User"
                        }
                    ]
                }
            ]
        )
        return await self.patch_group(group_id, patch_data)
    
    async def remove_user_from_group(self, group_id: str, user_id: str) -> SCIMGroupResponse:
        """Remove a user from a group via SCIM PATCH"""
        # Check if user is actually a member
        current_members = await self.get_group_current_members(group_id)
        if user_id not in current_members:
            logger.info(f"User {user_id} is not a member of group {group_id}")
            return await self.get_group(group_id)
        
        # Use exact format from Datadog SCIM API documentation for member removal
        patch_data = SCIMPatchRequest(
            Operations=[
                {
                    "op": "remove",
                    "path": f"members[value eq \"{user_id}\"]",
                    "value": None  # Explicitly set value to null for remove operations
                }
            ]
        )
        
        try:
            return await self.patch_group(group_id, patch_data)
        except Exception as e:
            logger.error(f"Failed to remove user {user_id} from group {group_id} using PATCH: {str(e)}")
            
            # Fallback: Use PUT with current members minus the user to remove
            try:
                logger.info(f"Attempting PUT fallback to remove user {user_id} from group {group_id}")
                current_group = await self.get_group(group_id)
                
                # Filter out the user to remove from members list
                updated_members = [
                    member for member in current_group.members 
                    if member.get("value") != user_id
                ]
                
                # Create updated group with filtered members
                updated_group = SCIMGroup(
                    displayName=current_group.displayName,
                    externalId=current_group.externalId,
                    members=updated_members
                )
                
                # Use PUT with filtered members
                response_data = await self._make_request("PUT", f"/Groups/{group_id}", updated_group.model_dump())
                return SCIMGroupResponse(**response_data)
                
            except Exception as put_error:
                logger.error(f"PUT fallback also failed for removing user {user_id}: {str(put_error)}")
                raise e  # Raise the original PATCH error

    async def sync_group_members(self, group_id: str, target_member_ids: List[str], member_display_names: Dict[str, str]) -> Dict[str, Any]:
        """Synchronize group members by adding/removing as needed"""
        try:
            # Get current members in Datadog
            current_members = await self.get_group_current_members(group_id)
            target_members = set(target_member_ids)
            current_members_set = set(current_members)
            
            # Calculate additions and removals
            to_add = target_members - current_members_set
            to_remove = current_members_set - target_members
            
            results = {
                "added": [],
                "removed": [],
                "errors": [],
                "current_members": current_members,
                "target_members": list(target_members)
            }
            
            # Add new members
            for user_id in to_add:
                try:
                    await self.add_user_to_group(
                        group_id, 
                        user_id, 
                        member_display_names.get(user_id, user_id)
                    )
                    results["added"].append(user_id)
                    logger.info(f"Added user {user_id} to group {group_id}")
                except Exception as e:
                    error_msg = f"Failed to add user {user_id}: {str(e)}"
                    results["errors"].append(error_msg)
                    logger.error(error_msg)
            
            # Remove old members
            for user_id in to_remove:
                try:
                    await self.remove_user_from_group(group_id, user_id)
                    results["removed"].append(user_id)
                    logger.info(f"Removed user {user_id} from group {group_id}")
                except Exception as e:
                    error_msg = f"Failed to remove user {user_id}: {str(e)}"
                    results["errors"].append(error_msg)
                    logger.error(error_msg)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to sync group members: {str(e)}")
            raise

    async def update_group_metadata(self, group_id: str, display_name: str = None, external_id: str = None) -> SCIMGroupResponse:
        """Update only group metadata using PATCH operations with correct Datadog SCIM format"""
        try:
            # Build update data object
            update_data = {}
            
            if display_name is not None:
                update_data["displayName"] = display_name
            
            if external_id is not None:
                update_data["externalId"] = external_id
            
            if not update_data:
                # No changes needed, just return current group
                return await self.get_group(group_id)
            
            # Use exact format from Datadog SCIM API documentation
            operations = [{
                "op": "replace",
                "path": "None",  # Datadog uses "None" as string for object replacement
                "value": update_data
            }]
            
            patch_data = SCIMPatchRequest(Operations=operations)
            response_data = await self._make_request("PATCH", f"/Groups/{group_id}", patch_data.model_dump())
            return SCIMGroupResponse(**response_data)
            
        except Exception as e:
            logger.error(f"PATCH operation failed for {group_id}: {str(e)}")
            
            # Fallback: GET current group, preserve members, and use PUT
            try:
                logger.info(f"Attempting PUT fallback for group {group_id}")
                current_group = await self.get_group(group_id)
                
                # Create updated group data with existing members preserved
                updated_group = SCIMGroup(
                    displayName=display_name if display_name is not None else current_group.displayName,
                    externalId=external_id if external_id is not None else current_group.externalId,
                    members=current_group.members  # Preserve existing members
                )
                
                # Use PUT with preserved members
                response_data = await self._make_request("PUT", f"/Groups/{group_id}", updated_group.model_dump())
                return SCIMGroupResponse(**response_data)
                
            except Exception as put_error:
                logger.error(f"PUT fallback also failed for {group_id}: {str(put_error)}")
                raise e  # Raise the original PATCH error

    async def remove_user_from_group_by_datadog_id(self, group_id: str, datadog_user_id: str) -> bool:
        """Remove a user from a group using their Datadog user ID directly (for cleanup)"""
        try:
            # Get current group members
            current_group = await self.get_group(group_id)
            
            # Check if user is actually in the group
            current_member_ids = [getattr(member, 'value', None) for member in current_group.members if getattr(member, 'value', None)]
            if datadog_user_id not in current_member_ids:
                logger.info(f"User {datadog_user_id} is not in group {group_id}")
                return True
            
            # Use PATCH remove operation for cleanup
            logger.info(f"Removing user {datadog_user_id} from group {group_id} (cleanup operation using PATCH)")
            
            # Try PATCH remove operation first
            patch_data = SCIMPatchRequest(
                Operations=[
                    {
                        "op": "remove",
                        "path": f"members[value eq \"{datadog_user_id}\"]",
                        "value": None
                    }
                ]
            )
            
            try:
                logger.info(f"Making SCIM API request: PATCH /Groups/{group_id}")
                response_data = await self._make_request("PATCH", f"/Groups/{group_id}", patch_data.model_dump())
                logger.info(f"Successfully removed user {datadog_user_id} from group {group_id} using PATCH")
                return True
            except Exception as patch_error:
                logger.warning(f"PATCH remove failed: {patch_error}")
                
                # Fallback: Use PUT with filtered member list
                logger.info(f"Falling back to PUT operation for user removal")
                remaining_members = [
                    member for member in current_group.members 
                    if getattr(member, 'value', None) != datadog_user_id
                ]
                
                # Create updated group with filtered members
                updated_group = SCIMGroup(
                    displayName=current_group.displayName,
                    externalId=current_group.externalId,
                    members=remaining_members
                )
                
                logger.info(f"Making SCIM API request: PUT /Groups/{group_id}")
                response_data = await self._make_request("PUT", f"/Groups/{group_id}", updated_group.model_dump())
                
                logger.info(f"Successfully removed user {datadog_user_id} from group {group_id} using PUT fallback")
                return True
                
        except Exception as e:
            logger.error(f"Error removing user {datadog_user_id} from group {group_id}: {e}")
            return False

# Global instance
scim_client = DatadogSCIMClient() 