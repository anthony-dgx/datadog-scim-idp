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
- Datadog API key with `user_access_invite` and `user_access_manage` scopes

## ⚙️ Environment Configuration

Create a `.env` file in the project root with the following variables:

```bash
# Datadog SCIM API Configuration
DD_SCIM_BASE_URL=https://api.datadoghq.com/api/v2/scim
DD_BEARER_TOKEN=your_datadog_api_key_here

# Database Configuration (auto-configured for Docker Compose)
DATABASE_URL=postgresql://scim_user:scim_password@localhost:5432/scim_demo

# Optional: Backend Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# Optional: Frontend Configuration  
REACT_APP_API_BASE_URL=http://localhost:8000
```

### 🔑 Getting Your Datadog API Key

1. Log into your Datadog account
2. Go to **Organization Settings** → **API Keys**
3. Click **New Key**
4. Name it "SCIM Demo" and ensure it has these scopes:
   - `user_access_invite`
   - `user_access_manage`
5. Copy the key and paste it as `DD_BEARER_TOKEN` in your `.env` file

### 🌍 Datadog Sites

Update `DD_SCIM_BASE_URL` based on your Datadog site:

- **US**: `https://api.datadoghq.com/api/v2/scim`
- **EU**: `https://api.datadoghq.eu/api/v2/scim`
- **Other sites**: Check [Datadog documentation](https://docs.datadoghq.com/api/)

## 🚀 Quick Start

1. **Clone and setup environment**:
   ```bash
   git clone <repository-url>
   cd scim-demo
   cp .env.example .env
   # Edit .env with your Datadog API key
   ```

2. **Start the application** (includes Datadog agent):
   ```bash
   docker-compose up --build
   ```

3. **Access the application**:
   - **Frontend**: http://localhost:3000
   - **Backend API**: http://localhost:8000
   - **API Documentation**: http://localhost:8000/docs
   - **Datadog Agent**: Runs automatically in background for log collection

**What's Running:**
- 🐘 **PostgreSQL**: Database on port 5433
- 🐍 **FastAPI Backend**: API server with comprehensive logging
- ⚛️ **React Frontend**: Modern UI with Datadog styling
- 🐕 **Datadog Agent**: Automatic log and metric collection

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
- **Deactivation**: Use "Deactivate in Datadog" to disable users
- **Error Handling**: View sync errors by hovering over failed status badges

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
- `POST /api/groups/{id}/sync` - Sync group to Datadog
- `POST /api/groups/bulk-sync` - Bulk sync all pending groups
- `POST /api/groups/{group_id}/members/{user_id}` - Add member to group
- `DELETE /api/groups/{group_id}/members/{user_id}` - Remove member from group

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

The application includes a **Datadog agent container** that automatically collects logs from all services. Add these environment variables to your `.env` file:

```env
# Required for SCIM operations
DD_BEARER_TOKEN=your_datadog_api_key_here

# Required for Datadog agent (logs and metrics)
DD_API_KEY=your_datadog_api_key_here
DD_SITE=datadoghq.com
DD_SERVICE_NAME=scim-demo
DD_ENV=development

# Agent configuration (auto-configured in Docker)
DD_AGENT_HOST=datadog-agent
DD_DOGSTATSD_HOST=datadog-agent
```

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
   - Ensure your `.env` file has the correct Datadog API key
   - Verify the API key has the required scopes

2. **"Failed to sync user to Datadog"**
   - Check your API key permissions
   - Verify the Datadog SCIM base URL is correct
   - Check network connectivity

3. **Database connection errors**
   - Ensure PostgreSQL is running (automatic with Docker Compose)
   - Check DATABASE_URL format

4. **Frontend not loading**
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