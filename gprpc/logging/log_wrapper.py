__all__ = ['configure_root_logger', 
           'class_wrapper', 
           'root_logger',
           'get_logger']

import logging

root_logger = None

def configure_root_logger(root):
    global root_logger
    assert root_logger is None
    root_logger = logging.getLogger(root)
    assert root_logger is not None
    return root_logger

def class_wrapper(cls):
    if root_logger is None:
        cls.logger = logging.getLogger(cls.__name__)
    else:
        cls.logger = root_logger.getChild(cls.__name__)
    return cls

def get_logger(name):
    if root_logger is None:
        logger = logging.getLogger(name)
    else:
        logger = root_logger.getChild(name)
    return logger

