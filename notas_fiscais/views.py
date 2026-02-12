

import requests
import re
from collections import OrderedDict

from django.conf import settings
from django import forms
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from decimal import Decimal

# Decorators e modelos do seu projeto
from accounts.decorators import (
    subscription_required, module_access_required, check_employee_permission
)
from accounts.models import Venda
from .models import NotaFiscal
from .forms import EmissaoNotaFiscalForm


# =========================
# Utilitários Multi-tenant
# =========================

def only_digits(s):
    return re.sub(r'\D', '', s or '')

def normalize_ibge(code):
    """Força IBGE com 7 dígitos (ex.: Contagem-MG = 3118601)."""
    code = only_digits(code)
    return code.zfill(7) if code else code

def normalize_cep(code):
    return only_digits(code).zfill(8) if code else code

def get_focus_credentials(user):
    """
    Permite token por tenant no futuro. Hoje usa tokens do settings.
    """
    base_url = getattr(settings, "FOCUS_API_URL", None)
    if not base_url:
        base_url = "https://homologacao.focusnfe.com.br" if settings.DEBUG else "https://api.focusnfe.com.br"

    if "homologacao" in base_url:
        api_token = settings.NFE_TOKEN_HOMOLOGACAO
    else:
        api_token = settings.NFE_TOKEN_PRODUCAO

    return base_url, api_token

def nfse_envia_aliquota():
    """Feature flag controlada em settings para NFSe Nacional."""
    return bool(getattr(settings, "FOCUS_NFSE_ENVIA_PALIQUOTA", False))

def nfse_tp_ret_default():
    """1 = sem retenção, 2 = com retenção."""
    return int(getattr(settings, "FOCUS_NFSE_TP_RETENCAO_DEFAULT", 1))


# =========================
# LISTAGEM / CONSULTA / EXCLUSÃO
# =========================

@login_required
@subscription_required
@module_access_required('fiscal')
@check_employee_permission('can_access_notas_fiscais')
def lista_notas_fiscais_view(request):
    notas_list = NotaFiscal.objects.filter(user=request.user).select_related('cliente', 'venda')

    status_filter = request.GET.get('status', '')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if status_filter:
        notas_list = notas_list.filter(status=status_filter)
    if start_date:
        notas_list = notas_list.filter(data_criacao__date__gte=start_date)
    if end_date:
        notas_list = notas_list.filter(data_criacao__date__lte=end_date)

    paginator = Paginator(notas_list, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'status_choices': NotaFiscal.STATUS_CHOICES,
        'status_filter': status_filter,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'notas_fiscais/lista_notas.html', context)


from accounts.services_asaas import AsaasMarketplaceService



@login_required
@subscription_required
@module_access_required('fiscal')
@check_employee_permission('can_access_notas_fiscais')
def emitir_nota_view(request, venda_id):
    venda = get_object_or_404(Venda, id=venda_id, user=request.user)
    perfil = request.user.company_profile
    
    primeiro_item = venda.itens.first()
    if not primeiro_item:
        messages.error(request, "Esta venda não possui itens para emissão.")
        return redirect('lista_notas_fiscais')

    tipo_produto = str(getattr(primeiro_item.produto, "tipo", "")).upper().strip()
    eh_servico = (tipo_produto == 'SERVICO')

    if hasattr(venda, 'nota_fiscal') and venda.nota_fiscal:
        messages.info(request, "Já existe uma nota fiscal para esta venda.")
        return redirect('lista_notas_fiscais')

    if request.method == 'POST':
        form = EmissaoNotaFiscalForm(request.POST, eh_servico=eh_servico)
        if form.is_valid():
            service = AsaasMarketplaceService()

            try:
                # 1. Sincroniza Cliente
                asaas_customer_id = service.get_or_create_asaas_customer(perfil, venda.cliente)
                
                if not asaas_customer_id:
                    raise ValueError("Não foi possível sincronizar o cliente com o Asaas.")

                # 2. Cria registro local
                nova_nota = NotaFiscal.objects.create(
                    user=request.user,
                    venda=venda,
                    cliente=venda.cliente,
                    valor_total=venda.valor_total_liquido,
                    modelo='NFSE' if eh_servico else 'NFE',
                    status='PENDENTE'
                )

                dados_emissao = {
                    'asaas_customer_id': asaas_customer_id,
                    'natureza_operacao': form.cleaned_data['natureza_operacao'],
                    'cfop': form.cleaned_data.get('cfop'),
                    'info_adicional': form.cleaned_data.get('informacoes_adicionais')
                }

                # 3. ETAPA 1: Cria o Pagamento no Asaas
                resposta = service.emitir_nota_com_cobranca(perfil, venda, dados_emissao)
                print(f"DEBUG ASAAS PAGAMENTO: {resposta}")

                if 'id' in resposta and not resposta.get('non_json_error'):
                    pay_id = resposta['id']
                    id_referencia = pay_id # Fallback inicial é o ID do pagamento

                    # 4. ETAPA 2: Se for Serviço, agenda a nota separadamente (Fluxo Oficial)
                    if eh_servico:
                        res_nota = service.agendar_nfse_por_payment(perfil, pay_id, venda)
                        print(f"DEBUG ASAAS AGENDAMENTO NOTA: {res_nota}")
                        
                        if 'id' in res_nota:
                            id_referencia = res_nota['id'] # Se agendou, usamos o ID da nota (inv_...)
                        else:
                            messages.warning(request, "Pagamento criado, mas o agendamento da nota falhou. Verifique os dados fiscais.")

                    # 5. Salva e finaliza
                    nova_nota.ref_id = id_referencia
                    nova_nota.status = 'PROCESSANDO'
                    nova_nota.save()
                    messages.success(request, f"Processo iniciado com sucesso! Referência: {id_referencia}")
                
                else:
                    # Captura erros de decodificação ou erros da API
                    erros_list = resposta.get('errors', [{}])
                    erro_msg = erros_list[0].get('description', 'Erro na comunicação com a API Asaas.')
                    nova_nota.status = 'ERRO'
                    nova_nota.mensagem_erro = erro_msg
                    nova_nota.save()
                    messages.error(request, f"Erro no Asaas: {erro_msg}")

            except Exception as e:
                messages.error(request, f"Erro interno: {str(e)}")
            
            return redirect('lista_notas_fiscais')

    else:
        form = EmissaoNotaFiscalForm(eh_servico=eh_servico)

    return render(request, 'notas_fiscais/emitir_nota.html', {
        'form': form, 
        'venda': venda, 
        'eh_servico': eh_servico 
    })




