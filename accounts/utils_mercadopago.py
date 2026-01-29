# import requests
# from datetime import datetime, timedelta
# from .models import MercadoPagoCredentials

# # URL Base da API do Mercado Pago
# MP_API_URL = "https://api.mercadopago.com"

# def get_mp_headers(user):
#     """
#     Busca as credenciais do usuário e monta o Header de autenticação.
#     """
#     try:
#         creds = user.mercadopago_creds
#     except MercadoPagoCredentials.DoesNotExist:
#         return {'erro': 'Credenciais do Mercado Pago não configuradas.'}

#     if not creds.access_token:
#         return {'erro': 'Access Token não informado.'}

#     return {
#         'Authorization': f'Bearer {creds.access_token}',
#         'Content-Type': 'application/json'
#     }

# def get_mp_user_id(headers):
#     """
#     Helper para buscar o ID numérico do usuário no Mercado Pago.
#     Necessário para consultar o saldo.
#     """
#     url = f"{MP_API_URL}/users/me"
#     try:
#         response = requests.get(url, headers=headers)
#         response.raise_for_status()
#         return response.json().get('id')
#     except Exception as e:
#         return None

# def buscar_saldo_mercadopago(user):
#     """
#     Busca o saldo disponível na conta Mercado Pago.
#     """
#     headers = get_mp_headers(user)
#     if 'erro' in headers:
#         return headers

#     # 1. Precisa descobrir o User ID do Mercado Pago antes
#     user_id = get_mp_user_id(headers)
#     if not user_id:
#         return {'erro': 'Falha ao identificar usuário MP. Verifique o Token.'}

#     # 2. Busca o saldo
#     url = f"{MP_API_URL}/users/{user_id}/mercadopago_account/balance"
    
#     try:
#         response = requests.get(url, headers=headers)
#         response.raise_for_status()
#         data = response.json()
        
#         # O MP retorna vários tipos de saldo. Focamos no 'available_balance' (disponível para saque/uso)
#         # e 'total_amount' (bruto).
#         return {
#             'disponivel': data.get('available_balance', 0),
#             'total': data.get('total_amount', 0),
#             'unavailable': data.get('unavailable_balance', 0)
#         }
#     except Exception as e:
#         erro_msg = str(e)
#         if 'response' in locals() and hasattr(response, 'text'):
#              erro_msg += f" | Detalhe MP: {response.text}"
#         return {'erro': erro_msg}

# def buscar_extrato_mercadopago(user, start_date, end_date):
#     """
#     Busca as transações (Pagamentos recebidos/Vendas) no período.
#     Nota: A API pública de 'payments/search' foca em RECEBIMENTOS (Vendas).
#     """
#     headers = get_mp_headers(user)
#     if 'erro' in headers:
#         return headers

#     url = f"{MP_API_URL}/v1/payments/search"
    
#     # O Mercado Pago exige data no formato ISO 8601 completo com hora (ex: 2023-01-01T00:00:00Z)
#     # Vamos garantir o intervalo completo do dia
#     begin_str = start_date.strftime('%Y-%m-%dT00:00:00Z')
#     end_str = end_date.strftime('%Y-%m-%dT23:59:59Z')

#     params = {
#         'sort': 'date_created',
#         'criteria': 'desc',
#         'range': 'date_created',
#         'begin_date': begin_str,
#         'end_date': end_str,
#         'limit': 50, # Pode aumentar ou paginar se tiver muito volume
#         'status': 'approved' # Focamos em pagamentos aprovados para o financeiro
#     }

#     try:
#         response = requests.get(url, headers=headers, params=params)
#         response.raise_for_status()
#         data = response.json()
        
#         results = data.get('results', [])
#         transacoes_formatadas = []

#         for item in results:
#             # Tenta pegar descrição do item ou usa padrão
#             descricao = item.get('description') or item.get('reason') or "Venda Mercado Pago"
            
#             # Data de Criação (Transação)
#             data_raw = item.get('date_created') # Ex: 2023-10-25T10:00:00.000-04:00
#             try:
#                 # Corta a string para pegar apenas a data YYYY-MM-DD
#                 data_movimento = data_raw.split('T')[0]
#             except:
#                 data_movimento = start_date.strftime('%Y-%m-%d')

#             # Valores
#             valor_bruto = float(item.get('transaction_amount', 0))
#             valor_liquido = float(item.get('transaction_details', {}).get('net_received_amount', valor_bruto))
#             taxa = valor_bruto - valor_liquido
            
#             # Identifica o tipo (Geralmente payments search retorna Entradas/Vendas)
#             # Se for um reembolso (refund), o status seria diferente, mas filtramos por 'approved'.
            
#             tipo_operacao = 'C' # Crédito (Entrada) por padrão na API de Payments
            
