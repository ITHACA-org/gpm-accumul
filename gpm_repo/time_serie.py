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
            self._adj_array = tiff2array(THRESH_ADJ_ABSPATH).T
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


class AlertDetector:
    TIF_BASENAME = 'alerts_{:03d}h.tif'

    def __init__(self, serie):
        if not isinstance(serie, PrecipTimeSerie):
            raise ValueError
        self.serie = serie
        self.hours = int(serie.duration.total_seconds() // 3600)
        self.threshold_obj = Threshold(self.hours)
        self.total_alerts = None

    def detect_alerts(self):
        alerts_low = (self.serie.accumul >
                      self.threshold_obj.low).astype(np.int16)
        alerts_medium = (self.serie.accumul >
                         self.threshold_obj.medium).astype(np.int16)
        alerts_high = (self.serie.accumul >
                       self.threshold_obj.high).astype(np.int16)
        self.total_alerts = alerts_low + alerts_medium + alerts_high
        return self.total_alerts

    def save_alerts(self, out_dir):
        if self.total_alerts is None:
            self.detect_alerts()
        tif_basename = self.TIF_BASENAME.format(self.hours)
        tif_abspath = os.path.join(out_dir, tif_basename)
        array2tiff(self.total_alerts, tif_abspath)