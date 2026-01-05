from django.urls import path
from . import views

urlpatterns = [
    path('pipeline/', views.crm_kanban_view, name='crm_pipeline'),
    path('ajax/mover/', views.mover_oportunidade_ajax, name='mover_oportunidade'),
    path('converter/<int:op_id>/', views.converter_para_orcamento, name='crm_converter_orcamento'),
]