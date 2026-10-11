from django.urls import include, re_path as url

urlpatterns = [
    url(r'', include('stub_app.urls')),
]
