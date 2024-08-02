import logging


def _get_ecs_logger(name: str = "main") -> logging.Logger:
    """
    Returns a logger with the specified name.
    :return: logging.Logger
    :param name: str
    """
    result = logging.getLogger(name)
    result.setLevel(logging.DEBUG)
    result.propagate = False

    # if result.hasHandlers():
    #     result.handlers.clear()

    return result


logger = _get_ecs_logger("psa")


def get_logger(name: str = "main") -> logging.Logger:
    return logger.getChild(name)
