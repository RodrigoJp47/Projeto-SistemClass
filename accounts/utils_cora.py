import requests
from datetime import datetime, timedelta
from django.utils import timezone
from .models import CoraCredentials

def get_cora_config(user):
    """
    Recupera credenciais e gerencia a renovação automática do Token OAuth2.
    """
    try:
        creds = user.cora_creds
    except CoraCredentials.DoesNotExist:
        return {'erro': 'Credenciais do Banco Cora não configuradas.'}

    base_url = "https://matriz.sandbox.cora.com.br" if creds.is_sandbox else "https://matriz.cora.com.br"
    token_url = f"{base_url}/token"

    # Lógica de Refresh Token (OAuth2)
    agora = timezone.now()
    if not creds.access_token or (creds.expires_at and agora >= creds.expires_at):
        try:
            payload = {
                'grant_type': 'refresh_token',
                'refresh_token': creds.refresh_token,
                'client_id': creds.client_id
            }
            # Se usar client_secret: payload['client_secret'] = creds.client_secret
            
            response = requests.post(token_url, data=payload)
            response.raise_for_status()
            token_data = response.json()
            
            creds.access_token = token_data.get('access_token')
            creds.refresh_token = token_data.get('refresh_token', creds.refresh_token)
            # Define expiração (geralmente 3600 segundos)
            creds.expires_at = agora + timedelta(seconds=int(token_data.get('expires_in', 3600)))
            creds.save()
        except Exception as e:
            return {'erro': f"Erro ao renovar token Cora: {str(e)}"}

    headers = {
        'Authorization': f'Bearer {creds.access_token}',
        'Content-Type': 'application/json'
    }

    return {'headers': headers, 'base_url': base_url}

def buscar_saldo_cora(user):
    """
    Busca o saldo atual da conta Cora (Saldo Disponível).
    """
    config = get_cora_config(user)
    if 'erro' in config:
        return config

    # Endpoint da Cora para consulta de saldo
    url = f"{config['base_url']}/balance"

    try:
        response = requests.get(url, headers=config['headers'])
        response.raise_for_status()
        data = response.json()
        
        # O Banco Cora geralmente retorna 'total_amount' ou 'available_balance'
        # Ajustamos para retornar a chave 'disponivel' que sua View espera
        return {
            'disponivel': float(data.get('available_balance', 0)),
        }
    except Exception as e:
        return {'erro': f"Erro ao buscar saldo Cora: {str(e)}"}

def buscar_extrato_cora(user, start_date, end_date):
    """
    Busca o extrato da Cora com paginação automática.
    Retorna lista padronizada para a views.py.
    """
    config = get_cora_config(user)
    if 'erro' in config:
        return config

    # Endpoint da Cora para extrato (pode variar conforme versão da API, ex: /v1/statement)
    url = f"{config['base_url']}/statement"
    
    transacoes_formatadas = []
    page = 1
    per_page = 50 
    
    while True:
        params = {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d'),
            'page': page,
            'per_page': per_page
        }

        try:
            response = requests.get(url, headers=config['headers'], params=params)
            response.raise_for_status()
            data = response.json()
            
            # A Cora costuma retornar a lista dentro de uma chave 'items' ou 'data'
            lista_atual = data.get('items', [])
            
            if not lista_atual:
                break
                
            for item in lista_atual:
                # Padronização para bater com o loop da sua view (Inter/Asaas)
                # Na Cora: 'amount' costuma vir em centavos ou decimal dependendo da versão
                valor_bruto = float(item.get('amount', 0))
                
                # Identifica Tipo: Cora costuma usar ENTRY (Entrada) ou EXIT (Saída)
                # Ou valores negativos para débito. Ajustamos para seu padrão 'C'/'D'.
                if valor_bruto < 0:
                    tipo_operacao = 'D'
                    valor_ajustado = abs(valor_bruto)
                else:
                    tipo_operacao = 'C'
                    valor_ajustado = valor_bruto

                transacoes_formatadas.append({
                    'id_cora': item.get('id'),
                    'data': item.get('created_at', '')[:10], # Pega apenas YYYY-MM-DD
                    'descricao': item.get('description') or f"Transação Cora: {item.get('type')}",
                    'valor': valor_ajustado,
                    'tipo': tipo_operacao,
                })

            # Verifica se há próxima página (Cora usa metadados de paginação)
            total_pages = data.get('total_pages', page)
            if page >= total_pages:
                break
            
            page += 1
                
        except Exception as e:
            return {'erro': f"Erro ao buscar extrato Cora (pág {page}): {str(e)}"}

    return {'transacoes': transacoes_formatadas}