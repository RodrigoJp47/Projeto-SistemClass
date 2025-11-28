from accounts.decorators import check_employee_permission

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Empresa, Quadro, Cartao, ChecklistItem
from .forms import EmpresaForm, QuadroForm, CartaoForm, ChecklistItemForm
from django.views.decorators.http import require_POST
from django.http import HttpResponse, HttpResponseForbidden # 3. Adicione HttpResponse
from django.db.models import F, FloatField, ExpressionWrapper # 4. Adicione para calcular progresso
from django.db.models.functions import Coalesce # 4. Adicione para calcular progresso
import json
from django.template.loader import render_to_string

@check_employee_permission('can_access_tarefas')
def home(request):
    if request.method == 'POST':
        form = EmpresaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Empresa cadastrada com sucesso!')
            return redirect('home')
    else:
        form = EmpresaForm()
    return render(request, 'home.html', {'form': form})


@check_employee_permission('can_access_tarefas')
def listar_empresas(request):
    empresas = Empresa.objects.all()
    return render(request, 'lista_empresas.html', {'empresas': empresas})


@check_employee_permission('can_access_tarefas')
def editar_empresa(request, id):
    empresa = get_object_or_404(Empresa, id=id)
    if request.method == 'POST':
        form = EmpresaForm(request.POST, instance=empresa)
        if form.is_valid():
            form.save()
            messages.success(request, 'Empresa atualizada com sucesso!')
            return redirect('listar_empresas')
    else:
        form = EmpresaForm(instance=empresa)
    return render(request, 'editar_empresa.html', {'form': form, 'empresa': empresa})


@check_employee_permission('can_access_tarefas')
def deletar_empresa(request, id):
    empresa = get_object_or_404(Empresa, id=id)
    if request.method == 'POST':
        empresa.delete()
        messages.success(request, 'Empresa deletada com sucesso!')
        return redirect('listar_empresas')
    return render(request, 'confirmar_delete.html', {'empresa': empresa})


@check_employee_permission('can_access_tarefas')
def listar_quadros(request, empresa_id):
    empresa = get_object_or_404(Empresa, id=empresa_id)
    if request.method == 'POST':
        form = QuadroForm(request.POST)
        if form.is_valid():
            quadro = form.save(commit=False)
            quadro.empresa = empresa
            quadro.save()
            messages.success(request, 'Novo quadro criado com sucesso!')
            return redirect('listar_quadros', empresa_id=empresa.id)
    
    form = QuadroForm()
    quadros_da_empresa = empresa.quadros.all()
    contexto = {
        'empresa': empresa,
        'quadros': quadros_da_empresa,
        'form': form
    }
    return render(request, 'lista_quadros.html', contexto)


# Em core/views.py, SUBSTITUA a view 'detalhes_quadro' inteira por esta:

@check_employee_permission('can_access_tarefas')
def detalhes_quadro(request, quadro_id):
    quadro = get_object_or_404(Quadro, id=quadro_id)

    if request.method == 'POST':
        # Esta view agora só processará o 'CartaoForm'
        form = CartaoForm(request.POST, request.FILES)
        if form.is_valid():
            cartao = form.save(commit=False)
            cartao.quadro = quadro
            cartao.save()
            messages.success(request, 'Novo cartão adicionado com sucesso!')
            # NÃO recarregue a página, o HTMX fará isso
            # return redirect('detalhes_quadro', quadro_id=quadro.id) 
            # Apenas re-renderize as colunas (se você estiver usando htmx para o form de cartão)
            # ou simplesmente retorne o redirect, se preferir.
            # Por simplicidade, vamos manter o redirect:
            return redirect('detalhes_quadro', quadro_id=quadro.id)
    else:
        form = CartaoForm()

    # --- Lógica do Checklist (NOVO) ---
    
    # Forms para adicionar itens
    form_agendamento = ChecklistItemForm()
    form_pendencia = ChecklistItemForm()

    # Buscando os itens
    agendamentos = quadro.checklist_items.filter(tipo='agendamento')
    pendencias = quadro.checklist_items.filter(tipo='pendencia')

    # Calculando progresso (ex: 3 de 5 concluídos = 60%)
    def calcular_progresso(queryset):
        if not queryset.exists():
            return 0
        total = queryset.count()
        concluidos = queryset.filter(concluido=True).count()
        return (concluidos / total) * 100

    progresso_agendamentos = calcular_progresso(agendamentos)
    progresso_pendencias = calcular_progresso(pendencias)

    # --- Fim da Lógica do Checklist ---

    # Lógica original das colunas
    cartoes_fixo = quadro.cartoes.filter(status='fixo')
    cartoes_fazer = quadro.cartoes.filter(status='fazer')
    cartoes_andamento = quadro.cartoes.filter(status='andamento')
    cartoes_concluido = quadro.cartoes.filter(status='concluido')

    contexto = {
        'quadro': quadro,
        'form': form,
        'cartoes_fixo': cartoes_fixo,
        'cartoes_fazer': cartoes_fazer,
        'cartoes_andamento': cartoes_andamento,
        'cartoes_concluido': cartoes_concluido,
        
        # --- Contexto do Checklist (NOVO) ---
        'form_agendamento': form_agendamento,
        'form_pendencia': form_pendencia,
        'agendamentos': agendamentos,
        'pendencias': pendencias,
        'progresso_agendamentos': progresso_agendamentos,
        'progresso_pendencias': progresso_pendencias,
        # --- Fim do Contexto do Checklist ---
    }
    return render(request, 'detalhes_quadro.html', contexto)


