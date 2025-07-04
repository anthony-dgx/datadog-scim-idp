# SCIM Demo Application

A full-stack demo application for provisioning users and teams into Datadog via SCIM API. This application showcases identity provider functionality with a beautiful Datadog-inspired UI.

## 🚀 Features

- **User Management**: Create, update, deactivate, and delete users
- **Group Management**: Create groups, manage team memberships
- **Datadog SCIM Integration**: Automatic and manual sync with Datadog
- **Modern UI**: Datadog-inspired dark theme with purple accents
- **Real-time Sync Status**: Track synchronization status and errors
- **Bulk Operations**: Sync all pending users/groups at once
- **Docker Support**: Full containerization with Docker Compose

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Frontend │    │  FastAPI Backend │    │   PostgreSQL    │
│                 │────│                 │────│    Database     │
│  - User List    │    │  - User API     │    │                 │
│  - Group List   │    │  - Group API    │    │                 │
│  - SCIM Sync UI │    │  - SCIM Client  │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                │ HTTPS/SCIM
                                ▼
                       ┌─────────────────┐
                       │   Datadog SCIM  │
                       │      API        │
                       │                 │
                       └─────────────────┘
```

## 📋 Prerequisites

- Docker and Docker Compose
- Datadog account with API access
- Datadog API key with required scopes (see below)

## ⚙️ Environment Configuration

Create a `.env` file in the project root with the following variables:

```bash
# Required: Datadog Agent Configuration
DD_API_KEY=your_datadog_api_key_here
DD_SITE=datadoghq.com
DD_ENV=development

# Required: Datadog SCIM API Configuration  
DD_SCIM_BASE_URL=https://api.datadoghq.com/api/v2/scim
DD_BEARER_TOKEN=your_datadog_api_key_here

# Auto-configured: Database (no changes needed for Docker)
DATABASE_URL=postgresql://scim_user:scim_password@localhost:5433/scim_demo

# Auto-configured: Agent connections (no changes needed for Docker)
DD_AGENT_HOST=datadog-agent
DD_DOGSTATSD_HOST=datadog-agent

# Optional: Application Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
REACT_APP_API_BASE_URL=http://localhost:8000
```

### 🔑 Required vs Optional Configuration

**✅ Required (Application won't work without these):**
- `DD_API_KEY` - For Datadog agent to send logs and metrics
- `DD_BEARER_TOKEN` - For SCIM API operations (can use same key as DD_API_KEY)
- `DD_SITE` - Your Datadog site region

**⚙️ Auto-configured (Docker handles these):**
- `DATABASE_URL` - Database connection 
- `DD_AGENT_HOST` - Agent hostname for metrics
- `DD_DOGSTATSD_HOST` - StatsD connection

**🔧 Optional (Has sensible defaults):**
- `DD_ENV` - Environment tag for logs (default: development)
- `BACKEND_HOST/PORT` - Server configuration
- `REACT_APP_API_BASE_URL` - Frontend API endpoint

### 🔑 Getting Your Datadog API Key

1. **Log into your Datadog account**
2. **Go to Organization Settings → API Keys**
3. **Click "New Key"**
4. **Name it "SCIM Demo"** and ensure it has these scopes:
   - `user_access_invite` (for SCIM user operations)
   - `user_access_manage` (for SCIM user management)  
   - `logs_write` (for agent log collection)
   - `metrics_write` (for agent metrics collection)
5. **Copy the key** and add it to your `.env` file as both:
   - `DD_API_KEY=your_key_here` (for agent)
   - `DD_BEARER_TOKEN=your_key_here` (for SCIM API)

### 🌍 Datadog Sites & Auto-Configuration

Set your `DD_SITE` and the application auto-configures everything:

| Site | DD_SITE Value | SCIM URL (auto-configured) |
|------|---------------|----------------------------|
| **US1** | `datadoghq.com` | `https://api.datadoghq.com/api/v2/scim` |
| **US3** | `us3.datadoghq.com` | `https://api.us3.datadoghq.com/api/v2/scim` |
| **US5** | `us5.datadoghq.com` | `https://api.us5.datadoghq.com/api/v2/scim` |
| **EU** | `datadoghq.eu` | `https://api.datadoghq.eu/api/v2/scim` |
| **AP1** | `ap1.datadoghq.com` | `https://api.ap1.datadoghq.com/api/v2/scim` |
| **Gov** | `ddog-gov.com` | `https://api.ddog-gov.com/api/v2/scim` |

