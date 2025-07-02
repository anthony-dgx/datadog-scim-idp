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
    """Configure structured logging for the application"""
    
    # Configure structlog
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
    
    # Configure standard logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            DatadogLogHandler()
        ]
    )

class ActionLogger:
    """Specialized logger for tracking user actions and SCIM operations"""
    
    def __init__(self):
        self.logger = structlog.get_logger("scim_actions")
    
    def log_user_action(self, action: str, user_data: Dict[str, Any], user_id: Optional[int] = None, success: bool = True, error: str = None):
        """Log user-related actions"""
        log_data = {
            "action_type": "user_action",
            "action": action,
            "user_id": user_id,
            "success": success,
            "user_data": {
                "username": user_data.get("username"),
                "email": user_data.get("email"),
                "active": user_data.get("active"),
                "sync_status": user_data.get("sync_status"),
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if error:
            log_data["error"] = error
            
        if success:
            self.logger.info(f"User {action} successful", **log_data)
            statsd.increment("scim.user.action.success", tags=[f"action:{action}"])
        else:
            self.logger.error(f"User {action} failed", **log_data)
            statsd.increment("scim.user.action.error", tags=[f"action:{action}"])
    
    def log_group_action(self, action: str, group_data: Dict[str, Any], group_id: Optional[int] = None, success: bool = True, error: str = None):
        """Log group-related actions"""
        log_data = {
            "action_type": "group_action",
            "action": action,
            "group_id": group_id,
            "success": success,
            "group_data": {
                "display_name": group_data.get("display_name"),
                "description": group_data.get("description"),
                "member_count": len(group_data.get("members", [])),
                "sync_status": group_data.get("sync_status"),
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if error:
            log_data["error"] = error
            
        if success:
            self.logger.info(f"Group {action} successful", **log_data)
            statsd.increment("scim.group.action.success", tags=[f"action:{action}"])
        else:
            self.logger.error(f"Group {action} failed", **log_data)
            statsd.increment("scim.group.action.error", tags=[f"action:{action}"])
    
    def log_scim_request(self, method: str, endpoint: str, request_payload: Dict[str, Any] = None, 
                        response_payload: Dict[str, Any] = None, status_code: int = None, 
                        duration_ms: float = None, success: bool = True, error: str = None):
        """Log SCIM API requests with full payloads"""
        log_data = {
            "action_type": "scim_api_call",
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
            self.logger.info(f"SCIM API call: {method} {endpoint}", **log_data)
            statsd.increment("scim.api.request.success", tags=[f"method:{method}", f"endpoint:{endpoint}"])
            if duration_ms:
                statsd.histogram("scim.api.request.duration", duration_ms, tags=[f"method:{method}", f"endpoint:{endpoint}"])
        else:
            self.logger.error(f"SCIM API call failed: {method} {endpoint}", **log_data)
            statsd.increment("scim.api.request.error", tags=[f"method:{method}", f"endpoint:{endpoint}"])
    
    def log_sync_operation(self, operation_type: str, entity_type: str, entity_id: int, 
                          datadog_id: str = None, success: bool = True, error: str = None, 
                          sync_data: Dict[str, Any] = None):
        """Log sync operations between local DB and Datadog"""
        log_data = {
            "action_type": "sync_operation",
            "operation_type": operation_type,  # create, update, delete, deactivate
            "entity_type": entity_type,  # user, group
            "entity_id": entity_id,
            "datadog_id": datadog_id,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if sync_data:
            log_data["sync_data"] = self._sanitize_payload(sync_data)
        
        if error:
            log_data["error"] = error
        
        if success:
            self.logger.info(f"Sync {operation_type} {entity_type} successful", **log_data)
            statsd.increment("scim.sync.success", tags=[f"operation:{operation_type}", f"entity:{entity_type}"])
        else:
            self.logger.error(f"Sync {operation_type} {entity_type} failed", **log_data)
            statsd.increment("scim.sync.error", tags=[f"operation:{operation_type}", f"entity:{entity_type}"])
    
    def _sanitize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from payloads before logging"""
        if not isinstance(payload, dict):
            return payload
        
        sanitized = payload.copy()
        
        # Remove sensitive fields
        sensitive_fields = ["password", "token", "secret", "key", "authorization"]
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

# Global logger instance
action_logger = ActionLogger() 