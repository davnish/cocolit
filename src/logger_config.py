import logging
import os

def setup_logger(name: str, logfile: str, level=logging.DEBUG):
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

        # Common formatter
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        error_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(error_handler)

        # Optional: Also log to console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
