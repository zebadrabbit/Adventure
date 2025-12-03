"""
Structured logging configuration for Adventure MUD.

This module configures structlog for structured, context-aware logging
throughout the application. It integrates with Flask's logger and provides
consistent formatting for development and production environments.

Usage:
    from app.logging_config import get_logger

    logger = get_logger(__name__)
    logger.info("player_login", username="alice", character_id=123)
"""

import logging
import sys
from typing import Optional

import structlog
from flask import Flask, has_request_context, request


def configure_structlog(app: Optional[Flask] = None, log_level: str = "INFO"):
    """
    Configure structlog with Flask integration.

    Args:
        app: Flask application instance (optional)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # Shared processors for all configurations
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    # Add Flask request context if available
    if app:

        def add_flask_context(logger, method_name, event_dict):
            """Add Flask request context to log entries."""
            if has_request_context():
                event_dict["request_id"] = getattr(request, "id", None)
                event_dict["endpoint"] = request.endpoint
                event_dict["method"] = request.method
                event_dict["path"] = request.path
                event_dict["remote_addr"] = request.remote_addr
            return event_dict

        shared_processors.append(add_flask_context)

    # Development: Use ConsoleRenderer for human-readable output
    # Production: Use JSONRenderer for machine-parseable logs
    is_dev = app and app.config.get("ENV") == "development" if app else True

    if is_dev:
        processors = shared_processors + [structlog.dev.ConsoleRenderer()]
    else:
        processors = shared_processors + [structlog.processors.format_exc_info, structlog.processors.JSONRenderer()]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """
    Get a configured structlog logger.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("user_action", user_id=123, action="login")
    """
    return structlog.get_logger(name)


def setup_flask_logging(app: Flask):
    """
    Setup logging for Flask application.

    This should be called during application initialization.

    Args:
        app: Flask application instance
    """
    log_level = app.config.get("LOG_LEVEL", "INFO")
    configure_structlog(app, log_level)

    # Integrate Flask's logger with structlog
    app.logger.handlers = []
    app.logger.propagate = True

    # Add request ID to each request
    @app.before_request
    def add_request_id():
        import uuid

        request.id = str(uuid.uuid4())

    # Log each request
    @app.after_request
    def log_request(response):
        logger = get_logger("flask.request")
        logger.info(
            "request_complete",
            status_code=response.status_code,
            content_length=response.content_length,
        )
        return response


# Example usage patterns
if __name__ == "__main__":
    # Initialize logging
    configure_structlog(log_level="DEBUG")

    # Get a logger
    logger = get_logger(__name__)

    # Structured logging examples
    logger.debug("debug_message", detail="low-level information")
    logger.info("player_login", username="alice", character_id=123)
    logger.warning("inventory_full", user_id=456, item_count=100)
    logger.error("database_error", table="users", operation="insert", error="unique constraint violation")

    # Exception logging with context
    try:
        raise ValueError("Example error")
    except Exception:
        logger.exception("operation_failed", operation="example", user_id=789)
