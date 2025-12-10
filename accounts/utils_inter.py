import requests
import os
import tempfile
from contextlib import contextmanager
from django.conf import settings

# URL Base da API (v2)
INTER_API_URL = "https://cdpj.partners.bancointer.com.br"

@contextmanager
def arquivos_temporarios(conteudo_crt, conteudo_key):
    """
    Cria arquivos temporários no disco (necessário para a lib requests com certificados)
    e garante que sejam apagados ou fechados após o uso.
    """
    # Cria arquivos temporários
    tmp_crt = tempfile.NamedTemporaryFile(delete=False)
    tmp_key = tempfile.NamedTemporaryFile(delete=False)
    
    try:
        # Escreve o conteúdo binário nos arquivos
        tmp_crt.write(conteudo_crt)
        tmp_crt.close() # Fecha para garantir que foi gravado
        
        tmp_key.write(conteudo_key)
        tmp_key.close()
        
        # Retorna os caminhos dos arquivos
        yield tmp_crt.name, tmp_key.name
        
    finally:
        # Limpeza: Tenta remover os arquivos após o uso
        try:
            os.unlink(tmp_crt.name)
            os.unlink(tmp_key.name)
        except:
            pass

def get_inter_token(user):
    # 1. Busca as credenciais do usuário no banco
    try:
        creds = user.inter_creds
    except:
        return {'erro': 'Credenciais não configuradas.'}

    url = f"{INTER_API_URL}/oauth/v2/token"
    
    payload = {
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scope': 'extrato.read',
        'grant_type': 'client_credentials'
    }
    
    # 2. Lê os arquivos (do S3 ou Local) para a memória
    try:
        # Força a abertura do arquivo para leitura
        creds.certificado_crt.open('rb')
        crt_content = creds.certificado_crt.read()
        creds.certificado_crt.close()

        creds.chave_key.open('rb')
        key_content = creds.chave_key.read()
        creds.chave_key.close()
        
        # --- DEBUG: Imprimir no terminal ---
        print(f"CRT lido: {len(crt_content)} bytes. Início: {crt_content[:20]}")
        print(f"KEY lida: {len(key_content)} bytes. Início: {key_content[:20]}")
        # -----------------------------------

    except Exception as e:
        return {'erro': f'Erro ao ler arquivos de certificado: {str(e)}'}

    # 3. Cria temporários e faz a requisição
    try:
        with arquivos_temporarios(crt_content, key_content) as (crt_path, key_path):
            response = requests.post(
                url, 
                data=payload,
                cert=(crt_path, key_path),
                verify=True
            )
            response.raise_for_status()
            return response.json().get('access_token')
    except Exception as e:
        erro_msg = str(e)
        if 'response' in locals() and hasattr(response, 'text'):
            erro_msg += f" | Detalhe: {response.text}"
        return {'erro': erro_msg}

def buscar_extrato_inter(user, start_date, end_date):
    # 1. Pega o token passando o usuário
    token_response = get_inter_token(user)
    
    # Se o retorno for um dicionário com erro, retorna o erro
    if isinstance(token_response, dict) and 'erro' in token_response:
        return token_response
        
    token = token_response

    # 2. Busca credenciais novamente
    creds = user.inter_creds
    
    url = f"{INTER_API_URL}/banking/v2/extrato"
    
    # Header sem x-conta-corrente (v2)
    headers = {'Authorization': f'Bearer {token}'}
    
    params = {
        'dataInicio': start_date.strftime('%Y-%m-%d'),
        'dataFim': end_date.strftime('%Y-%m-%d')
    }

    try:
        # --- CORREÇÃO AQUI: Reabrir os arquivos antes de ler novamente ---
        creds.certificado_crt.open('rb')
        crt_content = creds.certificado_crt.read()
        creds.certificado_crt.close() # Fecha após ler para memória

        creds.chave_key.open('rb')
        key_content = creds.chave_key.read()
        creds.chave_key.close() # Fecha após ler para memória
        # ---------------------------------------------------------------
        
        with arquivos_temporarios(crt_content, key_content) as (crt_path, key_path):
            response = requests.get(
                url,
                headers=headers,
                params=params,
                cert=(crt_path, key_path)
            )
            response.raise_for_status()
            return response.json()
            
    except Exception as e:
        erro_msg = str(e)
        if 'response' in locals() and hasattr(response, 'text'):
            erro_msg += f" | Detalhe Inter: {response.text}"
        print(f"Erro ao buscar extrato: {erro_msg}")
        return {'erro': erro_msg}
    



def buscar_saldo_inter(user):
    # 1. Pega o token (reutilizando a função existente)
    token_response = get_inter_token(user)
    
    # Se der erro no token, retorna o erro
    if isinstance(token_response, dict) and 'erro' in token_response:
        return token_response
        
    token = token_response

    # 2. Prepara a requisição
    creds = user.inter_creds
    url = f"{INTER_API_URL}/banking/v2/saldo"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        # Lê os arquivos do banco/S3 para memória
        creds.certificado_crt.open('rb')
        crt_content = creds.certificado_crt.read()
        creds.certificado_crt.close()

        creds.chave_key.open('rb')
        key_content = creds.chave_key.read()
        creds.chave_key.close()
        
        # Cria temporários e chama a API
        with arquivos_temporarios(crt_content, key_content) as (crt_path, key_path):
            response = requests.get(
                url,
                headers=headers,
                cert=(crt_path, key_path)
            )
            response.raise_for_status()
            return response.json() # Retorna o JSON com 'disponivel', 'limite', etc.
            
    except Exception as e:
        erro_msg = f"Erro ao buscar saldo: {str(e)}"
        return {'erro': erro_msg}




