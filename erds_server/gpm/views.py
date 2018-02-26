from django.http import (HttpResponse, HttpResponseBadRequest, JsonResponse, HttpResponseServerError,
                         HttpResponseNotFound)
from django.shortcuts import render
from django.urls import reverse

from gpm_repo.rain_chart import PrecipCalReader


def index(request):
    return HttpResponse("Hello, precipitation time serie will be available through this app!")


def time_series(request, lon, lat, time_period_hours):
    lon_f = float(lon)
    if lon_f < -180 or lon_f > 180:
        return HttpResponseBadRequest('Longitude value {} is not in the valid range -180 --> 180'.format(lon))

    lat_f = float(lat)
    if lat_f < -60 or lat_f > 60:
        return HttpResponseBadRequest('Latitude value {} is not in the valid GPM range -60 --> 60'.format(lat))

    hours = int(time_period_hours)

    try:
        pcr_obj = PrecipCalReader.get_latest()
    except Exception as e:
        return HttpResponseServerError(e.message)

    try:
        rain_data = pcr_obj.get_rain_series(lon_f, lat_f, hours)
    except Exception as e:
        return HttpResponseNotFound('{0} --> Lon: {1} | Lat: {2}'.format(str(e), lon, lat))

    rain_data_list = rain_data.tolist()
    return JsonResponse({'mm': rain_data_list})


def time_series_chart(request, lon, lat, time_period_hours):
    kw = {'lat': lat, 'lon': lon, 'time_period_hours': time_period_hours}
    url = reverse('gpm:time_series', kwargs=kw)

    context = {'json_url': url}
    return render(request, 'gpm/chart.html', context)
