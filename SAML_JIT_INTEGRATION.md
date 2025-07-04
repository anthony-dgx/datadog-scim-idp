# SAML Just-In-Time (JIT) Provisioning with Datadog

This document explains how to configure and use SAML JIT provisioning with Datadog in your IDP application.

## Overview

SAML JIT provisioning allows users to be automatically created in both your local system and Datadog when they first authenticate via SAML. This eliminates the need to pre-provision users manually.

## How It Works

```mermaid
sequenceDiagram
    participant U as User
    participant D as Datadog
    participant I as IDP App
    participant DB as Database
    participant SCIM as Datadog SCIM API
    
    U->>D: Access Datadog
    D->>I: SAML AuthnRequest
    I->>U: Show login form
    U->>I: Enter email
    I->>DB: Check if user exists
    
    alt User doesn't exist (JIT enabled)
        I->>DB: Create user locally
        I->>SCIM: Create user in Datadog
        SCIM-->>I: Return Datadog User ID
        I->>DB: Update user with Datadog ID
        I->>I: Generate SAML response
        I->>D: SAML Response
        D->>U: Grant access
    else User exists
        I->>I: Generate SAML response
        I->>D: SAML Response  
        D->>U: Grant access
    end
```

## Configuration

### 1. Environment Variables

Ensure you have the following environment variables configured:

```bash
# Datadog SCIM API Configuration
DD_SCIM_BASE_URL=https://api.datadoghq.com/api/v2/scim
DD_BEARER_TOKEN=your_datadog_api_key
DD_SITE=datadoghq.com

# SAML Configuration
SAML_ISSUER=http://localhost:8000/saml/metadata
SAML_CERT=-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----
SAML_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
BACKEND_BASE_URL=http://localhost:8000
```

### 2. Enable JIT Provisioning

JIT provisioning is enabled by default. You can configure it via the API:

```bash
# Enable JIT provisioning
curl -X POST "http://localhost:8000/api/saml/jit-config" \
  -H "Content-Type: application/json" \
  -d '{
    "enable_jit": true,
    "default_title": "User",
    "auto_activate": true,
    "create_in_datadog": true,
    "require_email_domain": null
  }'
```

### 3. View Current Configuration

```bash
# Get current JIT configuration
curl -X GET "http://localhost:8000/api/saml/jit-config"
```

## User Flow

### 1. User Authentication

When a user attempts to authenticate via SAML:

