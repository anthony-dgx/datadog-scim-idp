from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
import os
import logging

from .database import engine, get_db
from .models import Base
from .routers import users, groups, saml, roles
from .logging_config import setup_logging

# Initialize minimal logging
setup_logging()

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SCIM Demo Application",
    description="A full-stack demo application for provisioning users and teams into Datadog via SCIM API",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router, prefix="/api")
app.include_router(groups.router, prefix="/api")
app.include_router(roles.router, prefix="/api")  # Role management for SAML role mapping
app.include_router(saml.router)  # API endpoints for SAML management
app.include_router(saml.public_router)  # Public SAML protocol endpoints

@app.get("/", response_class=HTMLResponse)
def read_root():
    """Root endpoint with basic app information"""
    return """
    <html>
        <head>
            <title>SCIM Demo Application</title>
            <style>
                body { 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    max-width: 800px;
                    margin: 2rem auto;
                    padding: 0 1rem;
                    line-height: 1.6;
                }
                .header { color: #632ca6; }
                .endpoint { background: #f5f5f5; padding: 0.5rem; margin: 0.5rem 0; border-radius: 4px; }
                .method { font-weight: bold; color: #632ca6; }
            </style>
        </head>
        <body>
            <h1 class="header">🚀 SCIM Demo Application</h1>
            <p>A full-stack demo application for provisioning users and teams into Datadog via SCIM API.</p>
            
            <h2>🔗 Quick Links</h2>
            <ul>
                <li><a href="/docs" target="_blank">📚 API Documentation (Swagger)</a></li>
                <li><a href="/redoc" target="_blank">📖 ReDoc Documentation</a></li>
                <li><a href="http://localhost:3000" target="_blank">🖥️ Frontend Application</a></li>
            </ul>
            
            <h2>📋 API Endpoints</h2>
            
            <h3>👥 Users</h3>
            <div class="endpoint"><span class="method">GET</span> /api/users - List all users</div>
            <div class="endpoint"><span class="method">POST</span> /api/users - Create a new user</div>
            <div class="endpoint"><span class="method">GET</span> /api/users/{id} - Get user by ID</div>
            <div class="endpoint"><span class="method">PUT</span> /api/users/{id} - Update user</div>
            <div class="endpoint"><span class="method">DELETE</span> /api/users/{id} - Delete user</div>
            <div class="endpoint"><span class="method">POST</span> /api/users/{id}/sync - Sync user to Datadog</div>
            <div class="endpoint"><span class="method">POST</span> /api/users/{id}/sync-deactivate - Deactivate user in Datadog</div>
            <div class="endpoint"><span class="method">POST</span> /api/users/bulk-sync - Bulk sync all pending users</div>
            
            <h3>👨‍👩‍👧‍👦 Groups</h3>
            <div class="endpoint"><span class="method">GET</span> /api/groups - List all groups</div>
            <div class="endpoint"><span class="method">POST</span> /api/groups - Create a new group</div>
            <div class="endpoint"><span class="method">GET</span> /api/groups/{id} - Get group by ID</div>
            <div class="endpoint"><span class="method">PUT</span> /api/groups/{id} - Update group</div>
            <div class="endpoint"><span class="method">DELETE</span> /api/groups/{id} - Delete group</div>
            <div class="endpoint"><span class="method">POST</span> /api/groups/{id}/sync - Sync group to Datadog</div>
            <div class="endpoint"><span class="method">POST</span> /api/groups/bulk-sync - Bulk sync all pending groups</div>
            
            <h3>🔐 Roles & SAML Mapping</h3>
            <div class="endpoint"><span class="method">GET</span> /api/roles - List all roles</div>
            <div class="endpoint"><span class="method">POST</span> /api/roles - Create a new role</div>
            <div class="endpoint"><span class="method">GET</span> /api/roles/{id} - Get role by ID</div>
            <div class="endpoint"><span class="method">PUT</span> /api/roles/{id} - Update role</div>
            <div class="endpoint"><span class="method">DELETE</span> /api/roles/{id} - Delete role</div>
            <div class="endpoint"><span class="method">POST</span> /api/roles/mappings - Create role mappings</div>
            <div class="endpoint"><span class="method">POST</span> /api/roles/{role_id}/users/{user_id} - Assign role to user</div>
            <div class="endpoint"><span class="method">DELETE</span> /api/roles/{role_id}/users/{user_id} - Remove role from user</div>
            
            <h3>🔑 SAML Authentication</h3>
            <div class="endpoint"><span class="method">GET</span> /saml/metadata - Get IdP metadata</div>
            <div class="endpoint"><span class="method">POST</span> /saml/login - SAML login endpoint</div>
            <div class="endpoint"><span class="method">POST</span> /saml/validate - SAML validation with JIT provisioning</div>
            <div class="endpoint"><span class="method">GET</span> /api/saml/jit-config - Get JIT configuration</div>
            <div class="endpoint"><span class="method">POST</span> /api/saml/jit-config - Configure JIT provisioning</div>
            
            <h2>⚙️ Configuration</h2>
            <p>Make sure to set the following environment variables:</p>
            <ul>
                <li><code>DD_SCIM_BASE_URL</code> - Datadog SCIM API base URL</li>
                <li><code>DD_BEARER_TOKEN</code> - Datadog API bearer token</li>
                <li><code>DATABASE_URL</code> - PostgreSQL database connection string</li>
            </ul>
        </body>
    </html>
    """

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Test database connection
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    
    # Check environment variables
    dd_config = {
        "scim_url_configured": bool(os.getenv("DD_SCIM_BASE_URL")),
        "bearer_token_configured": bool(os.getenv("DD_BEARER_TOKEN"))
    }
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "datadog_config": dd_config,
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 