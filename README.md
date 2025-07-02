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

### Step 2: Configure Datadog Integration
Edit your `.env` file with **required** values:
```bash
# Get these from Datadog → Organization Settings → API Keys
DD_API_KEY=your_datadog_api_key_here
DD_BEARER_TOKEN=your_datadog_api_key_here  # Can use same key
DD_SITE=datadoghq.com  # Or your Datadog site (eu, us3, etc.)
```

### Step 3: Start the Full Stack
```bash
docker-compose up --build
```

### Step 4: Access the Application
- 🖥️ **Frontend**: http://localhost:3000 
- 🔗 **Backend API**: http://localhost:8000
- 📚 **API Docs**: http://localhost:8000/docs
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
   - Select members from the user list
4. Click **"Create Group"**

### Step 4: Sync Group to Datadog

1. Click the **Sync** button on the group
2. The system will:
   - Auto-sync any unsynced group members first
   - Create the group in Datadog
   - Add all members to the group
3. Verify in Datadog that the group and memberships were created

### Step 5: Advanced Features

- **Bulk Sync**: Use "Bulk Sync" to sync all pending users/groups
- **Member Management**: Add/remove members using the quick action buttons
- **Incremental Sync**: Groups use smart incremental member updates to prevent conflicts
- **Individual Member Sync**: Sync/remove specific members without affecting the entire group
- **Enhanced Member Removal**: Fixed SCIM PATCH format with automatic fallback strategies
- **Debug Tools**: Use the debug endpoint to troubleshoot sync discrepancies
- **Deactivation**: Use "Deactivate in Datadog" to disable users
- **Error Handling**: View sync errors by hovering over failed status badges
- **Conflict Resolution**: Comprehensive 409/400 error handling with validation and retry logic

## 🛠️ Development

### Local Development (without Docker)

1. **Backend setup**:
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

2. **Frontend setup**:
   ```bash
   cd frontend
   npm install
   npm start
   ```

3. **Database setup**:
   - Install PostgreSQL locally
   - Create database: `scim_demo`
   - Update `DATABASE_URL` in `.env`

### Project Structure

```
scim-demo/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── main.py         # FastAPI application
│   │   ├── models.py       # SQLAlchemy models
│   │   ├── schemas.py      # Pydantic models
│   │   ├── database.py     # Database configuration
│   │   ├── scim_client.py  # Datadog SCIM client
│   │   └── routers/        # API route handlers
│   │       ├── users.py    # User CRUD + sync
│   │       └── groups.py   # Group CRUD + sync
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # React frontend
│   ├── src/
│   │   ├── App.jsx         # Main application
│   │   ├── App.css         # Datadog-inspired styles
│   │   └── components/     # React components
│   │       ├── UserList.jsx    # User management
│   │       └── GroupList.jsx   # Group management
│   ├── public/
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml      # Container orchestration
└── README.md              # This file
```

## 📡 API Endpoints

### Users
- `GET /api/users` - List all users
- `POST /api/users` - Create a new user
- `GET /api/users/{id}` - Get user by ID
- `PUT /api/users/{id}` - Update user
- `DELETE /api/users/{id}` - Delete user
- `POST /api/users/{id}/sync` - Sync user to Datadog
- `POST /api/users/{id}/sync-deactivate` - Deactivate user in Datadog
- `POST /api/users/bulk-sync` - Bulk sync all pending users

### Groups
- `GET /api/groups` - List all groups
- `POST /api/groups` - Create a new group
- `GET /api/groups/{id}` - Get group by ID
- `PUT /api/groups/{id}` - Update group
- `DELETE /api/groups/{id}` - Delete group
- `POST /api/groups/{id}/sync` - Sync group to Datadog (incremental member updates)
- `PATCH /api/groups/{id}/metadata` - Update only group metadata (name/description) in Datadog
- `POST /api/groups/bulk-sync` - Bulk sync all pending groups
- `POST /api/groups/{group_id}/members/{user_id}` - Add member to group locally
- `DELETE /api/groups/{group_id}/members/{user_id}` - Remove member from group locally
- `POST /api/groups/{group_id}/members/{user_id}/sync` - Sync specific member to Datadog group
- `DELETE /api/groups/{group_id}/members/{user_id}/sync` - Remove specific member from Datadog group
- `GET /api/groups/{group_id}/debug` - Debug endpoint showing local vs Datadog group state

