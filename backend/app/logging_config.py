import logging
import os
import json
import structlog
from datadog import initialize, statsd
from ddtrace import tracer
from typing import Dict, Any, Optional
import time
from datetime import datetime

# Initialize Datadog for metrics (agent will collect logs from stdout)
api_key = os.getenv("DD_API_KEY", os.getenv("DD_BEARER_TOKEN"))
if api_key:
    initialize(
        api_key=api_key,
        statsd_host=os.getenv("DD_DOGSTATSD_HOST", os.getenv("DD_AGENT_HOST", "localhost")),
        statsd_port=int(os.getenv("DD_STATSD_PORT", 8125))
    )

class DatadogLogHandler(logging.Handler):
    """Custom log handler that outputs structured JSON logs for Datadog agent collection"""
    
    def __init__(self, service_name: str = "scim-demo", environment: str = "development"):
        super().__init__()
        self.service_name = service_name
        self.environment = environment
    
    def emit(self, record):
        """Output structured log record for Datadog agent to collect"""
        try:
            # Build the log entry in Datadog format
            log_entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": record.levelname.upper(),
                "message": record.getMessage(),
                "service": self.service_name,
                "ddsource": "python",
                "ddtags": f"env:{self.environment},service:{self.service_name},logger:{record.name}",
                "logger": {
                    "name": record.name,
                    "thread": record.thread,
                    "process": record.process,
                },
                "hostname": os.getenv("HOSTNAME", "scim-demo")
            }
            
            # Add extra fields if present
            if hasattr(record, 'extra_fields'):
                log_entry.update(record.extra_fields)
            
            # Add trace information if available
            span = tracer.current_span()
            if span:
                log_entry.update({
                    "dd.trace_id": str(span.trace_id),
                    "dd.span_id": str(span.span_id),
                })
            
            # Output as JSON to stdout for Datadog agent to collect
            print(json.dumps(log_entry), flush=True)
            
        except Exception as e:
            # Don't let logging errors break the application
            print(f"Logging error: {e}", flush=True)

def setup_logging():
    """Configure minimal logging for the application"""
    
    # Configure structlog for our specific loggers only
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure logging with minimal output - only errors for general application
    logging.basicConfig(
        level=logging.ERROR,  # Only log errors for general application
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            DatadogLogHandler()
        ]
    )
    
    # Set specific loggers to appropriate levels
    logging.getLogger("scim_operations").setLevel(logging.INFO)  # SCIM calls
    logging.getLogger("saml_operations").setLevel(logging.INFO)  # SAML operations
    logging.getLogger("uvicorn.access").setLevel(logging.ERROR)  # Suppress HTTP access logs
    logging.getLogger("uvicorn.error").setLevel(logging.ERROR)   # Only errors from uvicorn

