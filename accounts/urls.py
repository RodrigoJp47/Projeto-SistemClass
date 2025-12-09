from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    # Autenticação
    login_view,
    logout_view,

    # Páginas Principais
    home,
    contas_pagar,
    contas_receber,
    dre_view,
    orcamento_anual_view,
    fornecedor_view,
    clientes,
    cadastrar_bancos_view,
    importar_ofx_view,
    

    # Dashboards
    dashboards,
    faturamento_dashboard_view,

    # Módulo Comercial
    comercial_cadastros_view,
    editar_produto_view, 
    editar_vendedor_view,
    vendas_view,
    cadastrar_cliente_rapido,
    metas_comerciais_view,
    orcamentos_venda_view,               
    converter_orcamento_venda_view,
    precificacao_view,
    salvar_e_atualizar_precificacao_view,
    assinatura_view,
    register_view,
    search_cities,
    gerar_laudo_financeiro,
    gerar_laudo_comercial,
    gerenciamento_contratos_view,
    contaazul_auth_redirect,
    contaazul_callback,
    bpo_dashboard_view,
    switch_to_client_view,
    stop_managing_view,
    manage_users_view,
    company_profile_view,
    smart_redirect_view,
    editar_cliente_view,
    relatorios_view,
    configurar_inter_view,
)

urlpatterns = [
    # --- Autenticação ---
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', register_view, name='register'),

    # --- Páginas Principais ---
    path('', home, name='home'),
    path('contas-pagar/', contas_pagar, name='contas_pagar'),
    path('contas-receber/', contas_receber, name='contas_receber'),
    path('dre/', dre_view, name='dre'),
    path('financeiro/orcamento-anual/', orcamento_anual_view, name='orcamento_anual'),
    path('fornecedores/', fornecedor_view, name='fornecedores'),
    path('clientes/', clientes, name='clientes'),
    path('configuracoes/cadastrar-bancos/', cadastrar_bancos_view, name='cadastrar_bancos'),
    path('configuracoes/importar-ofx/', importar_ofx_view, name='importar_ofx'),
    path('configuracoes/perfil-empresa/', company_profile_view, name='company_profile'),
    
    path('configuracoes/relatorios/', relatorios_view, name='relatorios_central'),

    # --- Dashboards ---
    path('dashboards/', dashboards, name='dashboards'),

    path('configuracoes/inter/', configurar_inter_view, name='configurar_inter'),
   
    # --- Módulo Comercial ---
    path('faturamento/', faturamento_dashboard_view, name='faturamento_dashboard'),
    path('comercial/cadastros/', comercial_cadastros_view, name='comercial_cadastros'),
    path('comercial/produto/editar/<int:pk>/', editar_produto_view, name='editar_produto'),
    path('comercial/vendedor/editar/<int:pk>/', editar_vendedor_view, name='editar_vendedor'),
    path('comercial/vendas/', vendas_view, name='vendas'),
    path('comercial/metas/', metas_comerciais_view, name='metas_comerciais'),
    path('comercial/precificacao/salvar-e-atualizar/', salvar_e_atualizar_precificacao_view, name='salvar_e_atualizar_precificacao'),
    path('comercial/precificacao/', precificacao_view, name='precificacao'),
    path('comercial/orcamentos/', orcamentos_venda_view, name='orcamentos_venda'),
    path('comercial/orcamento/converter/<int:pk>/', converter_orcamento_venda_view, name='converter_orcamento'),
    path('search-cities/', search_cities, name='search_cities'),
    path('assinatura/', assinatura_view, name='assinatura'),

    path('gerar-laudo/', gerar_laudo_financeiro, name='gerar_laudo_financeiro'),
    path('gerar-laudo-comercial/', gerar_laudo_comercial, name='gerar_laudo_comercial'),
    path('comercial/contratos/', gerenciamento_contratos_view, name='gerenciamento_contratos'),

    path('contaazul/auth/', contaazul_auth_redirect, name='contaazul_auth'),
    path('contaazul/callback/', contaazul_callback, name='contaazul_callback'),

    path('bpo/dashboard/', bpo_dashboard_view, name='bpo_dashboard'),
    path('bpo/switch/<int:client_id>/', switch_to_client_view, name='switch_to_client'),
    path('bpo/stop/', stop_managing_view, name='stop_managing'),

    path('gerenciar-usuarios/', manage_users_view, name='manage_users'),
    path('redirect/', smart_redirect_view, name='smart_redirect'),
    
    path('comercial/cliente/editar/<int:pk>/', editar_cliente_view, name='editar_cliente'),
    # --- API (Interface para comunicação interna) ---
    path('api/cadastrar-cliente-rapido/', cadastrar_cliente_rapido, name='cadastrar_cliente_rapido'),
]