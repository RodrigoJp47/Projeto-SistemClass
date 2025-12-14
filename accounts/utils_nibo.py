# # accounts/utils_nibo.py

# import requests
# import json
# from datetime import datetime, timedelta
# from decimal import Decimal
# from django.conf import settings
# from .models import (
#     NiboCredentials, PayableAccount, ReceivableAccount, 
#     Category, BankAccount, ClassificacaoAutomatica
# )

# # URL Base da API V1 do Nibo
# NIBO_API_URL = "https://api.nibo.com.br/companies/v1"

# def nibo_request(endpoint, method, creds, params=None):
#     """
#     Função genérica para fazer chamadas na API do Nibo.
#     """
#     if params is None:
#         params = {}

#     url = f"{NIBO_API_URL}/{endpoint}"
    
#     headers = {
#         'Content-Type': 'application/json',
#         'Authorization': f'Bearer {creds.api_token}' # Padrão Bearer Token
#     }
    
#     try:
#         if method == 'GET':
#             response = requests.get(url, headers=headers, params=params)
#         elif method == 'POST':
#             response = requests.post(url, headers=headers, json=params)
            
#         response.raise_for_status()
#         return response.json()
#     except Exception as e:
#         return {'erro': f"Erro na requisição Nibo ({endpoint}): {str(e)}"}

# def prever_classificacao_local(user, descricao, tipo):
#     """
#     Réplica local da lógica de previsão (Idêntico ao utils_omie.py).
#     """
#     regras = ClassificacaoAutomatica.objects.filter(user=user, tipo=tipo)
#     descricao_lower = descricao.lower()
    
#     for regra in regras:
#         if regra.termo.lower() in descricao_lower:
#             return regra.categoria, regra.dre_area, regra.bank_account
            
#     return None, None, None

# def processar_contas_pagar_nibo(user, creds):
#     """
#     Busca e sincroniza contas a pagar do Nibo.
#     """
#     novos = 0
#     atualizados = 0
#     erros = []

#     # Cria ou pega um banco virtual para vincular
#     banco_nibo, _ = BankAccount.objects.get_or_create(
#         user=user, 
#         bank_name='Integração Nibo',
#         defaults={'agency': '0000', 'account_number': 'NIBO', 'initial_balance': 0}
#     )

#     # Categoria Padrão de Fallback
#     cat_padrao, _ = Category.objects.get_or_create(user=user, name='Despesas Gerais (Nibo)', category_type='PAYABLE')

#     # Nibo geralmente não usa paginação complexa em endpoints simples, ou usa skip/take.
#     # Vamos assumir buscar os agendamentos (Schedules) recentes.
#     endpoint = f"schedules/debit" # Endpoint hipotético padrão de débitos/pagar
    
#     # Busca itens
#     # Nota: A API do Nibo pode variar endpoints. Ajuste conforme doc oficial se necessário.
#     # Geralmente filtramos por data ou trazemos tudo.
#     data = nibo_request(endpoint, "GET", creds)
    
#     if 'erro' in data:
#         # Se falhar endpoint específico, tenta tratamento de erro ou endpoint alternativo
#         return {'erro': data['erro']}

#     # O Nibo retorna uma lista direta ou um objeto 'items'
#     registros = data.get('items', data) if isinstance(data, dict) else data

#     if not isinstance(registros, list):
#         registros = []

#     for reg in registros:
#         try:
#             # Mapeamento de campos do Nibo
#             id_nibo = str(reg.get('id') or reg.get('scheduleId'))
#             descricao = reg.get('description') or reg.get('stakeholderName') or "Conta Nibo"
#             observacao = reg.get('notes') or ""
#             valor = Decimal(str(reg.get('value', 0)))
            
#             # Tratamento de Data
#             dt_venc_str = reg.get('dueDate') # Ex: 2025-12-15T00:00:00
#             try:
#                 due_date = datetime.fromisoformat(dt_venc_str.replace('Z', '+00:00')).date()
#             except:
#                 due_date = datetime.now().date()
            
#             # Status
#             status_nibo = reg.get('status') # 'open', 'paid', 'scheduled'
#             is_paid = (status_nibo == 'paid' or status_nibo == 'settled')
            
