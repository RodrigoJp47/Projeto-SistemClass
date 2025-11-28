# Crie este novo arquivo: core/urls.py

from django.urls import path
from .views import (
    home, listar_empresas, editar_empresa, deletar_empresa,
    listar_quadros, editar_quadro, deletar_quadro,
    detalhes_quadro, editar_cartao, deletar_cartao,
    atualizar_status_cartoes, adicionar_checklist_item, toggle_checklist_item, deletar_checklist_item
)

# IMPORTANTE: Vamos renomear a 'name' da view 'home' para evitar conflito
# com a 'home' principal do seu app 'accounts'.
urlpatterns = [
    path('', home, name='tarefas_home'), # Renomeado de 'home' para 'tarefas_home'
    
    path('lista/', listar_empresas, name='listar_empresas'),
    path('editar/<int:id>/', editar_empresa, name='editar_empresa'),
    path('deletar/<int:id>/', deletar_empresa, name='deletar_empresa'),
    
    path('empresa/<int:empresa_id>/quadros/', listar_quadros, name='listar_quadros'),
    path('quadro/editar/<int:quadro_id>/', editar_quadro, name='editar_quadro'),
    path('quadro/deletar/<int:quadro_id>/', deletar_quadro, name='deletar_quadro'),
    
    path('quadro/<int:quadro_id>/', detalhes_quadro, name='detalhes_quadro'),
    path('cartao/editar/<int:cartao_id>/', editar_cartao, name='editar_cartao'),
    path('cartao/deletar/<int:cartao_id>/', deletar_cartao, name='deletar_cartao'),
    path('quadro/<int:quadro_id>/atualizar-status/', atualizar_status_cartoes, name='atualizar_status_cartoes'),
    # ========== INÍCIO DO NOVO BLOCO ==========
    # Adicione estas 3 linhas para o checklist
    
    path('quadro/<int:quadro_id>/checklist/add/<str:tipo>/', adicionar_checklist_item, name='adicionar_checklist_item'),
    path('checklist/toggle/<int:item_id>/', toggle_checklist_item, name='toggle_checklist_item'),
    path('checklist/delete/<int:item_id>/', deletar_checklist_item, name='deletar_checklist_item'),
    
    # ========== FIM DO NOVO BLOCO ==========
]