@login_required
def consultar_nota_view(request, nota_id):
    # 1. Localiza a nota e prepara o serviço
    nota = get_object_or_404(NotaFiscal, id=nota_id, user=request.user)
    
    if nota.modelo == 'NFE':
        messages.info(request, "Vendas de produtos (Laboratório) não geram invoices de serviço no Asaas.")
        return redirect('lista_notas_fiscais')

    from accounts.services_asaas import AsaasMarketplaceService
    service = AsaasMarketplaceService()
    perfil = request.user.company_profile
    # Usamos o método centralizado para garantir os headers de Accept: application/json
    headers = service.get_common_headers(perfil.asaas_api_key)

    try:
        current_id = nota.ref_id
        
        # 2. SE FOR ID DE PAGAMENTO (pay_), BUSCA A NOTA VINCULADA
        if current_id.startswith('pay_'):
            url_v = f"{service.base_url}/payments/{current_id}/invoices"
            res_v = requests.get(url_v, headers=headers, timeout=service.timeout)
            # Proteção contra erro de decodificação
            dados_v = service.safe_json(res_v)
            
            if res_v.status_code == 200 and not dados_v.get('non_json_error'):
                if dados_v.get('data') and len(dados_v['data']) > 0:
                    current_id = dados_v['data'][0].get('id')
                    nota.ref_id = current_id
                    nota.save()
                else:
                    messages.info(request, "O Asaas ainda está processando o agendamento desta nota.")
                    return redirect('lista_notas_fiscais')
            else:
                # Log detalhado no terminal sem quebrar a tela
                print(f"DEBUG VINCULO: Status {res_v.status_code} - Erro: {dados_v}")
                messages.warning(request, "Não foi possível localizar uma nota para este pagamento.")
                return redirect('lista_notas_fiscais')

        # 3. CONSULTA OS DETALHES DA NOTA REAL (inv_...)
        url_f = f"{service.base_url}/invoices/{current_id}"
        response = requests.get(url_f, headers=headers, timeout=service.timeout)
        dados = service.safe_json(response)
        
        # AQUI ESTÁ A PROTEÇÃO: Só processamos se o status for 200 e for um JSON válido
        if response.status_code == 200 and not dados.get('non_json_error'):
            status_asaas = dados.get('status')
            
            if status_asaas == 'AUTHORIZED':
                nota.status = 'EMITIDA'
                nota.numero_nf = dados.get('number')
                nota.url_pdf = dados.get('pdfUrl')
                nota.url_xml = dados.get('xmlUrl')
                messages.success(request, f"Nota #{nota.numero_nf} emitida com sucesso!")
            
            elif status_asaas == 'ERROR':
                nota.status = 'ERRO'
                ve = dados.get('validationErrors') or []
                nota.mensagem_erro = ve[0].get('description') if ve else 'Erro fiscal desconhecido'
                messages.error(request, f"Erro fiscal: {nota.mensagem_erro}")
            
            else:
                # Caso status seja SCHEDULED, SYNCHRONIZED, etc.
                messages.info(request, f"Status no Asaas: {status_asaas}. Tente novamente em instantes.")
            
            nota.save()
        else:
            # Captura erros 404, 500 ou HTML de erro do Asaas
            print(f"DEBUG CONSULTA: Status {response.status_code} - Erro: {dados}")
            messages.error(request, f"Erro na consulta (Status {response.status_code}). Verifique o terminal.")

    except Exception as e:
        messages.error(request, f"Erro técnico na consulta: {str(e)}")

    return redirect('lista_notas_fiscais')


@login_required
def excluir_nota_view(request, nota_id):
    nota = get_object_or_404(NotaFiscal, id=nota_id, user=request.user)
    if nota.status in ['EMITIDA', 'PROCESSANDO']:
        messages.error(request, "Você não pode excluir uma nota fiscal já emitida ou em processamento.")
    else:
        nota.delete()
        messages.success(request, "Nota fiscal excluída com sucesso.")
    return redirect('lista_notas_fiscais')