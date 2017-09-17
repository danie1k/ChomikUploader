import hashlib
import html
import json
import os
import progressbar
import socket
import time
import xmltodict
from collections import OrderedDict
from http.client import HTTPResponse
from json import JSONDecodeError
from pathlib import Path
from pyexpat import ExpatError
from traitlets.traitlets import Any

from model import Model as HamsterModel
from soap import ChomikSOAP, ChomikRequestMixin

RELOGIN_TIME = 300
REQUEST_CHUNK = 1024
REQUEST_TIMEOUT = 20


class ChomikException(Exception):
    args = None
    msg = None

    def __init__(self, msg: str, *args: Any, **_unused: Any) -> None:
        self.args = args
        self.msg = msg

    def __str__(self) -> str:
        return self.msg % self.args


class BaseChomikbox:
    FILE_OR_FOLDER_NAME_FORBIDDEN_CHARS = {'\\', '/', ':', '*', '?', '"', '<', '>', '|'}
    FILE_OR_FOLDER_NAME_FORBIDDEN_REPLACE = '_'
    FILE_OR_FOLDER_NAME_MAX_LENGTH = 100

    __cfduid = None
    __chomik_id = None
    __folders_dom = None
    __session_id = None

    _last_login = None
    _user = None
    _password = None
    _upload_port = None
    _upload_server = None
    _upload_stamp = None
    _upload_token = None

    current_folders = None
    logger = None
    soap_client = None
    model = None
    folder_id = 0

    def __init__(self, user, password, logger, model=None):
        self._user = user
        self._password = password
        self.logger = logger
        self.soap_client = ChomikSOAP()
        self.model = model or HamsterModel()

    @property
    def chomik_id(self):
        if self.__chomik_id is None:
            self.request_login_if_required(force_login=True)
        return self.__chomik_id
    
    @chomik_id.setter
    def chomik_id(self, value):
        self.__chomik_id = value

    @property
    def folders_dom(self):
        if self.__folders_dom is None:
            self.request_login_if_required(force_login=True)
        return self.__folders_dom
    
    @folders_dom.setter
    def folders_dom(self, value):
        self.__folders_dom = value

    @property
    def session_id(self):
        if self.__session_id is None:
            self.request_login_if_required(force_login=True)
        return self.__session_id
    
    @session_id.setter
    def session_id(self, value):
        self.__session_id = value

    def perform_request(self, method: str, request: dict, headers: dict=None) -> tuple:
        """
        :return: tuple(result, response)
        """
        def _check_status(result, msg):
            if method == 'AddFolder' and result['status']['#text'] != 'Ok':
                error_msg = result['errorMessage']['#text']
                if error_msg != 'NameExistsAtDestination':
                    raise ChomikException('%s - %s', msg, error_msg)
            elif result['a:status'] != 'Ok':
                raise ChomikException('%s - %s', msg, result['a:status'])

        if method != 'Auth':
            self.request_login_if_required()

        response = self.soap_client.request(method, request, headers)

        if response['status'] != 200:
            raise ChomikException('Błąd serwera [%s]', response['status'])

        if method == 'AddFolder':
            result = (
                response['content']['s:Envelope']['s:Body']['AddFolderResponse']['AddFolderResult']
            )
            _check_status(result, 'Nie można utworzyć folderu')

        elif method == 'Auth':
            result = response['content']['s:Envelope']['s:Body']['AuthResponse']['AuthResult']
            _check_status(result, 'Nie można zalogować')

        elif method == 'Folders':
            result = (
                response['content']['s:Envelope']['s:Body']['FoldersResponse']['FoldersResult']
            )
            _check_status(result, 'Nie można pobrać folderów')

        elif method == 'UploadToken':
            result = response['content']['s:Envelope']['s:Body']['UploadTokenResponse'][
                'UploadTokenResult'
            ]
            _check_status(result, 'Nie można pobrać tokenu')

        elif method == 'RemoveFolder':
            result = response['content']['s:Envelope']['s:Body']['RemoveFolderResponse'][
                'RemoveFolderResult'
            ]
            _check_status(result, 'Nie można usunąć folderu')

        else:
            raise NotImplementedError('Metoda API nie obsługiwana [%s]', method)

        if '__cfduid' in response['cookies']:
            self.__cfduid = response['cookies']['__cfduid']

        return result, response

    def request_dir_list(self, folder_id: int=0) -> None or OrderedDict:
        """
        Pobiera liste folderów z Chomika
        """
        request = {
            'token': self.session_id,
            'hamsterId': self.chomik_id,
            'folderId': folder_id,
            'depth': 0,
        }
        headers = {}
        if self.__cfduid:
            headers['Cookie'] = '__cfduid=%s' % self.__cfduid
        result, _unused = self.perform_request('Folders', request, headers)

        if folder_id != 0:
            return result['a:folder'][u'folders']

        self.folders_dom = result['a:folder']

    def request_file_upload(self, file_path: str, file_name: str) -> bool:
        current_progress = 0
        file_size = os.path.getsize(file_path)

        multipart_data = self.__prepare_multipart_data(file_name, file_size)
        sock = self.__open_socket(self._upload_server, self._upload_port)

        def _init_progress_bar() -> progressbar.ProgressBar:
            return progressbar.ProgressBar(
                max_value=file_size,
                widgets=[
                    progressbar.AdaptiveTransferSpeed(),
                    ' (', progressbar.ETA(), ') ',
                    progressbar.Bar(), ' ',
                    file_name[:40],
                ]
            )

        with _init_progress_bar() as progress_bar:
            # Sending file header
            sock.send(multipart_data['header'].encode())

            # Sending file in chunks
            fp = open(file_path, 'rb')
            try:
                while True:
                    chunk = fp.read(REQUEST_CHUNK)
                    if not chunk:
                        break
                    sock.send(chunk)

                    try:
                        current_progress += REQUEST_CHUNK
                        progress_bar.update(current_progress)
                    except ValueError:
                        progress_bar.update(file_size)
            except Exception:
                sock.close()
                raise
            finally:
                fp.close()

            progress_bar.update(file_size)

            # Sending file tail
            sock.send(multipart_data['tail'].encode())

        # Getting response
        try:
            r = HTTPResponse(sock)
            r.begin()
            http_response = r.read()
        finally:
            sock.close()

        return self.__parse_upload_response(http_response)

    def request_login_if_required(self, force_login: bool=False) -> None:
        if not force_login and ((self._last_login or 0) + RELOGIN_TIME > time.time()):
            return
        self._last_login = time.time()

        request = {
            'name': self._user,
            'passHash': self.__hash_password(self._password),
            'ver': '4',
            'client': {
                'name': 'chomikbox',
                'version': self.soap_client.VERSION,
            },
        }
        auth_result, response = self.perform_request('Auth', request)

        try:
            self.chomik_id = auth_result['a:hamsterId']
            self.session_id = auth_result['a:token']
        except KeyError:
            raise ChomikException('Nie można zalogować - niepoprawna odpowiedź serwera')

        if not (self.session_id and self.chomik_id):
            raise ChomikException('Nie można zalogować - brak danych o użytkowniku')

        self.request_dir_list()  # Getting initial dir list

    def request_mkdir(self, raw_dir_name: str, folder_id: int=None) -> None:
        """
        Tworzenie katalogu w katalogu o id = folder_id
        """
        self.logger.debug('Tworzenie folderu "%s" w folderze [%s]', raw_dir_name, folder_id)

        folder_id = folder_id or self.folder_id
        dir_name = self.sanitize_name(raw_dir_name)
        request = {
            'token': self.session_id,
            'newFolderId': folder_id,
            'name': html.escape(dir_name),
        }
        self.perform_request('AddFolder', request)

    def request_rmdir(self, folder_id: int=None) -> None:
        request = {
            'token': self.session_id,
            'folderId': folder_id,
            'force': 1,
        }
        self.perform_request('RemoveFolder', request)
        self.logger.debug('Katalog usunięty')

    def request_upload_tokens(self, file_name: str) -> None:
        """
        Pobiera informacje z serwera o tym gdzie i z jakimi parametrami wysłać plik
        :return dict(token, stamp, server, port)
        """
        request = {
            'token': self.session_id,
            'folderId': self.folder_id,
            'fileName': file_name,
        }
        result, _unused = self.perform_request('UploadToken', request)
        try:
            server, _unused, port = result['a:server'].partition(":")
            self._upload_token = result['a:key']
            self._upload_stamp = result['a:stamp']
            self._upload_server = server
            self._upload_port = int(port)
        except IndexError as ex:
            raise ChomikException('Nie można pobrać tokenu - %s', ex)

    def sanitize_name(self, file_or_folder_name: str) -> str:
        """
        Usuwa niedozwolone znaki z nazwy pliku lub folderu i przycina ją do dozwolonej długości
        """
        basename, extension = os.path.splitext(file_or_folder_name)
        ext_len = len(extension) + 1 if len(extension) else 0

        shortened_file_or_folder_name = '{basename}{extension}'.format(
            basename=basename[0:(self.FILE_OR_FOLDER_NAME_MAX_LENGTH - ext_len)],
            extension=extension
        )

        return ''.join(
            char if char not in self.FILE_OR_FOLDER_NAME_FORBIDDEN_CHARS
            else self.FILE_OR_FOLDER_NAME_FORBIDDEN_REPLACE
            for char in shortened_file_or_folder_name
        )

    def _create_hamster_path(self, path: list) -> tuple:
        """
        Przechodzi ścieżkę `path` i tworzy brakujące foldery
        :return: tuple(exists, dom, folder_id)
        """
        assert len(path)
        dom, folder_id, result_path = self.folders_dom, 0, []

        for raw_dir_name in path:
            subdirectories_dom, subdirectories_list = self.__get_subdirectories(dom)
            dir_name = self.sanitize_name(raw_dir_name)

            try:
                dir_position = subdirectories_list.index(dir_name)
            except ValueError:
                self.request_mkdir(dir_name, folder_id)

                dom = self.request_dir_list(folder_id)
                folder_id = dom.get('id')
            else:
                dom = subdirectories_dom[dir_position]
                folder_id = int(dom['id'])

            result_path.append(raw_dir_name)

        return True, dom, folder_id

    def _get_hamster_path(self, target_path: str) -> list:
        current_folders = self.current_folders or []
        return current_folders + [
            elem.replace('/', '') for elem in target_path.split('/') if elem != ''
        ]

    def __get_subdirectories(self, dom: OrderedDict=None) -> tuple:
        dom = dom or self.folders_dom
        subdirectories_dom = dom.get('folders', {}).get('FolderInfo', {})
        if not isinstance(subdirectories_dom, list):
            subdirectories_dom = [subdirectories_dom]

        return (
            subdirectories_dom,
            [html.unescape(elem.get('name', '')) for elem in subdirectories_dom],
        )

    def __hash_password(self, password: str) -> str:
        return hashlib.md5(password.encode()).hexdigest()

    def __open_socket(self, server: str, port: int) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(REQUEST_TIMEOUT)
        ip = socket.gethostbyname_ex(server)[2][0]
        sock.connect((ip, port))
        return sock

    def __parse_upload_response(self, http_response: HTTPResponse) -> bool:
        # Parsing response - it should be XML...
        try:
            response = xmltodict.parse(http_response)
        except ExpatError:
            # ...but critical exceptions are JSON
            try:
                response = json.loads(http_response)
            except JSONDecodeError:
                # This should never happen
                raise ChomikException('Błąd krytyczny - odpowiedź serwera:\n%s', http_response)
            else:
                raise ChomikException(
                    'Błąd wysyłania pliku - odpowiedź serwera:\n%s', response['ExceptionMessage']
                )

        resp = response.get('resp', {})
        error_msg = resp.get('@errorMessage')
        file_id = resp.get('@fileid')
        res = resp.get('@res')

        if not (file_id and res == '1'):
            self.logger.warning('Nie udało się wysłać pliku - %s', error_msg)
            return False

        return True

    def __prepare_multipart_data(self, file_name: str, file_size: int, resume_from: int=0) -> dict:
        """
        :return: dict(content_length, header, tail)
        """
        boundary = "--!CHB" + self._upload_stamp

        def translate_header(header: OrderedDict) -> str:
            result = []
            for name, value in header.items():
                if name == 'file':
                    row = '{boundary}\r\nname="file"; filename="{filename}"\r\n\r\n'.format(
                        boundary=boundary, filename=file_name
                    )
                else:
                    row = (
                        '{boundary}\r\nname="{name}"\r\nContent-Type: text/plain\r\n'
                        '\r\n{value}\r\n'.format(boundary=boundary, name=name, value=value)
                    )
                result.append(row)

            return ''.join(result)

        header = OrderedDict()
        header['chomik_id'] = self.chomik_id
        header['folder_id'] = self.folder_id
        header['key'] = self._upload_token
        header['time'] = self._upload_stamp
        if resume_from:
            header['resume_from'] = resume_from
        header['client'] = self.soap_client.CLIENT
        header['locale'] = 'PL'
        header['file'] = file_name

        content_header = translate_header(header)
        tail = '\r\n{boundary}--\r\n\r\n'.format(boundary=boundary)
        content_length = len(content_header) + (file_size - 2) + len(tail)

        header = 'POST /file/ HTTP/1.0\r\n'
        header += 'Content-Type: multipart/mixed; boundary={0}\r\n'.format(boundary[2:])
        # header += 'Connection: close\r\n'
        header += 'Host: {0}:{1}\r\n'.format(self._upload_server, self._upload_port)
        header += 'Content-Length: {0}\r\n\r\n'.format(content_length)
        header += content_header

        return {
            'content_length': content_length,
            'header': header,
            'tail': tail,
        }




    # TODO's ######################################################################################



