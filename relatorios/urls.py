from django.urls import path
from . import views

urlpatterns = [
    path('fluxo-analitico/', views.fluxo_caixa_analitico, name='fluxo_caixa_analitico'),
    path('fluxo-analitico/excel/', views.exportar_fluxo_excel, name='exportar_fluxo_excel'),
    path('fluxo-analitico/pdf/', views.exportar_fluxo_pdf, name='exportar_fluxo_pdf'),
]