💡 **Pro tip**: Just set `DD_SITE` - the application automatically configures the SCIM URL and agent endpoints!

## 🚀 Quick Start

### Step 1: Setup Environment
```bash
git clone https://github.com/anthony-dgx/datadog-scim-idp.git
cd datadog-scim-idp
cp env.example .env
```

### Step 2: Generate SAML Certificates (for SAML IdP functionality)
```bash
# Generate self-signed certificate (for development only)
openssl req -x509 -newkey rsa:2048 -keyout saml.key -out saml.crt -days 365 -nodes \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

# Convert to environment variable format (replace newlines with \n)
echo "SAML_CERT=$(awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}' saml.crt)"
echo "SAML_KEY=$(awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}' saml.key)"
```

### Step 3: Configure Environment Variables
Edit your `.env` file with **required** values:
```bash
# Get these from Datadog → Organization Settings → API Keys
DD_API_KEY=your_datadog_api_key_here
DD_BEARER_TOKEN=your_datadog_api_key_here  # Can use same key
DD_SITE=datadoghq.com  # Or your Datadog site (eu, us3, etc.)

# SAML IdP Configuration (copy the output from step 2)
SAML_ISSUER=http://localhost:8000/saml/metadata
SAML_CERT=-----BEGIN CERTIFICATE-----\nYOUR_CERTIFICATE_HERE\n-----END CERTIFICATE-----
SAML_KEY=-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_HERE\n-----END PRIVATE KEY-----
```

### Step 4: Start the Full Stack
```bash
docker-compose up --build
```

### Step 5: Access the Application
- 🖥️ **Frontend**: http://localhost:3000 
- 🔗 **Backend API**: http://localhost:8000
- 📚 **API Docs**: http://localhost:8000/docs
- 🔐 **SAML Config**: http://localhost:3000/saml (for SAML IdP setup)
- 📊 **View logs in Datadog**: Check your Datadog Log Explorer

## 🏗️ Architecture Overview

Your stack includes these containers:

| Service | Port | Purpose | Logs Collected |
|---------|------|---------|----------------|
| 🐕 **Datadog Agent** | 8125, 8126 | **Log & metric collection** | All container logs → Datadog |
| 🐘 **PostgreSQL** | 5433 | Database | Database queries & errors |
| 🐍 **FastAPI Backend** | 8000 | **SCIM API with structured logging** | All user/group actions & SCIM payloads |
| ⚛️ **React Frontend** | 3000 | Modern UI | Frontend access & errors |

✨ **The agent automatically discovers and collects logs from all containers!**

---

# 🔧 SCIM Integration Guide for Customers

This section provides comprehensive guidance for implementing SCIM with Datadog using this application as a reference.

## 📚 SCIM Overview

SCIM (System for Cross-domain Identity Management) is a standard for automating the exchange of user identity information between systems. With Datadog's SCIM API, you can:

- **Provision users** automatically from your identity provider
- **Manage group memberships** and team access
- **Deactivate users** when they leave your organization
- **Keep user information synchronized** between systems

## 🎯 Key Implementation Patterns

### 1. Authentication & Configuration

```python
# Environment setup for SCIM client
DD_SCIM_BASE_URL = "https://api.datadoghq.com/api/v2/scim"  # US1
DD_BEARER_TOKEN = "your_datadog_api_key"

# Headers for all SCIM requests
headers = {
    "Authorization": f"Bearer {DD_BEARER_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}
```

### 2. User Lifecycle Management

