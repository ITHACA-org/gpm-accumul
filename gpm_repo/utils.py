import os

import h5py
import numpy as np
from osgeo import gdal, osr


def array2tiff(array, out_abspath):
    if not os.path.isabs(out_abspath):
        raise ValueError("The path provided is not absolute")
    if not isinstance(array, np.ndarray):
        raise ValueError("The array provided is not a valid numpy array")
    gdal.AllRegister()
    driver = gdal.GetDriverByName('Gtiff')
    geotransform = (-180, 0.1, 0, -90, 0, 0.1)
    outDataset_options = ['COMPRESS=LZW']
    dtype = gdal.GDT_Int16
    if array.dtype == np.float32:
        dtype = gdal.GDT_Float32
    outDataset = driver.Create(out_abspath, array.shape[0], array.shape[1],
                               1, dtype, outDataset_options)
    outDataset.SetGeoTransform(geotransform)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    outDataset.SetProjection(srs.ExportToWkt())
    outband = outDataset.GetRasterBand(1)
    outband.WriteArray(array.T)
    outband.GetStatistics(0, 1)
    outband = None
    outDataset = None


def tiff2array(tif_abspath):
    ds = gdal.Open(tif_abspath, gdal.GA_ReadOnly)
    array = ds.GetRasterBand(1).ReadAsArray()
    return array


def get_gpm_lats(h5abspath):
    f = h5py.File(h5abspath, 'r')
    ds = f['/Grid/lat']
    lats = ds[()]
    f.close()
    return lats


def get_gpm_lons(h5abspath):
    f = h5py.File(h5abspath, 'r')
    ds = f['/Grid/lon']
    lons = ds[()]
    f.close()
    return lons