@check_employee_permission('can_access_tarefas')
def editar_quadro(request, quadro_id):
    quadro = get_object_or_404(Quadro, id=quadro_id)
    if request.method == 'POST':
        form = QuadroForm(request.POST, instance=quadro)
        if form.is_valid():
            form.save()
            messages.success(request, 'Quadro atualizado com sucesso!')
            return redirect('listar_quadros', empresa_id=quadro.empresa.id)
    else:
        form = QuadroForm(instance=quadro)
    return render(request, 'editar_quadro.html', {'form': form, 'quadro': quadro})


@check_employee_permission('can_access_tarefas')
def deletar_quadro(request, quadro_id):
    quadro = get_object_or_404(Quadro, id=quadro_id)
    empresa_id = quadro.empresa.id
    if request.method == 'POST':
        quadro.delete()
        messages.success(request, 'Quadro deletado com sucesso!')
        return redirect('listar_quadros', empresa_id=empresa_id)
    return render(request, 'confirmar_delete_quadro.html', {'quadro': quadro})


@check_employee_permission('can_access_tarefas')
def editar_cartao(request, cartao_id):
    cartao = get_object_or_404(Cartao, id=cartao_id)
    if request.method == 'POST':
        # Adicionado request.FILES para lidar com o upload de anexos na edição
        form = CartaoForm(request.POST, request.FILES, instance=cartao)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cartão atualizado com sucesso!')
            return redirect('detalhes_quadro', quadro_id=cartao.quadro.id)
    else:
        form = CartaoForm(instance=cartao)
    return render(request, 'editar_cartao.html', {'form': form, 'cartao': cartao})


@check_employee_permission('can_access_tarefas')
def deletar_cartao(request, cartao_id):
    cartao = get_object_or_404(Cartao, id=cartao_id)
    quadro_id = cartao.quadro.id
    if request.method == 'POST':
        cartao.delete()
        messages.success(request, 'Cartão deletado com sucesso!')
        return redirect('detalhes_quadro', quadro_id=quadro_id)
    return render(request, 'confirmar_delete_cartao.html', {'cartao': cartao})


@check_employee_permission('can_access_tarefas')
@require_POST
def atualizar_status_cartoes(request, quadro_id):
    quadro = get_object_or_404(Quadro, id=quadro_id)

    # Lógica correta para receber os dados das 4 colunas
    ids_fixo = request.POST.getlist('fixo')
    ids_fazer = request.POST.getlist('fazer')
    ids_andamento = request.POST.getlist('andamento')
    ids_concluido = request.POST.getlist('concluido')

    Cartao.objects.filter(id__in=ids_fixo).update(status='fixo')
    Cartao.objects.filter(id__in=ids_fazer).update(status='fazer')
    Cartao.objects.filter(id__in=ids_andamento).update(status='andamento')
    Cartao.objects.filter(id__in=ids_concluido).update(status='concluido')
    
    contexto = {
        'quadro': quadro,
        'cartoes_fixo': quadro.cartoes.filter(status='fixo'),
        'cartoes_fazer': quadro.cartoes.filter(status='fazer'),
        'cartoes_andamento': quadro.cartoes.filter(status='andamento'),
        'cartoes_concluido': quadro.cartoes.filter(status='concluido'),
    }
    
    return render(request, 'partials/_colunas_quadro.html', contexto)


