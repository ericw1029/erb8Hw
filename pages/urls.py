from django.urls import path
from . import views

# url define here is the endpoint e.g. xx/xxx/xxx/about
app_name = "pages"

urlpatterns = [
    path("", views.import_csv, name="import_csv"),
    path("<str:model_type>", views.export_csv, name="export_csv"),
    path("download-error-log/<str:filename>/", views.download_error_log, name="download_error_log",),
]
