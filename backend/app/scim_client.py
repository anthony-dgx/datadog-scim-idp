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
    async def add_user_to_group(self, group_id: str, user_id: str, user_display_name: str) -> SCIMGroupResponse:
        """Add a user to a group via SCIM PATCH"""
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
        patch_data = SCIMPatchRequest(
            Operations=[
                {
                    "op": "remove",
                    "path": f"members[value eq \"{user_id}\"]"
                }
            ]
        )
        return await self.patch_group(group_id, patch_data)

# Global instance
scim_client = DatadogSCIMClient() 