1. **User accesses Datadog** - User tries to access Datadog
2. **Datadog redirects to IdP** - Datadog sends SAML AuthnRequest
3. **IdP shows login form** - User enters email address
4. **User lookup** - IdP checks if user exists locally
5. **JIT provisioning** (if user doesn't exist):
   - Create user in local database
   - Create user in Datadog via SCIM API
   - Link local user to Datadog user ID
6. **SAML response** - Generate and send SAML response to Datadog
7. **User granted access** - User is logged into Datadog

### 2. Login Form

The login form includes a checkbox to enable/disable JIT provisioning for individual login attempts:

```html
<form method="post" action="/saml/validate">
  <input type="email" name="email" required>
  <input type="checkbox" name="enable_jit" value="true" checked>
  <input type="hidden" name="SAMLRequest" value="...">
  <button type="submit">Login</button>
</form>
```

## SAML Attribute Mapping

The following SAML attributes are supported for JIT provisioning:

| SAML Attribute | Local Field | Description |
|---------------|-------------|-------------|
| `firstName` | `first_name` | User's first name |
| `lastName` | `last_name` | User's last name |
| `givenName` | `first_name` | Alternative to firstName |
| `sn` | `last_name` | Alternative to lastName |
| `displayName` | `formatted_name` | Full display name |
| `title` | `title` | Job title |
| `mail` | `email` | Email address |
| `employeeID` | `external_id` | Employee ID |

## API Endpoints

### SAML JIT Configuration

```bash
# Get JIT configuration
GET /api/saml/jit-config

# Update JIT configuration  
POST /api/saml/jit-config
```

### SAML Authentication

```bash
# SAML metadata endpoint
GET /saml/metadata

# SAML login endpoint (SP-initiated)
POST /saml/login

# SAML validation endpoint (with JIT support)
POST /saml/validate
```

## Error Handling

The JIT provisioning process includes comprehensive error handling:

### 1. Partial Success

If the user is created locally but SCIM creation fails:
- User can still authenticate via SAML
- Local user is marked with `sync_status: "failed"`
- Error details are logged
- User can be manually synced later

### 2. Complete Failure

If JIT provisioning fails completely:
- User creation is rolled back
- Error is logged
- User receives error message
- Authentication is denied

### 3. Logging

All JIT operations are logged with structured data:

```json
{
  "operation_type": "saml_authentication",
  "operation": "jit_provisioning_success",
  "user_email": "john.doe@company.com",
  "success": true,
  "saml_data": {
    "datadog_user_id": "12345678-1234-1234-1234-123456789012",
    "local_user_id": 42,
    "created_attributes": {
      "first_name": "John",
      "last_name": "Doe",
      "title": "Software Engineer"
    }
  }
}
```

## Security Considerations

### 1. Email Domain Validation

You can restrict JIT provisioning to specific email domains:

```bash
curl -X POST "http://localhost:8000/api/saml/jit-config" \
  -d '{"require_email_domain": "company.com"}'
```

### 2. Default User Attributes

JIT-created users receive:
- `active: true` - User is active by default
- `title: "User"` - Default job title
- Generated UUID as external ID
- Basic name parsing from email address

### 3. Audit Trail

All JIT operations are logged for security auditing:
- User creation attempts
- SCIM API calls
- Authentication events
- Error conditions

## Datadog Integration

### 1. SCIM User Creation

When creating users in Datadog, the following SCIM payload is sent:

```json
{
  "userName": "john.doe@company.com",
  "active": true,
  "emails": [
    {
      "value": "john.doe@company.com",
      "type": "work", 
      "primary": true
    }
  ],
  "name": {
    "formatted": "John Doe",
    "givenName": "John",
    "familyName": "Doe"
  },
  "title": "Software Engineer",
  "externalId": "local-user-uuid",
  "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"]
}
```

### 2. Conflict Resolution

If a user already exists in Datadog:
- SCIM API returns 409 Conflict
- System searches for existing user
- Local user is linked to existing Datadog user
- Authentication proceeds normally

### 3. Group Membership

JIT-created users are not automatically added to groups. You can add them to groups later via:

```bash
# Add user to group
POST /api/groups/{group_id}/members/{user_id}
```

## Testing

### 1. Manual Testing

Test JIT provisioning by:

1. Start your application
2. Access Datadog (or simulate SAML request)
3. Enter email of non-existent user
4. Verify user is created locally and in Datadog
5. Check logs for success/failure details

### 2. Integration Testing

```python
import pytest
from your_app import create_user_jit

@pytest.mark.asyncio
async def test_jit_provisioning():
    # Test user creation
    user = await create_user_jit(
        db_session, 
        "test@example.com",
        {
            "first_name": "Test",
            "last_name": "User",
            "title": "Tester"
        }
    )
    
    assert user.email == "test@example.com"
    assert user.datadog_user_id is not None
    assert user.sync_status == "synced"
```

## Monitoring

### 1. Metrics

The application sends metrics to Datadog:

```python
# Success metrics
statsd.increment("saml.jit.success")
statsd.increment("saml.jit.user_created")

# Error metrics  
statsd.increment("saml.jit.error")
statsd.increment("saml.jit.scim_failed")
```

### 2. Alerts

Set up alerts for:
- JIT provisioning failures
- SCIM API errors
- High volume of new user creation
- Authentication failures

## Troubleshooting

### Common Issues

1. **SCIM API Authentication Failed**
   - Check `DD_BEARER_TOKEN` is valid
   - Verify API key has SCIM permissions
   - Check `DD_SITE` matches your Datadog instance

2. **User Creation Fails**
   - Check email format is valid
   - Verify required fields are present
   - Check domain restrictions

3. **User Exists but Can't Login**
   - Check user is active in local database
   - Verify user exists in Datadog
   - Check sync status and error messages

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
```

This will log detailed information about:
- SAML requests and responses
- SCIM API calls
- User creation attempts
- Error details

## Example Configuration

Here's a complete example of setting up SAML JIT provisioning:

```bash
# 1. Set environment variables
export DD_BEARER_TOKEN="your_datadog_api_key"
export DD_SITE="datadoghq.com"
export SAML_ISSUER="https://your-idp.com/saml/metadata"

# 2. Configure JIT provisioning
curl -X POST "http://localhost:8000/api/saml/jit-config" \
  -H "Content-Type: application/json" \
  -d '{
    "enable_jit": true,
    "default_title": "Employee",
    "auto_activate": true,
    "create_in_datadog": true,
    "require_email_domain": "your-company.com"
  }'

# 3. Upload Datadog SP metadata
curl -X POST "http://localhost:8000/api/saml/metadata" \
  -F "file=@datadog-sp-metadata.xml"

# 4. Test JIT provisioning
curl -X POST "http://localhost:8000/saml/validate" \
  -d "email=newuser@your-company.com" \
  -d "enable_jit=true" \
  -d "SAMLRequest=..." \
  -d "RelayState=..."
```

This completes the SAML JIT provisioning setup with Datadog integration. 