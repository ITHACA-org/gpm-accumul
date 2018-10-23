import os
from ftplib import FTP

from .gpm_wrapper import GPM_FFORMAT

try:
    from .credentials import *
except ImportError:
    print('You must define a user and a password')


class GPMFTP(FTP):

    GPM_HOST = 'jsimpson.pps.eosdis.nasa.gov'
    HHR_E_dir = '/NRTPUB/imerg/early/'

    def __init__(self):
        super().__init__(self.GPM_HOST, user, passwd)
        self._latest_mod_dir = None
        self._2latest_mod_dir = None

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

    @property
    def second_latest_mdir(self):
        if self._2latest_mod_dir is None:
            dirs = []  # should be filled with tuples like so [(dirname, modify_timestamp),
                       # (dirname2, modify_timestamp2)]
            for elm in self.mlsd(self.HHR_E_dir, ['modify', 'type']):
                if elm[1]['type'] != 'dir':
                    continue
                dirs.append((elm[0], elm[1]['modify']))
            dirs.sort(key=lambda dir: dir[1])
            self._2latest_mod_dir = dirs[-2][0]
            print('Second latest modified folder is', self._2latest_mod_dir, 'on', dirs[-2][1])
        return self._2latest_mod_dir

    def get_latest_nfnames(self, n):
        gpm_prefix = GPM_FFORMAT[:-7]
        absdirname = self.HHR_E_dir + self.latest_mod_dir
        fnames = []
        for elm in self.mlsd(absdirname, ['type']):
            if elm[1]['type'] != 'file':
                continue
            if elm[0].startswith(gpm_prefix):
                fnames.append(absdirname + '/' + elm[0])

        if len(fnames) < n:
            absdirname = self.HHR_E_dir + self.second_latest_mdir
            for elm in self.mlsd(absdirname, ['type']):
                if elm[1]['type'] != 'file':
                    continue
                if elm[0].startswith(gpm_prefix):
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
            self.retrbinary('RETR ' + path, localfile.write)
            print('    ...downloaded')
        return fname

    def grab_latest_nfiles(self, n, datadir):
        count = 0
        grabbed = []
        for path in self.get_latest_nfnames(n):
            count += 1
            print('GPM file number ' + str(count) + '/' + str(n))
            res = self.grab_file(path, datadir)
            if res is not None:
                grabbed.append(res)
        return grabbed


if __name__ == '__main__':
    with GPMFTP() as ftp:
        grabbed_files = ftp.grab_latest_nfiles(5, DATADIR)
        print('Grabbed files are:')
        for fname in grabbed_files:
            print(fname)
