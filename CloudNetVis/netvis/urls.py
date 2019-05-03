from django.contrib import admin 
from django.urls import include, path
from django.conf.urls import url
from netvis import views

urlpatterns = [
    url(r'^$', views.Index, name='Index'),
    url(r'^jsonet/$', views.LoadJsoNet, name='LoadJsoNet'),
] 
