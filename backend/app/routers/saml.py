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
from ..logging_config import ActionLogger

logger = logging.getLogger(__name__)
action_logger = ActionLogger()

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
        action_logger.log_sync_operation(
            operation_type="create" if not existing_metadata else "update",
            entity_type="saml_metadata",
            entity_id=db_metadata.id,
            success=True,
            sync_data={
                "entity_id": parsed_metadata['entityId'],
                "acs_url": parsed_metadata['assertionConsumerService']['url'],
                "parsed_services": len(parsed_metadata.get('assertionConsumerServices', [])),
                "name_id_formats": parsed_metadata.get('nameIdFormats', [])
            }
        )
        
        return db_metadata.to_dict()
        
    except Exception as e:
        logger.error(f"Failed to parse SP metadata: {e}")
        
        action_logger.log_sync_operation(
            operation_type="upload_metadata",
            entity_type="saml_metadata",
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
        
        # Log metadata access
        action_logger.log_sync_operation(
            operation_type="get_metadata",
            entity_type="saml_idp",
            entity_id="idp",
            success=True,
            sync_data={
                "sp_configured": sp_metadata is not None,
                "metadata_size": len(metadata_xml)
            }
        )
        
        return Response(
            content=metadata_xml,
            media_type="application/xml",
            headers={"Content-Disposition": "attachment; filename=idp-metadata.xml"}
        )
        
    except Exception as e:
        logger.error(f"Failed to generate IdP metadata: {e}")
        
        action_logger.log_sync_operation(
            operation_type="get_metadata",
            entity_type="saml_idp",
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
        action_logger.log_sync_operation(
            operation_type="saml_login_initiated",
            entity_type="saml_auth",
            entity_id="login",
            success=True,
            sync_data={
                "has_relay_state": RelayState is not None,
                "request_size": len(decoded_request)
            }
        )
        
        # Render email confirmation form
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>SAML Login - Email Confirmation</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 500px; margin: 50px auto; padding: 20px; }}
                form {{ background: #f5f5f5; padding: 30px; border-radius: 8px; }}
                input[type="email"] {{ width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; }}
                input[type="submit"] {{ background: #007cba; color: white; padding: 12px 30px; border: none; border-radius: 4px; cursor: pointer; }}
                input[type="submit"]:hover {{ background: #005a8b; }}
                .info {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <h2>Datadog SAML Authentication</h2>
            <div class="info">Please enter your email address to authenticate with Datadog</div>
            <form method="post" action="/saml/validate">
                <input type="hidden" name="SAMLRequest" value="{SAMLRequest}">
                <input type="hidden" name="RelayState" value="{RelayState or ''}">
                <label for="email">Email Address:</label>
                <input type="email" id="email" name="email" required placeholder="your.email@company.com">
                <input type="submit" value="Authenticate">
            </form>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        logger.error(f"SAML login error: {e}")
        
        action_logger.log_sync_operation(
            operation_type="saml_login_initiated",
            entity_type="saml_auth",
            entity_id="login",
            success=False,
            error=str(e)
        )
        
        raise HTTPException(status_code=400, detail=f"Invalid SAML request: {str(e)}")

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
            action_logger.log_sync_operation(
                operation_type="saml_auth_failed",
                entity_type="saml_auth",
                entity_id=email,
                success=False,
                error="User not found or inactive",
                sync_data={"email": email}
            )
            
            raise HTTPException(status_code=401, detail="User not found or inactive")
        
        # Get SP metadata for response generation
        sp_metadata_record = db.query(SAMLMetadata).filter(SAMLMetadata.active == True).first()
        
        if not sp_metadata_record:
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
        action_logger.log_sync_operation(
            operation_type="saml_auth_success",
            entity_type="saml_auth",
            entity_id=user.email,
            success=True,
            sync_data={
                "user_id": user.id,
                "user_email": user.email,
                "sp_entity_id": sp_metadata_record.entity_id,
                "has_relay_state": RelayState is not None
            }
        )
        
        # Generate auto-submit form to send SAML response to SP
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>SAML Authentication - Redirecting</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 100px; }}
                .spinner {{ border: 4px solid #f3f3f3; border-top: 4px solid #007cba; border-radius: 50%; 
                           width: 50px; height: 50px; animation: spin 1s linear infinite; margin: 20px auto; }}
                @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
            </style>
        </head>
        <body>
            <h2>Authentication Successful</h2>
            <p>Redirecting to Datadog...</p>
            <div class="spinner"></div>
            
            <form id="samlForm" method="post" action="{sp_metadata_record.acs_url}">
                <input type="hidden" name="SAMLResponse" value="{saml_response}">
                <input type="hidden" name="RelayState" value="{RelayState or ''}">
            </form>
            
            <script>
                // Auto-submit the form after a brief delay
                setTimeout(function() {{
                    document.getElementById('samlForm').submit();
                }}, 2000);
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SAML validation error: {e}")
        
        action_logger.log_sync_operation(
            operation_type="saml_auth_failed",
            entity_type="saml_auth",
            entity_id=email,
            success=False,
            error=str(e),
            sync_data={"email": email}
        )
        
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")

@public_router.get("/logout", response_class=HTMLResponse)
async def saml_logout(
    SAMLRequest: Optional[str] = None,
    RelayState: Optional[str] = None
):
    """SAML logout endpoint (optional)"""
    
    try:
        # Log logout attempt
        action_logger.log_sync_operation(
            operation_type="saml_logout",
            entity_type="saml_auth",
            entity_id="logout",
            success=True,
            sync_data={
                "has_saml_request": SAMLRequest is not None,
                "has_relay_state": RelayState is not None
            }
        )
        
        # Simple logout confirmation page
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>SAML Logout</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; margin-top: 100px; }
            </style>
        </head>
        <body>
            <h2>Logout Successful</h2>
            <p>You have been successfully logged out from the SAML Identity Provider.</p>
            <p><a href="/">Return to Home</a></p>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        logger.error(f"SAML logout error: {e}")
        raise HTTPException(status_code=500, detail=f"Logout failed: {str(e)}")

@router.get("/metadata-list", response_model=list[SAMLMetadataResponse])
async def list_sp_metadata(db: Session = Depends(get_db)):
    """List all configured SP metadata records"""
    
    metadata_records = db.query(SAMLMetadata).all()
    return [record.to_dict() for record in metadata_records]

@router.delete("/metadata/{metadata_id}")
async def delete_sp_metadata(metadata_id: int, db: Session = Depends(get_db)):
    """Delete SP metadata record"""
    
    metadata_record = db.query(SAMLMetadata).filter(SAMLMetadata.id == metadata_id).first()
    
    if not metadata_record:
        raise HTTPException(status_code=404, detail="Metadata record not found")
    
    db.delete(metadata_record)
    db.commit()
    
    action_logger.log_sync_operation(
        operation_type="delete",
        entity_type="saml_metadata",
        entity_id=metadata_id,
        success=True,
        sync_data={
            "entity_id": metadata_record.entity_id
        }
    )
    
    return {"message": "Metadata deleted successfully"} 