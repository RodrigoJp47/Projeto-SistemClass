import requests
import re
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from decimal import Decimal

# Importe seus decoradores e modelos
from accounts.decorators import (
    subscription_required, module_access_required, check_employee_permission
)
from accounts.models import Venda
from .models import NotaFiscal
from .forms import EmissaoNotaFiscalForm

# --- VIEW 1: Lista de Notas Fiscais ---

@login_required
@subscription_required
@module_access_required('fiscal')
@check_employee_permission('can_access_notas_fiscais')
def lista_notas_fiscais_view(request):
    # (request.user aqui é o DONO da licença, graças ao seu middleware)
    
    notas_list = NotaFiscal.objects.filter(user=request.user).select_related('cliente', 'venda')
    
    # Lógica de Filtros
    status_filter = request.GET.get('status', '')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if status_filter:
        notas_list = notas_list.filter(status=status_filter)
    if start_date:
        notas_list = notas_list.filter(data_criacao__date__gte=start_date)
    if end_date:
        notas_list = notas_list.filter(data_criacao__date__lte=end_date)
        
    paginator = Paginator(notas_list, 15) # 15 por página
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


@login_required
@subscription_required
@module_access_required('fiscal')
@check_employee_permission('can_access_notas_fiscais')
def emitir_nota_view(request, venda_id):
    venda = get_object_or_404(Venda, id=venda_id, user=request.user)
    
    if hasattr(venda, 'nota_fiscal') and venda.nota_fiscal:
        messages.info(request, f"Já existe uma nota fiscal para esta venda.")
        return redirect('lista_notas_fiscais')

    if request.method == 'POST':
        form = EmissaoNotaFiscalForm(request.POST)
        if form.is_valid():
            
            # Ambiente Focus (Dinâmico baseado no DEBUG)
            if settings.DEBUG:
                BASE_URL = "https://homologacao.focusnfe.com.br"
                API_TOKEN = settings.NFE_TOKEN_HOMOLOGACAO
            else:
                BASE_URL = "https://api.focusnfe.com.br"
                API_TOKEN = settings.NFE_TOKEN_PRODUCAO

            primeiro_item = venda.itens.first()
            eh_servico = primeiro_item and primeiro_item.produto.tipo == 'SERVICO'

            # --- 1. CARREGA DADOS DO PERFIL (DINÂMICO) ---
            try:
                perfil = request.user.company_profile
                if not perfil.cnpj: raise ValueError("CNPJ da empresa não configurado.")
                
                # Limpeza de caracteres para envio (Remove pontos, traços, barras)
                cnpj_emitente = perfil.cnpj.replace(".", "").replace("/", "").replace("-", "")
                im_emitente = perfil.inscricao_municipal.replace(".", "").replace("-", "").replace("/", "").strip() if perfil.inscricao_municipal else ""
                # Garante que código do município só tenha números
                cod_mun_emitente = perfil.codigo_municipio.replace(".", "").replace("-", "").strip() if perfil.codigo_municipio else ""
                
            except Exception as e:
                messages.error(request, "Erro no perfil da empresa: " + str(e))
                return redirect('company_profile')

            nova_nota = NotaFiscal.objects.create(
                user=request.user,
                venda=venda,
                cliente=venda.cliente,
                valor_total=venda.valor_total_liquido,
                status='PENDENTE'
            )

            try:
                cliente = venda.cliente
                if not cliente.logradouro or not cliente.numero or not cliente.bairro:
                    raise ValueError("Endereço do cliente incompleto.")

                # ==========================================================
                # LÓGICA A: EMISSÃO DE NOTA DE SERVIÇO (NFS-e) - SAAS DINÂMICO
                # ==========================================================
                if eh_servico:
                    URL_API = f"{BASE_URL}/v2/nfse?ref={nova_nota.id}"
                    if settings.DEBUG:
                        URL_API += "&dry_run=1"
                    
                    discriminacao = "; ".join([f"{i.quantidade:.0f}x {i.produto.nome}" for i in venda.itens.all()])
                    cod_servico = primeiro_item.produto.codigo_servico
                    if not cod_servico:
                        raise ValueError(f"O serviço '{primeiro_item.produto.nome}' não tem o 'Cód. Serviço (LC116)' cadastrado.")

                    # Monta dados do Prestador dinamicamente
                    prestador_data = {
                        "cnpj": cnpj_emitente,
                        "inscricao_municipal": im_emitente,
                        "codigo_municipio": cod_mun_emitente,
                        "iss_retido": False,
                        "optante_simples_nacional": perfil.optante_simples_nacional,
                        "incentivador_cultural": perfil.incentivador_cultural,
                    }

                    if perfil.regime_especial_tributacao and perfil.regime_especial_tributacao != '0':
                        prestador_data["regime_especial_tributacao"] = perfil.regime_especial_tributacao

                    # Monta dados do Serviço
                    servico_data = {
                        "item_lista_servico": cod_servico,
                        "discriminacao": discriminacao[:2000], # Limite Focus
                        "valor_servicos": float(venda.valor_total_liquido),
                    }

                    if not perfil.optante_simples_nacional:
                        servico_data["aliquota"] = float(perfil.aliquota_iss or 2.0)

                    # --- MONTAGEM DO PAYLOAD FINAL ---
                    dados_api = {
                        "data_emissao": timezone.now().strftime("%Y-%m-%dT%H:%M:%S"),
                        "serie_rps": "1",
                        "natureza_operacao": "1",
                        "prestador": prestador_data,
                        "tomador": {
                             "cnpj_cpf": re.sub(r'\D', '', cliente.cpf_cnpj or ''),
                             "razao_social": (cliente.razao_social or cliente.nome)[:115],
                             "email": cliente.email,
                             "endereco": {
                                "logradouro": cliente.logradouro,
                                "numero": cliente.numero,
                                "bairro": cliente.bairro,
                                "cep": re.sub(r'\D', '', cliente.cep or ''), # CORREÇÃO: Limpeza total do CEP
                                "codigo_municipio": cliente.codigo_municipio,
                                "uf": cliente.uf
                            }
                        },
                        "servico": servico_data
                    }
                # ==========================================================
                # LÓGICA B: EMISSÃO DE NOTA DE PRODUTO (NF-e)
                # ==========================================================
                else:
                    URL_API = f"{BASE_URL}/v2/nfe?ref={nova_nota.id}"
                    
                    itens_api = []
                    for item in venda.itens.all():
                        if not item.produto.ncm: raise ValueError(f"Produto {item.produto.nome} sem NCM.")
                        
                        itens_api.append({
                            "nome_produto": item.produto.nome,
                            "ncm": item.produto.ncm.replace(".", ""),
                            "quantidade": f"{item.quantidade:.2f}",
                            "valor_unitario": f"{item.preco_unitario:.2f}",
                            "unidade_medida": item.produto.unidade_medida,
                            "origem_produto": item.produto.origem,
                            "cfop": form.cleaned_data['cfop'],
                            
                            # Ajuste de ICMS simples para SaaS (Melhorar futuramente com regras fiscais)
                            "icms_situacao_tributaria": "102" if perfil.optante_simples_nacional else "00",
                        })

                    dados_api = {
                        "data_emissao": timezone.now().strftime("%Y-%m-%dT%H:%M:%S"),
                        "natureza_operacao": form.cleaned_data['natureza_operacao'],
                        "cnpj_emitente": cnpj_emitente,
                        "nome_destinatario": cliente.razao_social or cliente.nome,
                        "email_destinatario": cliente.email,
                        "cpf_cnpj_destinatario": re.sub(r'\D', '', cliente.cpf_cnpj or ''),
                        "logradouro_destinatario": cliente.logradouro,
                        "numero_destinatario": cliente.numero,
                        "itens": itens_api
                    }

                # --- DEBUG PAYLOAD EMISSÃO ---
                print("\n=== DEBUG PAYLOAD EMISSÃO ===")
                print(f"URL: {URL_API}")
                print(f"Token: {API_TOKEN[:4]}...{API_TOKEN[-4:]}")
                print(f"Payload: {dados_api}")
                print("=============================\n")
                # -----------------------------

                # --- 2. ENVIA PARA API FOCUS ---
                response = requests.post(URL_API, json=dados_api, auth=(API_TOKEN, ""))
                
                resposta_api = response.json()
                
                # --- DEBUG NO TERMINAL ---
                print("\n--- CONSULTA API FOCUS ---")
                print(f"Status Code: {response.status_code}")
                print(f"Resposta: {resposta_api}")
                print("--------------------------\n")
                # -------------------------
                
                if response.status_code in [200, 201, 202]:
                    status_api = resposta_api.get('status')
                    
                    if status_api == 'autorizado':
                        nova_nota.status = 'EMITIDA'
                        nova_nota.numero_nf = resposta_api.get('numero')
                        nova_nota.serie = resposta_api.get('serie')
                        # NFSe usa 'codigo_verificacao', NFe usa 'chave_nfe'
                        nova_nota.chave_acesso = resposta_api.get('codigo_verificacao', resposta_api.get('chave_nfe'))
                        nova_nota.data_emissao = timezone.now() 
                        nova_nota.url_pdf = resposta_api.get('url_danfe') or resposta_api.get('url')
                        nova_nota.url_xml = resposta_api.get('url_xml')
                        nova_nota.save()
                        messages.success(request, f"Nota Fiscal Nº {nova_nota.numero_nf} foi autorizada!")
                    
                    elif status_api in ['erro_autorizacao', 'rejeitado', 'cancelado']:
                        nova_nota.status = 'ERRO'
                        
                        # 2. CORREÇÃO DA LEITURA DE ERRO (Lista vs Texto)
                        lista_erros = resposta_api.get('erros', [])
                        if lista_erros and isinstance(lista_erros, list):
                            # Junta as mensagens da lista (Padrão NFSe)
                            msg_final = " | ".join([f"{e.get('codigo', '')}: {e.get('mensagem', '')}" for e in lista_erros])
                        else:
                            # Padrão NFe ou mensagem simples
                            msg_final = resposta_api.get('status_sefaz_mensagem', resposta_api.get('mensagem', 'Erro desconhecido'))

                        nova_nota.mensagem_erro = msg_final
                        nova_nota.save()
                        messages.error(request, f"Erro na nota: {msg_final}")
                    
                    elif status_api in ['processando', 'processando_autorizacao']:
                        nova_nota.status = 'PROCESSANDO'
                        nova_nota.save()
                        messages.info(request, "A nota foi enviada e está em processamento. Clique no botão verificar para atualizar o status.")
                    
                    else:
                        messages.warning(request, f"Status atual: {status_api}")
                        
                else:
                    messages.error(request, f"Erro de comunicação: {resposta_api.get('mensagem', 'Sem resposta')}")
                    
            except Exception as e:
                messages.error(request, f"Erro interno: {e}")
            
            return redirect('lista_notas_fiscais')
                
    else:
        form = EmissaoNotaFiscalForm()

    return render(request, 'notas_fiscais/emitir_nota.html', {'form': form, 'venda': venda})