#### Creating Users
```python
# Example SCIM user payload
user_payload = {
    "userName": "john.doe@company.com",
    "active": True,
    "emails": [
        {"value": "john.doe@company.com", "type": "work", "primary": True}
    ],
    "name": {
        "formatted": "John Doe",
        "givenName": "John",
        "familyName": "Doe"
    },
    "title": "Software Engineer",
    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"]
}

# POST to /Users endpoint
response = await client.post("/Users", json=user_payload)
```

#### Handling Conflicts (409 Errors)
When a user already exists, implement automatic discovery:

```python
try:
    response = await client.create_user(user_data)
except HTTPStatusError as e:
    if e.response.status_code == 409:
        # User exists - find them
        existing_user = await client.find_user_by_email(user_data.userName)
        if existing_user:
            return existing_user
        else:
            # Handle edge case where user exists but can't be found
            raise ValueError("User exists but couldn't be retrieved")
```

#### User Updates
```python
# PATCH operations for partial updates
patch_payload = {
    "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
    "Operations": [
        {
            "op": "replace",
            "path": "active",
            "value": False  # Deactivate user
        }
    ]
}

response = await client.patch(f"/Users/{user_id}", json=patch_payload)
```

### 3. Group Management Best Practices

#### Creating Groups with Members
```python
group_payload = {
    "displayName": "Engineering Team",
    "externalId": "eng-team-001",
    "members": [
        {
            "$ref": f"https://api.datadoghq.com/api/v2/scim/Users/{user_id}",
            "value": user_id,
            "display": "John Doe",
            "type": "User"
        }
    ],
    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"]
}
```

#### Incremental Member Synchronization
Instead of replacing the entire member list, use incremental updates:

```python
async def sync_group_members(group_id, target_members):
    # Get current members
    current_group = await client.get_group(group_id)
    current_member_ids = [m["value"] for m in current_group.members]
    
    # Calculate differences
    to_add = set(target_members) - set(current_member_ids)
    to_remove = set(current_member_ids) - set(target_members)
    
    # Add new members
    for user_id in to_add:
        await add_user_to_group(group_id, user_id)
    
    # Remove old members
    for user_id in to_remove:
        await remove_user_from_group(group_id, user_id)
```

## 🛠️ Production Implementation Tips

### 1. Error Handling Strategy

```python
class SCIMError(Exception):
    """Base exception for SCIM operations"""
    pass

class UserExistsError(SCIMError):
    """User already exists in Datadog"""
    pass

class UserNotFoundError(SCIMError):
    """User not found in Datadog"""
    pass

# Implement comprehensive error handling
async def safe_create_user(user_data):
    try:
        return await client.create_user(user_data)
    except HTTPStatusError as e:
        if e.response.status_code == 409:
            raise UserExistsError(f"User {user_data.userName} already exists")
        elif e.response.status_code == 404:
            raise UserNotFoundError("Resource not found")
        else:
            raise SCIMError(f"SCIM API error: {e.response.status_code}")
```

### 2. Retry Logic for Resilience

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def resilient_scim_request(method, endpoint, data=None):
    """SCIM request with automatic retries"""
    try:
        return await client.request(method, endpoint, data)
    except httpx.RequestError:
        # Network errors should be retried
        raise
    except HTTPStatusError as e:
        if e.response.status_code >= 500:
            # Server errors should be retried
            raise
        else:
            # Client errors should not be retried
            raise
```

### 3. Logging and Monitoring

```python
import structlog

logger = structlog.get_logger("scim_operations")

async def logged_scim_operation(operation, entity_type, entity_id, **kwargs):
    """Wrapper for SCIM operations with comprehensive logging"""
    start_time = time.time()
    
    try:
        result = await operation(**kwargs)
        duration = (time.time() - start_time) * 1000
        
        logger.info(
            "SCIM operation successful",
            operation_type=operation.__name__,
            entity_type=entity_type,
            entity_id=entity_id,
            duration_ms=duration,
            success=True
        )
        return result
        
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        
        logger.error(
            "SCIM operation failed",
            operation_type=operation.__name__,
            entity_type=entity_type,
            entity_id=entity_id,
            duration_ms=duration,
            success=False,
            error=str(e)
        )
        raise