#             transacoes_formatadas.append({
#                 'id_mp': str(item.get('id')), # ID único da transação
#                 'data': data_movimento,
#                 'descricao': descricao,
#                 'valor': valor_bruto,     # Usamos o bruto para lançar a venda cheia
#                 'valor_liquido': valor_liquido, # Útil se quiser lançar a taxa separada depois
#                 'tipo': tipo_operacao,    # C = Crédito, D = Débito
#                 'status': item.get('status')
#             })

#         return {'transacoes': transacoes_formatadas}

#     except Exception as e:
#         erro_msg = str(e)
#         if 'response' in locals() and hasattr(response, 'text'):
#             erro_msg += f" | Detalhe MP: {response.text}"
#         return {'erro': erro_msg}

import requests
from datetime import datetime, timedelta
from .models import MercadoPagoCredentials

# URL Base da API do Mercado Pago
MP_API_URL = "https://api.mercadopago.com"

def get_mp_headers(user):
    """
    Busca as credenciais do usuário e monta o Header de autenticação.
    """
    try:
        creds = user.mercadopago_creds
    except MercadoPagoCredentials.DoesNotExist:
        return {'erro': 'Credenciais do Mercado Pago não configuradas.'}

    if not creds.access_token:
        return {'erro': 'Access Token não informado.'}

    return {
        'Authorization': f'Bearer {creds.access_token}',
        'Content-Type': 'application/json'
    }

def get_mp_user_id(headers):
    """
    Helper para buscar o ID numérico do usuário no Mercado Pago.
    Necessário para consultar o saldo.
    """
    url = f"{MP_API_URL}/users/me"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get('id')
    except Exception as e:
        return None

def buscar_saldo_mercadopago(user):
    """
    Busca o saldo disponível na conta Mercado Pago.
    """
    headers = get_mp_headers(user)
    if 'erro' in headers:
        return headers

    # 1. Precisa descobrir o User ID do Mercado Pago antes
    user_id = get_mp_user_id(headers)
    if not user_id:
        return {'erro': 'Falha ao identificar usuário MP. Verifique o Token.'}

    # 2. Busca o saldo
    url = f"{MP_API_URL}/users/{user_id}/mercadopago_account/balance"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        return {
            'disponivel': data.get('available_balance', 0),
            'total': data.get('total_amount', 0),
            'unavailable': data.get('unavailable_balance', 0)
        }
    except Exception as e:
        erro_msg = str(e)
        if 'response' in locals() and hasattr(response, 'text'):
             erro_msg += f" | Detalhe MP: {response.text}"
        return {'erro': erro_msg}

def buscar_extrato_mercadopago(user, start_date, end_date):
    """
    Busca as transações (Pagamentos recebidos/Vendas) no período.
    COM PAGINAÇÃO AUTOMÁTICA (Busca tudo, sem limite de 50).
    """
    headers = get_mp_headers(user)
    if 'erro' in headers:
        return headers

    url = f"{MP_API_URL}/v1/payments/search"
    
    # Datas formato ISO 8601
    begin_str = start_date.strftime('%Y-%m-%dT00:00:00Z')
    end_str = end_date.strftime('%Y-%m-%dT23:59:59Z')

    transacoes_formatadas = []
    offset = 0
    limit = 50 # Limite por página recomendado pelo MP
    
    while True:
        params = {
            'sort': 'date_created',
            'criteria': 'desc',
            'range': 'date_created',
            'begin_date': begin_str,
            'end_date': end_str,
            'limit': limit,
            'offset': offset,
            'status': 'approved'
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            results = data.get('results', [])
            
            # Se a lista veio vazia, acabou
            if not results:
                break

            for item in results:
                # Descrição
                descricao = item.get('description') or item.get('reason') or "Venda Mercado Pago"
                
                # Data
                data_raw = item.get('date_created') 
                try:
                    data_movimento = data_raw.split('T')[0]
                except:
                    data_movimento = start_date.strftime('%Y-%m-%d')

                # Valores
                valor_bruto = float(item.get('transaction_amount', 0))
                # Tenta pegar valor líquido, se não tiver, usa o bruto
                detalhes = item.get('transaction_details') or {}
                valor_liquido = float(detalhes.get('net_received_amount', valor_bruto))
                
                transacoes_formatadas.append({
                    'id_mp': str(item.get('id')),
                    'data': data_movimento,
                    'descricao': descricao,
                    'valor': valor_bruto,
                    'valor_liquido': valor_liquido,
                    'tipo': 'C', # Crédito
                    'status': item.get('status')
                })

            # Atualiza o offset para buscar a próxima página
            offset += limit
            
            # Verifica se chegamos ao total disponível
            paging = data.get('paging', {})
            total = paging.get('total', 0)
            
            if offset >= total:
                break

        except Exception as e:
            return {'erro': f"Erro MP (offset {offset}): {str(e)}"}

    return {'transacoes': transacoes_formatadas}