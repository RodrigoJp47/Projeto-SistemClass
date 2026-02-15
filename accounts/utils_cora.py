import requests
from datetime import datetime, timedelta
from django.utils import timezone
from decimal import Decimal
from .models import CoraCredentials
import os

# def get_cora_config(user):
#     """
#     Recupera credenciais e Configura Autenticação mTLS (Certificado).
#     """
#     try:
#         creds = user.cora_creds
#     except CoraCredentials.DoesNotExist:
#         return {'erro': 'Credenciais não encontradas.'}

#     if not creds.certificado or not creds.chave_privada:
#         return {'erro': 'Arquivos de certificado (PEM/KEY) não encontrados.'}

#     try:
#         cert_file = creds.certificado.path
#         key_file = creds.chave_privada.path
#     except Exception:
#         return {'erro': 'Erro ao ler arquivos no servidor.'}
    
#     # Tupla do Certificado
#     cora_ssl_cert = (cert_file, key_file)

#     # URL DE PRODUÇÃO (INTEGRAÇÃO DIRETA)
#     base_url = "https://matls-clients.api.cora.com.br"
#     token_url = f"{base_url}/token" 

#     agora = timezone.now()

#     # --- AUTENTICAÇÃO (Renovação de Token) ---
#     if not creds.access_token or (creds.expires_at and agora >= creds.expires_at):
#         try:
#             payload = {
#                 'grant_type': 'client_credentials',
#                 'client_id': creds.client_id
#             }
#             # Sem client_secret pois é certificado
            
#             print(f"--- CORA: Autenticando em {token_url} ---")
            
#             response = requests.post(token_url, data=payload, cert=cora_ssl_cert, timeout=30)
            
#             if response.status_code != 200:
#                 return {'erro': f"Falha Login Cora ({response.status_code}): {response.text}"}

#             token_data = response.json()
            
#             creds.access_token = token_data.get('access_token')
#             expires_in = int(token_data.get('expires_in', 3600))
#             creds.expires_at = agora + timedelta(seconds=expires_in)
#             creds.save()
            
#         except Exception as e:
#             return {'erro': f"Erro na Conexão: {str(e)}"}

#     headers = {
#         'Authorization': f'Bearer {creds.access_token}',
#         'Content-Type': 'application/json',
#         'User-Agent': 'SistemClass/1.0'
#     }

#     return {'headers': headers, 'base_url': base_url, 'ssl_cert': cora_ssl_cert}

import tempfile
import os

def get_cora_config(user):
    """
    Recupera credenciais e Configura Autenticação mTLS usando arquivos temporários.
    Isso resolve o erro de leitura no Render/Produção.
    """
    try:
        creds = user.cora_creds
    except CoraCredentials.DoesNotExist:
        return {'erro': 'Credenciais não encontradas.'}

    if not creds.certificado or not creds.chave_privada:
        return {'erro': 'Arquivos de certificado (PEM/KEY) não encontrados.'}

    # --- SOLUÇÃO PARA O RENDER: Criar arquivos temporários físicos ---
    try:
        # Criamos dois arquivos temporários que serão excluídos automaticamente ao fechar
        # Mas como o 'requests' precisa do caminho, vamos gerenciar manualmente
        t_cert = tempfile.NamedTemporaryFile(delete=False, suffix='.pem')
        t_cert.write(creds.certificado.read())
        t_cert.close() # Fecha para garantir que o conteúdo foi gravado

        t_key = tempfile.NamedTemporaryFile(delete=False, suffix='.key')
        t_key.write(creds.chave_privada.read())
        t_key.close()

        # Agora temos caminhos REAIS que o Linux do Render entende
        cert_file_path = t_cert.name
        key_file_path = t_key.name
        
        # Voltamos os ponteiros para o início para não dar erro se precisar ler de novo
        creds.certificado.seek(0)
        creds.chave_privada.seek(0)

    except Exception as e:
        return {'erro': f'Erro ao processar certificados no servidor: {str(e)}'}
    
    # Tupla do Certificado usando os caminhos temporários
    cora_ssl_cert = (cert_file_path, key_file_path)

    # URL DE PRODUÇÃO
    base_url = "https://matls-clients.api.cora.com.br"
    token_url = f"{base_url}/token" 
    agora = timezone.now()

    try:
        # --- AUTENTICAÇÃO ---
        if not creds.access_token or (creds.expires_at and agora >= creds.expires_at):
            payload = {'grant_type': 'client_credentials', 'client_id': creds.client_id}
            
            response = requests.post(token_url, data=payload, cert=cora_ssl_cert, timeout=30)
            
            if response.status_code != 200:
                return {'erro': f"Falha Login Cora ({response.status_code}): {response.text}"}

            token_data = response.json()
            creds.access_token = token_data.get('access_token')
            expires_in = int(token_data.get('expires_in', 3600))
            creds.expires_at = agora + timedelta(seconds=expires_in)
            creds.save()

        headers = {
            'Authorization': f'Bearer {creds.access_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'SistemClass/1.0'
        }

        return {'headers': headers, 'base_url': base_url, 'ssl_cert': cora_ssl_cert, 'temp_files': [cert_file_path, key_file_path]}

    except Exception as e:
        return {'erro': f"Erro na Conexão: {str(e)}"}
    finally:
        # NOTA: Os arquivos temporários permanecem no disco para a requisição seguinte.
        # Eles serão limpos pelo SO ou podemos adicionar uma lógica de remoção no final de cada view.
        pass

