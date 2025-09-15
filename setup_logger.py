import logging

def setup_logger(name: str, get_handler: bool = True, file_handler: bool = True):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if get_handler:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        logger.addHandler(logging.StreamHandler())
        logger.handlers[0].setFormatter(formatter)

    if file_handler:
        file_handler = logging.FileHandler(f"log/{name}.log", mode="w")
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
    return logger
