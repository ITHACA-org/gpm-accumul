from django.urls import path, re_path

from . import views

app_name = 'gpm'

urlpatterns = [
    path('', views.index, name='index'),
    re_path(r'^time_series/(?P<lon>-?\d+.?\d*)/(?P<lat>-?\d+.?\d*)/(?P<time_period_hours>\d+)/$',
            views.time_series, name='time_series'),
    re_path(r'^chart/(?P<lon>-?\d+.?\d*)/(?P<lat>-?\d+.?\d*)/(?P<time_period_hours>\d+)/$',
            views.time_series_chart, name='time_series_chart')
]