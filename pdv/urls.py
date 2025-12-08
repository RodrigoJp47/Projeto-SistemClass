# pdv/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Página principal do PDV
    path('', views.frente_caixa_view, name='pdv_operacao'),
    # path('caixa/gerenciar/', views.gerenciar_caixa, name='gerenciar_caixa'),
    path('imprimir-cupom/<int:venda_id>/', views.imprimir_cupom_view, name='imprimir_cupom'),
    path('api/emitir-nfce/<int:venda_id>/', views.emitir_nfce_pdv, name='api_emitir_nfce'),
    path('api/dados-caixa/', views.dados_conferencia_caixa, name='api_dados_caixa'),
    # APIs usadas pelo Javascript do PDV
    path('api/buscar-produto/', views.buscar_produto_api, name='api_buscar_produto'),
    path('api/finalizar-venda/', views.finalizar_venda_pdv, name='api_finalizar_venda'),
    path('api/movimento-caixa/', views.registrar_movimento_caixa, name='api_movimento_caixa'),
    path('api/fechar-caixa/', views.fechar_caixa_pdv, name='api_fechar_caixa'),
    path('api/abrir-caixa/', views.abrir_caixa_pdv, name='api_abrir_caixa'),
]