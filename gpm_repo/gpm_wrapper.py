import os
import datetime
import glob

import numpy as np
import h5py

GPM_FFORMAT = '3B-HHR-E.MS.MRG.3IMERG.*.RT-H5'


def get_gpms(datadir):
    gpms = []
    for gpm_abspath in glob.iglob(os.path.join(datadir, GPM_FFORMAT)):
        gpms.append(os.path.basename(gpm_abspath))
    return gpms


class GPMImergeWrapper:
    """A class wrapper for GPM IMERG files"""

    SDTFORMAT = '%Y%m%dS%H%M%S'
    EDTFORMAT = '%Y%m%dE%H%M%S'

    @staticmethod
    def get_lon_index(lon):
        lons = np.arange(-179.95, 180, 0.1)
        diffs = lon - lons
        abs_diffs = np.absolute(diffs)
        return abs_diffs.argmin()

    @staticmethod
    def get_lat_index(lat):
        lats = np.arange(-59.95, 60, 0.1)
        diffs = lat - lats
        abs_diffs = np.absolute(diffs)
        return abs_diffs.argmin()

    def __init__(self, abspath):
        self.abspath = abspath
        self.basename = os.path.basename(abspath)
        self.start_dt = None
        self.end_dt = None

        self._set_datetimes()

    @property
    def precipCal(self):
        _precipCal = None
        try:
            with h5py.File(self.abspath, 'r') as f:
                ds = f['/Grid/precipitationCal']
                _precipCal = ds[:, 300:1500]
        except OSError:
            print('Cannot read GPM file:', self.basename)
            raise

        _precipCal[_precipCal == -9999.9] = 0
        return _precipCal

    def _set_datetimes(self):
        datetimeinfo = self.basename.split('.')[4]
        sdate, stime, etime = datetimeinfo.split('-')
        naive_start_dt = datetime.datetime.strptime(sdate + stime,
                                                    self.SDTFORMAT)
        naive_end_dt = datetime.datetime.strptime(sdate + etime,
                                                  self.EDTFORMAT)
        self.start_dt = naive_start_dt.replace(tzinfo=datetime.timezone.utc)
        self.end_dt = naive_end_dt.replace(tzinfo=datetime.timezone.utc)

    @property
    def is_corrupt(self):
        try:
            self.precipCal
        except OSError:
            return True
        return False