@login_required
@subscription_required
@module_access_required('fiscal')
@check_employee_permission('can_access_notas_fiscais')
def consultar_nota_view(request, nota_id): # <--- AJUSTADO PARA nota_id
    # Busca a nota no banco pelo ID (chave primária)
    nota = get_object_or_404(NotaFiscal, id=nota_id, user=request.user)
    
    # Ambiente Focus (Homologação ou Produção)
    BASE_URL = settings.FOCUS_API_URL
    
    if "homologacao" in BASE_URL:
        API_TOKEN = settings.NFE_TOKEN_HOMOLOGACAO
    else:
        API_TOKEN = settings.NFE_TOKEN_PRODUCAO

    # Verifica se é Serviço ou Produto
    primeiro_item = nota.venda.itens.first()
    eh_servico = primeiro_item and primeiro_item.produto.tipo == 'SERVICO'
    
    # Define a referência para busca na API
    # Como na emissão usamos ?ref={nova_nota.id}, aqui usamos o ID da nota como referência
    ref_focus = str(nota.id) 

    if eh_servico:
        URL_CONSULTA = f"{BASE_URL}/v2/nfse/{ref_focus}"
    else:
        URL_CONSULTA = f"{BASE_URL}/v2/nfe/{ref_focus}"

    try:
        response = requests.get(URL_CONSULTA, auth=(API_TOKEN, ""))
        dados = response.json()
        
        # --- DEBUG ---
        print(f"--- CONSULTA RETORNO ({response.status_code}) ---")
        print(dados)
        # -------------
        
        if response.status_code == 200:
            status_api = dados.get('status')
            
            if status_api == 'autorizado':
                nota.status = 'EMITIDA'
                nota.numero_nf = dados.get('numero')
                nota.serie = dados.get('serie')
                nota.chave_acesso = dados.get('codigo_verificacao', dados.get('chave_nfe'))
                # Ajuste para pegar a URL correta dependendo do retorno (NFSe as vezes vem em 'url')
                nota.url_pdf = dados.get('url_danfe') or dados.get('url')
                nota.url_xml = dados.get('url_xml')
                nota.save()
                messages.success(request, f"Nota atualizada: {status_api}")
                
            elif status_api in ['erro_autorizacao', 'rejeitado', 'cancelado']:
                
                # Tratamento de erro
                lista_erros = dados.get('erros', [])
                msg = ""
                codigo_erro = ""
                
                if lista_erros and isinstance(lista_erros, list):
                    msg = " | ".join([f"{e.get('mensagem')}" for e in lista_erros])
                    if len(lista_erros) > 0:
                        codigo_erro = lista_erros[0].get('codigo')
                else:
                    msg = dados.get('status_sefaz_mensagem', dados.get('mensagem', 'Erro desconhecido'))

                # --- BYPASS DE ERRO E45 EM HOMOLOGAÇÃO (MANTIDO) ---
                if settings.DEBUG and codigo_erro == 'E45':
                    print("=== BYPASS E45 ATIVADO ===")
                    nota.status = 'EMITIDA'
                    nota.numero_nf = 'SIMULACAO'
                    nota.serie = '1'
                    nota.chave_acesso = 'SIMULACAO_E45_BYPASS'
                    nota.url_pdf = '#' 
                    nota.mensagem_erro = "Nota simulada (Erro E45 ignorado em Homologação)"
                    nota.save()
                    messages.success(request, f"SUCESSO SIMULADO: O erro E45 foi ignorado.")
                # ---------------------------------------------------
                else:
                    nota.status = 'ERRO'
                    nota.mensagem_erro = msg
                    nota.save()
                    messages.error(request, f"Nota com erro: {msg}")
            
            elif status_api == 'processando_autorizacao':
                messages.info(request, "A nota ainda está em processamento. Tente novamente em alguns segundos.")

            else:
                messages.info(request, f"Status na API: {status_api}")
        
        else:
            messages.error(request, f"Erro ao consultar API: {dados.get('mensagem')}")

    except Exception as e:
        messages.error(request, f"Erro interno ao consultar: {e}")

    return redirect('lista_notas_fiscais')

@login_required
def excluir_nota_view(request, nota_id):
    # Busca a nota garantindo que pertence ao usuário logado
    nota = get_object_or_404(NotaFiscal, id=nota_id, user=request.user)
    
    # Só permite excluir se NÃO tiver sido emitida com sucesso
    if nota.status in ['EMITIDA', 'PROCESSANDO']:
        messages.error(request, "Você não pode excluir uma nota fiscal já emitida ou em processamento.")
    else:
        nota.delete()
        messages.success(request, "Nota fiscal excluída com sucesso.")
        
    return redirect('lista_notas_fiscais')