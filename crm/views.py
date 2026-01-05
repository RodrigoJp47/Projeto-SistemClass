from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
import json
from django.utils import timezone

# Seus modelos
from accounts.models import OrcamentoVenda, Cliente, Vendedor, ProdutoServico
from .models import FunilEtapa, Oportunidade, Interacao

@login_required
def crm_kanban_view(request):
    """
    View principal do Kanban: Gerencia a exibição, criação de oportunidades e garante as etapas padrão.
    """
    
    # 1. SETUP DE COLUNAS (AJUSTADO PARA CRIAR "NEGADO")
    # Lista de etapas que DEVEM existir no sistema
    etapas_obrigatorias = [
        {'nome': 'Prospecção', 'cor': '#3498db', 'ordem': 0},
        {'nome': 'Contato Feito', 'cor': '#f1c40f', 'ordem': 1},
        {'nome': 'Proposta Enviada', 'cor': '#e67e22', 'ordem': 2},
        {'nome': 'Negociação', 'cor': '#9b59b6', 'ordem': 3},
        {'nome': 'Fechamento', 'cor': '#2ecc71', 'ordem': 4},
        {'nome': 'Negado', 'cor': '#e74c3c', 'ordem': 5} # <--- Nova Coluna Vermelha
    ]

    for etapa_info in etapas_obrigatorias:
        # Verifica se a etapa já existe pelo nome. Se não, cria.
        if not FunilEtapa.objects.filter(user=request.user, nome=etapa_info['nome']).exists():
            FunilEtapa.objects.create(
                user=request.user, 
                nome=etapa_info['nome'], 
                ordem=etapa_info['ordem'], 
                cor_hexa=etapa_info['cor']
            )

    # 2. SALVAR NOVA OPORTUNIDADE (POST)
    if request.method == 'POST' and request.POST.get('action') == 'create_new':
        titulo = request.POST.get('titulo')
        cliente_id = request.POST.get('cliente')
        valor = request.POST.get('valor') or 0
        
        # Pega a primeira etapa (Prospecção)
        primeira_etapa = FunilEtapa.objects.filter(user=request.user, nome='Prospecção').first()
        # Se por algum motivo não achar pelo nome, pega a primeira por ordem
        if not primeira_etapa:
             primeira_etapa = FunilEtapa.objects.filter(user=request.user).order_by('ordem').first()

        cliente_obj = get_object_or_404(Cliente, id=cliente_id, user=request.user)
        
        Oportunidade.objects.create(
            user=request.user,
            titulo=titulo,
            cliente=cliente_obj,
            etapa=primeira_etapa,
            valor_estimado=valor,
            status='ABERTO'
        )
        messages.success(request, "Oportunidade criada com sucesso!")
        return redirect('crm_pipeline')

    # 3. EXIBIÇÃO
    etapas = FunilEtapa.objects.filter(user=request.user).order_by('ordem')
    
    kanban_data = {}
    for etapa in etapas:
        kanban_data[etapa] = Oportunidade.objects.filter(
            user=request.user, 
            etapa=etapa, 
            status='ABERTO'
        ).select_related('cliente', 'vendedor').order_by('-updated_at')

    # Dados para o Modal
    clientes = Cliente.objects.filter(user=request.user)
    vendedores = Vendedor.objects.filter(user=request.user)
    
    # Importante: Garanta que ProdutoServico esteja importado no topo do arquivo
    try:
        from accounts.models import ProdutoServico
        produtos = ProdutoServico.objects.filter(user=request.user)
    except ImportError:
        produtos = []

    context = {
        'kanban_data': kanban_data,
        'clientes': clientes,
        'vendedores': vendedores,
        'produtos': produtos,
    }
    return render(request, 'crm/kanban.html', context)

@login_required
@csrf_exempt 
def mover_oportunidade_ajax(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            oportunidade_id = data.get('oportunidade_id')
            nova_etapa_id = data.get('etapa_id')
            
            op = get_object_or_404(Oportunidade, id=oportunidade_id, user=request.user)
            nova_etapa = get_object_or_404(FunilEtapa, id=nova_etapa_id, user=request.user)
            
            op.etapa = nova_etapa
            op.save()
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Método inválido'}, status=400)


@login_required
def converter_para_orcamento(request, op_id):
    oportunidade = get_object_or_404(Oportunidade, pk=op_id, user=request.user)
    
    # Se já existe, redireciona para editar ele
    if oportunidade.orcamento_gerado:
        # MUDANÇA AQUI: Adiciona o parametro ?editar_id=...
        return redirect(f"/comercial/orcamentos/?editar_id={oportunidade.orcamento_gerado.id}")

    # Cria validade de 7 dias
    validade = timezone.now().date() + timezone.timedelta(days=7)
    
    novo_orcamento = OrcamentoVenda.objects.create(
        user=request.user,
        cliente=oportunidade.cliente,
        vendedor=oportunidade.vendedor,
        data_validade=validade,
        status='PENDENTE',
        observacoes=f"Gerado automaticamente a partir da Oportunidade: {oportunidade.titulo}"
    )
    
    oportunidade.orcamento_gerado = novo_orcamento
    
    # Move para etapa "Proposta Enviada" (lógica mantida)
    etapa_proposta = FunilEtapa.objects.filter(user=request.user, nome__icontains="Proposta").first()
    if etapa_proposta:
        oportunidade.etapa = etapa_proposta
    
    oportunidade.save()
    
    messages.success(request, "Orçamento criado! Preencha os itens abaixo.")
    
    # MUDANÇA AQUI: Redireciona forçando a abertura do formulário
    return redirect(f"/comercial/orcamentos/?editar_id={novo_orcamento.id}")