#             payment_date = None
#             if is_paid:
#                 # Tenta pegar data de pagamento se existir
#                 dt_pgto = reg.get('paymentDate') or reg.get('accrualDate')
#                 if dt_pgto:
#                     payment_date = datetime.fromisoformat(dt_pgto.replace('Z', '+00:00')).date()
#                 else:
#                     payment_date = due_date

#             # --- LÓGICA DE BLINDAGEM (Idêntica ao Omie) ---
            
#             conta_existente = PayableAccount.objects.filter(user=user, external_id=id_nibo).first()

#             if conta_existente:
#                 # >>> CENÁRIO: ATUALIZAÇÃO (Blindado) <<<
#                 # Atualiza APENAS financeiro/status/datas. NÃO toca em Categoria/DRE.
#                 conta_existente.amount = valor
#                 conta_existente.due_date = due_date
#                 conta_existente.is_paid = is_paid
#                 conta_existente.payment_date = payment_date
                
#                 if "Importado" in conta_existente.description:
#                     conta_existente.description = f"{descricao} - {observacao}"
                
#                 conta_existente.save()
#                 atualizados += 1
            
#             else:
#                 # >>> CENÁRIO: NOVO REGISTRO (Inteligente) <<<
#                 cat_prevista, dre_prevista, bank_previsto = prever_classificacao_local(user, descricao, 'PAYABLE')
                
#                 PayableAccount.objects.create(
#                     user=user,
#                     external_id=id_nibo,
#                     name=descricao[:200],
#                     description=f"{descricao} {observacao} (Nibo)",
#                     due_date=due_date,
#                     amount=valor,
#                     is_paid=is_paid,
#                     payment_date=payment_date,
                    
#                     category=cat_prevista if cat_prevista else cat_padrao,
#                     dre_area=dre_prevista if dre_prevista else 'OPERACIONAL',
#                     bank_account=bank_previsto if bank_previsto else banco_nibo,
                    
#                     payment_method='BOLETO',
#                     occurrence='AVULSO',
#                     cost_type='VARIAVEL'
#                 )
#                 novos += 1

#         except Exception as e:
#             erros.append(f"Erro ID Nibo {id_nibo}: {str(e)}")
    
#     return {'novos': novos, 'atualizados': atualizados, 'erros': erros}

# def processar_contas_receber_nibo(user, creds):
#     """
#     Busca e sincroniza contas a receber do Nibo.
#     """
#     novos = 0
#     atualizados = 0
#     erros = []

#     banco_nibo, _ = BankAccount.objects.get_or_create(
#         user=user, 
#         bank_name='Integração Nibo',
#         defaults={'agency': '0000', 'account_number': 'NIBO', 'initial_balance': 0}
#     )

#     cat_padrao, _ = Category.objects.get_or_create(user=user, name='Receitas de Vendas (Nibo)', category_type='RECEIVABLE')

#     endpoint = f"schedules/credit" # Endpoint hipotético de créditos/receber

#     data = nibo_request(endpoint, "GET", creds)
    
#     if 'erro' in data:
#         return {'erro': data['erro']}

#     registros = data.get('items', data) if isinstance(data, dict) else data
#     if not isinstance(registros, list): registros = []

#     for reg in registros:
#         try:
#             id_nibo = str(reg.get('id') or reg.get('scheduleId'))
#             descricao = reg.get('description') or reg.get('stakeholderName') or "Recebimento Nibo"
#             observacao = reg.get('notes') or ""
#             valor = Decimal(str(reg.get('value', 0)))
            
#             dt_venc_str = reg.get('dueDate')
#             try:
#                 due_date = datetime.fromisoformat(dt_venc_str.replace('Z', '+00:00')).date()
#             except:
#                 due_date = datetime.now().date()
            
#             status_nibo = reg.get('status')
#             is_received = (status_nibo == 'received' or status_nibo == 'settled')
            
#             payment_date = None
#             if is_received:
#                 dt_pgto = reg.get('paymentDate') or reg.get('accrualDate')
#                 if dt_pgto:
#                     payment_date = datetime.fromisoformat(dt_pgto.replace('Z', '+00:00')).date()
#                 else:
#                     payment_date = due_date

#             # --- BLINDAGEM ---
#             conta_existente = ReceivableAccount.objects.filter(user=user, external_id=id_nibo).first()

