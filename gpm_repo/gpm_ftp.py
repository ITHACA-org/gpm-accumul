import os
from concurrent import futures

from ftplib import FTP

try:
    from credentials import *
except ImportError:
    print('You must define a user and a password')

MAX_WORKERS = 20


class GPMFTP(FTP):

    GPM_HOST = 'jsimpson.pps.eosdis.nasa.gov'
    HHR_E_dir = '/NRTPUB/imerg/early/'

    def __init__(self):
        super().__init__(self.GPM_HOST, user, passwd)
        self._latest_mod_dir = None

    @staticmethod
    def get_latest_fname():
        with GPMFTP() as ftp:
            absdirname = ftp.HHR_E_dir + ftp.latest_mod_dir
            latest_fname = ''
            for elm in ftp.mlsd(absdirname, ['modify', 'type']):
                if elm[1]['type'] != 'file':
                    continue
                if elm[0] > latest_fname:
                    latest_fname = elm[0]

        print('Latest filename is', latest_fname)
        return latest_fname

    @property
    def latest_mod_dir(self):
        if self._latest_mod_dir is None:
            latst_modify = ''
            dirname = None

            for elm in self.mlsd(self.HHR_E_dir, ['modify', 'type']):
                if elm[1]['type'] != 'dir':
                    continue
                modify = elm[1]['modify']
                if modify > latst_modify:
                    latst_modify = modify
                    dirname = elm[0]
            print('Latest modified folder is', dirname, 'on', latst_modify)
            self._latest_mod_dir = dirname
        return self._latest_mod_dir

    def get_latest_nfnames(self, n):
        absdirname = self.HHR_E_dir + self.latest_mod_dir
        fnames = []
        for elm in self.mlsd(absdirname, ['type']):
            if elm[1]['type'] != 'file':
                continue
            if elm[0].startswith('3B-HHR-E.MS.MRG.3IMERG.'):
                fnames.append(absdirname + '/' + elm[0])
        fnames.sort(reverse=True)
        return fnames[:n]

    def grab_file(self, path, datadir):
        # https://pythonprogramming.net/ftp-transfers-python-ftplib/
        fname = path.split('/')[-1]
        absfname = os.path.join(datadir, fname)
        if fname in os.listdir(datadir):
            print('File', fname, 'already exists!')
            return
        with open(absfname, 'wb') as localfile:
            print('Downloading', fname, '...')
            ftp.retrbinary('RETR ' + path, localfile.write)
            print('    ...downloaded')

    def grab_latest_nfiles(self, n, datadir):
        paths = self.get_latest_nfnames(n)
        if len(paths) < 3:
            for path in paths:
                self.grab_file(path, datadir)
        else:
            workers = min(MAX_WORKERS, len(paths))
            datadirl = [datadir] * len(paths)
            with futures.ThreadPoolExecutor(workers) as executor:
                res = executor.map(self.grab_file, paths, datadirl)


if __name__ == '__main__':
    with GPMFTP() as ftp:
        ftp.grab_latest_nfiles(4, DATADIR)
