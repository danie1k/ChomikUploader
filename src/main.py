from getpass import getpass
from pathlib import Path

from chomikbox import ChomikException
from . import uploader


class BaseMain:
    cwd = None
    destination = None
    logger = None
    login = None
    password = None
    source_path = None
    __source = None

    def __init__(
            self, cwd, source, destination, login=None, password=None, logger=None, **_unused):
        self.cwd = cwd
        self.destination = destination
        self.logger = logger
        self.login = login
        self.password = password
        self.__source = source

        self.__validate_source_path()
        self.__validate_login()
        self.__validate_password()

    def __get_login(self):
        while not self.login:
            self.login = input('Login: ')

    def __get_password(self):
        while not self.password:
            self.password = getpass('Hasło: ')

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


class Main(BaseMain):
    def upload(self):
        u = uploader.Uploader(self.login, self.password, self.logger)

        try:
            u.run(self.source_path, self.destination)
        except ChomikException as ex:
            self.logger.error('Nie można wysłać - %s', ex)
        else:
            self.logger.info('Wysłano')