#             if conta_existente:
#                 conta_existente.amount = valor
#                 conta_existente.due_date = due_date
#                 conta_existente.is_received = is_received
#                 conta_existente.payment_date = payment_date
#                 conta_existente.save()
#                 atualizados += 1
#             else:
#                 cat_prevista, dre_prevista, bank_previsto = prever_classificacao_local(user, descricao, 'RECEIVABLE')
                
#                 ReceivableAccount.objects.create(
#                     user=user,
#                     external_id=id_nibo,
#                     name=descricao[:200],
#                     description=f"{observacao} (Integrado Nibo)",
#                     due_date=due_date,
#                     amount=valor,
#                     is_received=is_received,
#                     payment_date=payment_date,
                    
#                     category=cat_prevista if cat_prevista else cat_padrao,
#                     dre_area=dre_prevista if dre_prevista else 'BRUTA',
#                     bank_account=bank_previsto if bank_previsto else banco_nibo,
                    
#                     payment_method='BOLETO',
#                     occurrence='AVULSO'
#                 )
#                 novos += 1

#         except Exception as e:
#             erros.append(f"Erro ID Nibo {id_nibo}: {str(e)}")
    
#     return {'novos': novos, 'atualizados': atualizados, 'erros': erros}

# def sincronizar_nibo_completo(user):
#     """
#     Função principal chamada pela View.
#     """
#     try:
#         creds = user.nibo_creds
#     except NiboCredentials.DoesNotExist:
#         return {'erro': 'Credenciais Nibo não encontradas.'}

#     # Sincroniza Pagar
#     res_pagar = processar_contas_pagar_nibo(user, creds)
#     if 'erro' in res_pagar: return res_pagar

#     # Sincroniza Receber
#     res_receber = processar_contas_receber_nibo(user, creds)
#     if 'erro' in res_receber: return res_receber

#     return {
#         'pagar_novos': res_pagar['novos'],
#         'pagar_atualizados': res_pagar['atualizados'],
#         'receber_novos': res_receber['novos'],
#         'receber_atualizados': res_receber['atualizados'],
#         'erros': res_pagar['erros'] + res_receber['erros']
#     }

import requests
import json
from datetime import datetime, timedelta
from decimal import Decimal
from django.conf import settings
from .models import (
    NiboCredentials, PayableAccount, ReceivableAccount, 
    Category, BankAccount, ClassificacaoAutomatica
)

# URL Base da API V1 do Nibo
NIBO_API_URL = "https://api.nibo.com.br/companies/v1"

def get_mock_nibo_data(endpoint):
    """
    Gera dados falsos para teste local quando o token for 'TESTE'.
    """
    hoje = datetime.now()
    amanha = hoje + timedelta(days=1)
    ontem = hoje - timedelta(days=1)

    # Formato ISO que o Nibo usa: "2025-12-15T00:00:00Z"
    fmt = "%Y-%m-%dT00:00:00Z"

    if "debit" in endpoint: # Simulando Contas a Pagar
        return {
            "items": [
                {
                    "scheduleId": "MOCK_PAGAR_01",
                    "description": "Fornecedor Fake LTDA (Teste Nibo)",
                    "value": 150.50,
                    "dueDate": amanha.strftime(fmt),
                    "status": "open", # Em aberto
                    "notes": "Teste de importação local"
                },
                {
                    "scheduleId": "MOCK_PAGAR_02",
                    "description": "CEMIG Energia (Teste Nibo)",
                    "value": 300.00,
                    "dueDate": ontem.strftime(fmt),
                    "status": "paid", # Pago
                    "paymentDate": ontem.strftime(fmt),
                    "notes": "Conta paga mockada"
                }
            ]
        }
    
    elif "credit" in endpoint: # Simulando Contas a Receber
        return {
            "items": [
                {
                    "scheduleId": "MOCK_RECEBER_01",
                    "stakeholderName": "Cliente Exemplo SA (Teste Nibo)", # Nibo as vezes usa stakeholderName
                    "description": "Consultoria TI",
                    "value": 2500.00,
                    "dueDate": hoje.strftime(fmt),
                    "status": "received", # Recebido
                    "accrualDate": hoje.strftime(fmt), # Data baixa
                    "notes": "Recebimento mockado"
                },
                {
                    "scheduleId": "MOCK_RECEBER_02",
                    "description": "Venda de Produto (Teste Nibo)",
                    "value": 120.00,
                    "dueDate": amanha.strftime(fmt),
                    "status": "open", # Em aberto
                    "notes": "Aguardando pagamento"
                }
            ]
        }
    
    return {"items": []}

