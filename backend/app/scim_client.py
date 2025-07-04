"""
Datadog SCIM Integration Client

This module provides a comprehensive example of how to integrate with Datadog's SCIM API
for user and group provisioning. It demonstrates best practices for:

- Authentication with Datadog's API
- Proper SCIM request/response handling
- Error handling and retries
- User lifecycle management (create, update, deactivate)
- Group management with member synchronization
- Comprehensive logging for debugging

For customers implementing SCIM with Datadog, this serves as a reference implementation
showing production-ready patterns and error handling strategies.
"""

import httpx
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
from .schemas import SCIMUser, SCIMGroup, SCIMPatchRequest, SCIMPatchOperation, SCIMUserResponse, SCIMGroupResponse, SCIMGroupMember
from .logging_config import action_logger, TimingContext
import urllib.parse

logger = logging.getLogger(__name__)

class DatadogSCIMClient:
    """
    Production-ready SCIM client for Datadog integration.
    
    This client demonstrates how to properly integrate with Datadog's SCIM API,
    including authentication, error handling, and best practices for user/group
    management.
    
    Key features:
    - Comprehensive error handling with specific user-friendly messages
    - Automatic conflict resolution for existing users
    - Proper SCIM schema compliance
    - Performance monitoring and logging
    - Incremental group member synchronization
    
    Environment Variables Required:
    - DD_SCIM_BASE_URL: Datadog SCIM API endpoint (auto-configured by DD_SITE)
    - DD_BEARER_TOKEN: Datadog API key with SCIM permissions
    
    Example Usage:
        client = DatadogSCIMClient()
        
        # Create a user
        user_data = SCIMUser(
            userName="john.doe@company.com",
            emails=[SCIMEmail(value="john.doe@company.com")],
            name=SCIMName(formatted="John Doe", givenName="John", familyName="Doe")
        )
        response = await client.create_user(user_data)
        
        # Create a group with members
        group_data = SCIMGroup(
            displayName="Engineering Team",
            members=[SCIMGroupMember(value=response.id, display="John Doe")]
        )
        group_response = await client.create_group(group_data)
    """
    
    def __init__(self):
        """
        Initialize the SCIM client with Datadog configuration.
        
        The client automatically configures the correct SCIM endpoint based on
        your Datadog site (DD_SITE environment variable).
        
        Raises:
            ValueError: If DD_BEARER_TOKEN is not provided
        """
        # Datadog SCIM API endpoint - automatically configured based on site
        self.base_url = os.getenv("DD_SCIM_BASE_URL", "https://api.datadoghq.com/api/v2/scim")
        self.bearer_token = os.getenv("DD_BEARER_TOKEN")
        
        if not self.bearer_token:
            raise ValueError(
                "DD_BEARER_TOKEN environment variable is required. "
                "Get your API key from Datadog → Organization Settings → API Keys"
            )
        
        # Standard SCIM headers as per RFC 7644
        self.headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make an authenticated HTTP request to Datadog's SCIM API.
        
        This method includes comprehensive error handling, logging, and performance
        monitoring that customers should implement in their SCIM integrations.
        
        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            endpoint: SCIM endpoint path (e.g., "/Users", "/Groups/{id}")
            data: Request payload for POST/PUT/PATCH requests
            
        Returns:
            Dict containing the JSON response from Datadog
            
        Raises:
            httpx.HTTPStatusError: For HTTP 4xx/5xx responses
            httpx.RequestError: For network/connection errors
            
        Example Error Responses:
            409 Conflict: User already exists
            404 Not Found: User/Group not found
            401 Unauthorized: Invalid API key
            400 Bad Request: Invalid SCIM payload
        """
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
                    
                    # Parse response data - handle empty responses
                    response_data = response.json() if response.content else {}
                    
                    # Log the complete API call for debugging
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
                    
                    # Handle HTTP errors with specific customer-friendly messages
                    if response.status_code >= 400:
                        error_text = response.text
                        logger.error(f"SCIM API Error: {response.status_code} - {error_text}")
                        
                        # Provide specific error guidance for common issues
                        if response.status_code == 401:
                            error_text = f"Authentication failed. Please check your DD_BEARER_TOKEN. {error_text}"
                        elif response.status_code == 404:
                            error_text = f"Resource not found. The user or group may not exist in Datadog. {error_text}"
                        elif response.status_code == 409:
                            error_text = f"Resource conflict. This usually means the user already exists. {error_text}"
                        
                        raise httpx.HTTPStatusError(
                            f"SCIM API returned {response.status_code}: {error_text}",
                            request=response.request,
                            response=response
                        )
                    
                    return response_data
                    
            except httpx.RequestError as e:
                error_msg = f"Network error connecting to Datadog SCIM API: {str(e)}"
                logger.error(error_msg)
                
                # Log the failed API call for debugging
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
                error_msg = f"Unexpected error during SCIM API call: {str(e)}"
                logger.error(error_msg)
                
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

    # ==== USER MANAGEMENT OPERATIONS ====
    # These methods demonstrate the complete user lifecycle in SCIM
    
    async def create_user(self, user_data: SCIMUser) -> SCIMUserResponse:
        """
        Create a new user in Datadog via SCIM.
        
        This method includes automatic conflict resolution - if a user already exists,
        it will attempt to find and return the existing user instead of failing.
        
        Args:
            user_data: SCIMUser object with user information
            
        Returns:
            SCIMUserResponse with the created (or found existing) user
            
        Example Request Payload:
            {
                "userName": "john.doe@company.com",
                "active": true,
                "emails": [{"value": "john.doe@company.com", "type": "work", "primary": true}],
                "name": {
                    "formatted": "John Doe",
                    "givenName": "John",
                    "familyName": "Doe"
                },
                "title": "Software Engineer",
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"]
            }
            
        Example Response:
            {
                "id": "12345678-1234-1234-1234-123456789012",
                "userName": "john.doe@company.com",
                "active": true,
                "emails": [...],
                "name": {...},
                "meta": {
                    "resourceType": "User",
                    "created": "2023-01-01T00:00:00Z",
                    "lastModified": "2023-01-01T00:00:00Z"
                }
            }
            
        Raises:
            ValueError: For user-friendly errors (user exists but couldn't retrieve)
            httpx.HTTPStatusError: For other API errors
        """
        try:
            response_data = await self._make_request("POST", "/Users", user_data.model_dump())
            return SCIMUserResponse(**response_data)
        except Exception as e:
            # Handle 409 conflict - user already exists (common scenario)
            if "409" in str(e) and "user already exists" in str(e).lower():
                logger.info(f"User {user_data.userName} already exists in Datadog, attempting to find existing user")
                try:
                    # Search for the existing user by email
                    existing_user = await self.find_user_by_email(user_data.userName)
                    if existing_user:
                        logger.info(f"Found existing user in Datadog with ID: {existing_user.id}")
                        return existing_user
                    else:
                        logger.warning(f"User exists according to API but could not be found in search")
                        raise ValueError(
                            f"User {user_data.userName} already exists in Datadog but could not be retrieved. "
                            f"Please check Datadog manually and update the user's Datadog ID in your system."
                        )
                except Exception as search_error:
                    logger.error(f"Failed to search for existing user: {search_error}")
                    raise ValueError(
                        f"User {user_data.userName} already exists in Datadog but could not be retrieved: {str(search_error)}"
                    )
            else:
                raise e
    
    async def get_user(self, user_id: str) -> SCIMUserResponse:
        """
        Retrieve a user from Datadog by their SCIM ID.
        
        Args:
            user_id: The Datadog user ID (UUID format)
            
        Returns:
            SCIMUserResponse with user details
            
        Example Response:
            Same as create_user response format
        """
        response_data = await self._make_request("GET", f"/Users/{user_id}")
        return SCIMUserResponse(**response_data)
    
    async def update_user(self, user_id: str, user_data: SCIMUser) -> SCIMUserResponse:
        """
        Update an existing user in Datadog via SCIM.
        
        This performs a full update (PUT) of the user resource.
        
        Args:
            user_id: The Datadog user ID
            user_data: Complete SCIMUser object with updated information
            
        Returns:
            SCIMUserResponse with updated user details
        """
        response_data = await self._make_request("PUT", f"/Users/{user_id}", user_data.model_dump())
        return SCIMUserResponse(**response_data)
    
    async def patch_user(self, user_id: str, patch_data: SCIMPatchRequest) -> SCIMUserResponse:
        """
        Partially update a user using SCIM PATCH operations.
        
        This is more efficient than full updates when you only need to change
        specific attributes.
        
        Args:
            user_id: The Datadog user ID
            patch_data: SCIM PATCH request with operations
            
        Returns:
            SCIMUserResponse with updated user details
            
        Example PATCH Request:
            {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [
                    {
                        "op": "replace",
                        "path": "active",
                        "value": false
                    }
                ]
            }
        """
        response_data = await self._make_request("PATCH", f"/Users/{user_id}", patch_data.model_dump())
        return SCIMUserResponse(**response_data)
    
    async def deactivate_user(self, user_id: str) -> SCIMUserResponse:
        """
        Deactivate a user in Datadog (set active=false).
        
        This is the recommended way to disable a user rather than deleting them,
        as it preserves audit history and allows reactivation.
        
        Args:
            user_id: The Datadog user ID
            
        Returns:
            SCIMUserResponse with updated user (active=false)
        """
        patch_data = SCIMPatchRequest(
            Operations=[
                SCIMPatchOperation(
                    op="replace",
                    path="active", 
                    value=False
                )
            ]
        )
        return await self.patch_user(user_id, patch_data)
    
    async def delete_user(self, user_id: str) -> bool:
        """
        Permanently delete a user from Datadog.
        
        WARNING: This permanently removes the user and cannot be undone.
        Consider using deactivate_user() instead for most use cases.
        
        Args:
            user_id: The Datadog user ID
            
        Returns:
            True if deletion was successful
        """
        await self._make_request("DELETE", f"/Users/{user_id}")
        return True
    
    async def list_users(self, start_index: int = 1, count: int = 100, filter_expr: Optional[str] = None) -> Dict[str, Any]:
        """
        List users from Datadog with optional filtering.
        
        Args:
            start_index: Starting index for pagination (1-based)
            count: Number of users to return (max 100)
            filter_expr: SCIM filter expression (e.g., 'emails.value eq "john@company.com"')
            
        Returns:
            Dict with 'Resources' array and pagination info
            
        Example Response:
            {
                "Resources": [
                    {user1}, {user2}, ...
                ],
                "totalResults": 150,
                "startIndex": 1,
                "itemsPerPage": 100
            }
        """
        params = f"?startIndex={start_index}&count={count}"
        if filter_expr:
            # URL encode the filter expression properly
            encoded_filter = urllib.parse.quote(filter_expr)
            params += f"&filter={encoded_filter}"
        
        return await self._make_request("GET", f"/Users{params}")
    
    async def find_user_by_email(self, email: str) -> Optional[SCIMUserResponse]:
        """
        Find a user by their email address using SCIM filtering.
        
        This method tries multiple filter formats to ensure compatibility
        with different SCIM implementations.
        
        Args:
            email: User's email address
            
        Returns:
            SCIMUserResponse if found, None otherwise
        """
        try:
            # Try multiple filter formats since different SCIM implementations may vary
            filter_expressions = [
                f'emails.value eq "{email}"',
                f'emails eq "{email}"',
                f'userName eq "{email}"'
            ]
            
            for filter_expr in filter_expressions:
                try:
                    logger.info(f"Searching for user with filter: {filter_expr}")
                    users_data = await self.list_users(filter_expr=filter_expr)
                    
                    if users_data.get("Resources") and len(users_data["Resources"]) > 0:
                        # Return the first matching user
                        user_data = users_data["Resources"][0]
                        logger.info(f"Found user via filter '{filter_expr}': {user_data.get('id', 'unknown')}")
                        return SCIMUserResponse(**user_data)
                    
                except Exception as filter_error:
                    logger.warning(f"Filter '{filter_expr}' failed: {filter_error}")
                    continue
            
            # If filters don't work, try searching through all users (less efficient but more reliable)
            logger.info("Filter search failed, trying manual search through all users")
            try:
                all_users = await self.list_users(count=100)  # Get first 100 users
                
                if all_users.get("Resources"):
                    for user_data in all_users["Resources"]:
                        # Check if any email matches
                        user_emails = []
                        if user_data.get("emails"):
                            for email_obj in user_data["emails"]:
                                if isinstance(email_obj, dict) and email_obj.get("value"):
                                    user_emails.append(email_obj["value"].lower())
                        
                        # Also check userName field
                        if user_data.get("userName"):
                            user_emails.append(user_data["userName"].lower())
                        
                        if email.lower() in user_emails:
                            logger.info(f"Found user via manual search: {user_data.get('id', 'unknown')}")
                            return SCIMUserResponse(**user_data)
                
                logger.info(f"User with email {email} not found in first 100 users")
                return None
                
            except Exception as manual_error:
                logger.error(f"Manual search failed: {manual_error}")
                return None
                
        except Exception as e:
            logger.error(f"Error searching for user by email {email}: {e}")
            return None

    # ==== GROUP MANAGEMENT OPERATIONS ====
    # These methods demonstrate group lifecycle and member management
    
    async def create_group(self, group_data: SCIMGroup) -> SCIMGroupResponse:
        """
        Create a new group in Datadog via SCIM.
        
        Args:
            group_data: SCIMGroup object with group information
            
        Returns:
            SCIMGroupResponse with the created group
            
        Example Request Payload:
            {
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
        """
        response_data = await self._make_request("POST", "/Groups", group_data.model_dump())
        return SCIMGroupResponse(**response_data)
    
    async def get_group(self, group_id: str) -> SCIMGroupResponse:
        """Retrieve a group from Datadog by its SCIM ID."""
        response_data = await self._make_request("GET", f"/Groups/{group_id}")
        return SCIMGroupResponse(**response_data)
    
    async def update_group(self, group_id: str, group_data: SCIMGroup) -> SCIMGroupResponse:
        """
        Update an existing group in Datadog via SCIM using PATCH operations.
        
        This method will update both metadata (displayName, externalId) and members
        using the official Datadog SCIM API PATCH format.
        
        Args:
            group_id: The ID of the group to update
            group_data: SCIMGroup object with updated data
            
        Returns:
            SCIMGroupResponse with the updated group
        """
        # Update metadata if provided
        if group_data.displayName or group_data.externalId:
            await self.update_group_metadata(
                group_id=group_id,
                display_name=group_data.displayName,
                external_id=group_data.externalId
            )
        
        # Update members if provided
        if group_data.members:
            target_member_ids = [member.value for member in group_data.members if member.value]
            member_display_names = {member.value: member.display for member in group_data.members if member.value and member.display}
            await self.sync_group_members(group_id, target_member_ids, member_display_names)
        
        # Return the updated group
        return await self.get_group(group_id)
    
    async def patch_group(self, group_id: str, patch_data: SCIMPatchRequest) -> SCIMGroupResponse:
        """Partially update a group using SCIM PATCH operations."""
        response_data = await self._make_request("PATCH", f"/Groups/{group_id}", patch_data.model_dump())
        return SCIMGroupResponse(**response_data)
    
    async def delete_group(self, group_id: str) -> bool:
        """Permanently delete a group from Datadog."""
        await self._make_request("DELETE", f"/Groups/{group_id}")
        return True
    
    async def list_groups(self, start_index: int = 1, count: int = 100, filter_expr: Optional[str] = None) -> Dict[str, Any]:
        """List groups from Datadog with optional filtering."""
        params = f"?startIndex={start_index}&count={count}"
        if filter_expr:
            encoded_filter = urllib.parse.quote(filter_expr)
            params += f"&filter={encoded_filter}"
        
        return await self._make_request("GET", f"/Groups{params}")

    # ==== ADVANCED GROUP MEMBER MANAGEMENT ====
    # These methods show best practices for group member synchronization
    
    async def validate_user_exists(self, user_id: str) -> bool:
        """Check if a user exists in Datadog before adding to groups."""
        try:
            await self.get_user(user_id)
            return True
        except Exception:
            return False
    
    async def get_group_current_members(self, group_id: str) -> List[str]:
        """Get the current list of member IDs for a group."""
        group = await self.get_group(group_id)
        return [member.value for member in group.members if member.value]
    
    async def add_user_to_group(self, group_id: str, user_id: str, user_display_name: str) -> SCIMGroupResponse:
        """
        Add a single user to a group using SCIM PATCH operations.
        
        Uses the correct PATCH format for Datadog's SCIM API v2 to incrementally
        add a member without affecting other group properties.
        
        Args:
            group_id: The Datadog group ID
            user_id: The Datadog user ID to add
            user_display_name: Display name for the user
            
        Returns:
            SCIMGroupResponse with updated group
        """
        # First validate the user exists
        if not await self.validate_user_exists(user_id):
            raise ValueError(f"User {user_id} does not exist in Datadog")
        
        # Check if user is already a member
        current_member_ids = await self.get_group_current_members(group_id)
        if user_id in current_member_ids:
            logger.info(f"User {user_id} is already a member of group {group_id}")
            return await self.get_group(group_id)
        
        # Create PATCH operation to add member using official Datadog format
        patch_data = SCIMPatchRequest(
            Operations=[
                SCIMPatchOperation(
                    op="add",
                    path="members",
                    value=[{"value": user_id}]  # Array with member object, as per Datadog docs
                )
            ]
        )
        
        # Apply PATCH operation
        try:
            return await self.patch_group(group_id, patch_data)
        except Exception as e:
            if "409" in str(e) or "Conflict" in str(e):
                logger.warning(f"Conflict when adding user {user_id} to group {group_id}, user may already be a member")
                return await self.get_group(group_id)
            else:
                raise e
    
    async def remove_user_from_group(self, group_id: str, user_id: str) -> SCIMGroupResponse:
        """
        Remove a user from a group using SCIM PATCH operations.
        
        Uses the correct PATCH format for Datadog's SCIM API v2 to incrementally
        remove a member without affecting other group properties.
        
        Args:
            group_id: The Datadog group ID
            user_id: The Datadog user ID to remove
            
        Returns:
            SCIMGroupResponse with updated group
        """
        # Check if user is currently a member
        current_member_ids = await self.get_group_current_members(group_id)
        
        if user_id not in current_member_ids:
            logger.warning(f"User {user_id} is not a member of group {group_id}")
            return await self.get_group(group_id)
        
        # Create PATCH operation to remove member using correct Datadog format
        patch_data = SCIMPatchRequest(
            Operations=[
                SCIMPatchOperation(
                    op="remove",
                    path=f"members[value eq \"{user_id}\"]"
                )
            ]
        )
        
        # Apply PATCH operation
        try:
            return await self.patch_group(group_id, patch_data)
        except Exception as e:
            if "409" in str(e) or "Conflict" in str(e):
                logger.warning(f"Conflict when removing user {user_id} from group {group_id}, user may already be removed")
                return await self.get_group(group_id)
            else:
                raise e
    
    async def sync_group_members(self, group_id: str, target_member_ids: List[str], member_display_names: Dict[str, str]) -> Dict[str, Any]:
        """
        Efficiently synchronize group membership using incremental updates.
        
        This method compares current membership with target membership and only
        makes the necessary updates, with proper conflict handling.
        
        Args:
            group_id: The Datadog group ID
            target_member_ids: List of user IDs that should be in the group
            member_display_names: Dict mapping user IDs to display names
            
        Returns:
            Dict with sync results: {"added": [...], "removed": [...], "unchanged": [...]}
        """
        # Get current group membership
        current_member_ids = await self.get_group_current_members(group_id)
        
        # Calculate differences
        members_to_add = [uid for uid in target_member_ids if uid not in current_member_ids]
        members_to_remove = [uid for uid in current_member_ids if uid not in target_member_ids]
        unchanged_members = [uid for uid in current_member_ids if uid in target_member_ids]
        
        logger.info(f"Group {group_id} sync: +{len(members_to_add)}, -{len(members_to_remove)}, ={len(unchanged_members)}")
        
        # If no changes needed, return early to avoid unnecessary API calls
        if not members_to_add and not members_to_remove:
            logger.info(f"Group {group_id} already has the correct membership, no changes needed")
            return {
                "added": [],
                "removed": [],
                "unchanged": unchanged_members
            }
        
        # Use PATCH "replace" operation for full member synchronization
        # This is more efficient than PUT as it only updates the members field
        try:
            # Create member value list for PATCH replace operation (as per Datadog docs)
            member_values = [{"value": user_id} for user_id in target_member_ids]
            
            # Create PATCH operation to replace all members
            patch_data = SCIMPatchRequest(
                Operations=[
                    SCIMPatchOperation(
                        op="replace",
                        path="members",
                        value=member_values
                    )
                ]
            )
            
            # Apply PATCH operation with retry logic for conflicts
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await self.patch_group(group_id, patch_data)
                    logger.info(f"Successfully synced group {group_id} membership using PATCH replace")
                    break
                except Exception as e:
                    if "409" in str(e) or "Conflict" in str(e):
                        if attempt < max_retries - 1:
                            logger.warning(f"Group member sync conflict on attempt {attempt + 1}, retrying...")
                            # Brief delay before retry
                            import asyncio
                            await asyncio.sleep(1)
                            continue
                        else:
                            logger.error(f"Group member sync failed after {max_retries} attempts due to conflicts")
                            # Fall back to individual operations
                            return await self._sync_group_members_fallback(group_id, members_to_add, members_to_remove, member_display_names)
                    else:
                        raise e
            
            return {
                "added": members_to_add,
                "removed": members_to_remove,
                "unchanged": unchanged_members
            }
            
        except Exception as e:
            logger.error(f"Failed to sync group {group_id} members: {e}")
            # Fall back to individual operations if bulk update fails
            return await self._sync_group_members_fallback(group_id, members_to_add, members_to_remove, member_display_names)
    
    async def _sync_group_members_fallback(self, group_id: str, members_to_add: List[str], members_to_remove: List[str], member_display_names: Dict[str, str]) -> Dict[str, Any]:
        """Fallback method using individual add/remove operations"""
        logger.info(f"Using fallback individual member operations for group {group_id}")
        
        # Remove members that shouldn't be in the group
        for user_id in members_to_remove:
            try:
                await self.remove_user_from_group(group_id, user_id)
                logger.info(f"Removed user {user_id} from group {group_id}")
            except Exception as e:
                logger.error(f"Failed to remove user {user_id} from group {group_id}: {e}")
        
        # Add new members to the group
        for user_id in members_to_add:
            try:
                display_name = member_display_names.get(user_id, f"User {user_id}")
                await self.add_user_to_group(group_id, user_id, display_name)
                logger.info(f"Added user {user_id} to group {group_id}")
            except Exception as e:
                logger.error(f"Failed to add user {user_id} to group {group_id}: {e}")
        
        return {
            "added": members_to_add,
            "removed": members_to_remove,
            "unchanged": []
        }
    
    async def update_group_metadata(self, group_id: str, display_name: str = None, external_id: str = None) -> Dict[str, Any]:
        """
        Update a group's metadata (displayName and/or externalId) using PATCH operations.
        Uses the official Datadog SCIM API format with path="None" and value as an object.
        
        Args:
            group_id: The ID of the group to update
            display_name: New display name for the group (optional)
            external_id: New external ID for the group (optional)
            
        Returns:
            Updated group object from the API
            
        Raises:
            httpx.HTTPError: If the API request fails
            
        Example:
            >>> client = SCIMClient(base_url="https://api.datadoghq.com", token="your_token")
            >>> updated_group = await client.update_group_metadata(
            ...     group_id="123e4567-e89b-12d3-a456-426614174000",
            ...     display_name="New Group Name"
            ... )
            >>> print(updated_group["displayName"])
            "New Group Name"
        """
        # Build the value object for the PATCH operation
        value_obj = {"id": group_id}
        
        if display_name is not None:
            value_obj["displayName"] = display_name
            
        if external_id is not None:
            value_obj["externalId"] = external_id
        
        # Use the official Datadog PATCH format
        patch_data = {
            "Operations": [
                {
                    "op": "replace",
                    "path": "None",  # Datadog uses "None" for full object replacement
                    "value": value_obj
                }
            ],
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"]
        }
        
        response = await self._make_request("PATCH", f"/Groups/{group_id}", patch_data)
        
        if response.status_code != 200:
            logger.error(f"Failed to update group metadata: {response.status_code} - {response.text}")
            response.raise_for_status()
            
        result = response.json()
        logger.info(f"Successfully updated group metadata: {result.get('displayName', 'N/A')}")
        return result
    
    async def remove_user_from_group_by_datadog_id(self, group_id: str, datadog_user_id: str) -> bool:
        """
        Utility method to remove a user from a group by their Datadog user ID.
        
        This is helpful for cleanup operations when you have the Datadog user ID
        but need to remove them from a specific group.
        
        Args:
            group_id: The Datadog group ID
            datadog_user_id: The Datadog user ID to remove
            
        Returns:
            True if removal was successful or user wasn't in group
        """
        try:
            await self.remove_user_from_group(group_id, datadog_user_id)
            logger.info(f"Successfully removed user {datadog_user_id} from group {group_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to remove user {datadog_user_id} from group {group_id}: {e}")
            return False

# Global SCIM client instance for use throughout the application
scim_client = DatadogSCIMClient() 