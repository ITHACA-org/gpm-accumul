import os
import datetime
from operator import attrgetter
import configparser

import numpy as np

from . import gpm_wrapper
from .utils import array2tiff, tiff2array
from .credentials import THRESH_ADJ_ABSPATH, THRESHOLDS_ABSPATH


class PrecipTimeSerie:
    """handle and manage a time serie of precipitation data"""

    MEAS_DURATION = datetime.timedelta(minutes=30)

    def __init__(self, duration, end_dt, datadir):
        self.duration = duration
        self.end_dt = end_dt
        self.datadir = datadir
        self.start_dt = end_dt - duration
        self.exp_nmeas = self.duration // self.MEAS_DURATION
        self.measurements = []
        self.dt_index = None
        self._serie = None
        self._accumul = None

    @classmethod
    def latest(cls, duration, datadir):
        gpm_files = gpm_wrapper.get_gpms(datadir)
        gpm_files.sort()
        end_absfile = os.path.join(datadir, gpm_files[-1])
        end_gpmobj = gpm_wrapper.GPMImergeWrapper(end_absfile)
        end_dt = end_gpmobj.end_dt
        time_serie = cls(duration, end_dt, datadir)
        return time_serie

    @property
    def serie(self):
        if self._serie is None:
            self._build_serie()
        return self._serie

    @property
    def accumul(self):
        if self._accumul is None:
            self._accumul = np.around(np.sum(
                    self.serie, axis=0, keepdims=False) / 2, 0).astype(np.int16)
        return self._accumul

    def _build_serie(self):
        for meas_fname in gpm_wrapper.get_gpms(self.datadir):
            meas_abspath = os.path.join(self.datadir, meas_fname)
            gpm_meas = gpm_wrapper.GPMImergeWrapper(meas_abspath)
            if gpm_meas.end_dt <= self.end_dt and \
                            gpm_meas.end_dt > self.start_dt:
                self.measurements.append(gpm_meas)
        if len(self.measurements) != self.exp_nmeas:
            raise ValueError("Missing measurements in the serie")
        self.measurements.sort(key=attrgetter('start_dt'))
        self.dt_index = tuple(measure.start_dt for measure in
                              self.measurements)
        self._serie = np.array([measure.precipCal for measure
                                in self.measurements])
        
    def save_accumul(self, out_abspath):
        array2tiff(self.accumul, out_abspath)

    def latest_subserie(self, duration):
        if self._serie is None:
            raise ValueError('No need to create a subserie from a'
                             ' non-built serie')

        if duration >= self.duration:
            raise ValueError('Required duration of subserie is greater '
                             'than original serie')

        subserie = PrecipTimeSerie(duration, self.end_dt, self.datadir)
        n_throw = self.exp_nmeas - subserie.exp_nmeas
        subserie.measurements = self.measurements[n_throw:]
        subserie.dt_index = self.dt_index[n_throw:]
        subserie._serie = self.serie[n_throw:]
        return subserie


class Threshold:
    def __init__(self, hours):
        if not isinstance(hours, int):
            raise ValueError
        self.hours = hours
        self._low_threshold = None
        self._medium_threshold = None
        self._high_threshold = None
        self._adj_array = None
        self.config = configparser.ConfigParser()
        self.config.read(THRESHOLDS_ABSPATH)
        self.section = str(hours) + ' Hours'
        self.low_scalar = int(self.config[self.section]['low'])
        self.medium_scalar = int(self.config[self.section]['medium'])
        self.high_scalar = int(self.config[self.section]['high'])

    @property
    def adj_array(self):
        if self._adj_array is None:
            self._adj_array = np.fliplr(tiff2array(THRESH_ADJ_ABSPATH).T)
        return self._adj_array

    @property
    def low(self):
        if self._low_threshold is None:
            self._low_threshold = self.low_scalar * self.adj_array
        return self._low_threshold

    @property
    def medium(self):
        if self._medium_threshold is None:
            self._medium_threshold = self.medium_scalar * self.adj_array
        return self._medium_threshold

    @property
    def high(self):
        if self._high_threshold is None:
            self._high_threshold = self.high_scalar * self.adj_array
        return self._high_threshold

    def save_high(self, out_abspath):
        array2tiff(self.high, out_abspath)


class GridThreshold:
    SECTION = 'Grid Thresholds'

    def __init__(self, hours):
        if not isinstance(hours, int):
            raise ValueError('Duration must be expressed in hours, integer value is expected')
        self.hours = hours
        self._grid = None
        config = configparser.ConfigParser()
        config.read(THRESHOLDS_ABSPATH)
        self.ref = '{:03d}h'.format(hours)
        self.grid_fname = config[self.SECTION][self.ref]
        self.grid_apath = os.path.join(os.path.dirname(THRESHOLDS_ABSPATH), self.grid_fname)
        del config

    @property
    def grid(self):
        if self._grid is None:
            grid_toflip = tiff2array(self.grid_apath).T
            self._grid = np.fliplr(grid_toflip)
        return self._grid


class AlertDetector:
    TIF_BASENAME = 'alerts_{:03d}h.tif'

    def __init__(self, serie):
        if not isinstance(serie, PrecipTimeSerie):
            raise ValueError
        self.serie = serie
        self.hours = int(serie.duration.total_seconds() // 3600)
        try:
            self.threshold_obj = GridThreshold(self.hours)
        except:
            print('Grid threshold not available for {:3d} hours duration'.format(self.hours))
            self.threshold_obj = Threshold(self.hours)
        self.total_alerts = None

    def detect_alerts(self):
        if isinstance(self.threshold_obj, GridThreshold):
            self.total_alerts = (self.serie.accumul > self.threshold_obj.grid).astype(np.int16)
            return self.total_alerts

        alerts_low = (self.serie.accumul >
                      self.threshold_obj.low).astype(np.int16)
        alerts_medium = (self.serie.accumul >
                         self.threshold_obj.medium).astype(np.int16)
        alerts_high = (self.serie.accumul >
                       self.threshold_obj.high).astype(np.int16)
        self.total_alerts = alerts_low + alerts_medium + alerts_high
        return self.total_alerts

    def get_masked_alerts(self):
        alerts = self.detect_alerts()
        mask = self.get_mask()
        return alerts * mask

    def save_alerts(self, out_dir):
        if self.total_alerts is None:
            self.detect_alerts()
        tif_basename = self.TIF_BASENAME.format(self.hours)
        tif_abspath = os.path.join(out_dir, tif_basename)
        array2tiff(self.total_alerts, tif_abspath)

    def save_masked_alerts(self, out_dir):
        tif_basename = self.TIF_BASENAME.format(self.hours)
        tif_abspath = os.path.join(out_dir, tif_basename)
        array2tiff(self.get_masked_alerts(), tif_abspath)

    def get_mask(self):
        config = configparser.ConfigParser()
        config.read(THRESHOLDS_ABSPATH)
        mask_filename = config['Files']['mask']
        mask_dirname = os.path.dirname(THRESHOLDS_ABSPATH)
        mask_abspath = os.path.join(mask_dirname, mask_filename)
        gpm_mask = tiff2array(mask_abspath)
        return np.fliplr(gpm_mask.T)
