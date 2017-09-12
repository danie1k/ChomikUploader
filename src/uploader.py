import threading

from . import model as chomik_model, view as chomik_view
from .chomikbox import *


class UploaderThread(threading.Thread):
    daemon = True
    local_path = None
    remote_path = None

    def __init__(
            self, user, password, local_path, remote_path, view, model, logger=None):
        super().__init__()
        self.local_path = local_path
        self.uploader = Uploader(user, password, view, model, logger)
        self.remote_path = remote_path

    def run(self):
        self.uploader.upload_dir(self.local_path, self.remote_path)


class Uploader:
    chomik = None
    debug = True  # @TODO Remove debug
    logger = None
    model = None
    password = None
    user = None
    view = None
    _notuploaded = None
    _uploaded = None
    __logged_in = False

    def __init__(self, user, password, view=None, model=None, logger=None):
        self._notuploaded = 'notuploaded.txt'
        self._uploaded = 'uploaded.txt'
        self.logger = logger
        self.model = model or chomik_model.Model()
        self.password = password
        self.user = user
        self.view = view or chomik_view.View()
        self.chomik = Chomik(self.view, self.model, logger=logger, debug=True)  # @TODO Remove debug

    def upload(self, local_path, remote_path, threads=1):
        """
        :type local_path: pathlib.Path
        :type remote_path: str
        :type threads: int
        """
        if local_path.is_file():
            self.upload_file(str(local_path), remote_path)
        else:
            # @TODO Bug: trzeba wywolac funkcje encoding zanim uruchomi sie watek
            try:
                text = ''.decode('cp1250')
            except Exception:
                pass
            try:
                ''.decode('utf8')
            except Exception:
                pass

            for i in range(threads):
                UploaderThread(
                    self.user, self.password, str(local_path), remote_path, self.view, self.model
                ).start()

            while threading.active_count() > 1:
                time.sleep(1)

    def upload_file(self, local_path, remote_path):
        self.login()

        if not self.chomik.chdirs(remote_path):
            sys.exit(1)

        self.logger.debug('Uploadowanie pliku...')
        try:
            result = self.chomik.upload(local_path, os.path.basename(local_path))
        except Exception as e:
            self.logger.error('%s', e)

            if self.debug:  # @TODO Remove debug
                trbck = sys.exc_info()[2]
                debug_fun(trbck)

            result = False
        if result == True:
            self.logger.info('Plik został wysłany')
        else:
            self.logger.error('Plik nie został wysłany')

    def upload_dir(self, local_path, remote_path):
        self.login()
        self.resume()

        lock = self.model.return_chdirlock()
        lock.acquire()
        try:
            if not self.chomik.chdirs(remote_path):
                sys.exit(1)
        finally:
            lock.release()
        self.__upload_aux(local_path)
        self.resume()

    def login(self):
        if self.__logged_in:
            self.logger.debug('Już zalogowano')
            return

        self.logger.debug('Logowanie')
        if self.chomik.login(self.user, self.password):
            self.logger.debug('Zalogowano')
            self.__logged_in = True
        else:
            self.logger.error('Błędny login lub hasło')
            sys.exit(1)


    ###############################################################################################


    def __upload_aux(self, dirpath):
        """
        Uploaduje pliki z danego katalogu i jego podkatalogi.
        """
        files = [ i for i in os.listdir(dirpath) if os.path.isfile( os.path.join(dirpath, i) ) ]
        files.sort()
        dirs  = [ i for i in os.listdir(dirpath) if os.path.isdir( os.path.join(dirpath, i) ) ]
        dirs.sort()
        for fil in files:
            #TODO: przetwarzany jest plik
            filepath = os.path.join(dirpath, fil)
            #if not self.model.in_uploaded(filepath):
            if not self.model.is_uploaded_or_pended_and_add(filepath):
                self.__upload_file_aux(fil, dirpath)
                self.model.remove_from_pending(filepath)
            
        for dr in dirs:
            #address = self.chomik.cur_adr
            address = self.chomik.cur_adr()
            self.__upload_dir_aux(dirpath,dr)
            self.chomik.cur_adr(address)
            #self.chomik.cur_adr = address

    def __upload_file_aux(self, fil, dirpath):
        """
        Wysylanie pliku wraz z kontrola bledow.
        W odpowiednim pliku zapisujemy, czy plik zostal poprawnie wyslany
        """
        filepath = os.path.join(dirpath, fil)
        self.view.print_( 'Uploadowanie pliku:', filepath )
        try:
            result = self.chomik.upload(filepath, os.path.basename(filepath))
        except Exception as e:
            self.view.print_( 'Blad:', e )
            self.view.print_( 'Blad. Plik ',filepath, ' nie zostal wyslany\r\n' )

            if self.debug:  # @TODO Remove debug
                trbck = sys.exc_info()[2]
                debug_fun(trbck)

            return

        if result == False:
            self.view.print_( 'Blad. Plik ',filepath, ' nie zostal wyslany\r\n' )
        else:
            self.model.add_uploaded(filepath)
            self.model.remove_notuploaded(filepath)
            self.view.print_( 'Zakonczono uploadowanie\r\n' )

    def __upload_dir_aux(self, dirpath,dr):
        """
        Zmiana pozycji na chomiku i wyslanie katalogu
        """
        lock = self.model.return_chdirlock()
        lock.acquire()
        try:
            changed = self.chomik.chdirs(dr)
        except Exception as e:
            self.view.print_( 'Blad. Nie wyslano katalogu: ', os.path.join(dirpath, dr)  )
            self.view.print_( e )

            if self.debug:  # @TODO Remove debug
                trbck = sys.exc_info()[2]
                debug_fun(trbck)

            time.sleep(60)
            return
        finally:
            lock.release()
        if changed != True:
            self.view.print_( "Nie udalo sie zmienic katalogu", dr  )
            return
        self.__upload_aux( os.path.join(dirpath, dr) )        
    ####################################################################

    def resume(self):
        """
        Wznawia wysyłanie plikow z listy notuploaded.txt
        """
        self.logger.debug('Wznawianie nieudanych transferów')

        notuploaded = self.model.get_notuploaded_resume()
        for filepath, filename, folder_id, chomik_id, token, host, port, stamp in notuploaded:
            if not self.model.is_uploaded_or_pended_and_add(filepath):
                self.__resume_file_aux(
                    filepath, filename, folder_id, chomik_id, token, host, port, stamp
                )
                self.model.remove_from_pending(filepath)

        self.logger.debug('Zakończono wznawianie nieudanych transferów')

    def __resume_file_aux(self, filepath, filename, folder_id, chomik_id, token, host, port, stamp):
        """
        Wysylanie/wznawianie pojedynczego pliku
        """
        self.view.print_( 'Wznawianie pliku:', filepath )
        try:
            result = self.chomik.resume(filepath, filename, folder_id, chomik_id, token, host, port, stamp)
        except Exception as e:
            self.view.print_( 'Blad:', e)

            if self.debug:  # @TODO Remove debug
                trbck = sys.exc_info()[2]
                debug_fun(trbck)

            self.view.print_( 'Blad. Plik ',filepath,' nie zostal wyslany\r\n' )
            return False
            
        if result == False:
            self.view.print_( 'Blad. Plik ',filepath, ' nie zostal wyslany\r\n' )
            return False
        else:
            self.model.add_uploaded(filepath)
            self.model.remove_notuploaded(filepath)
            self.view.print_( 'Zakonczono uploadowanie\r\n' )
            return True