### System
- `GET /health` - Health check endpoint
- `GET /docs` - API documentation (Swagger UI)

## 📊 Comprehensive Logging & Monitoring with Datadog Agent

The application includes comprehensive logging with a **Datadog agent** that automatically collects all logs and sends them to Datadog for monitoring and debugging.

### 🔍 What Gets Logged

**All User Actions:**
- User creation, updates, deletions with full payloads
- Sync operations with before/after states
- Success/failure metrics and timing

**All Group Actions:**
- Group creation, updates, deletions with member details
- Group sync operations including member auto-sync
- Member management (add/remove) activities

**SCIM API Calls:**
- Complete request payloads sent to Datadog
- Full response payloads received from Datadog
- HTTP status codes, timing, and error details
- Authentication token usage (sanitized)

**System Events:**
- Application startup with configuration status
- Database connection health
- Environment variable configuration

### 📋 Log Structure

All logs are structured JSON with the following fields:

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "service": "scim-demo",
  "environment": "development",
  "action_type": "user_action|group_action|scim_api_call|sync_operation",
  "success": true,
  "duration_ms": 150,
  "user_id": 123,
  "datadog_id": "dd-user-456",
  "request_payload": { /* Full SCIM request */ },
  "response_payload": { /* Full SCIM response */ },
  "trace_id": "abc123",
  "span_id": "def456"
}
```

### 🔧 Datadog Agent Configuration

The application includes a **Datadog agent container** that automatically collects logs from all services and forwards them to Datadog. The agent is configured via environment variables:

**✅ Required Configuration:**
```env
# Single API key for both agent and SCIM operations
DD_API_KEY=your_datadog_api_key_here          # Agent log collection
DD_BEARER_TOKEN=your_datadog_api_key_here     # SCIM API (can be same key)
DD_SITE=datadoghq.com                         # Your Datadog region
```

**⚙️ Auto-configured by Docker (no changes needed):**
```env
DD_SERVICE_NAME=scim-demo                     # Service name in logs
DD_ENV=development                            # Environment tag
DD_AGENT_HOST=datadog-agent                   # Agent hostname
DD_DOGSTATSD_HOST=datadog-agent               # Metrics endpoint
```

**🔍 Agent Features:**
- **Automatic log discovery** - Finds and collects logs from all containers
- **Container metadata** - Adds container name, image, labels to logs
- **Log processing** - Parses JSON logs and adds structured fields
- **Buffering & retry** - Local buffering prevents log loss

**Benefits of Agent-Based Logging:**
- ✅ **Local buffering** - No log loss during network issues
- ✅ **Automatic collection** - Picks up all container logs automatically
- ✅ **Better performance** - No blocking HTTP calls from application
- ✅ **Rich metadata** - Container info, labels, and auto-tagging
- ✅ **APM integration** - Automatic trace correlation

### 📈 Metrics & Dashboards

The application sends metrics to Datadog:

- `scim.user.action.success` - User operation success count
- `scim.user.action.error` - User operation error count  
- `scim.group.action.success` - Group operation success count
- `scim.group.action.error` - Group operation error count
- `scim.api.request.success` - SCIM API success count
- `scim.api.request.error` - SCIM API error count
- `scim.api.request.duration` - SCIM API response times
- `scim.sync.success` - Sync operation success count
- `scim.sync.error` - Sync operation error count

### 🔍 Example Log Outputs

**User Sync Operation:**
```json
{
  "action_type": "sync_operation",
  "operation_type": "create",
  "entity_type": "user",
  "entity_id": 123,
  "datadog_id": "dd-user-456",
  "success": true,
  "sync_data": {
    "local_user": { "username": "john.doe", "email": "john@example.com" },
    "scim_payload": { "userName": "john.doe", "active": true, "emails": [...] },
    "datadog_response": { "id": "dd-user-456", "userName": "john.doe" }
  }
}
```

**SCIM API Call:**
```json
{
  "action_type": "scim_api_call",
  "method": "POST",
  "endpoint": "/Users",
  "status_code": 201,
  "duration_ms": 245,
  "request_payload": { "userName": "john.doe", "active": true },
  "response_payload": { "id": "dd-user-456", "userName": "john.doe" },
  "success": true
}
```

### 🛡️ Security & Privacy

- **Sensitive Data**: Passwords, tokens, and secrets are automatically redacted
- **PII Handling**: Personal information is logged but can be configured to exclude
- **Payload Sanitization**: All payloads are sanitized before logging
- **Structured Logging**: Consistent JSON format for easy parsing and alerting

## 🎨 UI Features

### Datadog-Inspired Design
- **Dark Theme**: Modern dark UI matching Datadog's aesthetic
- **Purple Accents**: Datadog's signature purple color (#632ca6)
- **Status Indicators**: Color-coded sync status badges
- **Smooth Animations**: Hover effects and loading states
- **Responsive Design**: Works on desktop and mobile

### User Experience
- **Real-time Feedback**: Toast notifications for all actions
- **Loading States**: Spinners during async operations
- **Error Handling**: Clear error messages and retry options
- **Empty States**: Helpful prompts when no data exists
- **Bulk Operations**: Efficient management of multiple items

## 🔧 Troubleshooting

### Common Issues

1. **"DD_BEARER_TOKEN environment variable is required"**
   - Ensure your `.env` file has both `DD_API_KEY` and `DD_BEARER_TOKEN` set
   - Both can use the same Datadog API key value
   - Verify the API key has the required scopes: `user_access_invite`, `user_access_manage`, `logs_write`, `metrics_write`

2. **"Failed to sync user to Datadog"**
   - Check your API key permissions in Datadog
   - Verify `DD_SITE` matches your Datadog region
   - SCIM URL is auto-configured based on `DD_SITE`
   - Check network connectivity and API rate limits

3. **"Issues with group member management (409 conflicts, member removal failures)"**
   - **Fixed in v2.1**: 
     - Groups use incremental PATCH operations with correct Datadog SCIM format
     - Member removal now includes required `"value": null` for remove operations
     - Automatic fallback to PUT operations if PATCH fails
     - Enhanced validation and error handling
   - **Debug tools**: Use `GET /api/groups/{id}/debug` to compare local vs Datadog state
   - **Individual operations**: 
     - `PATCH /api/groups/{id}/metadata` - Update only group name/description
     - `POST/DELETE /api/groups/{group_id}/members/{user_id}/sync` - Individual member management

4. **"Datadog agent connection issues"**
   - Ensure `DD_API_KEY` is set for the agent
   - Verify `DD_SITE` is correctly configured
   - Check agent logs: `docker-compose logs datadog-agent`
   - Agent automatically connects to other containers via Docker networking

5. **Database connection errors**
   - Ensure PostgreSQL is running (automatic with Docker Compose)
   - Check DATABASE_URL format

6. **Frontend not loading**
   - Verify both backend and frontend containers are running
   - Check that ports 3000 and 8000 are available

### Logs and Debugging

```bash
# View all container logs
docker-compose logs

# View specific service logs
docker-compose logs backend
docker-compose logs frontend
docker-compose logs db

# Follow logs in real-time
docker-compose logs -f backend
```

## 🚦 Health Checks

The application includes health check endpoints:

- **Backend Health**: `GET /health`
- **Database Status**: Included in health check response
- **Datadog Configuration**: Shows if API credentials are configured

## 🔒 Security Considerations

- API keys are passed via environment variables
- HTTPS should be used in production
- Database credentials should be rotated regularly
- Consider implementing rate limiting for production use

## 📚 Additional Resources

- [Datadog SCIM API Documentation](https://docs.datadoghq.com/api/latest/scim/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://reactjs.org/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Built with ❤️ for Datadog SCIM integration demos** 