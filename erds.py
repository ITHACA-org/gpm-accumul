import glob
import os
import datetime

from gpm_repo import gpm_wrapper
from gpm_repo.credentials import DATADIR
from gpm_repo.gpm_ftp import GPMFTP
from gpm_repo.gpm_wrapper import GPM_FFORMAT
from gpm_repo.time_serie import PrecipTimeSerie, AlertDetector
from gpm_repo.rain_chart import PrecipCalBuilder


UPDATE_FILE = 'update.txt'
UPDATE_ABSPATH = os.path.join(DATADIR, UPDATE_FILE)
DATETIME_FORMAT = '%Y-%m-%dT%H:%M%z'
TIFF_FFORMAT = 'precip_{:03d}h.tif'


def mirror_gpm_site():
    # since the maximum cumulate is 144h, we need 288 files to build it
    print('Mirroring FTP site')
    n_gpm_files = 192
    with GPMFTP() as ftp:
        ftp.grab_latest_nfiles(n_gpm_files, DATADIR)
    # delete old files
    gpm_filelist = glob.glob(os.path.join(DATADIR, GPM_FFORMAT))
    gpm_filelist.sort()
    if len(gpm_filelist) > n_gpm_files:
        for gpm_file in gpm_filelist[: -n_gpm_files]:
            try:
                os.remove(gpm_file)
            except OSError:
                print('Cannot remove old gpm file: ' + gpm_file)


def compare_dates():
    try:
        with open(UPDATE_ABSPATH, 'r') as update_file:
            update_file.readline()
            datetime_str = update_file.readline()
        erds_update = datetime.datetime.strptime(datetime_str, DATETIME_FORMAT)
    except FileNotFoundError:
        is_up_to_date = False
        return is_up_to_date
    print('ERDS latest update is on: ', erds_update.isoformat())

    gpm_filelist = glob.glob(os.path.join(DATADIR, GPM_FFORMAT))
    gpm_filelist.sort()
    latest_gpm_obj = gpm_wrapper.GPMImergeWrapper(gpm_filelist[-1])
    gpmfiles_update = latest_gpm_obj.end_dt
    print('GPM latest file ends on: ', gpmfiles_update.isoformat())

    delta = gpmfiles_update - erds_update
    if delta.total_seconds() > 120:
        print('ERDS is not up-to-date with the GPM data')
        is_up_to_date = False
    else:
        print('ERDS is up-to-date with the GPM data available')
        is_up_to_date = True
    return is_up_to_date


def compare_precip(serie):
    alert_detect = AlertDetector(serie)
    alert_detect.save_masked_alerts(DATADIR)


def cumulate(hours):
    duration = datetime.timedelta(hours=hours)
    serie = PrecipTimeSerie.latest(duration, DATADIR)
    tif_abspath = os.path.join(DATADIR, TIFF_FFORMAT.format(hours))
    serie.save_accumul(tif_abspath)
    return serie


def generate_alerts():
    cumulate_hours = [12, 24, 48, 72, 96]
    cumulate_hours.sort(reverse=True)

    # the first serie is built from scratch
    hours = cumulate_hours[0]
    print('Working on', str(hours), 'hours accumulation... ')
    longest_serie = cumulate(hours)
    compare_precip(longest_serie)
    # the other series are subserie of the previous
    for hours in cumulate_hours[1:]:
        print('Working on', str(hours), 'hours accumulation... ')
        duration = datetime.timedelta(hours=hours)
        serie = longest_serie.latest_subserie(duration)
        tif_abspath = os.path.join(DATADIR, TIFF_FFORMAT.format(hours))
        serie.save_accumul(tif_abspath)
        compare_precip(serie)

    # filter precipitation on the basis of the alerts
    pcb = PrecipCalBuilder(longest_serie)
    pcb.store_series()
    pcb.delete_old()

    # write update file
    if serie.measurements:
        with open(UPDATE_ABSPATH, 'w') as update_file:
            update_file.write('latest measure ended at:\n')
            update_file.write(
                serie.measurements[-1].end_dt.strftime(DATETIME_FORMAT))


def start():
    mirror_gpm_site()
    is_up_to_date = compare_dates()
    if not is_up_to_date:
        print('Updating ERDS -', 'start time:',
              datetime.datetime.utcnow().isoformat())
        generate_alerts()
    print('Stop time:', datetime.datetime.utcnow().isoformat())


if __name__ == '__main__':
    start()
