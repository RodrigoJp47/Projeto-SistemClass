import requests
import base64
from datetime import timedelta
from django.utils import timezone
from decimal import Decimal
from .models import SicrediCredentials

# def get_sicredi_config(user):
#     """
#     Recupera as configurações, gerencia o Access Token e 
#     vincula corretamente a x-api-key desde a autenticação.
#     """
#     try:
#         creds = user.sicredi_creds
#     except SicrediCredentials.DoesNotExist:
#         return {'erro': 'Configurações do Sicredi não encontradas.'}

#     agora = timezone.now()
    
#     if creds.is_sandbox:
#         # Endpoints de Sandbox para Conta Corrente (Extrato e Saldo)
#         base_url = "https://api-parceiro.sicredi.com.br/sb/openapi/v1/conta-corrente"
#         auth_url = "https://api-parceiro.sicredi.com.br/auth/openapi/v1/token"
#     else:
#         # Endpoints de Produção para Conta Corrente
#         base_url = "https://api-parceiro.sicredi.com.br/openapi/v1/conta-corrente"
#         auth_url = "https://api-parceiro.sicredi.com.br/auth/openapi/v1/token"
#     # Define a x-api-key mandatória (Partner ID ou Client ID)
#     x_api_key = creds.partner_id if creds.partner_id else creds.client_id

#     # 1. Geração/Atualização do Token
#     if not creds.access_token or (creds.expires_at and agora >= creds.expires_at - timedelta(minutes=5)):
#         auth_string = f"{creds.client_id}:{creds.client_secret}"
#         auth_b64 = base64.b64encode(auth_string.encode()).decode()

#         # No Sandbox, o x-api-key DEVE ser enviado no login para validar o Token posterior
#         headers_auth = {
#             'Authorization': f'Basic {auth_b64}',
#             'Content-Type': 'application/x-www-form-urlencoded',
#             'x-api-key': x_api_key
#         }

#         payload = {'grant_type': 'client_credentials', 'scope': 'extrato'}

#         try:
#             response = requests.post(auth_url, data=payload, headers=headers_auth, timeout=30)
            
#             if response.status_code not in [200, 201]:
#                 return {'erro': f"Erro Login Sicredi ({response.status_code}): {response.text}"}

#             token_data = response.json()
#             creds.access_token = token_data.get('access_token')
#             expires_in = int(token_data.get('expires_in', 3600))
#             creds.expires_at = agora + timedelta(seconds=expires_in)
#             creds.save()
#         except Exception as e:
#             return {'erro': f"Falha na conexão: {str(e)}"}

#     # 2. Cabeçalhos para as chamadas de API (Consultas)
#     headers = {
#         'Authorization': f'Bearer {creds.access_token}',
#         'Content-Type': 'application/json',
#         'x-api-key': x_api_key
#     }

#     return {'headers': headers, 'base_url': base_url}

def get_sicredi_config(user):
    """
    Recupera as configurações, gerencia o Access Token para Conta Corrente
    e vincula corretamente a x-api-key desde a autenticação.
    """
    try:
        creds = user.sicredi_creds
    except SicrediCredentials.DoesNotExist:
        return {'erro': 'Configurações do Sicredi não encontradas.'}

    agora = timezone.now()
    
    # URLs ajustadas para abranger Saldo e Extrato (Conta Corrente)
    if creds.is_sandbox:
        base_url = "https://api-parceiro.sicredi.com.br/sb/openapi/v1/conta-corrente"
        auth_url = "https://api-parceiro.sicredi.com.br/auth/openapi/v1/token"
    else:
        base_url = "https://api-parceiro.sicredi.com.br/openapi/v1/conta-corrente"
        auth_url = "https://api-parceiro.sicredi.com.br/auth/openapi/v1/token"

    x_api_key = creds.partner_id if creds.partner_id else creds.client_id

    # 1. Geração/Atualização do Token com proteção para expires_at None
    if not creds.access_token or (creds.expires_at and agora >= creds.expires_at - timedelta(minutes=5)):
        auth_string = f"{creds.client_id}:{creds.client_secret}"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()

        headers_auth = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'x-api-key': x_api_key
        }

        # Escopo alterado para 'extrato' para permitir acesso a movimentações e saldo
        payload = {'grant_type': 'client_credentials', 'scope': 'extrato'}

        try:
            response = requests.post(auth_url, data=payload, headers=headers_auth, timeout=30)
            
            if response.status_code not in [200, 201]:
                return {'erro': f"Erro Login Sicredi ({response.status_code}): {response.text}"}

            token_data = response.json()
            creds.access_token = token_data.get('access_token')
            expires_in = int(token_data.get('expires_in', 3600))
            creds.expires_at = agora + timedelta(seconds=expires_in)
            creds.save()
        except Exception as e:
            return {'erro': f"Falha na conexão: {str(e)}"}

    # 2. Cabeçalhos para as chamadas de API (Consultas)
    headers = {
        'Authorization': f'Bearer {creds.access_token}',
        'Content-Type': 'application/json',
        'x-api-key': x_api_key
    }

    return {'headers': headers, 'base_url': base_url}

