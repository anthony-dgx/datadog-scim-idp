# SCIM & SAML Demo Application

A comprehensive identity provider demo application that provides both **SCIM provisioning** and **SAML authentication** capabilities for Datadog. This application showcases complete identity management functionality with a beautiful Datadog-inspired UI.

---

## ⚠️ **IMPORTANT: Educational & Testing Purpose Only**

> **🚨 This is NOT a production-ready identity provider!**
> 
> This application is designed as an **educational and testing tool** to help you:
> - 📚 **Learn SAML and SCIM protocols** in a hands-on environment
> - 🧪 **Test identity management integrations** with Datadog
> - 🔍 **Understand identity provider concepts** and workflows
> - 🛠️ **Experiment with role mapping** and JIT provisioning
> - 📖 **Reference implementation patterns** for your own systems
> 
> **❌ DO NOT USE IN PRODUCTION** - This demo lacks essential security features required for production identity providers:
> - No multi-factor authentication
> - Basic session management
> - Self-signed certificates for development
> - No advanced security hardening
> - No compliance certifications
> - No enterprise-grade monitoring
> 
> **✅ Perfect for:** Learning, testing, proof-of-concepts, and development environments
> 
> **❌ Not suitable for:** Production authentication, sensitive data, or real user accounts

---

## 🚀 What This Application Does

This demo application provides a complete identity management platform with these key capabilities:

### 🔐 **SAML Identity Provider**
- **Full SAML 2.0 Authentication**: Acts as Identity Provider for testing SAML SSO flows
- **SAML JIT Provisioning**: Automatically creates users in Datadog during SAML authentication
- **Role-Based Access Control**: Assigns roles based on SAML attributes from IdP
- **Secure Redirects**: OAuth-like redirect URL validation and handling

### 👥 **User Provisioning (Two Sync Approaches)**
- **SCIM Provisioning**: Create users in IdP → manually sync to Datadog via SCIM API
- **JIT Provisioning**: Create users in IdP → automatically sync to Datadog during SAML login
- **Group Management**: Organize users into teams and sync to Datadog
- **Bulk Operations**: Sync multiple users/groups at once

### 🎭 **Role Management**
- **Dynamic Role Assignment**: Map IdP roles to application roles
- **User Assignment Interface**: Assign roles to users with intuitive UI
- **Bulk Role Creation**: Create multiple role mappings efficiently
- **Real-time Updates**: See user counts and assignments update immediately

### 📊 **Modern UI & Monitoring**
- **Datadog-Inspired Interface**: Clean, modern web interface
- **Real-time Status**: Track sync status, errors, and operations
- **Comprehensive Logging**: All operations logged and sent to Datadog
- **Docker Support**: Full containerization with monitoring

---

## 🛠️ Setup & Installation

### Prerequisites
- Docker and Docker Compose
- Datadog account with API access

### Step 1: Get the Code
```bash
git clone https://github.com/anthony-dgx/datadog-scim-idp.git
cd datadog-scim-idp
cp env.example .env
```

### Step 2: Get Your Datadog API Key
1. Go to **Datadog → Organization Settings → API Keys**
2. Create a new key with these scopes:
   - `user_access_invite` and `user_access_manage` (for SCIM)
   - `logs_write` and `metrics_write` (for monitoring)

### Step 3: Generate SAML Certificates
```bash
# Generate self-signed certificate for development
openssl req -x509 -newkey rsa:2048 -keyout saml.key -out saml.crt -days 365 -nodes \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

# Convert to environment format
echo "SAML_CERT=$(awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}' saml.crt)"
echo "SAML_KEY=$(awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}' saml.key)"
```

### Step 4: Configure Environment
Edit your `.env` file:
```bash
# Required: Your Datadog API key
DD_API_KEY=your_datadog_api_key_here
DD_BEARER_TOKEN=your_datadog_api_key_here
DD_SITE=datadoghq.com  # Or your Datadog site (eu, us3, etc.)

# Required: SAML certificates (copy output from step 3)
SAML_ISSUER=http://localhost:8000/saml/metadata
SAML_CERT=-----BEGIN CERTIFICATE-----\nYOUR_CERTIFICATE_HERE\n-----END CERTIFICATE-----
SAML_KEY=-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_HERE\n-----END PRIVATE KEY-----
```

### Step 5: Start the Application
```bash
docker-compose up --build
```

### Step 6: Access the Application
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## 🎯 How to Use

You have **two approaches** for user provisioning - choose the one that fits your needs:

### 🤔 **Which Sync Approach Should You Choose?**

