from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import base64
import json
import logging

from ..database import get_db
from ..models import User, SAMLMetadata
from ..schemas import (
    SAMLMetadataResponse, SAMLLoginRequest, SAMLValidateRequest, SAMLResponseData
)
from ..saml_client import saml_config
from ..logging_config import action_logger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/saml", tags=["saml"])
public_router = APIRouter(prefix="/saml", tags=["saml-public"])

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
    """SP-initiated SAML login endpoint"""
    
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
        
        # Decode and validate SAMLRequest
        decoded_request = base64.b64decode(SAMLRequest).decode('utf-8')
        
        # Log the login attempt
        action_logger.log_saml_login(
            operation="login_initiated",
            success=True,
            saml_data={
                "relay_state": RelayState,
                "request_method": request.method,
                "has_saml_request": bool(SAMLRequest)
            }
        )
        
        # Return login form
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
                </style>
            </head>
            <body>
                <div class="login-container">
                    <h2>SAML Login</h2>
                    <form method="post" action="/saml/validate">
                        <div class="form-group">
                            <label for="email">Email Address:</label>
                            <input type="email" id="email" name="email" required>
                        </div>
                        <input type="hidden" name="SAMLRequest" value="{SAMLRequest}">
                        <input type="hidden" name="RelayState" value="{RelayState or ''}">
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

@public_router.post("/validate", response_class=HTMLResponse)
async def saml_validate(
    email: str = Form(...),
    SAMLRequest: str = Form(...),
    RelayState: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Validate user email and generate SAML response"""
    
    try:
        # Check if user exists and is active
        user = db.query(User).filter(
            User.email == email,
            User.active == True
        ).first()
        
        if not user:
            # Log authentication failure
            action_logger.log_saml_login(
                operation="auth_failed",
                user_email=email,
                success=False,
                error="User not found or inactive"
            )
            
            raise HTTPException(status_code=401, detail="User not found or inactive")
        
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
        
        # Prepare user data for SAML assertion
        user_data = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "email": user.email
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
                "user_attributes": {
                    "has_first_name": bool(user.first_name),
                    "has_last_name": bool(user.last_name),
                    "username": user.username
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