def testar_conexao_sicredi(user):
    """
    Valida a conexão usando a função get_sicredi_config corrigida.
    """
    # 1. Obtém a configuração (já valida Client ID, Secret e gera o Token)
    config = get_sicredi_config(user)
    
    if 'erro' in config:
        return {'erro': config['erro']}

    # 2. Tenta acessar o endpoint de beneficiários para validar a x-api-key
    url = f"{config['base_url']}/beneficiarios"
    
    try:
        response = requests.get(url, headers=config['headers'], timeout=15)
        
        if response.status_code == 200:
            return {'sucesso': True}
        elif response.status_code == 401:
            return {'erro': "Não autorizado: Chave de API (x-api-key) inválida ou ausente."}
        elif response.status_code == 403:
            return {'erro': "Acesso Negado: Verifique as permissões da App no Sicredi."}
        else:
            return {'erro': f"Erro API ({response.status_code}): {response.text}"}
            
    except Exception as e:
        return {'erro': f"Erro de comunicação: {str(e)}"}


    
def buscar_saldo_sicredi(user):
    config = get_sicredi_config(user)
    if 'erro' in config: return config

    url = f"{config['base_url']}/saldo" # Endpoint correto de saldo
    
    try:
        response = requests.get(url, headers=config['headers'], timeout=15)
        if response.status_code == 200:
            dados = response.json()
            # O Sicredi costuma retornar 'saldoDisponivel'
            valor = dados.get('saldoDisponivel', 0)
            return {'disponivel': Decimal(str(valor))}
        return {'erro': f"Erro Saldo: {response.status_code}"}
    except Exception as e:
        return {'erro': f"Erro ao buscar saldo: {str(e)}"}

def buscar_extrato_sicredi(user, start_date, end_date):
    config = get_sicredi_config(user)
    if 'erro' in config: return config

    # Mudança para o endpoint de extrato real da conta corrente
    url = f"{config['base_url']}/extrato" 
    
    # O Sicredi (Sensedia) geralmente espera ISO (YYYY-MM-DD) para Conta Corrente
    params = {
        'dataInicio': start_date.strftime('%Y-%m-%d'),
        'dataFim': end_date.strftime('%Y-%m-%d')
    }

    try:
        response = requests.get(url, headers=config['headers'], params=params, timeout=20)
        if response.status_code != 200:
            return {'erro': f"Erro Extrato: {response.text}"}

        # No endpoint de extrato, o campo comum é 'movimentacoes' ou 'lista'
        conteudo = response.json().get('movimentacoes', []) 
        transacoes_formatadas = []

        for item in conteudo:
            valor_raw = Decimal(str(item.get('valor', 0)))
            
            # Lógica de Tipo: Se o valor for negativo é Débito (D), se positivo é Crédito (C)
            tipo_op = 'D' if valor_raw < 0 else 'C'

            transacoes_formatadas.append({
                'id_sicredi': item.get('identificador'), # ID único da transação no extrato
                'data': item.get('data'), # Formato YYYY-MM-DD
                'nome_parte': item.get('descricaoDetalhada', 'MOVIMENTAÇÃO SICREDI').upper(),
                'descricao': item.get('historico', 'TRANSACAO BANCARIA'),
                'valor': abs(valor_raw), # Valor absoluto para salvar no banco (o sinal vai no 'tipo')
                'tipo': tipo_op, 
            })

        return {'transacoes': transacoes_formatadas}
    except Exception as e:
        return {'erro': f"Erro Extrato: {str(e)}"}






from fpdf import FPDF
import io

def gerar_pdf_instrucoes_sicredi():
    pdf = FPDF()
    pdf.add_page()
    
    # Configuração de Cores (Verde Sicredi)
    pdf.set_fill_color(0, 107, 63)
    pdf.rect(0, 0, 210, 30, 'F')
    
    # Título Branco sobre Fundo Verde
    pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 20, "Guia de Integracao: SistemClass + Sicredi", 0, 1, 'C')
    
    pdf.ln(15)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 12)
    
    # Conteúdo do Roteiro
    texto = [
        ("1. Solicitacao ao Gerente", "B"),
        ("Entre em contato com seu gerente Sicredi e peça a liberação da 'API de Cobrança/Extrato' para o SistemClass.", ""),
        ("2. Obtencao das Chaves", "B"),
        ("No Internet Banking (Menu Arquivos > API), gere o Client ID, Client Secret e localize seu Partner ID.", ""),
        ("3. Configuracao", "B"),
        ("Insira os dados na tela de configuracao do sistema e clique em 'Salvar e Validar'.", ""),
    ]
    
    for linha, estilo in texto:
        pdf.set_font("Arial", estilo, 12)
        pdf.multi_cell(0, 8, linha)
        if estilo == "B": pdf.ln(2)
        else: pdf.ln(5)

    # Retorna o PDF como um stream de bytes para o Django enviar
    return pdf.output(dest='S').encode('latin-1')
