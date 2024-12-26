import logging
from pathlib import Path
from datetime import datetime

class BrowserLogger:
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup loggers
        self.setup_logger('browser', 'browser.log')
        self.setup_logger('network', 'network.log')
        self.setup_logger('error', 'error.log')
        
    def setup_logger(self, name: str, filename: str):
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        
        handler = logging.FileHandler(self.log_dir / filename)
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        
        logger.addHandler(handler)
        return logger 