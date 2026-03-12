from django.urls import path
from . import views
from .views import compress_view, download_compressed

urlpatterns = [
    path('', compress_view, name='compress_view'),
    path('download/', download_compressed, name='download_compressed'),
    path('download/rgb/', views.download_recon_rgb, name='download_recon_rgb'),
    path('download/bw/', views.download_recon_bw, name='download_recon_bw'),
]
