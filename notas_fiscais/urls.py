# notas_fiscais/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path(
        '', 
        views.lista_notas_fiscais_view, 
        name='lista_notas_fiscais'
    ),
    path(
        'emitir/<int:venda_id>/', 
        views.emitir_nota_view, 
        name='emitir_nota'
    ),
    # --- ESTA É A LINHA QUE FALTAVA NO SEU ARQUIVO ---
    path(
        'consultar/<str:ref_id>/', 
        views.consultar_nota_view, 
        name='consultar_nota'
    ),
    # -------------------------------------------------
    path('excluir/<int:nota_id>/', views.excluir_nota_view, name='excluir_nota'),
]