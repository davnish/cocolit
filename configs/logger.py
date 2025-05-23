import logging
import logging.handlers
import streamlit as st
import os

def get_smtp_logger(name: str, level: int = logging.ERROR) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        # Shared Warning SMTP logger
        smtp_handler = logging.handlers.SMTPHandler(
            mailhost=("smtp.gmail.com", 587),
            fromaddr=st.secrets.smpt["fromaddr"],
            toaddrs=st.secrets.smpt["toaddrs"],
            subject="Application Error",
            credentials=st.secrets.smpt["credentials"],
            secure=(),
        )
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        smtp_handler.setLevel(level)
        smtp_handler.setFormatter(formatter)
        logger.addHandler(smtp_handler)

        # Optional: Also log to console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        
    return logger

def setup_logger(name: str, logfile: str, level: int = logging.DEBUG) -> logging.Logger:
    """
    Sets up and returns a logger with both module-specific and error logging.

    Args:
        name (str): Logger name (typically module name)
        logfile (str): File name for module-specific logs
        level (int): Logging level (default: DEBUG)

    Returns:
        logging.Logger: Configured logger instance
    """
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        # Module-specific log file
        file_handler = logging.FileHandler(os.path.join(log_dir, logfile))
        file_handler.setLevel(level)

        # Shared error log file
        error_handler = logging.FileHandler(os.path.join(log_dir, "errors.log"))
        error_handler.setLevel(logging.ERROR)

        # A Shared debug file
        debug_handler = logging.FileHandler(os.path.join(log_dir, "debug.log"))
        debug_handler.setLevel(logging.DEBUG)

        # Common formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        file_handler.setFormatter(formatter)
        error_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(error_handler)
        logger.addHandler(debug_handler)

        # Optional: Also log to console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