```

### 4. Rate Limiting Considerations

```python
import asyncio
from asyncio import Semaphore

# Limit concurrent SCIM requests
scim_semaphore = Semaphore(5)  # Max 5 concurrent requests

async def rate_limited_scim_call(operation):
    async with scim_semaphore:
        # Add small delay between requests
        await asyncio.sleep(0.1)
        return await operation()
```

This comprehensive guide provides everything you need to implement a production-ready SCIM integration with Datadog. Use this demo application as a reference, and adapt the patterns to your specific infrastructure and requirements.

---

## 📖 Demo Walkthrough

### Step 1: Create Users

1. Navigate to the **Users** tab
2. Click **"Add User"**
3. Fill in user details:
   - Username: `john.doe`
   - Email: `john.doe@example.com`
   - First Name: `John`
   - Last Name: `Doe`
   - Title: `Software Engineer`
4. Click **"Create User"**
5. Notice the user appears with "Pending" sync status

### Step 2: Sync User to Datadog

1. Click the green **Sync** button next to the user
2. Watch the sync status change to "Synced"
3. Verify in Datadog that the user was created
4. Check the "Last Synced" timestamp

### Step 3: Create and Manage Groups

1. Navigate to the **Groups** tab
2. Click **"Add Group"**
3. Create a group:
   - Group Name: `Engineering Team`
   - Description: `Software development team`
4. Select team members from the dropdown
5. Click **"Create Group"**
6. Sync the group to Datadog

### Step 4: Test SAML Authentication

1. Navigate to the **SAML Config** tab
2. Upload Datadog's SP metadata XML file
3. Download the generated IdP metadata
4. Configure Datadog to use this app as SAML IdP
5. Test SSO login flow

## 🔄 Advanced Workflows

### Bulk User Management

1. **Create Multiple Users**: Use the bulk import feature
2. **Bulk Sync**: Sync all pending users at once
3. **Group Assignment**: Automatically assign users to groups based on attributes
4. **Deactivation**: Bulk deactivate users who left the organization

### Group Synchronization

1. **Incremental Updates**: Only sync changed group memberships
2. **Dependency Management**: Ensure users exist before adding to groups
3. **Cleanup Operations**: Remove orphaned group memberships
4. **Metadata Updates**: Update group names and descriptions

## 🔐 SAML Identity Provider for Testing

This application **doubles as a SAML Identity Provider**, allowing you to test complete SAML authentication flows with Datadog. This is incredibly valuable for customers who want to:

- **Test SAML SSO** before implementing their own IdP
- **Validate SCIM + SAML integration** end-to-end
- **Debug authentication issues** in a controlled environment
- **Demo complete identity management** to stakeholders

### 🚀 SAML Setup Quick Start

#### Step 1: Generate SAML Certificates

```bash
# Generate self-signed certificate (for development/testing)
openssl req -x509 -newkey rsa:2048 -keyout saml.key -out saml.crt -days 365 -nodes \
  -subj "/C=US/ST=CA/L=San Francisco/O=YourCompany/CN=localhost"

