import requests
import json
from datetime import datetime, timedelta
from decimal import Decimal
from django.conf import settings
from .models import (
    OmieCredentials, PayableAccount, ReceivableAccount, 
    Category, BankAccount, ClassificacaoAutomatica
)

OMIE_API_URL = "https://app.omie.com.br/api/v1"

def get_mock_omie_data(call):
    """Retorna dados falsos idênticos aos da Omie para teste local."""
    
    if call == "ListarContasPagar":
        return {
            "pagina": 1,
            "total_de_paginas": 1,
            "registros": 2,
            "conta_pagar_cadastro": [
                {
                    "codigo_lancamento_omie": 99901,
                    "data_vencimento": "15/12/2025",
                    "valor_documento": 1600.00,
                    "status_titulo": "EM ABERTO",
                    "descricao": "Fornecedor de Teste 01",
                    "observacao": "Teste de inclusão",
                    "data_pagamento": ""
                },
                {
                    "codigo_lancamento_omie": 99902,
                    "data_vencimento": "10/12/2025",
                    "valor_documento": 200.00,
                    "status_titulo": "PAGO",
                    "descricao": "Conta de Luz CEMIG",
                    "observacao": "Teste de classificação automática",
                    "data_pagamento": "10/12/2025"
                }
            ]
        }
        
    elif call == "ListarContasReceber":
        return {
            "pagina": 1,
            "total_de_paginas": 1,
            "registros": 1,
            "conta_receber_cadastro": [
                {
                    "codigo_lancamento_omie": 88801,
                    "numero_documento": "NF 102030",
                    "data_vencimento": "20/12/2025",
                    "valor_documento": 5000.00,
                    "status_titulo": "RECEBIDO",
                    "observacao": "Venda Consultoria Teste",
                    "data_pagamento": "19/12/2025"
                }
            ]
        }
    return {}

