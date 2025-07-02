import os
import base64
from typing import Dict, Any, Optional
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.settings import OneLogin_Saml2_Settings
from onelogin.saml2.utils import OneLogin_Saml2_Utils
from onelogin.saml2.constants import OneLogin_Saml2_Constants
import logging

logger = logging.getLogger(__name__)

class SAMLConfig:
    """SAML Identity Provider configuration"""
    
    def __init__(self):
        # Load environment variables
        self.issuer = os.getenv("SAML_ISSUER", "https://my-idp.example.com/saml/metadata")
        self.cert = os.getenv("SAML_CERT", "").replace("\\n", "\n")
        self.key = os.getenv("SAML_KEY", "").replace("\\n", "\n")
        
        # Base settings for our IdP
        self.base_url = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")
        
    def get_saml_settings(self, sp_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate SAML settings for OneLogin library"""
        
        # Default SP settings if no metadata provided
        sp_settings = {
            "entityId": "https://api.datadoghq.com",
            "assertionConsumerService": {
                "url": "https://api.datadoghq.com/saml/assertion_consumer",
                "binding": OneLogin_Saml2_Constants.BINDING_HTTP_POST
            },
            "singleLogoutService": {
                "url": "https://api.datadoghq.com/saml/logout",
                "binding": OneLogin_Saml2_Constants.BINDING_HTTP_POST
            },
            "NameIDFormat": OneLogin_Saml2_Constants.NAMEID_EMAIL_ADDRESS,
            "x509cert": "",
            "privateKey": ""
        }
        
        # Override with actual SP metadata if provided
        if sp_metadata:
            sp_settings.update({
                "entityId": sp_metadata.get("entityId", sp_settings["entityId"]),
                "assertionConsumerService": sp_metadata.get("assertionConsumerService", sp_settings["assertionConsumerService"]),
                "singleLogoutService": sp_metadata.get("singleLogoutService", sp_settings["singleLogoutService"]),
            })
        
        settings = {
            "strict": True,
            "debug": False,
            "sp": sp_settings,
            "idp": {
                "entityId": self.issuer,
                "singleSignOnService": {
                    "url": f"{self.base_url}/saml/login",
                    "binding": OneLogin_Saml2_Constants.BINDING_HTTP_POST
                },
                "singleLogoutService": {
                    "url": f"{self.base_url}/saml/logout",
                    "binding": OneLogin_Saml2_Constants.BINDING_HTTP_POST
                },
                "x509cert": self.cert,
                "privateKey": self.key
            },
            "security": {
                "nameIdEncrypted": False,
                "authnRequestsSigned": False,
                "logoutRequestSigned": False,
                "logoutResponseSigned": False,
                "signMetadata": True,
                "wantAssertionsSigned": False,
                "wantNameId": True,
                "wantNameIdEncrypted": False,
                "wantAssertionsEncrypted": False,
                "signatureAlgorithm": OneLogin_Saml2_Constants.RSA_SHA256,
                "digestAlgorithm": OneLogin_Saml2_Constants.SHA256,
                "requestedAuthnContext": True,
                "requestedAuthnContextComparison": "exact",
                "wantXMLValidation": True,
                "relaxDestinationValidation": False,
                "destinationStrictlyMatches": False,
                "allowRepeatAttributeName": False,
                "rejectUnsolicitedResponsesWithInResponseTo": False,
                "signatureWrappingAttack": False,
                "lowercaseUrlencoding": False,
            }
        }
        
        return settings

    def generate_idp_metadata(self, sp_metadata: Dict[str, Any] = None) -> str:
        """Generate IdP metadata XML"""
        try:
            # Manually generate IdP metadata XML
            metadata_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
                     entityID="{self.issuer}">
    <md:IDPSSODescriptor WantAuthnRequestsSigned="false"
                         protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
        <md:KeyDescriptor use="signing">
            <ds:KeyInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
                <ds:X509Data>
                    <ds:X509Certificate>{self._format_cert_for_xml(self.cert)}</ds:X509Certificate>
                </ds:X509Data>
            </ds:KeyInfo>
        </md:KeyDescriptor>
        <md:NameIDFormat>urn:oasis:names:tc:SAML:2.0:nameid-format:emailAddress</md:NameIDFormat>
        <md:SingleSignOnService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
                                Location="{self.base_url}/saml/login"/>
        <md:SingleLogoutService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
                               Location="{self.base_url}/saml/logout"/>
    </md:IDPSSODescriptor>
</md:EntityDescriptor>"""
            
            return metadata_xml
            
        except Exception as e:
            logger.error(f"Error generating IdP metadata: {e}")
            raise

    def _format_cert_for_xml(self, cert: str) -> str:
        """Format certificate for XML by removing headers and newlines"""
        cert_lines = cert.replace('-----BEGIN CERTIFICATE-----', '').replace('-----END CERTIFICATE-----', '').strip()
        return ''.join(cert_lines.split())
    
    def parse_sp_metadata(self, metadata_xml: str) -> Dict[str, Any]:
        """Parse Service Provider metadata XML"""
        try:
            from lxml import etree
            
            root = etree.fromstring(metadata_xml.encode('utf-8'))
            
            # Extract namespace map
            nsmap = {
                'md': 'urn:oasis:names:tc:SAML:2.0:metadata',
                'ds': 'http://www.w3.org/2000/09/xmldsig#'
            }
            
            # Extract entity ID - handle both EntityDescriptor and EntitiesDescriptor
            entity_id = root.get('entityID')
            
            # If root is EntitiesDescriptor, find the first EntityDescriptor
            if entity_id is None and root.tag.endswith('EntitiesDescriptor'):
                entity_descriptor = root.find('.//md:EntityDescriptor', nsmap)
                if entity_descriptor is not None:
                    entity_id = entity_descriptor.get('entityID')
                    # Use the EntityDescriptor as root for further parsing
                    root = entity_descriptor
            
            # Find SPSSODescriptor
            sp_sso_descriptor = root.find('.//md:SPSSODescriptor', nsmap)
            if sp_sso_descriptor is None:
                raise ValueError("No SPSSODescriptor found in metadata")
            
            # Extract AssertionConsumerService endpoints
            acs_elements = sp_sso_descriptor.findall('.//md:AssertionConsumerService', nsmap)
            acs_endpoints = []
            
            for acs in acs_elements:
                binding = acs.get('Binding')
                location = acs.get('Location')
                index = acs.get('index', '0')
                is_default = acs.get('isDefault', 'false').lower() == 'true'
                
                acs_endpoints.append({
                    'binding': binding,
                    'location': location,
                    'index': int(index),
                    'isDefault': is_default
                })
            
            # Extract SingleLogoutService endpoints
            sls_elements = sp_sso_descriptor.findall('.//md:SingleLogoutService', nsmap)
            sls_endpoints = []
            
            for sls in sls_elements:
                binding = sls.get('Binding')
                location = sls.get('Location')
                
                sls_endpoints.append({
                    'binding': binding,
                    'location': location
                })
            
            # Extract NameID formats
            nameid_formats = []
            nameid_elements = sp_sso_descriptor.findall('.//md:NameIDFormat', nsmap)
            for nameid in nameid_elements:
                nameid_formats.append(nameid.text)
            
            return {
                'entityId': entity_id,
                'assertionConsumerServices': acs_endpoints,
                'singleLogoutServices': sls_endpoints,
                'nameIdFormats': nameid_formats,
                'assertionConsumerService': {
                    'url': acs_endpoints[0]['location'] if acs_endpoints else '',
                    'binding': acs_endpoints[0]['binding'] if acs_endpoints else OneLogin_Saml2_Constants.BINDING_HTTP_POST
                },
                'singleLogoutService': {
                    'url': sls_endpoints[0]['location'] if sls_endpoints else '',
                    'binding': sls_endpoints[0]['binding'] if sls_endpoints else OneLogin_Saml2_Constants.BINDING_HTTP_POST
                }
            }
            
        except Exception as e:
            logger.error(f"Error parsing SP metadata: {e}")
            raise
    
    def create_saml_auth(self, request_data: Dict[str, Any], sp_metadata: Dict[str, Any] = None) -> OneLogin_Saml2_Auth:
        """Create SAML Auth object for handling requests"""
        try:
            settings = self.get_saml_settings(sp_metadata)
            return OneLogin_Saml2_Auth(request_data, settings)
        except Exception as e:
            logger.error(f"Error creating SAML auth: {e}")
            raise
    
    def generate_saml_response(self, user_email: str, user_data: Dict[str, Any], 
                              saml_request: str, relay_state: str = None,
                              sp_metadata: Dict[str, Any] = None) -> str:
        """Generate SAML Response assertion for successful authentication"""
        try:
            import uuid
            from datetime import datetime, timedelta
            from onelogin.saml2.response import OneLogin_Saml2_Response
            from onelogin.saml2.utils import OneLogin_Saml2_Utils
            
            # Create request data structure for OneLogin
            request_data = {
                'https': 'off',  # Set to 'on' for HTTPS
                'http_host': 'localhost:8000',
                'server_port': '8000',
                'script_name': '/saml/validate',
                'get_data': {},
                'post_data': {
                    'SAMLRequest': saml_request,
                    'RelayState': relay_state or ''
                }
            }
            
            auth = self.create_saml_auth(request_data, sp_metadata)
            
            # Parse the SAML request to extract necessary information
            decoded_request = base64.b64decode(saml_request)
            
            # Parse the SAML AuthnRequest to extract the ID and AssertionConsumerServiceURL
            from lxml import etree
            root = etree.fromstring(decoded_request)
            
            # Extract the ID from the AuthnRequest
            request_id = root.get('ID')
            if not request_id:
                raise Exception("Could not extract ID from SAML AuthnRequest")
            
            # Extract AssertionConsumerServiceURL from the AuthnRequest if present
            request_acs_url = root.get('AssertionConsumerServiceURL')
            
            logger.info(f"AuthnRequest ID: {request_id}")
            logger.info(f"AuthnRequest ACS URL: {request_acs_url}")
            logger.info(f"Metadata ACS URL: {sp_metadata.get('assertionConsumerService', {}).get('url', '')}")
            
            # Generate timestamps
            now = datetime.utcnow()
            not_on_or_after = now + timedelta(minutes=5)
            
            # Generate unique IDs
            response_id = f"_response_{uuid.uuid4().hex}"
            assertion_id = f"_assertion_{uuid.uuid4().hex}"
            
            # Get SP entity ID from metadata
            sp_entity_id = sp_metadata.get('entityId', 'https://app.datadoghq.com')
            
            # Use AssertionConsumerServiceURL from the AuthnRequest if present, otherwise use metadata
            acs_url = request_acs_url or sp_metadata.get('assertionConsumerService', {}).get('url', '')
            
            logger.info(f"Final ACS URL being used: {acs_url}")
            
            # Prepare user attributes for SAML assertion
            attributes_xml = ""
            if user_data.get('first_name'):
                attributes_xml += f'<saml:Attribute Name="givenName"><saml:AttributeValue>{user_data["first_name"]}</saml:AttributeValue></saml:Attribute>'
            if user_data.get('last_name'):
                attributes_xml += f'<saml:Attribute Name="sn"><saml:AttributeValue>{user_data["last_name"]}</saml:AttributeValue></saml:Attribute>'
            
            attributes_xml += f'<saml:Attribute Name="eduPersonPrincipalName"><saml:AttributeValue>{user_email}</saml:AttributeValue></saml:Attribute>'
            
            # First create the assertion XML separately so we can sign it
            assertion_xml = f"""<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                    ID="{assertion_id}"
                    Version="2.0"
                    IssueInstant="{now.strftime('%Y-%m-%dT%H:%M:%S')}Z">
        <saml:Issuer>{self.issuer}</saml:Issuer>
        <saml:Subject>
            <saml:NameID Format="urn:oasis:names:tc:SAML:2.0:nameid-format:emailAddress">{user_email}</saml:NameID>
            <saml:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">
                <saml:SubjectConfirmationData NotOnOrAfter="{not_on_or_after.strftime('%Y-%m-%dT%H:%M:%S')}Z"
                                              Recipient="{acs_url}"
                                              InResponseTo="{request_id}"/>
            </saml:SubjectConfirmation>
        </saml:Subject>
        <saml:Conditions NotBefore="{now.strftime('%Y-%m-%dT%H:%M:%S')}Z"
                         NotOnOrAfter="{not_on_or_after.strftime('%Y-%m-%dT%H:%M:%S')}Z">
            <saml:AudienceRestriction>
                <saml:Audience>{sp_entity_id}</saml:Audience>
            </saml:AudienceRestriction>
        </saml:Conditions>
        <saml:AuthnStatement AuthnInstant="{now.strftime('%Y-%m-%dT%H:%M:%S')}Z">
            <saml:AuthnContext>
                <saml:AuthnContextClassRef>urn:oasis:names:tc:SAML:2.0:ac:classes:unspecified</saml:AuthnContextClassRef>
            </saml:AuthnContext>
        </saml:AuthnStatement>
        <saml:AttributeStatement>
            {attributes_xml}
        </saml:AttributeStatement>
    </saml:Assertion>"""
            
            # Sign the assertion
            signed_assertion = OneLogin_Saml2_Utils.add_sign(
                assertion_xml,
                self.key,
                self.cert,
                debug=False,
                sign_algorithm=OneLogin_Saml2_Constants.RSA_SHA256
            )
            
            # Handle both string and bytes return types for assertion
            if isinstance(signed_assertion, bytes):
                signed_assertion_str = signed_assertion.decode()
            else:
                signed_assertion_str = signed_assertion
            
            # Create SAML Response XML with the signed assertion
            saml_response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                ID="{response_id}"
                InResponseTo="{request_id}"
                Version="2.0"
                IssueInstant="{now.strftime('%Y-%m-%dT%H:%M:%S')}Z"
                Destination="{acs_url}">
    <saml:Issuer>{self.issuer}</saml:Issuer>
    <samlp:Status>
        <samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/>
    </samlp:Status>
    {signed_assertion_str}
</samlp:Response>"""
            
            # Sign the SAML response using OneLogin utils
            signed_response = OneLogin_Saml2_Utils.add_sign(
                saml_response_xml,
                self.key,
                self.cert,
                debug=False,
                sign_algorithm=OneLogin_Saml2_Constants.RSA_SHA256
            )
            
            # Handle both string and bytes return types
            if isinstance(signed_response, bytes):
                return base64.b64encode(signed_response).decode()
            else:
                return base64.b64encode(signed_response.encode()).decode()
            
        except Exception as e:
            logger.error(f"Error generating SAML response: {e}")
            raise

# Global instance
saml_config = SAMLConfig() 