def nibo_request(endpoint, method, creds, params=None):
    """
    Função genérica para fazer chamadas na API do Nibo.
    """
    # --- MODO DE TESTE (MOCK) ---
    # if creds.api_token == "TESTE":
    #     print(f"--- [MOCK NIBO] Simulando chamada para: {endpoint} ---")
    #     return get_mock_nibo_data(endpoint)
    # ----------------------------

    if params is None:
        params = {}

    url = f"{NIBO_API_URL}/{endpoint}"
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {creds.api_token}'
    }
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, params=params)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=params)
            
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {'erro': f"Erro na requisição Nibo ({endpoint}): {str(e)}"}

def prever_classificacao_local(user, descricao, tipo):
    """
    Réplica local da lógica de previsão (Idêntico ao utils_omie.py).
    """
    regras = ClassificacaoAutomatica.objects.filter(user=user, tipo=tipo)
    descricao_lower = descricao.lower()
    
    for regra in regras:
        if regra.termo.lower() in descricao_lower:
            return regra.categoria, regra.dre_area, regra.bank_account
            
    return None, None, None

def processar_contas_pagar_nibo(user, creds):
    """
    Busca e sincroniza contas a pagar do Nibo.
    """
    novos = 0
    atualizados = 0
    erros = []

    # Cria ou pega um banco virtual para vincular
    banco_nibo, _ = BankAccount.objects.get_or_create(
        user=user, 
        bank_name='Integração Nibo',
        defaults={'agency': '0000', 'account_number': 'NIBO', 'initial_balance': 0}
    )

    # Categoria Padrão de Fallback
    cat_padrao, _ = Category.objects.get_or_create(user=user, name='Despesas Gerais (Nibo)', category_type='PAYABLE')

    endpoint = f"schedules/debit" 
    
    data = nibo_request(endpoint, "GET", creds)
    
    if 'erro' in data:
        return {'erro': data['erro']}

    registros = data.get('items', data) if isinstance(data, dict) else data

    if not isinstance(registros, list):
        registros = []

    for reg in registros:
        try:
            id_nibo = str(reg.get('id') or reg.get('scheduleId'))
            descricao = reg.get('description') or reg.get('stakeholderName') or "Conta Nibo"
            observacao = reg.get('notes') or ""
            valor = Decimal(str(reg.get('value', 0)))
            
            dt_venc_str = reg.get('dueDate') 
            try:
                # Remove Z e milissegundos se houver, para garantir parse
                clean_date = dt_venc_str.split('.')[0].replace('Z', '')
                due_date = datetime.fromisoformat(clean_date).date()
            except:
                due_date = datetime.now().date()
            
            status_nibo = reg.get('status') 
            is_paid = (status_nibo == 'paid' or status_nibo == 'settled')
            
            payment_date = None
            if is_paid:
                dt_pgto = reg.get('paymentDate') or reg.get('accrualDate')
                if dt_pgto:
                    try:
                        clean_pgto = dt_pgto.split('.')[0].replace('Z', '')
                        payment_date = datetime.fromisoformat(clean_pgto).date()
                    except:
                        payment_date = due_date
                else:
                    payment_date = due_date

            conta_existente = PayableAccount.objects.filter(user=user, external_id=id_nibo).first()

            if conta_existente:
                conta_existente.amount = valor
                conta_existente.due_date = due_date
                conta_existente.is_paid = is_paid
                conta_existente.payment_date = payment_date
                
                if "Importado" in conta_existente.description:
                    conta_existente.description = f"{descricao} - {observacao}"
                
                conta_existente.save()
                atualizados += 1
            
            else:
                cat_prevista, dre_prevista, bank_previsto = prever_classificacao_local(user, descricao, 'PAYABLE')
                
                PayableAccount.objects.create(
                    user=user,
                    external_id=id_nibo,
                    name=descricao[:200],
                    description=f"{descricao} {observacao} (Nibo)",
                    due_date=due_date,
                    amount=valor,
                    is_paid=is_paid,
                    payment_date=payment_date,
                    
                    category=cat_prevista if cat_prevista else cat_padrao,
                    dre_area=dre_prevista if dre_prevista else 'OPERACIONAL',
                    bank_account=bank_previsto if bank_previsto else banco_nibo,
                    
                    payment_method='BOLETO',
                    occurrence='AVULSO',
                    cost_type='VARIAVEL'
                )
                novos += 1

        except Exception as e:
            erros.append(f"Erro ID Nibo {id_nibo}: {str(e)}")
    
    return {'novos': novos, 'atualizados': atualizados, 'erros': erros}

