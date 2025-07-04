# SCIM Integration Examples for Datadog

This document provides practical, production-ready examples of how to integrate with Datadog's SCIM API. These examples are based on the reference implementation in this demo application.

## Table of Contents

1. [Basic Setup](#basic-setup)
2. [User Management Examples](#user-management-examples)
3. [Group Management Examples](#group-management-examples)
4. [Common Integration Patterns](#common-integration-patterns)
5. [Error Handling Examples](#error-handling-examples)
6. [Performance Optimization](#performance-optimization)
7. [Testing Examples](#testing-examples)

## Basic Setup

### Environment Configuration

```python
import os
from datadog import initialize

# Datadog SCIM Configuration
DATADOG_CONFIG = {
    'base_url': os.getenv('DD_SCIM_BASE_URL', 'https://api.datadoghq.com/api/v2/scim'),
    'bearer_token': os.getenv('DD_BEARER_TOKEN'),
    'site': os.getenv('DD_SITE', 'datadoghq.com'),
    'timeout': 30.0
}

# Initialize Datadog metrics (optional)
initialize(api_key=os.getenv('DD_API_KEY'))
```

### Basic SCIM Client

```python
import httpx
import asyncio
from typing import Optional, Dict, Any

class SimpleSCIMClient:
    def __init__(self, base_url: str, bearer_token: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {bearer_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    async def request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data
            )
            
            if response.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"SCIM API error: {response.status_code} {response.text}",
                    request=response.request,
                    response=response
                )
            
            return response.json() if response.content else {}
```

## User Management Examples

### 1. Creating a User

```python
async def create_user_example():
    """Complete example of creating a user in Datadog"""
    
    # Define user data
    user_data = {
        "userName": "john.doe@company.com",
        "active": True,
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
        "title": "Software Engineer",
        "externalId": "emp-12345",
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"]
    }
    
    client = SimpleSCIMClient(
        base_url=DATADOG_CONFIG['base_url'],
        bearer_token=DATADOG_CONFIG['bearer_token']
    )
    
    try:
        # Create user
        response = await client.request('POST', '/Users', user_data)
        print(f"User created with ID: {response['id']}")
        return response
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409:
            print("User already exists - attempting to find existing user")
            # Search for existing user
            existing_user = await find_user_by_email(client, user_data['userName'])
            if existing_user:
                print(f"Found existing user: {existing_user['id']}")
                return existing_user
            else:
                raise ValueError("User exists but could not be retrieved")
        else:
            raise

async def find_user_by_email(client: SimpleSCIMClient, email: str) -> Optional[Dict]:
    """Find user by email address"""
    try:
        # Use SCIM filter to search
        filter_expr = f'emails.value eq "{email}"'
        response = await client.request('GET', f'/Users?filter={filter_expr}')
        
        if response.get('Resources') and len(response['Resources']) > 0:
            return response['Resources'][0]
        return None
        
    except Exception as e:
        print(f"Error searching for user: {e}")
        return None
```

### 2. Updating a User

```python
async def update_user_example(user_id: str, updates: Dict[str, Any]):
    """Update user using PATCH operations"""
    
    client = SimpleSCIMClient(
        base_url=DATADOG_CONFIG['base_url'],
        bearer_token=DATADOG_CONFIG['bearer_token']
    )
    
    # Build PATCH operations
    operations = []
    
    if 'active' in updates:
        operations.append({
            "op": "replace",
            "path": "active",
            "value": updates['active']
        })
    
    if 'title' in updates:
        operations.append({
            "op": "replace",
            "path": "title",
            "value": updates['title']
        })
    
    if 'name' in updates:
        operations.append({
            "op": "replace",
            "path": "name",
            "value": updates['name']
        })
    
    patch_request = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": operations
    }
    
    try:
        response = await client.request('PATCH', f'/Users/{user_id}', patch_request)
        print(f"User {user_id} updated successfully")
        return response
        
    except httpx.HTTPStatusError as e:
        print(f"Failed to update user {user_id}: {e}")
        raise

# Example usage
async def deactivate_user_example():
    """Deactivate a user"""
    user_id = "12345678-1234-1234-1234-123456789012"
    
    await update_user_example(user_id, {
        'active': False,
        'title': 'Former Employee'
    })
```

### 3. Bulk User Operations

```python
async def bulk_create_users(users: List[Dict]) -> List[Dict]:
    """Create multiple users with proper error handling"""
    
    client = SimpleSCIMClient(
        base_url=DATADOG_CONFIG['base_url'],
        bearer_token=DATADOG_CONFIG['bearer_token']
    )
    
    results = []
    batch_size = 5  # Limit concurrent requests
    
    for i in range(0, len(users), batch_size):
        batch = users[i:i + batch_size]
        
        # Create tasks for concurrent execution
        tasks = []
        for user_data in batch:
            task = create_user_with_retry(client, user_data)
            tasks.append(task)
        
        # Execute batch
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        results.extend(batch_results)
        
        # Rate limiting - pause between batches
        if i + batch_size < len(users):
            await asyncio.sleep(1)
    
    return results

async def create_user_with_retry(client: SimpleSCIMClient, user_data: Dict, max_retries: int = 3) -> Dict:
    """Create user with retry logic"""
    
    for attempt in range(max_retries):
        try:
            return await client.request('POST', '/Users', user_data)
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                # User exists - try to find them
                existing_user = await find_user_by_email(client, user_data['userName'])
                if existing_user:
                    return existing_user
                else:
                    raise ValueError(f"User {user_data['userName']} exists but could not be retrieved")
            
            elif e.response.status_code >= 500 and attempt < max_retries - 1:
                # Server error - retry with backoff
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)
                continue
            else:
                raise
                
        except httpx.RequestError as e:
            if attempt < max_retries - 1:
                # Network error - retry
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)
                continue
            else:
                raise
    
    raise Exception(f"Failed to create user after {max_retries} attempts")
```

## Group Management Examples

### 1. Creating a Group

```python
async def create_group_example():
    """Complete example of creating a group in Datadog"""
    
    # Define group data
    group_data = {
        "displayName": "Engineering Team",
        "externalId": "eng-team-001",
        "members": [
            {
                "$ref": "https://api.datadoghq.com/api/v2/scim/Users/12345678-1234-1234-1234-123456789012",
                "value": "12345678-1234-1234-1234-123456789012",
                "display": "John Doe",
                "type": "User"
            },
            {
                "$ref": "https://api.datadoghq.com/api/v2/scim/Users/87654321-4321-4321-4321-210987654321",
                "value": "87654321-4321-4321-4321-210987654321",
                "display": "Jane Smith",
                "type": "User"
            }
        ],
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"]
    }
    
    client = SimpleSCIMClient(
        base_url=DATADOG_CONFIG['base_url'],
        bearer_token=DATADOG_CONFIG['bearer_token']
    )
    
    try:
        response = await client.request('POST', '/Groups', group_data)
        print(f"Group created with ID: {response['id']}")
        return response
        
    except httpx.HTTPStatusError as e:
        print(f"Failed to create group: {e}")
        raise
```

### 2. Managing Group Members

```python
async def add_user_to_group(group_id: str, user_id: str, display_name: str):
    """Add a user to a group using PATCH operations"""
    
    client = SimpleSCIMClient(
        base_url=DATADOG_CONFIG['base_url'],
        bearer_token=DATADOG_CONFIG['bearer_token']
    )
    
    # First, verify user exists
    try:
        await client.request('GET', f'/Users/{user_id}')
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise ValueError(f"User {user_id} not found in Datadog")
        raise
    
    # Add user to group
    patch_request = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": [
            {
                "op": "add",
                "path": "members",
                "value": [
                    {
                        "$ref": f"https://api.datadoghq.com/api/v2/scim/Users/{user_id}",
                        "value": user_id,
                        "display": display_name,
                        "type": "User"
                    }
                ]
            }
        ]
    }
    
    try:
        response = await client.request('PATCH', f'/Groups/{group_id}', patch_request)
        print(f"User {user_id} added to group {group_id}")
        return response
        
    except httpx.HTTPStatusError as e:
        print(f"Failed to add user to group: {e}")
        raise

async def remove_user_from_group(group_id: str, user_id: str):
    """Remove a user from a group"""
    
    client = SimpleSCIMClient(
        base_url=DATADOG_CONFIG['base_url'],
        bearer_token=DATADOG_CONFIG['bearer_token']
    )
    
    patch_request = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": [
            {
                "op": "remove",
                "path": f"members[value eq \"{user_id}\"]"
            }
        ]
    }
    
    try:
        response = await client.request('PATCH', f'/Groups/{group_id}', patch_request)
        print(f"User {user_id} removed from group {group_id}")
        return response
        
    except httpx.HTTPStatusError as e:
        print(f"Failed to remove user from group: {e}")
        raise
```

### 3. Incremental Group Synchronization

```python
async def sync_group_members(group_id: str, target_member_ids: List[str], member_display_names: Dict[str, str]):
    """Efficiently sync group membership using incremental updates"""
    
    client = SimpleSCIMClient(
        base_url=DATADOG_CONFIG['base_url'],
        bearer_token=DATADOG_CONFIG['bearer_token']
    )
    
    # Get current group membership
    current_group = await client.request('GET', f'/Groups/{group_id}')
    current_member_ids = [member['value'] for member in current_group.get('members', [])]
    
    # Calculate differences
    members_to_add = set(target_member_ids) - set(current_member_ids)
    members_to_remove = set(current_member_ids) - set(target_member_ids)
    
    print(f"Group {group_id} sync: +{len(members_to_add)}, -{len(members_to_remove)}")
    
    # Remove members that shouldn't be in the group
    for user_id in members_to_remove:
        try:
            await remove_user_from_group(group_id, user_id)
            print(f"Removed {user_id} from group {group_id}")
        except Exception as e:
            print(f"Failed to remove {user_id}: {e}")
    
    # Add new members to the group
    for user_id in members_to_add:
        try:
            display_name = member_display_names.get(user_id, f"User {user_id}")
            await add_user_to_group(group_id, user_id, display_name)
            print(f"Added {user_id} to group {group_id}")
        except Exception as e:
            print(f"Failed to add {user_id}: {e}")
    
    return {
        'added': list(members_to_add),
        'removed': list(members_to_remove)
    }
```

## Common Integration Patterns

### 1. HR System Integration

```python
async def onboard_employee(employee_data: Dict):
    """Complete employee onboarding workflow"""
    
    client = SimpleSCIMClient(
        base_url=DATADOG_CONFIG['base_url'],
        bearer_token=DATADOG_CONFIG['bearer_token']
    )
    
    # Step 1: Create user in Datadog
    user_data = {
        "userName": employee_data['email'],
        "active": True,
        "emails": [{"value": employee_data['email'], "type": "work", "primary": True}],
        "name": {
            "formatted": f"{employee_data['first_name']} {employee_data['last_name']}",
            "givenName": employee_data['first_name'],
            "familyName": employee_data['last_name']
        },
        "title": employee_data['job_title'],
        "externalId": employee_data['employee_id'],
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"]
    }
    
    try:
        user_response = await client.request('POST', '/Users', user_data)
        print(f"Created user: {user_response['id']}")
        
        # Step 2: Add to department group
        department_group_id = await get_department_group_id(employee_data['department'])
        if department_group_id:
            await add_user_to_group(
                department_group_id,
                user_response['id'],
                f"{employee_data['first_name']} {employee_data['last_name']}"
            )
            print(f"Added user to department group")
        
        # Step 3: Add to role-based groups
        role_groups = await get_role_groups(employee_data['role'])
        for group_id in role_groups:
            await add_user_to_group(
                group_id,
                user_response['id'],
                f"{employee_data['first_name']} {employee_data['last_name']}"
            )
            print(f"Added user to role group: {group_id}")
        
        return user_response
        
    except Exception as e:
        print(f"Employee onboarding failed: {e}")
        raise

async def offboard_employee(employee_email: str):
    """Complete employee offboarding workflow"""
    
    client = SimpleSCIMClient(
        base_url=DATADOG_CONFIG['base_url'],
        bearer_token=DATADOG_CONFIG['bearer_token']
    )
    
    # Step 1: Find user
    user = await find_user_by_email(client, employee_email)
    if not user:
        raise ValueError(f"User {employee_email} not found in Datadog")
    
    # Step 2: Deactivate user
    await update_user_example(user['id'], {
        'active': False,
        'title': 'Former Employee'
    })
    
    # Step 3: Remove from all groups (optional)
    # Note: Datadog may handle this automatically when user is deactivated
    
    print(f"Employee {employee_email} offboarded successfully")
```

### 2. Identity Provider Sync

```python
async def sync_from_identity_provider(idp_users: List[Dict]):
    """Sync users from external identity provider"""
    
    client = SimpleSCIMClient(
        base_url=DATADOG_CONFIG['base_url'],
        bearer_token=DATADOG_CONFIG['bearer_token']
    )
    
    results = {
        'created': [],
        'updated': [],
        'errors': []
    }
    
    for idp_user in idp_users:
        try:
            # Check if user exists in Datadog
            existing_user = await find_user_by_email(client, idp_user['email'])
            
            if existing_user:
                # Update existing user
                updated_user = await update_user_from_idp(client, existing_user['id'], idp_user)
                results['updated'].append(updated_user['id'])
            else:
                # Create new user
                new_user = await create_user_from_idp(client, idp_user)
                results['created'].append(new_user['id'])
                
        except Exception as e:
            error_msg = f"Failed to sync user {idp_user['email']}: {str(e)}"
            results['errors'].append(error_msg)
            print(error_msg)
    
    return results

async def create_user_from_idp(client: SimpleSCIMClient, idp_user: Dict) -> Dict:
    """Create Datadog user from IdP user data"""
    
    user_data = {
        "userName": idp_user['email'],
        "active": idp_user.get('active', True),
        "emails": [{"value": idp_user['email'], "type": "work", "primary": True}],
        "name": {
            "formatted": f"{idp_user['first_name']} {idp_user['last_name']}",
            "givenName": idp_user['first_name'],
            "familyName": idp_user['last_name']
        },
        "title": idp_user.get('title'),
        "externalId": idp_user.get('id'),
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"]
    }
    
    return await client.request('POST', '/Users', user_data)
```

### 3. Scheduled Synchronization

```python
import schedule
import time

async def scheduled_sync():
    """Example of scheduled synchronization"""
    
    print("Starting scheduled SCIM sync...")
    
    try:
        # Sync users from HR system
        hr_users = await fetch_hr_users()
        user_results = await sync_from_identity_provider(hr_users)
        
        # Sync group memberships
        org_groups = await fetch_org_groups()
        group_results = await sync_group_memberships(org_groups)
        
        # Log results
        print(f"Sync completed - Users: {len(user_results['created'])} created, {len(user_results['updated'])} updated")
        print(f"Groups: {len(group_results['synced'])} synced")
        
    except Exception as e:
        print(f"Scheduled sync failed: {e}")
        # Send alert to monitoring system
        await send_alert(f"SCIM sync failed: {e}")

# Schedule sync every 6 hours
schedule.every(6).hours.do(scheduled_sync)

def run_scheduler():
    """Run the scheduler"""
    while True:
        schedule.run_pending()
        time.sleep(60)
```

## Error Handling Examples

### 1. Comprehensive Error Handling

```python
import logging
from enum import Enum

class SCIMErrorType(Enum):
    USER_EXISTS = "user_exists"
    USER_NOT_FOUND = "user_not_found"
    GROUP_NOT_FOUND = "group_not_found"
    INVALID_DATA = "invalid_data"
    NETWORK_ERROR = "network_error"
    AUTHENTICATION_ERROR = "authentication_error"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"

class SCIMError(Exception):
    def __init__(self, message: str, error_type: SCIMErrorType, details: Dict = None):
        self.error_type = error_type
        self.details = details or {}
        super().__init__(message)

async def safe_scim_operation(operation, *args, **kwargs):
    """Wrapper for SCIM operations with comprehensive error handling"""
    
    try:
        return await operation(*args, **kwargs)
        
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        
        if status_code == 401:
            raise SCIMError(
                "Authentication failed. Check your API token.",
                SCIMErrorType.AUTHENTICATION_ERROR,
                {"status_code": status_code, "response": e.response.text}
            )
        elif status_code == 404:
            raise SCIMError(
                "Resource not found.",
                SCIMErrorType.USER_NOT_FOUND,
                {"status_code": status_code, "response": e.response.text}
            )
        elif status_code == 409:
            raise SCIMError(
                "Resource already exists.",
                SCIMErrorType.USER_EXISTS,
                {"status_code": status_code, "response": e.response.text}
            )
        elif status_code == 429:
            raise SCIMError(
                "Rate limit exceeded.",
                SCIMErrorType.RATE_LIMIT,
                {"status_code": status_code, "response": e.response.text}
            )
        elif status_code >= 500:
            raise SCIMError(
                "Server error occurred.",
                SCIMErrorType.SERVER_ERROR,
                {"status_code": status_code, "response": e.response.text}
            )
        else:
            raise SCIMError(
                f"API error: {status_code}",
                SCIMErrorType.INVALID_DATA,
                {"status_code": status_code, "response": e.response.text}
            )
            
    except httpx.RequestError as e:
        raise SCIMError(
            f"Network error: {str(e)}",
            SCIMErrorType.NETWORK_ERROR,
            {"original_error": str(e)}
        )
    except Exception as e:
        raise SCIMError(
            f"Unexpected error: {str(e)}",
            SCIMErrorType.SERVER_ERROR,
            {"original_error": str(e)}
        )

# Example usage
async def create_user_with_error_handling(user_data: Dict):
    """Create user with proper error handling"""
    
    try:
        result = await safe_scim_operation(
            create_user_example,
            user_data
        )
        return result
        
    except SCIMError as e:
        if e.error_type == SCIMErrorType.USER_EXISTS:
            # Handle user already exists
            print(f"User {user_data['userName']} already exists - finding existing user")
            existing_user = await find_user_by_email(client, user_data['userName'])
            return existing_user
        elif e.error_type == SCIMErrorType.RATE_LIMIT:
            # Handle rate limiting
            print("Rate limit hit - waiting before retry")
            await asyncio.sleep(60)  # Wait 1 minute
            return await create_user_with_error_handling(user_data)
        else:
            # Log error and re-raise
            logging.error(f"SCIM error: {e}, Details: {e.details}")
            raise
```

### 2. Retry Logic with Exponential Backoff

```python
import random
from functools import wraps

def retry_with_backoff(max_retries=3, base_delay=1, max_delay=60):
    """Decorator for retry logic with exponential backoff"""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                    
                except SCIMError as e:
                    if e.error_type in [SCIMErrorType.RATE_LIMIT, SCIMErrorType.SERVER_ERROR]:
                        if attempt < max_retries - 1:
                            # Calculate delay with jitter
                            delay = min(base_delay * (2 ** attempt), max_delay)
                            jitter = random.uniform(0, delay * 0.1)
                            total_delay = delay + jitter
                            
                            print(f"Attempt {attempt + 1} failed, retrying in {total_delay:.2f}s")
                            await asyncio.sleep(total_delay)
                            continue
                    
                    # Don't retry for other error types
                    raise
                    
            raise SCIMError(
                f"Operation failed after {max_retries} attempts",
                SCIMErrorType.SERVER_ERROR
            )
            
        return wrapper
    return decorator

# Example usage
@retry_with_backoff(max_retries=3, base_delay=2)
async def create_user_with_retry(user_data: Dict):
    """Create user with automatic retry"""
    client = SimpleSCIMClient(
        base_url=DATADOG_CONFIG['base_url'],
        bearer_token=DATADOG_CONFIG['bearer_token']
    )
    
    return await client.request('POST', '/Users', user_data)
```

## Performance Optimization

### 1. Connection Pooling

```python
import httpx
from typing import AsyncContextManager

class PooledSCIMClient:
    """SCIM client with connection pooling for better performance"""
    
    def __init__(self, base_url: str, bearer_token: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {bearer_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Configure connection pool
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
                keepalive_expiry=30.0
            )
        )
    
    async def request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make request using pooled connection"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        response = await self.client.request(
            method=method,
            url=url,
            headers=self.headers,
            json=data
        )
        
        if response.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"SCIM API error: {response.status_code} {response.text}",
                request=response.request,
                response=response
            )
        
        return response.json() if response.content else {}
    
    async def close(self):
        """Close the connection pool"""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

# Usage
async def efficient_bulk_operations():
    """Perform bulk operations with connection pooling"""
    
    async with PooledSCIMClient(
        base_url=DATADOG_CONFIG['base_url'],
        bearer_token=DATADOG_CONFIG['bearer_token']
    ) as client:
        
        # Perform multiple operations using the same client
        users = await fetch_users_to_sync()
        
        # Use semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(10)
        
        async def create_user_limited(user_data):
            async with semaphore:
                return await client.request('POST', '/Users', user_data)
        
        # Execute in batches
        results = await asyncio.gather(
            *[create_user_limited(user) for user in users],
            return_exceptions=True
        )
        
        return results
```

### 2. Caching Strategies

```python
import time
from functools import lru_cache
from typing import Dict, Optional

class CachedSCIMClient:
    """SCIM client with caching for read operations"""
    
    def __init__(self, base_url: str, bearer_token: str, cache_ttl: int = 300):
        self.client = SimpleSCIMClient(base_url, bearer_token)
        self.cache_ttl = cache_ttl
        self._user_cache: Dict[str, tuple] = {}
        self._group_cache: Dict[str, tuple] = {}
    
    async def get_user_cached(self, user_id: str) -> Dict:
        """Get user with caching"""
        now = time.time()
        
        # Check cache
        if user_id in self._user_cache:
            cached_user, timestamp = self._user_cache[user_id]
            if now - timestamp < self.cache_ttl:
                return cached_user
        
        # Cache miss - fetch from API
        user = await self.client.request('GET', f'/Users/{user_id}')
        self._user_cache[user_id] = (user, now)
        
        return user
    
    async def get_group_cached(self, group_id: str) -> Dict:
        """Get group with caching"""
        now = time.time()
        
        # Check cache
        if group_id in self._group_cache:
            cached_group, timestamp = self._group_cache[group_id]
            if now - timestamp < self.cache_ttl:
                return cached_group
        
        # Cache miss - fetch from API
        group = await self.client.request('GET', f'/Groups/{group_id}')
        self._group_cache[group_id] = (group, now)
        
        return group
    
    def invalidate_user_cache(self, user_id: str):
        """Invalidate user cache after updates"""
        if user_id in self._user_cache:
            del self._user_cache[user_id]
    
    def invalidate_group_cache(self, group_id: str):
        """Invalidate group cache after updates"""
        if group_id in self._group_cache:
            del self._group_cache[group_id]
```

## Testing Examples

### 1. Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, patch
import httpx

@pytest.fixture
def mock_client():
    """Mock SCIM client for testing"""
    client = AsyncMock()
    return client

@pytest.mark.asyncio
async def test_create_user_success(mock_client):
    """Test successful user creation"""
    # Mock response
    mock_response = {
        "id": "12345678-1234-1234-1234-123456789012",
        "userName": "test@example.com",
        "active": True,
        "emails": [{"value": "test@example.com", "type": "work", "primary": True}]
    }
    
    mock_client.request.return_value = mock_response
    
    # Test user creation
    user_data = {
        "userName": "test@example.com",
        "emails": [{"value": "test@example.com", "type": "work", "primary": True}]
    }
    
    result = await mock_client.request('POST', '/Users', user_data)
    
    assert result["id"] == "12345678-1234-1234-1234-123456789012"
    assert result["userName"] == "test@example.com"
    mock_client.request.assert_called_once_with('POST', '/Users', user_data)

@pytest.mark.asyncio
async def test_create_user_conflict(mock_client):
    """Test handling of user already exists"""
    # Mock 409 conflict response
    mock_response = httpx.Response(
        status_code=409,
        content=b'{"error": "User already exists"}',
        headers={'content-type': 'application/json'}
    )
    
    mock_client.request.side_effect = httpx.HTTPStatusError(
        "409 Conflict",
        request=None,
        response=mock_response
    )
    
    user_data = {
        "userName": "existing@example.com",
        "emails": [{"value": "existing@example.com", "type": "work", "primary": True}]
    }
    
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await mock_client.request('POST', '/Users', user_data)
    
    assert exc_info.value.response.status_code == 409
```

### 2. Integration Tests

```python
@pytest.mark.integration
async def test_full_user_lifecycle():
    """Test complete user lifecycle against live API"""
    
    # Skip if no credentials provided
    if not DATADOG_CONFIG['bearer_token']:
        pytest.skip("No Datadog credentials provided")
    
    client = SimpleSCIMClient(
        base_url=DATADOG_CONFIG['base_url'],
        bearer_token=DATADOG_CONFIG['bearer_token']
    )
    
    # Generate unique test user
    import uuid
    test_email = f"test-{uuid.uuid4()}@example.com"
    
    user_data = {
        "userName": test_email,
        "active": True,
        "emails": [{"value": test_email, "type": "work", "primary": True}],
        "name": {
            "formatted": "Test User",
            "givenName": "Test",
            "familyName": "User"
        },
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"]
    }
    
    created_user = None
    
    try:
        # Create user
        created_user = await client.request('POST', '/Users', user_data)
        assert created_user["id"] is not None
        assert created_user["userName"] == test_email
        
        # Get user
        retrieved_user = await client.request('GET', f'/Users/{created_user["id"]}')
        assert retrieved_user["id"] == created_user["id"]
        
        # Update user
        patch_data = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {
                    "op": "replace",
                    "path": "active",
                    "value": False
                }
            ]
        }
        
        updated_user = await client.request('PATCH', f'/Users/{created_user["id"]}', patch_data)
        assert updated_user["active"] is False
        
    finally:
        # Clean up
        if created_user:
            try:
                await client.request('DELETE', f'/Users/{created_user["id"]}')
            except Exception as e:
                print(f"Cleanup failed: {e}")
```

### 3. Load Testing

```python
import asyncio
import time
from typing import List

async def load_test_user_creation(num_users: int = 100):
    """Load test user creation"""
    
    client = SimpleSCIMClient(
        base_url=DATADOG_CONFIG['base_url'],
        bearer_token=DATADOG_CONFIG['bearer_token']
    )
    
    # Generate test users
    users = []
    for i in range(num_users):
        user_data = {
            "userName": f"loadtest-{i}@example.com",
            "active": True,
            "emails": [{"value": f"loadtest-{i}@example.com", "type": "work", "primary": True}],
            "name": {
                "formatted": f"Load Test User {i}",
                "givenName": "Load",
                "familyName": f"User{i}"
            },
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"]
        }
        users.append(user_data)
    
    # Measure performance
    start_time = time.time()
    
    # Limit concurrent requests
    semaphore = asyncio.Semaphore(10)
    
    async def create_user_limited(user_data):
        async with semaphore:
            try:
                return await client.request('POST', '/Users', user_data)
            except Exception as e:
                return {'error': str(e)}
    
    # Execute load test
    results = await asyncio.gather(
        *[create_user_limited(user) for user in users],
        return_exceptions=True
    )
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Analyze results
    successful = len([r for r in results if isinstance(r, dict) and 'id' in r])
    failed = len(results) - successful
    
    print(f"Load test completed in {duration:.2f}s")
    print(f"Successful: {successful}, Failed: {failed}")
    print(f"Rate: {successful/duration:.2f} users/second")
    
    return {
        'duration': duration,
        'successful': successful,
        'failed': failed,
        'rate': successful/duration
    }
```

This comprehensive guide provides practical, production-ready examples for implementing SCIM with Datadog. Use these patterns as a foundation for your integration, adapting them to your specific requirements and infrastructure. 