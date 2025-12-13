import requests
from datetime import datetime
from .models import AsaasCredentials

def get_asaas_config(user):
    """
    Recupera as credenciais e define a URL base (Sandbox ou Produção).
    """
    try:
        creds = user.asaas_creds
    except AsaasCredentials.DoesNotExist:
        return {'erro': 'Credenciais do Asaas não configuradas.'}

    if not creds.access_token:
        return {'erro': 'Chave de API não informada.'}

    # Define a URL base dependendo do modo (Sandbox ou Produção)
    base_url = "https://sandbox.asaas.com/api/v3" if creds.is_sandbox else "https://www.asaas.com/api/v3"

    headers = {
        'access_token': creds.access_token,
        'Content-Type': 'application/json'
    }

    return {'headers': headers, 'base_url': base_url}

def buscar_saldo_asaas(user):
    """
    Busca o saldo atual da conta Asaas.
    """
    config = get_asaas_config(user)
    if 'erro' in config:
        return config

    url = f"{config['base_url']}/finance/balance"

    try:
        response = requests.get(url, headers=config['headers'])
        response.raise_for_status()
        data = response.json()
        
        # O Asaas retorna 'balance' (saldo total)
        return {
            'disponivel': float(data.get('balance', 0)),
        }
    except Exception as e:
        return {'erro': f"Erro ao buscar saldo Asaas: {str(e)}"}

def buscar_extrato_asaas(user, start_date, end_date):
    """
    Busca o extrato financeiro (entradas e saídas) do Asaas.
    Endpoint: /financialTransactions
    """
    config = get_asaas_config(user)
    if 'erro' in config:
        return config

    url = f"{config['base_url']}/financialTransactions"
    
    # Parâmetros de filtro
    params = {
        'startDate': start_date.strftime('%Y-%m-%d'),
        'endDate': end_date.strftime('%Y-%m-%d'),
        'limit': 100, # Busca até 100 movimentos no período
    }

    try:
        response = requests.get(url, headers=config['headers'], params=params)
        response.raise_for_status()
        data = response.json()
        
        transacoes_api = data.get('data', [])
        transacoes_formatadas = []

        for item in transacoes_api:
            # O Asaas detalha muito bem o tipo (PAYMENT_RECEIVED, TRANSFER_OUT, BILL_PAYMENT, ASAAS_CARD_TRANSACTION...)
            tipo_asaas = item.get('type')
            valor = abs(float(item.get('value', 0)))
            data_movimento = item.get('date') # YYYY-MM-DD
            descricao = item.get('description') or f"Movimento Asaas: {tipo_asaas}"
            
            # Define se é Crédito (C) ou Débito (D) baseado no valor positivo/negativo do extrato
            # Na API 'financialTransactions', saídas vêm negativas, entradas positivas.
            valor_original = float(item.get('value', 0))
            
            if valor_original < 0:
                tipo_operacao = 'D' # Débito (Saída)
                descricao = f"[SAÍDA] {descricao}"
            else:
                tipo_operacao = 'C' # Crédito (Entrada)
                descricao = f"[ENTRADA] {descricao}"

            transacoes_formatadas.append({
                'id_asaas': item.get('id'), # ID único da transação
                'data': data_movimento,
                'descricao': descricao,
                'valor': valor,     # Valor absoluto para salvar no banco
                'tipo': tipo_operacao,    # C ou D
            })

        return {'transacoes': transacoes_formatadas}

    except Exception as e:
        erro_msg = str(e)
        if 'response' in locals() and hasattr(response, 'text'):
            erro_msg += f" | Detalhe Asaas: {response.text}"
        return {'erro': erro_msg}