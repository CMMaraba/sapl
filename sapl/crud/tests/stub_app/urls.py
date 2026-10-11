from django.urls import include, re_path as url

from .views import CityCrud, CountryCrud

urlpatterns = [
    url(r'^country/', include(
        CountryCrud.get_urls() + CityCrud.get_urls(), 'stub_app')),
]