def omie_request(endpoint, call, creds, params=None):

    # --- MODO DE TESTE LOCAL ---
    # Se estiver rodando localmente, não chama a API de verdade
    # if settings.DEBUG: 
    #     print(f"--- [MOCK OMIE] Simulando chamada: {call} ---")
    #     return get_mock_omie_data(call)
    # ---------------------------
    """
    Função genérica para fazer chamadas POST na API da Omie.
    """
    if params is None:
        params = []

    payload = {
        "call": call,
        "app_key": creds.app_key,
        "app_secret": creds.app_secret,
        "param": params
    }

    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(f"{OMIE_API_URL}/{endpoint}", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {'erro': f"Erro na requisição Omie ({call}): {str(e)}"}

def prever_classificacao_local(user, descricao, tipo):
    """
    Réplica local da lógica de previsão para evitar importação circular com views.py.
    """
    regras = ClassificacaoAutomatica.objects.filter(user=user, tipo=tipo)
    descricao_lower = descricao.lower()
    
    for regra in regras:
        if regra.termo.lower() in descricao_lower:
            return regra.categoria, regra.dre_area, regra.bank_account
            
    return None, None, None

def processar_contas_pagar_omie(user, creds):
    """
    Busca e sincroniza contas a pagar.
    """
    pagina = 1
    total_paginas = 1
    novos = 0
    atualizados = 0
    erros = []

    # Cria ou pega um banco virtual para vincular
    banco_omie, _ = BankAccount.objects.get_or_create(
        user=user, 
        bank_name='Integração Omie',
        defaults={'agency': '0000', 'account_number': 'OMIE', 'initial_balance': 0}
    )

    # Categoria Padrão de Fallback
    cat_padrao, _ = Category.objects.get_or_create(user=user, name='Despesas Gerais (Omie)', category_type='PAYABLE')

    while pagina <= total_paginas:
        # Parâmetros de filtro (pode adicionar data se quiser limitar o período)
        params = [{
            "pagina": pagina,
            "registros_por_pagina": 50,
            "apenas_importado_api": "N"
        }]

        data = omie_request("financas/contapagar/", "ListarContasPagar", creds, params)
        
        if 'erro' in data:
            return {'erro': data['erro']}

        total_paginas = data.get('total_de_paginas', 1)
        registros = data.get('conta_pagar_cadastro', [])

        for reg in registros:
            try:
                # Dados básicos da Omie
                id_omie = str(reg.get('codigo_lancamento_omie'))
                descricao = reg.get('descricao') or "Conta a Pagar Omie"
                observacao = reg.get('observacao') or ""
                valor = Decimal(str(reg.get('valor_documento', 0)))
                
                # Datas (Omie usa DD/MM/YYYY)
                dt_venc_str = reg.get('data_vencimento')
                due_date = datetime.strptime(dt_venc_str, "%d/%m/%Y").date() if dt_venc_str else datetime.now().date()
                
                # Status e Pagamento
                status_omie = reg.get('status_titulo') # "PAGO", "EM ABERTO"
                is_paid = (status_omie == "PAGO")
                
                payment_date = None
                if is_paid and reg.get('data_pagamento'):
                    payment_date = datetime.strptime(reg.get('data_pagamento'), "%d/%m/%Y").date()

                # --- LÓGICA DE BLINDAGEM ---
                
                # 1. Tenta buscar o registro existente pelo ID externo (Omie ID)
                conta_existente = PayableAccount.objects.filter(user=user, external_id=id_omie).first()

                if conta_existente:
                    # >>> CENÁRIO: ATUALIZAÇÃO (Blindado) <<<
                    # Atualizamos APENAS dados financeiros. Não tocamos em Categoria ou DRE.
                    conta_existente.amount = valor
                    conta_existente.due_date = due_date
                    conta_existente.is_paid = is_paid
                    conta_existente.payment_date = payment_date
                    
                    # Atualiza descrição apenas se estiver muito genérica antes
                    if "Importado" in conta_existente.description:
                        conta_existente.description = f"{descricao} - {observacao}"
                    
                    conta_existente.save()
                    atualizados += 1
                
                else:
                    # >>> CENÁRIO: NOVO REGISTRO (Inteligente) <<<
                    # Tenta prever a classificação
                    cat_prevista, dre_prevista, bank_previsto = prever_classificacao_local(user, descricao, 'PAYABLE')
                    
                    PayableAccount.objects.create(
                        user=user,
                        external_id=id_omie, # Vínculo chave
                        name=descricao[:200],
                        description=f"{descricao} {observacao} (Omie)",
                        due_date=due_date,
                        amount=valor,
                        is_paid=is_paid,
                        payment_date=payment_date,
                        
                        # Usa a previsão ou o padrão
                        category=cat_prevista if cat_prevista else cat_padrao,
                        dre_area=dre_prevista if dre_prevista else 'OPERACIONAL',
                        bank_account=bank_previsto if bank_previsto else banco_omie,
                        
                        payment_method='BOLETO', # Padrão
                        occurrence='AVULSO',
                        cost_type='VARIAVEL'
                    )
                    novos += 1

            except Exception as e:
                erros.append(f"Erro ID {id_omie}: {str(e)}")
        
        pagina += 1

    return {'novos': novos, 'atualizados': atualizados, 'erros': erros}

def processar_contas_receber_omie(user, creds):
    """
    Busca e sincroniza contas a receber.
    """
    pagina = 1
    total_paginas = 1
    novos = 0
    atualizados = 0
    erros = []

    banco_omie, _ = BankAccount.objects.get_or_create(
        user=user, 
        bank_name='Integração Omie',
        defaults={'agency': '0000', 'account_number': 'OMIE', 'initial_balance': 0}
    )

    cat_padrao, _ = Category.objects.get_or_create(user=user, name='Receitas de Vendas (Omie)', category_type='RECEIVABLE')

    while pagina <= total_paginas:
        params = [{
            "pagina": pagina,
            "registros_por_pagina": 50,
            "apenas_importado_api": "N"
        }]

        data = omie_request("financas/contareceber/", "ListarContasReceber", creds, params)
        
        if 'erro' in data:
            return {'erro': data['erro']}

        total_paginas = data.get('total_de_paginas', 1)
        registros = data.get('conta_receber_cadastro', [])

        for reg in registros:
            try:
                id_omie = str(reg.get('codigo_lancamento_omie'))
                # No receber, as vezes o nome do cliente vem separado, aqui simplificamos usando descrição
                descricao = reg.get('numero_documento') or "Recebimento Omie"
                observacao = reg.get('observacao') or ""
                valor = Decimal(str(reg.get('valor_documento', 0)))
                
                dt_venc_str = reg.get('data_vencimento')
                due_date = datetime.strptime(dt_venc_str, "%d/%m/%Y").date() if dt_venc_str else datetime.now().date()
                
                status_omie = reg.get('status_titulo')
                is_received = (status_omie == "RECEBIDO" or status_omie == "PAGO") # Omie as vezes usa PAGO pra receber também dependendo da versão
                
                payment_date = None
                if is_received and reg.get('data_pagamento'): # Data da baixa
                    payment_date = datetime.strptime(reg.get('data_pagamento'), "%d/%m/%Y").date()

                # --- BLINDAGEM ---
                conta_existente = ReceivableAccount.objects.filter(user=user, external_id=id_omie).first()

                if conta_existente:
                    conta_existente.amount = valor
                    conta_existente.due_date = due_date
                    conta_existente.is_received = is_received
                    conta_existente.payment_date = payment_date
                    conta_existente.save()
                    atualizados += 1
                else:
                    cat_prevista, dre_prevista, bank_previsto = prever_classificacao_local(user, descricao, 'RECEIVABLE')
                    
                    ReceivableAccount.objects.create(
                        user=user,
                        external_id=id_omie,
                        name=f"Cliente Omie - Doc {descricao}",
                        description=f"{observacao} (Integrado Omie)",
                        due_date=due_date,
                        amount=valor,
                        is_received=is_received,
                        payment_date=payment_date,
                        
                        category=cat_prevista if cat_prevista else cat_padrao,
                        dre_area=dre_prevista if dre_prevista else 'BRUTA',
                        bank_account=bank_previsto if bank_previsto else banco_omie,
                        
                        payment_method='BOLETO',
                        occurrence='AVULSO'
                    )
                    novos += 1

            except Exception as e:
                erros.append(f"Erro ID {id_omie}: {str(e)}")
        
        pagina += 1

    return {'novos': novos, 'atualizados': atualizados, 'erros': erros}

def sincronizar_omie_completo(user):
    """
    Função principal chamada pela View.
    """
    try:
        creds = user.omie_creds
    except OmieCredentials.DoesNotExist:
        return {'erro': 'Credenciais não encontradas.'}

    # Sincroniza Pagar
    res_pagar = processar_contas_pagar_omie(user, creds)
    if 'erro' in res_pagar: return res_pagar

    # Sincroniza Receber
    res_receber = processar_contas_receber_omie(user, creds)
    if 'erro' in res_receber: return res_receber

    return {
        'pagar_novos': res_pagar['novos'],
        'pagar_atualizados': res_pagar['atualizados'],
        'receber_novos': res_receber['novos'],
        'receber_atualizados': res_receber['atualizados'],
        'erros': res_pagar['erros'] + res_receber['erros']
    }