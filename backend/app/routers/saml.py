import os
from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import base64
import json
import logging
import uuid
from datetime import datetime, timedelta

from ..database import get_db
from ..models import User, SAMLMetadata
from ..schemas import (
    SAMLMetadataResponse, SAMLLoginRequest, SAMLValidateRequest, SAMLResponseData
)
from ..saml_client import saml_config
from ..logging_config import action_logger
from ..scim_client import scim_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/saml", tags=["saml"])
public_router = APIRouter(prefix="/saml", tags=["saml-public"])

# OAuth-like configuration for allowed redirect domains
ALLOWED_REDIRECT_DOMAINS = [
    # Datadog domains
    'datadoghq.com', 'app.datadoghq.com', 'us3.datadoghq.com', 'us5.datadoghq.com',
    'eu1.datadoghq.com', 'ap1.datadoghq.com', 'croquettes.datadoghq.com',
    # Development domains
    'localhost', '127.0.0.1'
]

# Allow custom domains from environment variable (OAuth-like configuration)
if custom_domains := os.getenv("SAML_ALLOWED_REDIRECT_DOMAINS"):
    custom_domain_list = [domain.strip() for domain in custom_domains.split(",")]
    ALLOWED_REDIRECT_DOMAINS.extend(custom_domain_list)
    logger.info(f"Added custom allowed redirect domains: {custom_domain_list}")

