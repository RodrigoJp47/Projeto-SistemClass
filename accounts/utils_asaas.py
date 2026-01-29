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
    Busca o extrato financeiro COMPLETO (com paginação automática).
    """
    config = get_asaas_config(user)
    if 'erro' in config:
        return config

    url = f"{config['base_url']}/financialTransactions"
    
    transacoes_formatadas = []
    offset = 0
    limit = 100 # Máximo permitido pelo Asaas por página
    
    while True:
        params = {
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': end_date.strftime('%Y-%m-%d'),
            'limit': limit,
            'offset': offset # Pula os que já pegamos
        }

        try:
            response = requests.get(url, headers=config['headers'], params=params)
            response.raise_for_status()
            data = response.json()
            
            lista_atual = data.get('data', [])
            
            # Se não veio nada, encerra o loop
            if not lista_atual:
                break
                
            for item in lista_atual:
                tipo_asaas = item.get('type')
                
                # --- CORREÇÃO DAS TAXAS DE BOLETO ---
                # Asaas costuma chamar taxa de boleto de 'BOLETO_FEE' ou similar.
                # Vamos garantir que ele pegue tudo.
                
                valor_original = float(item.get('value', 0))
                descricao = item.get('description') or f"Movimento Asaas: {tipo_asaas}"
                data_movimento = item.get('date')
                
                if valor_original < 0:
                    tipo_operacao = 'D'
                    # Removemos o prefixo [SAÍDA] para não ficar repetitivo se já tiver
                    if "Tarifa" in descricao or "FEE" in str(tipo_asaas):
                        descricao = f"Tarifa Asaas: {tipo_asaas}"
                else:
                    tipo_operacao = 'C'

                transacoes_formatadas.append({
                    'id_asaas': item.get('id'),
                    'data': data_movimento,
                    'descricao': descricao,
                    'valor': abs(valor_original),
                    'tipo': tipo_operacao,
                })

            # Atualiza o offset para a próxima página
            offset += limit
            
            # Se a lista atual veio menor que o limite, significa que acabou
            if len(lista_atual) < limit:
                break
                
        except Exception as e:
            return {'erro': f"Erro ao buscar extrato (pág {offset}): {str(e)}"}

    return {'transacoes': transacoes_formatadas}