# Convert to environment variable format (replace newlines with \n)
echo "SAML_CERT=$(awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}' saml.crt)"
echo "SAML_KEY=$(awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}' saml.key)"
```

#### Step 2: Configure SAML Environment Variables

Add these to your `.env` file:

```bash
# SAML Identity Provider Configuration
SAML_ISSUER=http://localhost:8000/saml/metadata
SAML_CERT=-----BEGIN CERTIFICATE-----\nMIIDXTCC...YOUR_CERTIFICATE_HERE...\n-----END CERTIFICATE-----
SAML_KEY=-----BEGIN PRIVATE KEY-----\nMIIEvQ...YOUR_KEY_HERE...\n-----END PRIVATE KEY-----
```

⚠️ **Important**: Copy the exact output from the commands above, including the `\n` characters for line breaks.

#### Step 3: Start the Application

```bash
docker-compose up --build
```

### 🔧 Complete SAML Integration with Datadog

#### Step 1: Configure Datadog SAML Settings

1. **Access Datadog SAML Configuration**:
   - Go to **Organization Settings → Login Methods → SAML**
   - Click **"Configure SAML"**

2. **Upload IdP Metadata**:
   - Download metadata from: `http://localhost:8000/saml/metadata`
   - Or use the metadata URL directly: `http://localhost:8000/saml/metadata`
   - Upload the metadata XML in Datadog's SAML configuration

3. **Configure SAML Settings**:
   - **Identity Provider Entity ID**: `http://localhost:8000/saml/metadata`
   - **SSO URL**: `http://localhost:8000/saml/login`
   - **Certificate**: Will be auto-imported from metadata
   - **Attribute Mapping**: 
     - User ID: `eduPersonPrincipalName` → `email`
     - First Name: `givenName` → `first_name`
     - Last Name: `sn` → `last_name`

4. **Enable SAML and Get SP Metadata**:
   - Enable SAML authentication
   - Download the **SP metadata XML** file from Datadog

#### Step 2: Configure SP Metadata in Demo App

1. **Access SAML Configuration UI**:
   - Navigate to `http://localhost:3000/saml`

2. **Upload Datadog SP Metadata**:
   - Upload the SP metadata XML file you downloaded from Datadog
   - The app will automatically parse the Assertion Consumer Service URL

3. **Verify Configuration**:
   - Check that the ACS URL is correctly configured
   - Download the IdP metadata to double-check it matches what you uploaded to Datadog

### 🧪 Testing SAML Authentication

#### Complete Test Flow:

1. **Ensure Users Exist**:
   ```bash
   # First, create test users via SCIM
   # User must exist in the demo app database AND be synced to Datadog
   ```

2. **Initiate SAML Login**:
   - In Datadog, click **"Login with SAML"**
   - You'll be redirected to `http://localhost:8000/saml/login`

3. **Authenticate**:
   - Enter the **email address** of a user that exists in your demo database
   - User must be **active** and **synced to Datadog** via SCIM
   - Click **"Login"**

4. **Automatic Redirect**:
   - The app generates a signed SAML assertion
   - You're automatically redirected back to Datadog
   - You should be logged in as that user

#### OAuth-like Redirect URL Security

The SAML implementation includes **OAuth-inspired security features** for handling redirect URLs through the `RelayState` parameter:

**🔒 Redirect URL Validation:**
- **Length Limits**: Maximum 2048 characters (OAuth standard)
- **Protocol Allowlist**: Only `http` and `https` schemes allowed
- **Domain Allowlist**: Configurable list of trusted domains
- **XSS Protection**: HTML escaping of all RelayState parameters
- **Open Redirect Prevention**: Blocks dangerous schemes (`javascript:`, `data:`, etc.)

**⚙️ Configuration:**
```env
# Add custom allowed redirect domains (comma-separated)
SAML_ALLOWED_REDIRECT_DOMAINS=example.com,app.example.com
```

**🛠️ Discovery Endpoint:**
```bash
# Get SAML configuration (OAuth-like discovery)
curl http://localhost:8000/saml/config
```

**📋 Default Allowed Domains:**
- `datadoghq.com` and all Datadog subdomains (`us3.datadoghq.com`, `eu1.datadoghq.com`, etc.)
- `localhost` and `127.0.0.1` for development
- Custom domains via environment variable

**🎨 User Experience:**
- Users see where they'll be redirected before authentication
- Clear visual indication of destination URL
- Validated and sanitized redirect parameters

#### Troubleshooting SAML:

**Authentication Failed**:
- ✅ User exists in demo database
- ✅ User is active (`active: true`)
- ✅ User is synced to Datadog (`sync_status: "synced"`)
- ✅ Email matches exactly between systems