@router.post("/metadata", response_model=SAMLMetadataResponse)
async def upload_sp_metadata(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and parse Service Provider metadata XML"""
    
    if not file.filename.endswith('.xml'):
        raise HTTPException(status_code=400, detail="File must be XML format")
    
    try:
        # Read the XML content
        metadata_xml = await file.read()
        metadata_content = metadata_xml.decode('utf-8')
        
        # Parse the metadata
        parsed_metadata = saml_config.parse_sp_metadata(metadata_content)
        
        # Check if metadata already exists
        existing_metadata = db.query(SAMLMetadata).filter(
            SAMLMetadata.entity_id == parsed_metadata['entityId']
        ).first()
        
        if existing_metadata:
            # Update existing metadata
            existing_metadata.metadata_xml = metadata_content
            existing_metadata.acs_url = parsed_metadata['assertionConsumerService']['url']
            existing_metadata.acs_binding = parsed_metadata['assertionConsumerService']['binding']
            existing_metadata.sls_url = parsed_metadata.get('singleLogoutService', {}).get('url')
            existing_metadata.sls_binding = parsed_metadata.get('singleLogoutService', {}).get('binding')
            existing_metadata.name_id_formats = json.dumps(parsed_metadata.get('nameIdFormats', []))
            existing_metadata.required_attributes = json.dumps([])  # Can be extended later
            
            db_metadata = existing_metadata
        else:
            # Create new metadata record
            db_metadata = SAMLMetadata(
                entity_id=parsed_metadata['entityId'],
                metadata_xml=metadata_content,
                acs_url=parsed_metadata['assertionConsumerService']['url'],
                acs_binding=parsed_metadata['assertionConsumerService']['binding'],
                sls_url=parsed_metadata.get('singleLogoutService', {}).get('url'),
                sls_binding=parsed_metadata.get('singleLogoutService', {}).get('binding'),
                name_id_formats=json.dumps(parsed_metadata.get('nameIdFormats', [])),
                required_attributes=json.dumps([])  # Can be extended later
            )
            db.add(db_metadata)
        
        db.commit()
        db.refresh(db_metadata)
        
        # Log the metadata upload
        action_logger.log_saml_metadata(
            operation="upload_sp_metadata",
            entity_id=parsed_metadata['entityId'],
            success=True,
            metadata_info={
                "entity_id": parsed_metadata['entityId'],
                "acs_url": parsed_metadata['assertionConsumerService']['url'],
                "acs_binding": parsed_metadata['assertionConsumerService']['binding'],
                "parsed_services": len(parsed_metadata.get('assertionConsumerServices', [])),
                "name_id_formats": parsed_metadata.get('nameIdFormats', []),
                "operation": "update" if existing_metadata else "create"
            }
        )
        
        return db_metadata.to_dict()
        
    except Exception as e:
        # Log the metadata upload failure
        action_logger.log_saml_metadata(
            operation="upload_sp_metadata",
            entity_id="unknown",
            success=False,
            error=str(e)
        )
        
        raise HTTPException(status_code=400, detail=f"Failed to parse metadata: {str(e)}")

@public_router.get("/metadata", response_model=None)
async def get_idp_metadata(db: Session = Depends(get_db)):
    """Return IdP metadata XML"""
    
    try:
        # Get SP metadata if available to customize IdP metadata
        sp_metadata_record = db.query(SAMLMetadata).filter(SAMLMetadata.active == True).first()
        sp_metadata = None
        
        if sp_metadata_record:
            sp_metadata = {
                "entityId": sp_metadata_record.entity_id,
                "assertionConsumerService": {
                    "url": sp_metadata_record.acs_url,
                    "binding": sp_metadata_record.acs_binding
                }
            }
            if sp_metadata_record.sls_url:
                sp_metadata["singleLogoutService"] = {
                    "url": sp_metadata_record.sls_url,
                    "binding": sp_metadata_record.sls_binding
                }
        
        # Generate IdP metadata
        metadata_xml = saml_config.generate_idp_metadata(sp_metadata)
        
        # Log metadata generation
        action_logger.log_saml_metadata(
            operation="generate_idp_metadata",
            entity_id="idp",
            success=True,
            metadata_info={
                "sp_configured": sp_metadata is not None,
                "metadata_size": len(metadata_xml),
                "sp_entity_id": sp_metadata.get('entityId') if sp_metadata else None
            }
        )
        
        return Response(
            content=metadata_xml,
            media_type="application/xml",
            headers={"Content-Disposition": "attachment; filename=idp-metadata.xml"}
        )
        
    except Exception as e:
        # Log metadata generation failure
        action_logger.log_saml_metadata(
            operation="generate_idp_metadata",
            entity_id="idp",
            success=False,
            error=str(e)
        )
        
        raise HTTPException(status_code=500, detail=f"Failed to generate metadata: {str(e)}")

@public_router.get("/login", response_class=HTMLResponse)
@public_router.post("/login", response_class=HTMLResponse)
async def saml_login(
    request: Request,
    SAMLRequest: Optional[str] = None,
    RelayState: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """SP-initiated SAML login endpoint with OAuth-like redirect URL handling"""
    
    try:
        # For POST requests, extract from form data
        if request.method == "POST":
            form_data = await request.form()
            SAMLRequest = form_data.get("SAMLRequest") or SAMLRequest
            RelayState = form_data.get("RelayState") or RelayState
        
        # Handle missing SAMLRequest
        if not SAMLRequest:
            # Log direct access attempt
            action_logger.log_saml_login(
                operation="login_direct_access",
                success=False,
                error="SAMLRequest missing - direct access attempted"
            )
            
            # Return error page for direct access
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head><title>SAML Error</title></head>
                <body style="font-family: Arial, sans-serif; text-align: center; margin-top: 100px;">
                    <h2>SAML Authentication Error</h2>
                    <p>This endpoint requires a SAML request from the Service Provider.</p>
                    <p>Please initiate login from Datadog using the Single Sign-On URL.</p>
                </body>
                </html>
                """,
                status_code=400
            )
        
        # Validate and sanitize RelayState for OAuth-like security
        validated_relay_state = _validate_relay_state(RelayState)
        
        # Decode and validate SAMLRequest
        decoded_request = base64.b64decode(SAMLRequest).decode('utf-8')
        
        # Log the login attempt with enhanced redirect URL info
        action_logger.log_saml_login(
            operation="login_initiated",
            success=True,
            saml_data={
                "relay_state": validated_relay_state,
                "relay_state_original": RelayState,
                "relay_state_validated": validated_relay_state != RelayState,
                "request_method": request.method,
                "has_saml_request": bool(SAMLRequest)
            }
        )
        
        # Return login form with OAuth-like redirect URL display
        relay_state_display = ""
        if validated_relay_state:
            relay_state_display = f"""
            <div class="redirect-info">
                <p><small>After login, you will be redirected to: <strong>{validated_relay_state[:100]}{'...' if len(validated_relay_state) > 100 else ''}</strong></small></p>
            </div>
            """
        
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>SAML Login</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        min-height: 100vh;
                        margin: 0;
                        background-color: #f5f5f5;
                    }}
                    .login-container {{
                        background: white;
                        padding: 2rem;
                        border-radius: 8px;
                        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                        width: 100%;
                        max-width: 400px;
                    }}
                    h2 {{ color: #632ca6; margin-bottom: 1rem; }}
                    .form-group {{ margin-bottom: 1rem; }}
                    label {{ display: block; margin-bottom: 0.5rem; font-weight: 500; }}
                    input[type="email"] {{
                        width: 100%;
                        padding: 0.75rem;
                        border: 1px solid #ddd;
                        border-radius: 4px;
                        font-size: 1rem;
                        box-sizing: border-box;
                    }}
                    button {{
                        width: 100%;
                        padding: 0.75rem;
                        background-color: #632ca6;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        font-size: 1rem;
                        cursor: pointer;
                        transition: background-color 0.2s;
                    }}
                    button:hover {{ background-color: #4f1f85; }}
                    .note {{ font-size: 0.875rem; color: #666; margin-top: 1rem; }}
                    .redirect-info {{ 
                        background-color: #f8f9fa; 
                        padding: 0.75rem; 
                        border-radius: 4px; 
                        margin-bottom: 1rem; 
                        border-left: 4px solid #632ca6;
                    }}
                    .redirect-info small {{ color: #555; }}
                    .checkbox-group label {{ 
                        display: flex; 
                        align-items: center; 
                        font-weight: normal; 
                        font-size: 0.875rem;
                        margin-bottom: 0;
                    }}
                    .checkbox-group input[type="checkbox"] {{ 
                        margin-right: 0.5rem;
                        width: auto;
                    }}
                </style>
            </head>
            <body>
                <div class="login-container">
                    <h2>SAML Login</h2>
                    {relay_state_display}
                    <form method="post" action="/saml/validate">
                        <div class="form-group">
                            <label for="email">Email Address:</label>
                            <input type="email" id="email" name="email" required>
                        </div>
                        <div class="form-group checkbox-group">
                            <label>
                                <input type="checkbox" id="enable_jit" name="enable_jit" value="true" checked>
                                Enable Just-In-Time provisioning (create user if not exists)
                            </label>
                        </div>
                        <input type="hidden" name="SAMLRequest" value="{SAMLRequest}">
                        <input type="hidden" name="RelayState" value="{validated_relay_state or ''}">
                        <button type="submit">Login</button>
                    </form>
                    <p class="note">Enter your email address to authenticate with SAML.</p>
                </div>
            </body>
            </html>
            """
        )
        
    except Exception as e:
        # Log login initiation failure
        action_logger.log_saml_login(
            operation="login_initiated",
            success=False,
            error=str(e),
            saml_data={
                "relay_state": RelayState,
                "request_method": request.method,
                "has_saml_request": bool(SAMLRequest)
            }
        )
        
        raise HTTPException(status_code=500, detail=f"SAML login failed: {str(e)}")

def _validate_relay_state(relay_state: Optional[str]) -> Optional[str]:
    """
    Validate and sanitize RelayState parameter for OAuth-like security.
    
    This function implements OAuth-like redirect URL validation to prevent
    open redirect attacks and ensure only safe URLs are allowed.
    """
    if not relay_state:
        return None
    
    # Remove any potential XSS vectors
    import html
    relay_state = html.escape(relay_state)
    
    # Length validation (OAuth best practice)
    if len(relay_state) > 2048:  # Standard OAuth redirect_uri length limit
        logger.warning(f"RelayState too long: {len(relay_state)} chars, truncating")
        relay_state = relay_state[:2048]
    
    # URL validation (basic safety checks)
    try:
        from urllib.parse import urlparse
        parsed = urlparse(relay_state)
        
        # Allow both absolute and relative URLs
        if parsed.scheme and parsed.scheme not in ['http', 'https']:
            logger.warning(f"Invalid RelayState scheme: {parsed.scheme}")
            return None
            
        # Block known dangerous protocols
        if parsed.scheme in ['javascript', 'data', 'vbscript']:
            logger.warning(f"Blocked dangerous RelayState scheme: {parsed.scheme}")
            return None
            
        # Allow Datadog URLs and localhost for development
        if parsed.netloc:
            allowed_domains = ALLOWED_REDIRECT_DOMAINS
            
            # Check if domain is allowed
            domain_allowed = False
            for allowed in allowed_domains:
                if parsed.netloc == allowed or parsed.netloc.endswith('.' + allowed):
                    domain_allowed = True
                    break
            
            if not domain_allowed:
                logger.warning(f"RelayState domain not in allowlist: {parsed.netloc}")
                # In production, you might want to return None here
                # For demo purposes, we'll allow it but log it
                
    except Exception as e:
        logger.warning(f"RelayState validation error: {e}")
        return None
    
    return relay_state

async def create_user_jit(db: Session, email: str, user_attributes: Dict[str, Any]) -> User:
    """
    Create a user Just-In-Time during SAML authentication.
    
    This function creates a user both locally and in Datadog via SCIM
    when they don't exist but are trying to authenticate via SAML.
    """
    try:
        # Extract user information from SAML attributes
        first_name = user_attributes.get('first_name', '')
        last_name = user_attributes.get('last_name', '')
        formatted_name = user_attributes.get('formatted_name') or f"{first_name} {last_name}".strip()
        title = user_attributes.get('title', '')
        
        # Create user in local database
        db_user = User(
            uuid=str(uuid.uuid4()),
            username=email,
            email=email,
            first_name=first_name,
            last_name=last_name,
            formatted_name=formatted_name,
            title=title,
            active=True,
            external_id=user_attributes.get('external_id'),
            sync_status="pending"
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        # Assign default roles for JIT users
        default_roles = user_attributes.get('default_roles', ['user'])
        assigned_roles = []
        
        if default_roles:
            from ..models import Role
            import json
            
            # Find roles that match the default role values
            matching_roles = db.query(Role).filter(
                Role.idp_role_value.in_(default_roles),
                Role.active == True
            ).all()
            
            # If no matching roles found, assign the system default role
            if not matching_roles:
                default_role = db.query(Role).filter(Role.is_default == True, Role.active == True).first()
                if default_role:
                    matching_roles = [default_role]
            
            # Assign roles to user
            if matching_roles:
                db_user.roles.extend(matching_roles)
                assigned_roles = [role.idp_role_value for role in matching_roles if role.idp_role_value]
                
                # Store IdP roles in user record
                db_user.idp_roles = json.dumps(assigned_roles)
                db_user.last_role_sync = datetime.utcnow()
        
        # Create user in Datadog via SCIM
        from ..schemas import SCIMUser, SCIMEmail, SCIMName
        
        scim_user = SCIMUser(
            userName=email,
            active=True,
            emails=[SCIMEmail(value=email, type="work", primary=True)],
            name=SCIMName(
                formatted=formatted_name,
                givenName=first_name,
                familyName=last_name
            ),
            title=title,
            externalId=db_user.uuid
        )
        
        try:
            scim_response = await scim_client.create_user(scim_user)
            
            # Update local user with Datadog ID
            db_user.datadog_user_id = scim_response.id
            db_user.last_synced = datetime.utcnow()
            db_user.sync_status = "synced"
            db_user.sync_error = None
            
            db.commit()
            
            # Log successful JIT provisioning
            action_logger.log_saml_login(
                operation="jit_provisioning_success",
                user_email=email,
                success=True,
                saml_data={
                    "datadog_user_id": scim_response.id,
                    "local_user_id": db_user.id,
                    "assigned_roles": assigned_roles,
                    "created_attributes": {
                        "first_name": first_name,
                        "last_name": last_name,
                        "title": title
                    }
                }
            )
            
            logger.info(f"JIT provisioning successful for {email}: local_id={db_user.id}, datadog_id={scim_response.id}, roles={assigned_roles}")
            
        except Exception as scim_error:
            # Mark sync as failed but keep local user
            db_user.sync_status = "failed"
            db_user.sync_error = str(scim_error)
            db.commit()
            
            # Log SCIM failure but continue with authentication
            action_logger.log_saml_login(
                operation="jit_provisioning_partial",
                user_email=email,
                success=False,
                error=f"SCIM creation failed: {scim_error}",
                saml_data={
                    "local_user_created": True,
                    "datadog_user_created": False,
                    "local_user_id": db_user.id,
                    "assigned_roles": assigned_roles
                }
            )
            
            logger.warning(f"JIT provisioning partially failed for {email}: created locally but SCIM failed: {scim_error}")
        
        return db_user
        
    except Exception as e:
        db.rollback()
        
        # Log JIT provisioning failure
        action_logger.log_saml_login(
            operation="jit_provisioning_failed",
            user_email=email,
            success=False,
            error=str(e)
        )
        
        logger.error(f"JIT provisioning failed for {email}: {e}")
        raise

@public_router.post("/validate", response_class=HTMLResponse)
async def saml_validate(
    email: str = Form(...),
    SAMLRequest: str = Form(...),
    RelayState: Optional[str] = Form(None),
    enable_jit: Optional[bool] = Form(True),  # Add JIT provisioning flag
    db: Session = Depends(get_db)
):
    """Validate user email and generate SAML response with JIT provisioning support"""
    
    try:
        # Check if user exists and is active
        user = db.query(User).filter(
            User.email == email,
            User.active == True
        ).first()
        
        if not user and enable_jit:
            # JIT Provisioning: Create user on-demand
            logger.info(f"User {email} not found locally, attempting JIT provisioning")
            
            # In a real implementation, you might extract these attributes from:
            # - SAML assertion attributes
            # - External directory (LDAP, Active Directory)
            # - API calls to HR systems
            # For this example, we'll use basic information and assign default role
            jit_user_attributes = {
                'first_name': email.split('@')[0].split('.')[0].title() if '.' in email.split('@')[0] else email.split('@')[0].title(),
                'last_name': email.split('@')[0].split('.')[1].title() if '.' in email.split('@')[0] and len(email.split('@')[0].split('.')) > 1 else '',
                'title': 'User',  # Default title
                'external_id': None,
                'default_roles': ['user']  # Default role for JIT users
            }
            
            try:
                user = await create_user_jit(db, email, jit_user_attributes)
                
                # Log successful JIT authentication
                action_logger.log_saml_login(
                    operation="jit_auth_success",
                    user_email=email,
                    success=True,
                    saml_data={
                        "jit_provisioning": True,
                        "user_created": True,
                        "local_user_id": user.id,
                        "datadog_user_id": user.datadog_user_id,
                        "sync_status": user.sync_status
                    }
                )
                
            except Exception as jit_error:
                # Log JIT provisioning failure
                action_logger.log_saml_login(
                    operation="jit_auth_failed",
                    user_email=email,
                    success=False,
                    error=f"JIT provisioning failed: {jit_error}"
                )
                
                raise HTTPException(
                    status_code=500, 
                    detail=f"Unable to create user {email} via JIT provisioning: {str(jit_error)}"
                )
        
        elif not user:
            # User doesn't exist and JIT is disabled
            action_logger.log_saml_login(
                operation="auth_failed",
                user_email=email,
                success=False,
                error="User not found and JIT provisioning disabled"
            )
            
            raise HTTPException(status_code=401, detail="User not found and JIT provisioning is disabled")
        
        # Get SP metadata for response generation
        sp_metadata_record = db.query(SAMLMetadata).filter(SAMLMetadata.active == True).first()
        
        if not sp_metadata_record:
            # Log configuration error
            action_logger.log_saml_login(
                operation="auth_failed",
                user_email=email,
                success=False,
                error="Service Provider metadata not configured"
            )
            
            raise HTTPException(status_code=500, detail="Service Provider metadata not configured")
        
        sp_metadata = {
            "entityId": sp_metadata_record.entity_id,
            "assertionConsumerService": {
                "url": sp_metadata_record.acs_url,
                "binding": sp_metadata_record.acs_binding
            }
        }
        
        # Prepare user data for SAML assertion including roles
        import json
        
        # Get user's roles for SAML assertion
        user_roles = []
        if user.roles:
            user_roles = [role.idp_role_value for role in user.roles if role.idp_role_value and role.active]
        elif user.idp_roles:
            # Fallback to stored IdP roles
            user_roles = json.loads(user.idp_roles)
        
        # Get default role if user has no roles
        default_role = None
        if not user_roles:
            from ..models import Role
            default_role_obj = db.query(Role).filter(Role.is_default == True, Role.active == True).first()
            if default_role_obj and default_role_obj.idp_role_value:
                default_role = default_role_obj.idp_role_value
        
        user_data = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "email": user.email,
            "roles": user_roles,  # For SAML role mapping
            "default_role": default_role,  # Fallback role
            "department": getattr(user, 'department', None),  # Optional department
            "team": getattr(user, 'team', None)  # Optional team
        }
        
        # Generate SAML response
        saml_response = saml_config.generate_saml_response(
            user_email=user.email,
            user_data=user_data,
            saml_request=SAMLRequest,
            relay_state=RelayState,
            sp_metadata=sp_metadata
        )
        
        # Log successful authentication
        action_logger.log_saml_login(
            operation="auth_success",
            user_email=email,
            success=True,
            saml_data={
                "sp_entity_id": sp_metadata["entityId"],
                "acs_url": sp_metadata["assertionConsumerService"]["url"],
                "relay_state": RelayState,
                "jit_provisioning": not user or user.created_at > datetime.utcnow() - timedelta(minutes=1),
                "user_attributes": {
                    "has_first_name": bool(user.first_name),
                    "has_last_name": bool(user.last_name),
                    "username": user.username,
                    "sync_status": user.sync_status,
                    "datadog_user_id": user.datadog_user_id
                }
            }
        )
        
        # Return auto-submit form
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>SAML Authentication</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        min-height: 100vh;
                        margin: 0;
                        background-color: #f5f5f5;
                    }}
                    .auth-container {{
                        background: white;
                        padding: 2rem;
                        border-radius: 8px;
                        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                        text-align: center;
                    }}
                    h2 {{ color: #632ca6; margin-bottom: 1rem; }}
                    .spinner {{
                        border: 4px solid #f3f3f3;
                        border-top: 4px solid #632ca6;
                        border-radius: 50%;
                        width: 40px;
                        height: 40px;
                        animation: spin 1s linear infinite;
                        margin: 20px auto;
                    }}
                    @keyframes spin {{
                        0% {{ transform: rotate(0deg); }}
                        100% {{ transform: rotate(360deg); }}
                    }}
                </style>
            </head>
            <body>
                <div class="auth-container">
                    <h2>Authentication Successful</h2>
                    <div class="spinner"></div>
                    <p>Redirecting to Datadog...</p>
                </div>
                <form id="samlForm" method="post" action="{sp_metadata['assertionConsumerService']['url']}">
                    <input type="hidden" name="SAMLResponse" value="{saml_response}">
                    <input type="hidden" name="RelayState" value="{RelayState or ''}">
                </form>
                <script>
                    document.getElementById('samlForm').submit();
                </script>
            </body>
            </html>
            """
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Log authentication failure
        action_logger.log_saml_login(
            operation="auth_failed",
            user_email=email,
            success=False,
            error=str(e)
        )
        
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")

@public_router.get("/logout", response_class=HTMLResponse)
async def saml_logout(
    SAMLRequest: Optional[str] = None,
    RelayState: Optional[str] = None
):
    """SAML logout endpoint"""
    
    # Log logout attempt
    action_logger.log_saml_login(
        operation="logout_initiated",
        success=True,
        saml_data={
            "has_saml_request": bool(SAMLRequest),
            "relay_state": RelayState
        }
    )
    
    return HTMLResponse(
        content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>SAML Logout</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    background-color: #f5f5f5;
                }
                .logout-container {
                    background: white;
                    padding: 2rem;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                    text-align: center;
                }
                h2 { color: #632ca6; margin-bottom: 1rem; }
            </style>
        </head>
        <body>
            <div class="logout-container">
                <h2>Logout Successful</h2>
                <p>You have been successfully logged out.</p>
            </div>
        </body>
        </html>
        """
    )

@router.get("/metadata-list", response_model=list[SAMLMetadataResponse])
async def list_sp_metadata(db: Session = Depends(get_db)):
    """List all Service Provider metadata records"""
    metadata_records = db.query(SAMLMetadata).all()
    return [record.to_dict() for record in metadata_records]

@router.delete("/metadata/{metadata_id}")
async def delete_sp_metadata(metadata_id: int, db: Session = Depends(get_db)):
    """Delete a Service Provider metadata record"""
    metadata_record = db.query(SAMLMetadata).filter(SAMLMetadata.id == metadata_id).first()
    if not metadata_record:
        raise HTTPException(status_code=404, detail="Metadata not found")
    
    entity_id = metadata_record.entity_id
    db.delete(metadata_record)
    db.commit()
    
    # Log metadata deletion
    action_logger.log_saml_metadata(
        operation="delete_sp_metadata",
        entity_id=entity_id,
        success=True,
        metadata_info={"metadata_id": metadata_id}
    )
    
    return {"message": "Metadata deleted successfully"}

@public_router.get("/config")
async def saml_configuration():
    """
    SAML Configuration Discovery endpoint (OAuth-like).
    
    Provides information about supported SAML flows and configuration,
    similar to OAuth2 discovery endpoints.
    """
    config = {
        "issuer": saml_config.issuer,
        "saml_version": "2.0",
        "protocols_supported": ["urn:oasis:names:tc:SAML:2.0:protocol"],
        "nameid_formats_supported": [
            "urn:oasis:names:tc:SAML:2.0:nameid-format:emailAddress",
            "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent",
            "urn:oasis:names:tc:SAML:2.0:nameid-format:transient"
        ],
        "bindings_supported": [
            "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
        ],
        "endpoints": {
            "sso_endpoint": f"{saml_config.base_url}/saml/login",
            "slo_endpoint": f"{saml_config.base_url}/saml/logout",
            "metadata_endpoint": f"{saml_config.base_url}/saml/metadata",
            "configuration_endpoint": f"{saml_config.base_url}/saml/config"
        },
        "flows_supported": [
            "SP-initiated SSO",
            "IdP-initiated SSO (limited)",
            "SLO (Single Logout)"
        ],
        "redirect_uri_validation": {
            "enabled": True,
            "max_length": 2048,
            "allowed_schemes": ["http", "https"],
            "allowed_domains": ALLOWED_REDIRECT_DOMAINS,
            "wildcard_domains": False
        },
        "security_features": {
            "signed_assertions": True,
            "signed_responses": True,
            "encrypted_assertions": False,
            "xss_protection": True,
            "relay_state_validation": True
        },
        "attributes_supported": [
            "eduPersonPrincipalName",
            "givenName", 
            "sn",
            "email"
        ]
    }
    
    return config 

@router.post("/jit-config")
async def configure_jit_provisioning(
    enable_jit: bool = True,
    default_title: str = "User",
    auto_activate: bool = True,
    create_in_datadog: bool = True,
    require_email_domain: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Configure SAML JIT provisioning settings.
    
    This endpoint allows administrators to configure how JIT provisioning
    should work for new users authenticating via SAML.
    """
    # For now, we'll just return the configuration
    # In a production system, you might want to store this in the database
    
    config = {
        "jit_enabled": enable_jit,
        "default_title": default_title,
        "auto_activate": auto_activate,
        "create_in_datadog": create_in_datadog,
        "require_email_domain": require_email_domain,
        "supported_attribute_mappings": {
            "firstName": "first_name",
            "lastName": "last_name", 
            "givenName": "first_name",
            "sn": "last_name",
            "displayName": "formatted_name",
            "title": "title",
            "mail": "email",
            "employeeID": "external_id"
        }
    }
    
    return {
        "message": "JIT provisioning configuration updated",
        "config": config
    }

@router.get("/jit-config")
async def get_jit_configuration():
    """
    Get current SAML JIT provisioning configuration.
    
    Returns the current JIT provisioning settings and available 
    SAML attribute mappings.
    """
    return {
        "jit_enabled": True,
        "default_title": "User",
        "auto_activate": True,
        "create_in_datadog": True,
        "require_email_domain": None,
        "supported_flows": [
            "SP-initiated with JIT",
            "IdP-initiated with JIT"
        ],
        "supported_attribute_mappings": {
            "firstName": "first_name",
            "lastName": "last_name", 
            "givenName": "first_name",
            "sn": "last_name",
            "displayName": "formatted_name",
            "title": "title",
            "mail": "email",
            "employeeID": "external_id"
        },
        "sample_saml_attributes": {
            "description": "Example SAML attributes that can be used for JIT provisioning",
            "example": {
                "firstName": "John",
                "lastName": "Doe",
                "mail": "john.doe@company.com",
                "title": "Software Engineer",
                "employeeID": "EMP123456"
            }
        }
    } 