class Chomik(ChomikRequestMixin, BaseChomikbox):
    _last_login = None

    def chdir(self, target_path: str) -> None:
        """
        Zmien katalog na chomiku. Jezeli jakis katalog nie istnieje, to zostaje stworzony
        np. (chdirs(/katalog1/katalog2/katalog3) )
        """
        self.logger.debug('Przechodzenie do ścieżki "%s"', target_path)
        directories = []

        for path in self._get_hamster_path(target_path):
            if path == '..':
                if path != []:  # @TODO: Verify what's going on here
                    del(directories[-1])
            else:
                directories.append(path[:self.FILE_OR_FOLDER_NAME_MAX_LENGTH])


        result, dom, folder_id = self._create_hamster_path(directories)
        if not result:
            raise ChomikException('Nie udało się przejść do ścieżki "%s"', target_path)

        self.current_folders = directories
        self.folder_id = folder_id

    def curr_adr(self, atr: int=None) -> tuple or None:  # @TODO curr_adr - co to robi i po co
        """
        Zwracanie lub ustawianie obecnego polozenia w katalogach
        """
        if atr is None:
            return self.current_folders, self.folder_id
        else:
            self.current_folders, self.folder_id = atr

    def rmdir(self, folder_id: int) -> None:
        self.request_rmdir(folder_id)

    def upload_file(self, file_path: Path) -> bool:
        file_path = str(file_path)
        self.model.add_notuploaded_normal(file_path)

        raw_file_name = os.path.basename(file_path)
        file_name = self.sanitize_name(raw_file_name)

        self.request_upload_tokens(file_name)
        self.model.add_notuploaded_resume(
            file_path, file_name, self.folder_id, self.chomik_id,
            self._upload_token, self._upload_server, self._upload_port, self._upload_stamp
        )

        try:
            # try:
            result = self.request_file_upload(file_path, file_name)
            # except (socket.error, socket.timeout):
            #     self.logger.debug('Wznawianie')
            #     result = self.resume(file_path, file_name, self.folder_id, self.chomik_id, **tokens)
        finally:
            self._upload_port = None
            self._upload_server = None
            self._upload_stamp = None
            self._upload_token = None

        self.model.remove_notuploaded(file_path)
        return result

    # TODO's ######################################################################################

    # def resume(self, file_path, file_name, folder_id, chomik_id, token, stamp, server, port):
    #     self.request_login_if_required()
    #     self.chomik_id = chomik_id
    #     self.folder_id = folder_id
    #     filename_tmp   = change_coding(file_name)
    #     filesize_sent = self.__resume_get_tokens(file_path, file_name, token, server, port)
    #     if (filesize_sent == -1) or token == None:
    #         if self.debug:
    #             self.view.print_( "Resume ", filename_tmp )
    #             self.view.print_( "Filesize sent", filesize_sent )
    #         return False
    #     else:
    #         return self.__resume_with_resume_option(file_path, file_name, token, server, port, stamp, filesize_sent, chomik_id, folder_id)
    #
    # def __resume_with_resume_option(self, filepath, filename, token, server, port, stamp, filesize_sent, chomik_id, folder_id):
    #     try:
    #         result = self.__resume(filepath, filename, token, server, port, stamp, filesize_sent)
    #         self.view.print_( "Result", result )
    #     except (socket.error, socket.timeout) as e:
    #         self.view.print_("Wznawianie\n")
    #         result = self.resume(filepath, filename, folder_id, chomik_id, token, stamp, server,
    #                              port)
    #     return result
    #
    # def __resume_get_tokens(self, filepath, filename, token, server, port):
    #     """
    #     Pobiera informacje z serwera o tym gdzie i z jakimi parametrami wyslac plik
    #     """
    #     #Pobieranie informacji o serwerze
    #     filename_len = len(filename)
    #     sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #     sock.settimeout(glob_timeout)
    #     ip = socket.gethostbyname_ex(server)[2][0]
    #     sock.connect( (ip, int(port) ) )
    #     tmp = """GET /resume/check/?key={0}& HTTP/1.1\r\nConnection: close\r\nUser-Agent: ChomikBox\r\nHost: {1}:{2}\r\n\r\n""".format(token, server, port)
    #     sock.send( tmp )
    #     #Odbieranie odpowiedzi
    #     resp = ""
    #     while True:
    #         tmp = sock.recv(640)
    #         if tmp ==  '':
    #             break
    #         resp   += tmp
    #     resp += tmp
    #     sock.close()
    #     try:
    #         filesize_sent = int(re.findall( """<resp file_size="([^"]*)" skipThumbnails="[^"]*" res="1"/>""", resp)[0])
    #         return filesize_sent
    #     except IndexError as e:
    #         self.view.print_( "Nie mozna bylo wznowic pobierania" )
    #         self.view.print_( resp )
    #         return -1
    #
    # def __resume(self, filepath, filename, token, server, port, stamp, filesize_sent):
    #     """
    #     Wznawianie uploadowania pliku filepath o nazwie filename o danych: folder_id, chomik_id, token, server, port, stamp
    #     """
    #     #Tworzenie naglowka
    #     size  = os.path.getsize(filepath)
    #     header, contenttail =  self.__create_header(server, port, token, stamp, filename, (size - filesize_sent), resume_from = filesize_sent)
    #
    #     sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #     sock.settimeout(glob_timeout)
    #     ip = socket.gethostbyname_ex(server)[2][0]
    #     sock.connect( (ip,int(port) ) )
    #     sock.send(header)
    #
    #     f = open(filepath,'rb')
    #     f.seek(filesize_sent)
    #     pb = ProgressBar(total=size, rate_refresh = 0.5, count = filesize_sent, name = filepath)
    #     self.view.add_progress_bar(pb)
    #     last_time = time.time()
    #     #g = open("log_resume" + filename + ".txt", "w")
    #     #g.write(header)
    #     #g.close()
    #     try:
    #         while True:
    #             chunk = f.read(1024)
    #             if not chunk:
    #                 break
    #             sock.send(chunk)
    #             pb.update(len(chunk))
    #             now = time.time()
    #             if now - last_time > 0.5:
    #                 self.view.update_progress_bars()
    #                 last_time = now
    #         f.close()
    #         sock.send(contenttail)
    #     except Exception as e:
    #         if self.debug:
    #             trbck = sys.exc_info()[2]
    #             debug_fun(trbck)
    #         raise e
    #     finally:
    #         self.view.update_progress_bars()
    #         self.view.delete_progress_bar(pb)
    #
    #     resp = ""
    #     while True:
    #         tmp = sock.recv(640)
    #         resp   += tmp
    #         if tmp ==  '' or "/>" in resp:
    #             break
    #     if '<resp res="1" fileid=' in resp:
    #         return True
    #     else:
    #         try:
    #             error_msg = re.findall('errorMessage="([^"]*)"',resp)[0]
    #             self.view.print_( "BLAD(nieudane wysylanie):\r\n",error_msg )
    #         except IndexError:
    #             pass
    #         self.view.print_( resp )
    #         return False