class FocusedLogger:
    """Focused logger for SCIM and SAML operations only"""
    
    def __init__(self):
        self.scim_logger = structlog.get_logger("scim_operations")
        self.saml_logger = structlog.get_logger("saml_operations")
    
    def log_scim_request(self, method: str, endpoint: str, request_payload: Dict[str, Any] = None, 
                        response_payload: Dict[str, Any] = None, status_code: int = None, 
                        duration_ms: float = None, success: bool = True, error: str = None):
        """Log SCIM API requests to Datadog with full payloads"""
        log_data = {
            "operation_type": "scim_api_call",
            "method": method,
            "endpoint": endpoint,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Include request payload (sanitized)
        if request_payload:
            log_data["request_payload"] = self._sanitize_payload(request_payload)
        
        # Include response payload (sanitized)
        if response_payload:
            log_data["response_payload"] = self._sanitize_payload(response_payload)
        
        if error:
            log_data["error"] = error
        
        if success:
            self.scim_logger.info(f"SCIM API call: {method} {endpoint}", **log_data)
            statsd.increment("scim.api.request.success", tags=[f"method:{method}", f"endpoint:{endpoint}"])
            if duration_ms:
                statsd.histogram("scim.api.request.duration", duration_ms, tags=[f"method:{method}", f"endpoint:{endpoint}"])
        else:
            self.scim_logger.error(f"SCIM API call failed: {method} {endpoint}", **log_data)
            statsd.increment("scim.api.request.error", tags=[f"method:{method}", f"endpoint:{endpoint}"])
    
    def log_saml_login(self, operation: str, user_email: str = None, success: bool = True, 
                      error: str = None, saml_data: Dict[str, Any] = None):
        """Log SAML authentication operations"""
        log_data = {
            "operation_type": "saml_authentication",
            "operation": operation,  # login_initiated, auth_success, auth_failed, response_generated
            "user_email": user_email,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if saml_data:
            log_data["saml_data"] = self._sanitize_payload(saml_data)
        
        if error:
            log_data["error"] = error
        
        if success:
            self.saml_logger.info(f"SAML {operation}", **log_data)
            statsd.increment("saml.operation.success", tags=[f"operation:{operation}"])
        else:
            self.saml_logger.error(f"SAML {operation} failed", **log_data)
            statsd.increment("saml.operation.error", tags=[f"operation:{operation}"])
    
    def log_saml_metadata(self, operation: str, entity_id: str = None, success: bool = True, 
                         error: str = None, metadata_info: Dict[str, Any] = None):
        """Log SAML metadata operations"""
        log_data = {
            "operation_type": "saml_metadata",
            "operation": operation,  # upload, generate, parse
            "entity_id": entity_id,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if metadata_info:
            log_data["metadata_info"] = self._sanitize_payload(metadata_info)
        
        if error:
            log_data["error"] = error
        
        if success:
            self.saml_logger.info(f"SAML metadata {operation}", **log_data)
            statsd.increment("saml.metadata.success", tags=[f"operation:{operation}"])
        else:
            self.saml_logger.error(f"SAML metadata {operation} failed", **log_data)
            statsd.increment("saml.metadata.error", tags=[f"operation:{operation}"])
    
    def log_user_action(self, operation: str, resource_type: str = None, resource_id: Any = None, 
                       success: bool = True, error: str = None, details: Dict[str, Any] = None):
        """Log user management operations (roles, assignments, etc.)"""
        log_data = {
            "operation_type": "user_management",
            "operation": operation,  # role_created, role_assigned, roles_synced, etc.
            "resource_type": resource_type,  # role, user, assignment
            "resource_id": resource_id,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if details:
            log_data["details"] = self._sanitize_payload(details)
        
        if error:
            log_data["error"] = error
        
        logger = self.scim_logger  # Use SCIM logger for user management operations
        
        if success:
            logger.info(f"User action: {operation}", **log_data)
            statsd.increment("user.action.success", tags=[f"operation:{operation}", f"resource_type:{resource_type}"])
        else:
            logger.error(f"User action failed: {operation}", **log_data)
            statsd.increment("user.action.error", tags=[f"operation:{operation}", f"resource_type:{resource_type}"])
    
    def _sanitize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from payloads before logging"""
        if not isinstance(payload, dict):
            return payload
        
        sanitized = payload.copy()
        
        # Remove sensitive fields
        sensitive_fields = ["password", "token", "secret", "key", "authorization", "bearer", "privateKey"]
        for field in sensitive_fields:
            if field in sanitized:
                sanitized[field] = "***REDACTED***"
        
        # Recursively sanitize nested dictionaries
        for key, value in sanitized.items():
            if isinstance(value, dict):
                sanitized[key] = self._sanitize_payload(value)
            elif isinstance(value, list):
                sanitized[key] = [self._sanitize_payload(item) if isinstance(item, dict) else item for item in value]
        
        return sanitized

class TimingContext:
    """Context manager for timing operations"""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.duration_ms = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            self.duration_ms = (time.time() - self.start_time) * 1000

# Global logger instance - focused on SCIM and SAML only
action_logger = FocusedLogger() 