def buscar_saldo_cora(user):
    """
    Função adaptada para TESTE DE CONEXÃO.
    Como a endpoint de saldo é incerta na API mTLS, buscamos o extrato para validar o token.
    """
    config = get_cora_config(user)
    if 'erro' in config: return config

    # Usamos o endpoint de EXTRATO para validar se a conexão funciona
    url = f"{config['base_url']}/bank-statement/statement"
    
    # Pegamos apenas o dia de hoje para ser rápido
    hoje = timezone.now().strftime('%Y-%m-%d')
    params = {'start': hoje, 'end': hoje, 'perPage': 1}

    try:
        response = requests.get(url, headers=config['headers'], params=params, cert=config['ssl_cert'], timeout=15)
        response.raise_for_status()
        
        # Se chegou aqui, a conexão é SUCESSO!
        # Retornamos 0.00 pois o objetivo principal aqui é validar a credencial
        return {'disponivel': Decimal('0.00'), 'total': Decimal('0.00')}
    
        
    except Exception as e:
        return {'erro': f"Erro ao validar conexão (Teste Extrato): {str(e)}"}
    
    finally:
        # LIMPEZA DOS TEMPORÁRIOS
        for f in config.get('temp_files', []):
            if os.path.exists(f): os.remove(f)





def buscar_extrato_cora(user, start_date, end_date):
    """
    Busca o extrato com NOME DO BENEFICIÁRIO + TAGS (Para ajudar a IA).
    """
    config = get_cora_config(user)
    if 'erro' in config: return config

    url = f"{config['base_url']}/bank-statement/statement"
    transacoes_formatadas = []
    page = 1
    
    while True:
        params = {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d'),
            'perPage': 250,
            'page': page
        }

        try:
            response = requests.get(url, headers=config['headers'], params=params, cert=config['ssl_cert'])
            response.raise_for_status()
            
            data = response.json()
            lista_atual = data.get('entries', []) 
            
            if not lista_atual: break

            for item in lista_atual:
                valor_centavos = int(item.get('amount', 0))
                tipo_cora = item.get('type', 'DEBIT')
                tipo_sistema = 'C' if tipo_cora == 'CREDIT' else 'D'
                
                detalhes = item.get('transaction', {})
                
                # 1. Nome da Parte (Beneficiário/Pagador)
                nome_terceiro = detalhes.get('counterParty', {}).get('name')
                if not nome_terceiro:
                    nome_terceiro = detalhes.get('description') or "Transação Cora"

                # 2. TAGS DA CORA (Isso ajuda a IA a definir o Centro de Custo)
                # Se tiver a tag "Obra", a IA vai ler "Joao Silva [TAG: Obra]"
                tags = item.get('tags', [])
                if tags:
                    tags_str = " ".join(tags)
                    nome_completo_ia = f"{nome_terceiro} [TAG: {tags_str}]"
                else:
                    nome_completo_ia = nome_terceiro

                descricao_tecnica = detalhes.get('description') or f"ID {item.get('id')}"
                data_str = item.get('createdAt', '')[:10]

                transacoes_formatadas.append({
                    'id_cora': item.get('id'),
                    'data': data_str,
                    'nome_parte': nome_completo_ia.upper(), # Nome turbinado com Tags
                    'descricao': descricao_tecnica,
                    'valor': Decimal(valor_centavos) / 100,
                    'tipo': tipo_sistema,
                })

            page += 1
            if len(lista_atual) < 250: break
                
        except Exception as e:
            return {'erro': f"Erro Extrato Cora: {str(e)}"}
        
        finally:
            # LIMPEZA DOS TEMPORÁRIOS
            for f in config.get('temp_files', []):
                if os.path.exists(f): os.remove(f)

    return {'transacoes': transacoes_formatadas}