def processar_contas_receber_nibo(user, creds):
    """
    Busca e sincroniza contas a receber do Nibo.
    """
    novos = 0
    atualizados = 0
    erros = []

    banco_nibo, _ = BankAccount.objects.get_or_create(
        user=user, 
        bank_name='Integração Nibo',
        defaults={'agency': '0000', 'account_number': 'NIBO', 'initial_balance': 0}
    )

    cat_padrao, _ = Category.objects.get_or_create(user=user, name='Receitas de Vendas (Nibo)', category_type='RECEIVABLE')

    endpoint = f"schedules/credit" 

    data = nibo_request(endpoint, "GET", creds)
    
    if 'erro' in data:
        return {'erro': data['erro']}

    registros = data.get('items', data) if isinstance(data, dict) else data
    if not isinstance(registros, list): registros = []

    for reg in registros:
        try:
            id_nibo = str(reg.get('id') or reg.get('scheduleId'))
            descricao = reg.get('description') or reg.get('stakeholderName') or "Recebimento Nibo"
            observacao = reg.get('notes') or ""
            valor = Decimal(str(reg.get('value', 0)))
            
            dt_venc_str = reg.get('dueDate')
            try:
                clean_date = dt_venc_str.split('.')[0].replace('Z', '')
                due_date = datetime.fromisoformat(clean_date).date()
            except:
                due_date = datetime.now().date()
            
            status_nibo = reg.get('status')
            is_received = (status_nibo == 'received' or status_nibo == 'settled')
            
            payment_date = None
            if is_received:
                dt_pgto = reg.get('paymentDate') or reg.get('accrualDate')
                if dt_pgto:
                    try:
                        clean_pgto = dt_pgto.split('.')[0].replace('Z', '')
                        payment_date = datetime.fromisoformat(clean_pgto).date()
                    except:
                        payment_date = due_date
                else:
                    payment_date = due_date

            conta_existente = ReceivableAccount.objects.filter(user=user, external_id=id_nibo).first()

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
                    external_id=id_nibo,
                    name=descricao[:200],
                    description=f"{observacao} (Integrado Nibo)",
                    due_date=due_date,
                    amount=valor,
                    is_received=is_received,
                    payment_date=payment_date,
                    
                    category=cat_prevista if cat_prevista else cat_padrao,
                    dre_area=dre_prevista if dre_prevista else 'BRUTA',
                    bank_account=bank_previsto if bank_previsto else banco_nibo,
                    
                    payment_method='BOLETO',
                    occurrence='AVULSO'
                )
                novos += 1

        except Exception as e:
            erros.append(f"Erro ID Nibo {id_nibo}: {str(e)}")
    
    return {'novos': novos, 'atualizados': atualizados, 'erros': erros}

def sincronizar_nibo_completo(user):
    """
    Função principal chamada pela View.
    """
    try:
        creds = user.nibo_creds
    except NiboCredentials.DoesNotExist:
        return {'erro': 'Credenciais Nibo não encontradas.'}

    # Sincroniza Pagar
    res_pagar = processar_contas_pagar_nibo(user, creds)
    if 'erro' in res_pagar: return res_pagar

    # Sincroniza Receber
    res_receber = processar_contas_receber_nibo(user, creds)
    if 'erro' in res_receber: return res_receber

    return {
        'pagar_novos': res_pagar['novos'],
        'pagar_atualizados': res_pagar['atualizados'],
        'receber_novos': res_receber['novos'],
        'receber_atualizados': res_receber['atualizados'],
        'erros': res_pagar['erros'] + res_receber['erros']
    }