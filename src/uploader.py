import os
import time

from .chomikbox import Chomik
from .model import Model as HamsterModel
from .view import View as HamsterView


class BaseUploader:
    __hamster = None
    __model = None
    __not_uploaded = 'notuploaded.txt'
    __password = None
    __uploaded = 'uploaded.txt'
    __user = None
    __view = None
    logger = None

    def __init__(self, user, password, logger, view=None, model=None):
        self.__password = password
        self.__user = user
        self.logger = logger
        self.__model = model or HamsterModel()
        self.__view = view or HamsterView()

    @property
    def hamster(self):
        if self.__hamster is None:
            self.__hamster = Chomik(
                self.__user, self.__password, self.logger, self.__view, self.__model
            )
        return self.__hamster

    def _upload_dir(self, local_path, remote_path):
        lock = self.__model.return_chdirlock()
        lock.acquire()

        try:
            self.hamster.chdir(remote_path)
            raise NotImplementedError
            # self.__upload_aux(local_path)
            # self.__resume()
        finally:
            lock.release()

    def _upload_file(self, local_path, remote_path):
        self.hamster.chdir(remote_path)
        self.hamster.upload(local_path)

    # TODO's ######################################################################################

    # def __resume(self):
    #     """
    #     Wznawia wysyłanie plikow z listy notuploaded.txt
    #     """
    #     self.logger.debug('Wznawianie nieudanych transferów')
    #
    #     notuploaded = self.__model.get_notuploaded_resume()
    #     for filepath, filename, folder_id, chomik_id, token, host, port, stamp in notuploaded:
    #         if not self.__model.is_uploaded_or_pended_and_add(filepath):
    #             self.__resume_file_aux(
    #                 filepath, filename, folder_id, chomik_id, token, host, port, stamp
    #             )
    #             self.__model.remove_from_pending(filepath)
    #
    #     self.logger.debug('Zakończono wznawianie nieudanych transferów')
    #
    # def __resume_file_aux(self, filepath, filename, folder_id, chomik_id, token, host, port, stamp):
    #     """
    #     Wysylanie/wznawianie pojedynczego pliku
    #     """
    #     self.__view.print_('Wznawianie pliku:', filepath)
    #     try:
    #         result = self.hamster.resume(filepath, filename, folder_id, chomik_id, token, host, port, stamp)
    #     except Exception as e:
    #         self.__view.print_('Blad:', e)
    #
    #         # if self.debug:  # @TODO Remove debug
    #         #     trbck = sys.exc_info()[2]
    #         #     debug_fun(trbck)
    #
    #         self.__view.print_('Blad. Plik ', filepath, ' nie zostal wyslany\r\n')
    #         return False
    #
    #     if result == False:
    #         self.__view.print_('Blad. Plik ', filepath, ' nie zostal wyslany\r\n')
    #         return False
    #     else:
    #         self.__model.add_uploaded(filepath)
    #         self.__model.remove_notuploaded(filepath)
    #         self.__view.print_('Zakonczono uploadowanie\r\n')
    #         return True
    #
    # def __upload_aux(self, dirpath):
    #     """
    #     Uploaduje pliki z danego katalogu i jego podkatalogi.
    #     """
    #     files = [ i for i in os.listdir(dirpath) if os.path.isfile( os.path.join(dirpath, i) ) ]
    #     files.sort()
    #     dirs  = [ i for i in os.listdir(dirpath) if os.path.isdir( os.path.join(dirpath, i) ) ]
    #     dirs.sort()
    #     for fil in files:
    #         #TODO: przetwarzany jest plik
    #         filepath = os.path.join(dirpath, fil)
    #         #if not self.model.in_uploaded(filepath):
    #         if not self.__model.is_uploaded_or_pended_and_add(filepath):
    #             self.__upload_file_aux(fil, dirpath)
    #             self.__model.remove_from_pending(filepath)
    #
    #     for dr in dirs:
    #         #address = self.hamster.cur_adr
    #         address = self.hamster.curr_adr()
    #         self.__upload_dir_aux(dirpath,dr)
    #         self.hamster.curr_adr(address)
    #         #self.hamster.cur_adr = address
    #
    # def __upload_dir_aux(self, dirpath,dr):
    #     """
    #     Zmiana pozycji na chomiku i wyslanie katalogu
    #     """
    #     lock = self.__model.return_chdirlock()
    #     lock.acquire()
    #     try:
    #         changed = self.hamster.chdir(dr)
    #     except Exception as e:
    #         self.__view.print_('Blad. Nie wyslano katalogu: ', os.path.join(dirpath, dr))
    #         self.__view.print_(e)
    #
    #         # if self.debug:  # @TODO Remove debug
    #         #     trbck = sys.exc_info()[2]
    #         #     debug_fun(trbck)
    #
    #         time.sleep(60)
    #         return
    #     finally:
    #         lock.release()
    #     if changed != True:
    #         self.__view.print_("Nie udalo sie zmienic katalogu", dr)
    #         return
    #     self.__upload_aux( os.path.join(dirpath, dr) )
    #
    # def __upload_file_aux(self, fil, dirpath):
    #     """
    #     Wysylanie pliku wraz z kontrola bledow.
    #     W odpowiednim pliku zapisujemy, czy plik zostal poprawnie wyslany
    #     """
    #     filepath = os.path.join(dirpath, fil)
    #     self.__view.print_('Uploadowanie pliku:', filepath)
    #     try:
    #         result = self.hamster.upload(filepath, os.path.basename(filepath))
    #     except Exception as e:
    #         self.__view.print_('Blad:', e)
    #         self.__view.print_('Blad. Plik ', filepath, ' nie zostal wyslany\r\n')
    #
    #         # if self.debug:  # @TODO Remove debug
    #         #     trbck = sys.exc_info()[2]
    #         #     debug_fun(trbck)
    #
    #         return
    #
    #     if result == False:
    #         self.__view.print_('Blad. Plik ', filepath, ' nie zostal wyslany\r\n')
    #     else:
    #         self.__model.add_uploaded(filepath)
    #         self.__model.remove_notuploaded(filepath)
    #         self.__view.print_('Zakonczono uploadowanie\r\n')


class Uploader(BaseUploader):
    def run(self, local_path, remote_path):
        """
        :type local_path: pathlib.Path
        :type remote_path: str
        :type threads: int
        """
        method = '_upload_file'

        if local_path.is_dir():
            method = '_upload_dir'

        getattr(self, method)(str(local_path), remote_path)
