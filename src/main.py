from pathlib import Path

from . import uploader


class Main:
    cwd = None
    debug = None
    destination = None
    login = None
    password = None
    recursive = None
    source_path = None
    threads = None
    __source = None

    def __init__(
            self, cwd, source, destination, login=None, password=None,
            recursive=False, threads=1, debug=False):
        self.cwd = cwd
        self.debug = debug
        self.destination = destination
        self.login = login
        self.password = password
        self.recursive = recursive
        self.threads = threads
        self.__source = source

        self.__validate_source_path()
        self.__validate_login()
        self.__validate_password()

    def upload(self):
        u = uploader.Uploader(
            self.login, self.password, debug=self.debug
        )

        if self.recursive:
            if self.threads > 1:
                u.upload_multi(
                    self.destination, self.source_path, self.threads
                )
            else:
                u.upload_dir(self.destination, self.source_path)
        else:
            u.upload_file(self.destination, self.source_path)

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

        if self.recursive:
            if not self.source_path.is_dir():
                raise OSError('Ścieżka źródłowa nie jest katalogiem')
        else:
            if not self.source_path.is_file():
                raise OSError('Ścieżka źródłowa nie jest plikiem')

        self.source_path = str(self.source_path)
