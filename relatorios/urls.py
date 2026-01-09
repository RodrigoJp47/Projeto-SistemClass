from django.urls import path
from . import views

urlpatterns = [
    path('fluxo-analitico/', views.fluxo_caixa_analitico, name='fluxo_caixa_analitico'),
]