@check_employee_permission('can_access_tarefas')
@require_POST
def adicionar_checklist_item(request, quadro_id, tipo):
    quadro = get_object_or_404(Quadro, id=quadro_id)
    if tipo not in ['agendamento', 'pendencia']:
        return HttpResponseForbidden("Tipo inválido")
        
    form = ChecklistItemForm(request.POST)
    if form.is_valid():
        item = form.save(commit=False)
        item.quadro = quadro
        item.tipo = tipo
        item.save()
        
        # --- INÍCIO DA NOVA LÓGICA ---
        
        # 1. Renderiza SÓ o novo item para uma string
        #    (Assumindo que 'partials/_checklist_item.html' existe,
        #     o que é verdade baseado no seu _checklist_coluna.html)
        item_html = render_to_string('partials/_checklist_item.html', {'item': item, 'quadro': quadro})

        # 2. Recalcula o progresso
        items_do_tipo = quadro.checklist_items.filter(tipo=tipo)
        total = items_do_tipo.count()
        concluidos = items_do_tipo.filter(concluido=True).count()
        progresso = (concluidos / total) * 100 if total > 0 else 0
        
        # 3. Prepara o contexto SÓ para a barra de progresso
        context = {
            'progresso': progresso, 
            'tipo': tipo
        }
        
        # 4. Renderiza SÓ a barra de progresso
        #    (O 'partials/_checklist_progresso.html' será colocado
        #     dentro do #progresso-container-{{ tipo_id }} pelo HTMX)
        response = render(request, 'partials/_checklist_progresso.html', context)
        
        # 5. Dispara o gatilho para o JavaScript
        #    Envia o 'tipo' e o 'html' do novo item
        response['HX-Trigger-After-Swap'] = json.dumps({
            "itemAdicionado": {
                "tipo": tipo,
                "html": item_html
            }
        })
        
        return response
        
        # --- FIM DA NOVA LÓGICA ---
        
    # Se o form for inválido, re-renderiza a coluna com os erros
    # (Esta parte ainda pode recarregar a página, mas o caminho feliz está corrigido)
    # TODO: Tratar o form inválido via HTMX também
    messages.error(request, 'Ocorreu um erro ao adicionar o item.')
    return redirect('detalhes_quadro', quadro_id=quadro.id)

@check_employee_permission('can_access_tarefas')
@require_POST
def toggle_checklist_item(request, item_id):
    item = get_object_or_404(ChecklistItem, id=item_id)
    # (Opcional: Verifique se o request.user tem permissão neste quadro)
    
    item.concluido = not item.concluido
    item.save()
    
    # Recalcula o progresso
    quadro = item.quadro
    tipo = item.tipo
    items_do_tipo = quadro.checklist_items.filter(tipo=tipo)
    total = items_do_tipo.count()
    concluidos = items_do_tipo.filter(concluido=True).count()
    progresso = (concluidos / total) * 100 if total > 0 else 0

    # Retorna o item atualizado E a barra de progresso
    context = {
        'item': item, 
        'progresso': progresso, 
        'tipo': tipo,
        'swap': True # Flag para o HTMX
    }
    
    # Retorna dois HTMLs: o item atualizado e a barra de progresso
    return render(request, 'partials/_checklist_item_e_progresso.html', context)


@check_employee_permission('can_access_tarefas')
@require_POST # Por segurança, use POST para deleção com HTMX
def deletar_checklist_item(request, item_id):
    item = get_object_or_404(ChecklistItem, id=item_id)
    # (Opcional: Verifique se o request.user tem permissão neste quadro)
    quadro = item.quadro
    tipo = item.tipo
    item.delete()
    
    # Recalcula o progresso e retorna SÓ a barra de progresso
    items_do_tipo = quadro.checklist_items.filter(tipo=tipo)
    total = items_do_tipo.count()
    concluidos = items_do_tipo.filter(concluido=True).count()
    progresso = (concluidos / total) * 100 if total > 0 else 0

    context = {'progresso': progresso, 'tipo': tipo}
    
    # Retorna uma barra de progresso atualizada e uma resposta vazia para o item (que foi deletado)
    response = render(request, 'partials/_checklist_progresso.html', context)
    response['HX-Trigger'] = json.dumps({
        "itemDeletado": {
            "item_id": item_id
        }
    })

    return response