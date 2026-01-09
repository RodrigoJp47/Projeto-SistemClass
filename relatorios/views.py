

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from accounts.models import PayableAccount, ReceivableAccount
import calendar # <--- Adicione isso junto com os outros imports
# O login_required vem direto do Django
from django.contrib.auth.decorators import login_required 

# Os outros vêm do seu arquivo de decorators customizados
from accounts.decorators import subscription_required, check_employee_permission, module_access_required

@login_required
@subscription_required
@module_access_required('financial') # Garante que a empresa tem o módulo financeiro
@check_employee_permission('can_access_fluxo_caixa')
def fluxo_caixa_analitico(request):
    # --- 1. CONFIGURAÇÕES INICIAIS ---
    ano_get = request.GET.get('ano', str(timezone.now().year))
    try:
        ano_atual = int(str(ano_get).replace('.', ''))
    except ValueError:
        ano_atual = timezone.now().year

    # Captura os modos de visualização
    view_mode = request.GET.get('view', 'mensal') # 'mensal' ou 'diario'
    status_view = request.GET.get('status_view', 'realizado') # 'realizado' ou 'projetado' (NOVO)
    mes_atual = int(request.GET.get('mes', timezone.now().month))

    # --- 2. DEFINIR COLUNAS (MESES ou DIAS) ---
    if view_mode == 'diario':
        _, num_dias = calendar.monthrange(ano_atual, mes_atual)
        colunas_ids = range(1, num_dias + 1)
        colunas_labels = [str(d) for d in colunas_ids]
    else:
        colunas_ids = range(1, 13)
        colunas_labels = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

    # --- 3. PROCESSAMENTO ---
    def processar_fluxo(modelo, is_field):
        # Define qual campo de data usar (Vencimento ou Pagamento)
        campo_data = 'payment_date' if status_view == 'realizado' else 'due_date'
        
        filtro_base = {
            'user': request.user,
            f'{campo_data}__year': ano_atual # Filtra ano pelo campo dinâmico
        }
        
        # Lógica do Status:
        # Se for 'realizado', OBRIGA a estar pago (is_paid=True).
        # Se for 'projetado', não filtramos o status (mostra pagos e abertos).
        if status_view == 'realizado':
            filtro_base[f'{is_field}'] = True

        # Se for diário, filtra o mês específico
        if view_mode == 'diario':
            filtro_base[f'{campo_data}__month'] = mes_atual

        # Busca NOMES únicos
        nomes = modelo.objects.filter(**filtro_base).values_list('name', flat=True).distinct().order_by('name')
        
        dados = []
        totais_coluna = {c: 0 for c in colunas_ids}
        total_geral_ano = 0

        for nome in nomes:
            valores_periodo = []
            total_linha = 0
            
            for col in colunas_ids:
                filtro_celula = filtro_base.copy()
                filtro_celula['name'] = nome
                
                # Filtra dia ou mês usando o campo de data dinâmico
                if view_mode == 'diario':
                    filtro_celula[f'{campo_data}__day'] = col
                else:
                    filtro_celula[f'{campo_data}__month'] = col

                valor = modelo.objects.filter(**filtro_celula).aggregate(Sum('amount'))['amount__sum'] or 0
                
                valores_periodo.append(valor)
                total_linha += valor
                totais_coluna[col] += valor
            
            dados.append({'nome': nome, 'valores': valores_periodo, 'total': total_linha})
            total_geral_ano += total_linha
            
        return dados, list(totais_coluna.values()), total_geral_ano

    # Executa a lógica
    dados_receita, totais_receita_col, total_receitas_ano = processar_fluxo(ReceivableAccount, 'is_received')
    dados_despesa, totais_despesa_col, total_despesas_ano = processar_fluxo(PayableAccount, 'is_paid')

    # --- 4. SALDO LÍQUIDO ---
    saldo_mensal = []
    saldo_acumulado = 0
    for i, _ in enumerate(colunas_ids):
        saldo = totais_receita_col[i] - totais_despesa_col[i]
        saldo_mensal.append(saldo)
        saldo_acumulado += saldo

    context = {
        'ano': ano_atual,
        'mes': mes_atual,
        'view_mode': view_mode,
        'status_view': status_view, # Passamos a nova variável para o template
        'colunas_labels': colunas_labels,
        'dados_receita': dados_receita,
        'totais_receita_col': totais_receita_col,
        'total_receitas_ano': total_receitas_ano,
        'dados_despesa': dados_despesa,
        'totais_despesa_col': totais_despesa_col,
        'total_despesas_ano': total_despesas_ano,
        'saldo_mensal': saldo_mensal,
        'saldo_acumulado_ano': saldo_acumulado,
    }
    
    return render(request, 'relatorios/fluxo_analitico.html', context)