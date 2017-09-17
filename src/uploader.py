from pathlib import Path

from chomikbox import Chomik, ChomikException
from model import Model as HamsterModel


class BaseUploader:
    __hamster = None
    __model = None
    __password = None
    __user = None
    logger = None

    def __init__(self, user, password, logger, model=None):
        self.__password = password
        self.__user = user
        self.logger = logger
        self.__model = model or HamsterModel()

    @property
    def hamster(self):
        if self.__hamster is None:
            self.__hamster = Chomik(self.__user, self.__password, self.logger, self.__model)
        return self.__hamster

    def _upload_dir(self, local_path: Path, remote_path: str) -> None:
        lock = self.__model.return_chdirlock()
        lock.acquire()

        try:
            self.hamster.chdir(remote_path)
            self.__upload_node(local_path)
            # self.__resume()
        finally:
            lock.release()

    def _upload_file(self, local_path: Path, remote_path: str=None) -> bool:
        self.logger.debug('Wysłanie pliku "%s"', local_path)

        if remote_path:
            self.hamster.chdir(remote_path)

        try:
            result = self.hamster.upload_file(local_path)
        except ChomikException as ex:
            self.logger.error('Plik nie został wysłany - %s', ex)
            return False

        if not result:
            self.logger.error('Plik nie został wysłany')
            return False

        self.logger.debug('Plik wysłany pomyślnie')
        return True

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

    def __upload_node(self, dir_path: Path) -> None:
        """
        Rekurencyjnie uploaduje zawartość katalogu
        """
        self.logger.info('Wysyłanie "%s"', dir_path)
        files, directories = [], []

        for path in sorted(dir_path.iterdir()):
            if path.is_dir():
                directories.append(path)
            else:
                files.append(path)

        for path in files:
            if self.__model.is_uploaded_or_pended_and_add(str(path)):
                continue

            self._upload_file(path)
            self.__model.add_uploaded(str(path))
            self.__model.remove_notuploaded(str(path))
            self.__model.remove_from_pending(str(path))

        for path in directories:
            raise NotImplementedError
            # address = self.hamster.curr_adr()
            # self.__upload_dir_aux(path)
            # self.hamster.curr_adr(address)

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
    #     self.__upload_node( os.path.join(dirpath, dr) )


class Uploader(BaseUploader):
    def run(self, local_path, remote_path):
        """
        :type local_path: pathlib.Path
        :type remote_path: str
        """
        uploaders = {
            True: self._upload_dir,
            False: self._upload_file,
        }
        uploaders[local_path.is_dir()](local_path, remote_path)