**SAML Response Invalid**:
- ✅ Certificates are properly formatted in `.env`
- ✅ SP metadata is uploaded correctly
- ✅ Datadog SP metadata is configured in demo app

**Redirect Issues**:
- ✅ ACS URL in Datadog matches the one in SP metadata
- ✅ Both systems can reach each other's URLs

### 🔍 SAML Technical Details

**Supported Features**:
- ✅ **HTTP-POST binding** (required by Datadog)
- ✅ **Email-based NameID** format
- ✅ **Signed assertions** with X.509 certificate
- ✅ **SP-initiated SSO** flow
- ✅ **Just-in-Time (JIT) provisioning** via SCIM integration

**SAML Attributes Sent**:
- `eduPersonPrincipalName` → User's email (NameID)
- `givenName` → First name
- `sn` → Last name (surname)

**Authentication Flow**:
1. User clicks "Login with SAML" in Datadog
2. Datadog redirects to IdP with SAMLRequest
3. IdP displays authentication form
4. User enters email and submits
5. IdP validates user exists and is active
6. IdP generates signed SAML assertion
7. IdP auto-submits response back to Datadog
8. Datadog validates assertion and logs user in

### 💡 Customer Use Cases

**For Testing SCIM + SAML Integration**:
```bash
# 1. Create users via SCIM
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -d '{"username":"test.user","email":"test.user@company.com","first_name":"Test","last_name":"User"}'

# 2. Sync to Datadog
curl -X POST http://localhost:8000/api/users/1/sync

# 3. Test SAML login with test.user@company.com
# 4. Verify user appears in Datadog with correct attributes
```

**For Customer Demos**:
- Show complete identity management lifecycle
- Demonstrate automatic provisioning + authentication
- Test group memberships and access control
- Validate attribute mapping and JIT provisioning

**For Development**:
- Test SAML assertion formats
- Debug attribute mapping issues
- Validate certificate and signature handling
- Test error conditions and edge cases

### 🔐 Security Notes

**For Production Use**:
- 🔒 Use proper SSL/TLS certificates (not self-signed)
- 🔑 Generate secure RSA keys (2048-bit minimum)
- 💾 Store certificates securely (not in environment variables)
- 📝 Implement proper session management
- 🛡️ Add CSRF protection
- 📊 Monitor all authentication attempts

**Development Setup**:
- ⚠️ Self-signed certificates are OK for testing
- 📋 All SAML operations are logged for debugging
- 🔍 Users must exist locally to authenticate
- ⚡ SAML and SCIM work together seamlessly

This SAML functionality makes the demo app a complete **identity management testing platform**, perfect for validating your SCIM integration alongside authentication flows.

## 🐛 Troubleshooting

### Common Issues

**401 Unauthorized**
- Check your `DD_BEARER_TOKEN` is valid
- Verify API key has required scopes
- Ensure correct Datadog site configuration

**409 Conflict Errors**
- User already exists in Datadog
- The app automatically handles this by finding existing users
- Check logs for user discovery results

**Network Timeouts**
- Check Datadog service status
- Verify firewall/proxy settings
- Review rate limiting logs

**Group Sync Failures**
- Ensure all group members are synced to Datadog first
- Check group size limits
- Verify member permissions

### Debugging with Logs

Check Datadog Log Explorer for detailed operation logs:

```
# View all SCIM operations
logger.name:scim_operations

# View failed operations only
logger.name:scim_operations success:false

# View specific user operations
logger.name:scim_operations user_email:john.doe@company.com
```

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines for:

- Code style and standards
- Testing requirements
- Documentation updates
- Feature requests and bug reports

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙋‍♂️ Support

For questions and support:

- 📧 Email: support@example.com
- 🐛 Issues: GitHub Issues
- 📖 Documentation: This README and inline code comments
- 💬 Community: Join our Slack channel

---

  **Made with ❤️ for the Datadog community**
``` 