Both approaches require **admin to create users in the IdP first**. The difference is **when/how users get created in Datadog**:

| **SCIM Provisioning** | **JIT Provisioning** |
|---|---|
| ✅ **Immediate sync control** | ✅ **Automatic sync on login** |
| ✅ **Bulk sync operations** | ✅ **No manual sync required** |
| ✅ **Pre-provision before login** | ✅ **Users only created when needed** |
| ✅ **Good for planned rollouts** | ✅ **Great for gradual adoption** |
| ❌ **Requires manual sync step** | ❌ **Users must authenticate first** |
| ❌ **More administrative overhead** | ❌ **No control over sync timing** |

**💡 Pro Tip**: You can use both approaches together! Sync some users via SCIM and let others be created via JIT.

### 📋 **Approach 1: SCIM Provisioning (Manual Sync)**
*Best for: Pre-planning users, bulk operations, immediate provisioning*

1. **Create Users & Groups in IdP**
   - Go to **Users** tab → Add users with email, name, title
   - Go to **Groups** tab → Create groups and assign members
   - Assign roles to users if needed

2. **Manually Sync to Datadog**
   - Use **Sync** buttons to push users/groups to Datadog via SCIM
   - Users are immediately available in Datadog
   - No authentication required for provisioning

3. **Configure SAML Authentication**
   - Go to **SAML Config** tab → Upload Datadog's SP metadata
   - Download IdP metadata and configure in Datadog
   - Test SAML login with existing users

### ⚡ **Approach 2: JIT Provisioning (Automatic Sync)**
*Best for: On-demand provisioning, minimal admin overhead*

1. **Create Users in IdP First**
   - Go to **Users** tab → Add users with email, name, title
   - ⚠️ **Important**: Users must exist in IdP before they can login
   - Assign roles to users if needed

2. **Configure SAML with JIT**
   - Go to **SAML Config** tab → Upload Datadog's SP metadata  
   - ✅ **Enable JIT Provisioning** checkbox
   - Configure default roles for new users
   - Download IdP metadata and configure in Datadog

3. **Test JIT Flow**
   ```
   📋 Step-by-step JIT Flow:
   1. Admin creates user account in IdP (this application)
   2. User attempts to login to Datadog
   3. Datadog redirects user to IdP for authentication
   4. User enters credentials in IdP login form
   5. IdP validates credentials:
      ✅ If user exists in IdP → Authentication succeeds → User created in Datadog automatically
      ❌ If user doesn't exist in IdP → Authentication fails → "User not found" error
   ```

### 🔄 **Complete Authentication Flow**
Regardless of sync approach chosen:
1. **User Exists in IdP**: Admin must create user in IdP first
2. **SAML Login**: Users authenticate via SAML from Datadog  
3. **IdP Validation**: IdP checks if user exists and authenticates
4. **Role Assignment**: Users get roles based on SAML attributes
5. **Access Control**: Users gain appropriate permissions in Datadog

---

## 🏗️ Architecture & Technical Details

### Container Stack
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Frontend │    │  FastAPI Backend │    │   PostgreSQL    │
│  (Port 3000)    │────│  (Port 8000)    │────│  (Port 5433)    │
│                 │    │                 │    │                 │
│  - User Interface│    │  - SAML IdP     │    │  - User Data    │
│  - Role Management│   │  - SCIM Client  │    │  - Role Mapping │
│  - SAML Config   │    │  - Role API     │    │  - Groups       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                    ┌───────────┼───────────┐
                    │           │           │
                    ▼           │           ▼
         ┌─────────────────┐    │  ┌─────────────────┐
         │  Datadog Agent  │    │  │   Datadog SCIM  │
         │  (Monitoring)   │    │  │      API        │
         │                 │    │  │                 │
         └─────────────────┘    │  └─────────────────┘
                                │
                                │ SAML Authentication
                                ▼
                       ┌─────────────────┐
                       │   External      │
                       │   Applications  │
                       │   (via SAML)    │
                       └─────────────────┘
