from pathlib import Path

from . import uploader


class Main:
    cwd = None
    debug = None
    destination = None
    logger = None
    login = None
    password = None
    source_path = None
    threads = None
    __source = None

    def __init__(
            self, cwd, source, destination, login=None, password=None, threads=1, logger=None,
            verbose=False):
        self.cwd = cwd
        self.debug = verbose  # @TODO Remove
        self.destination = destination
        self.logger = logger
        self.login = login
        self.password = password
        self.threads = threads
        self.__source = source

        self.__validate_source_path()
        self.__validate_login()
        self.__validate_password()

    def upload(self):
        u = uploader.Uploader(self.login, self.password, logger=self.logger, debug=self.debug)
        u.upload(self.source_path, self.destination, self.threads)

    def __get_login(self):
        while not self.login:
            self.login = input('Login: ')

    def __get_password(self):
        while not self.password:
            self.password = input('Hasło: ')

    def __validate_login(self):
        if not self.login:
            self.__get_login()

    def __validate_password(self):
        if not self.password:
            self.__get_password()

    def __validate_source_path(self):
        self.source_path = Path(self.__source)
        if not self.source_path.is_absolute():
            self.source_path = Path(self.cwd, self.source_path)

        if not self.source_path.exists():
            raise OSError('Ścieżka źródłowa nie istnieje')


def setup_logger(verbose=False):
    import logging
    import sys

    logger_format = '%(asctime)s [%(levelname)s] %(message)s'
    logger = logging.getLogger('chomik')
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if verbose:
        logger_handler = logging.StreamHandler(stream=sys.stdout)
        logger_handler.setLevel(logging.DEBUG)
        logger_handler.setFormatter(logging.Formatter(logger_format))
    else:
        debug_handler = logging.NullHandler(level=logging.DEBUG)
        logger.addHandler(debug_handler)

        logger_handler = logging.StreamHandler(stream=sys.stdout)
        logger_handler.setLevel(logging.INFO)
        logger_handler.setFormatter(logging.Formatter(logger_format))

    logger.addHandler(logger_handler)

    return logger