```

### Key Features Explained

#### User Provisioning Options
- **SCIM Provisioning**: Create users in IdP → manually sync to Datadog via SCIM API
- **JIT Provisioning**: Create users in IdP → automatically sync to Datadog during SAML authentication
- **User Validation**: Users must exist in IdP before authentication (both approaches)
- **Flexible Configuration**: Choose the sync approach that fits your workflow

#### Role Mapping System
- **Dynamic Assignment**: Map IdP roles to local roles
- **Bulk Management**: Create multiple mappings efficiently
- **User Interface**: Assign roles with comprehensive UI
- **Real-time Updates**: Immediate feedback on assignments

#### SCIM Integration
- **Full CRUD Operations**: Create, read, update, delete users/groups
- **Datadog Sync**: Push users and groups to Datadog
- **Error Handling**: Comprehensive error handling and retries
- **Bulk Operations**: Sync multiple entities at once

### Environment Configuration

#### Required Variables
```bash
DD_API_KEY=your_datadog_api_key_here          # Datadog API key
DD_BEARER_TOKEN=your_datadog_api_key_here     # Same as DD_API_KEY
DD_SITE=datadoghq.com                         # Your Datadog site
SAML_ISSUER=http://localhost:8000/saml/metadata
SAML_CERT=-----BEGIN CERTIFICATE-----\n...   # SAML certificate
SAML_KEY=-----BEGIN PRIVATE KEY-----\n...     # SAML private key
```

#### Optional Variables
```bash
DD_ENV=development                            # Environment tag
SAML_JIT_ENABLED=true                        # Enable JIT provisioning
SAML_JIT_DEFAULT_ROLE=user                   # Default role for JIT users
SAML_JIT_AUTO_SYNC=true                      # Auto-sync JIT users
```

#### Datadog Sites
| Site | DD_SITE Value | Auto-configured SCIM URL |
|------|---------------|---------------------------|
| US1  | `datadoghq.com` | `https://api.datadoghq.com/api/v2/scim` |
| US3  | `us3.datadoghq.com` | `https://api.us3.datadoghq.com/api/v2/scim` |
| EU   | `datadoghq.eu` | `https://api.datadoghq.eu/api/v2/scim` |
| Gov  | `ddog-gov.com` | `https://api.ddog-gov.com/api/v2/scim` |

---

## 🔧 API Reference

### SCIM Endpoints
```bash
# Users
GET    /api/users           # List all users
POST   /api/users           # Create user
GET    /api/users/{id}      # Get user
PUT    /api/users/{id}      # Update user
DELETE /api/users/{id}      # Delete user
POST   /api/users/{id}/sync # Sync user to Datadog

# Groups
GET    /api/groups          # List all groups
POST   /api/groups          # Create group
POST   /api/groups/{id}/sync # Sync group to Datadog
```

### Role Management
```bash
# Roles
GET    /api/roles           # List all roles
POST   /api/roles           # Create role
POST   /api/roles/mappings  # Bulk create role mappings
POST   /api/roles/{id}/users/{user_id}    # Assign role to user
DELETE /api/roles/{id}/users/{user_id}    # Remove role from user
```

### SAML Endpoints
```bash
GET    /saml/metadata       # Get IdP metadata
POST   /saml/login          # SAML login endpoint
POST   /saml/validate       # Validate SAML request
GET    /saml/jit/config     # Get JIT configuration
POST   /saml/jit/config     # Update JIT configuration
```

---

## 🐛 Troubleshooting

### Common Issues

**401 Unauthorized**
- Check your `DD_API_KEY` and `DD_BEARER_TOKEN`
- Verify API key has required scopes
- Ensure correct `DD_SITE` configuration

**SAML Authentication Failed**
- Verify user exists in database and is active
- Check SAML certificates are properly formatted
- Ensure SP metadata is uploaded correctly

**Role Assignment Issues**
- Check role exists and is active
- Verify IdP role attributes are being sent
- Ensure role mapping is configured correctly

**JIT Provisioning Issues**
- Check if JIT is enabled in SAML config
- Verify SAML assertion contains required attributes
- Ensure default roles are configured

### Debug Logging

Check Datadog Log Explorer for detailed logs:
```bash
# View all operations
logger.name:scim_operations

# View failed operations
logger.name:scim_operations success:false

# View JIT operations
logger.name:scim_operations operation:jit_*

# View role operations
logger.name:scim_operations operation:role_*
```

---

## 📚 Additional Resources

### Documentation Files
- `SAML_JIT_INTEGRATION.md` - Complete JIT provisioning guide
- `SAML_ROLE_MAPPING.md` - Role mapping integration guide
- `SCIM_INTEGRATION_EXAMPLES.md` - SCIM implementation examples

### Test Scripts
- `test_saml_jit.py` - Test JIT provisioning functionality
- `test_role_mapping.py` - Test role mapping features

### API Documentation
- **Interactive API Docs**: http://localhost:8000/docs
- **OpenAPI Spec**: http://localhost:8000/openapi.json

---

## 🤝 Contributing

We welcome contributions! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Made with ❤️ by Anthony and Claude for the Datadog community**

*Perfect for learning SAML and SCIM protocols in a hands-on environment!* 