# # accounts/management/commands/sync_conta_azul.py

# import os
# import time
# import requests
# import traceback
# from django.core.management.base import BaseCommand
# from django.contrib.auth import get_user_model
# from django.conf import settings
# # USE datetime DIRECTAMENTE, NÃO datetime.datetime
# from datetime import datetime, timedelta, date # Adicione date
# from django.utils import timezone
# from decimal import Decimal, InvalidOperation

# from accounts.models import ContaAzulCredentials as ContaAzulToken
# from accounts.models import ReceivableAccount, PayableAccount, Category

# CLIENT_ID = os.environ.get('CONTA_AZUL_CLIENT_ID')
# CLIENT_SECRET = os.environ.get('CONTA_AZUL_CLIENT_SECRET')
# TOKEN_URL = 'https://auth.contaazul.com/oauth2/token'
# API_BASE_URL = 'https://api-v2.contaazul.com'

# class Command(BaseCommand):
#     help = "Sincroniza Contas a Receber/Pagar (Abertas, Atrasadas e Quitadas dos últimos 30 dias) com a API Conta Azul V2"

#     def handle(self, *args, **options):
#         User = get_user_model()
#         self.stdout.write(self.style.SUCCESS("--- Iniciando sincronização Conta Azul ---"))

#         if not CLIENT_ID or not CLIENT_SECRET:
#             self.stderr.write(self.style.ERROR("Client ID ou Client Secret não configurados."))
#             return

#         for user in User.objects.filter(is_active=True):
#             self.stdout.write(f"\n--- Sincronizando Conta Azul para: {user.username} ---")

#             token_obj = ContaAzulToken.objects.filter(user=user).first()
#             if not token_obj:
#                 self.stdout.write(self.style.WARNING(f"Usuário {user.username} sem credenciais Conta Azul."))
#                 continue

#             # --- Verifica validade do token E ATUALIZA SE NECESSÁRIO (sem alterações aqui) ---
#             access_token = token_obj.access_token
#             headers = {}
#             now = timezone.now()
#             if not token_obj.expires_at or token_obj.expires_at <= (now + timedelta(minutes=5)):
#                 self.stdout.write("⚠️ Token expirado ou próximo. Tentando atualizar...")
#                 if not token_obj.refresh_token:
#                     self.stderr.write(self.style.ERROR(f"Refresh token não encontrado para {user.username}."))
#                     continue
#                 auth = (CLIENT_ID, CLIENT_SECRET)
#                 data = {"grant_type": "refresh_token", "refresh_token": token_obj.refresh_token}
#                 try:
#                     response = requests.post(TOKEN_URL, data=data, auth=auth)
#                     response.raise_for_status()
#                     new_token = response.json()
#                     expires_in = new_token.get('expires_in', 3600)
#                     token_obj.access_token = new_token["access_token"]
#                     token_obj.refresh_token = new_token.get("refresh_token", token_obj.refresh_token)
#                     token_obj.expires_at = timezone.now() + timedelta(seconds=expires_in)
#                     token_obj.save()
#                     access_token = token_obj.access_token
#                     self.stdout.write(self.style.SUCCESS("✅ Token atualizado com sucesso."))
#                 except requests.exceptions.RequestException as e:
#                     self.stderr.write(self.style.ERROR(f"Erro HTTP ao atualizar token: {e}. Resposta: {e.response.text if e.response else 'N/A'}"))
#                     print(traceback.format_exc())
#                     continue
#                 except Exception as e:
#                     self.stderr.write(self.style.ERROR(f"Erro inesperado ao atualizar token: {e}"))
#                     print(traceback.format_exc())
#                     continue
#             else:
#                 self.stdout.write("✅ Token ainda válido.")

#             headers = {
#                 "Authorization": f"Bearer {access_token}",
#                 "Content-Type": "application/json",
#                 "User-Agent": "SistemClass/1.0"
#             }

#             # --- Função com retry (sem alterações aqui) ---
#             def call_api_with_retry(url, params=None, max_retries=3, initial_delay=5):
#                 delay = initial_delay
#                 for attempt in range(max_retries):
#                     try:
#                         response = requests.get(url, headers=headers, params=params, timeout=30)
#                         if response.status_code == 429:
#                             wait_time = int(response.headers.get("Retry-After", delay))
#                             self.stdout.write(self.style.WARNING(f"⚠️ Limite (429). Aguardando {wait_time}s... (Tentativa {attempt + 1}/{max_retries})"))
#                             time.sleep(wait_time)
#                             delay = min(delay * 2, 60)
#                             continue
#                         # Apenas lança erro para 4xx (exceto 429) e 5xx
#                         if 400 <= response.status_code < 500 and response.status_code != 429:
#                             response.raise_for_status()
#                         elif response.status_code >= 500:
#                             response.raise_for_status()
#                         return response # Retorna mesmo se for erro não tratado pelo raise_for_status
#                     except requests.exceptions.RequestException as e:
#                         self.stderr.write(self.style.ERROR(f"Erro HTTP API (Tentativa {attempt + 1}/{max_retries}): {e}"))
#                         if attempt == max_retries - 1: return response # Retorna a última resposta (com erro)
#                         time.sleep(delay)
#                         delay = min(delay * 2, 60)
#                 self.stderr.write(self.style.ERROR(f"Falha API após {max_retries} tentativas: {url}"))
#                 return None # Retorna None se todas as tentativas falharem

#             # --- ALTERAÇÃO 1: Definir período de busca para 90 dias --- # <-- Pode atualizar o comentário também
#             data_fim_dt = timezone.now().date()
#             data_inicio_dt = data_fim_dt - timedelta(days=90) # <-- ALTERADO DE VOLTA PARA 90
#             data_inicio_str = data_inicio_dt.strftime('%Y-%m-%d')
#             data_fim_str = data_fim_dt.strftime('%Y-%m-%d')

#             # --- Sincronizar Contas a Receber (V2) ---
#             page = 1
#             size = 50
#             self.stdout.write("--- Buscando Contas a Receber (V2 - Abertas, Atrasadas, Recebidas) ---")
#             while True:
#                 url_receber = f"{API_BASE_URL}/v1/financeiro/eventos-financeiros/contas-a-receber/buscar"
#                 params_receber = {
#                     'pagina': page,
#                     'tamanho_pagina': size,
#                     # ALTERAÇÃO 2: Incluir status RECEBIDO
#                     'status': ['EM_ABERTO', 'ATRASADO', 'RECEBIDO'],
#                     # Usar datas de VENCIMENTO para buscar pendentes E datas de PAGAMENTO para buscar quitadas
#                     # Para simplificar, vamos buscar por data de VENCIMENTO no período e tratar o status
#                     'data_vencimento_de': data_inicio_str,
#                     'data_vencimento_ate': data_fim_str
#                     # Poderia usar data_pagamento_de/ate se quisesse APENAS as pagas no período
#                 }
#                 self.stdout.write(f"Buscando C.Receber - Página {page}...")
#                 response_receber = call_api_with_retry(url_receber, params=params_receber)

#                 if response_receber is None or response_receber.status_code != 200:
#                     self.stderr.write(self.style.ERROR(f"Erro crítico ao buscar C.Receber (Status: {response_receber.status_code if response_receber else 'N/A'}). {response_receber.text if response_receber else ''}"))
#                     break

#                 try:
#                     response_data = response_receber.json()
#                     contas_receber_ca = response_data.get('itens', [])

#                     if not contas_receber_ca:
#                         self.stdout.write("Nenhuma C.Receber encontrada nesta página. Finalizando busca.")
#                         break

#                     self.stdout.write(f"Processando {len(contas_receber_ca)} C.Receber (Pag.{page})...")
#                     for conta in contas_receber_ca:
#                         try:
#                             cliente_data = conta.get('cliente')
#                             cliente_nome = cliente_data.get('nome', 'Cliente CA V2') if isinstance(cliente_data, dict) else 'Cliente CA V2'
#                             valor_str = str(conta.get('total', '0.0')).replace(',', '.')
#                             valor = Decimal(valor_str)
#                             data_venc_str = conta.get('data_vencimento')
#                             data_venc = datetime.strptime(data_venc_str, '%Y-%m-%d').date() if data_venc_str else None

#                             if not data_venc:
#                                 self.stdout.write(self.style.WARNING(f"  -> Pulando C.Receber ID {conta.get('id', 'N/A')} sem data de vencimento."))
#                                 continue

#                             categoria_padrao, _ = Category.objects.get_or_create(name='Receita V2 Padrão')

#                             # ALTERAÇÃO 3: Lógica para atualizar status e data de pagamento
#                             status_ca = conta.get('status_traduzido') # Usa o campo traduzido
#                             is_received_ca = status_ca == 'RECEBIDO'

#                             # Tenta pegar a data de pagamento da API (VERIFICAR NOME DO CAMPO NA DOC V2!)
#                             # Supondo que o campo se chame 'data_pagamento' na resposta da API para itens quitados
#                             data_pagamento_str = None
#                             if is_received_ca:
#                                 # A API V2 retorna a data de pagamento dentro do array 'baixas'?
#                                 baixas = conta.get('baixas', [])
#                                 if baixas:
#                                     # Pega a data da primeira baixa encontrada
#                                     data_pagamento_str = baixas[0].get('data_pagamento')

#                             data_pagamento = datetime.strptime(data_pagamento_str, '%Y-%m-%d').date() if data_pagamento_str else None

#                             # Se está recebido na CA mas não temos data de pagamento, usamos a data de hoje como fallback
#                             if is_received_ca and not data_pagamento:
#                                 data_pagamento = timezone.now().date()
#                                 self.stdout.write(self.style.WARNING(f"  -> C.Receber ID {conta.get('id')} recebida sem data de pagamento na API. Usando data atual."))

#                             # Se não estiver recebido na CA, garante que a data de pagamento seja None
#                             if not is_received_ca:
#                                 data_pagamento = None

#                             obj, created = ReceivableAccount.objects.update_or_create(
#                                 user=user,
#                                 external_id=conta.get('id'),
#                                 defaults={
#                                     'name': cliente_nome,
#                                     'description': conta.get('descricao', f"Conta Azul V2 ID: {conta.get('id', 'N/A')}"),
#                                     'amount': valor,
#                                     'due_date': data_venc,
#                                     'category': categoria_padrao,
#                                     'is_received': is_received_ca, # Atualiza com o status da CA
#                                     'payment_date': data_pagamento, # Atualiza com a data de pagamento da CA
#                                     'payment_method': 'BOLETO',
#                                     'dre_area': 'BRUTA',
#                                     'occurrence': 'AVULSO',
#                                 }
#                             )
#                             action = "criada" if created else "atualizada"
#                             status_desc = "Recebida" if is_received_ca else "Pendente"
#                             self.stdout.write(f"  -> C.Receber {obj.external_id} {action}. Status: {status_desc}")


#                         except (KeyError, ValueError, TypeError, InvalidOperation) as map_error:
#                             self.stderr.write(self.style.ERROR(f"Erro mapeamento C.Receber ID {conta.get('id', 'N/A')}: {map_error}. Dados: {conta}"))
#                             print(traceback.format_exc()) # Imprime traceback completo para depuração
#                         except Exception as db_error:
#                             self.stderr.write(self.style.ERROR(f"Erro BD C.Receber ID {conta.get('id', 'N/A')}: {db_error}"))
#                             print(traceback.format_exc()) # Imprime traceback completo

#                 except ValueError as json_error:
#                     self.stderr.write(self.style.ERROR(f"Erro JSON API C.Receber: {json_error}"))
#                     break
#                 except Exception as general_error: # Captura outros erros inesperados
#                      self.stderr.write(self.style.ERROR(f"Erro geral no processamento de C.Receber: {general_error}"))
#                      print(traceback.format_exc())
#                      break


#                 page += 1
#                 time.sleep(1)

#             # --- Sincronizar Contas a Pagar (V2) ---
#             page = 1
#             self.stdout.write("--- Buscando Contas a Pagar (V2 - Abertas, Atrasadas, Quitadas) ---")
#             while True:
#                 url_pagar = f"{API_BASE_URL}/v1/financeiro/eventos-financeiros/contas-a-pagar/buscar"
#                 params_pagar = {
#                     'pagina': page,
#                     'tamanho_pagina': size,
#                     # ALTERAÇÃO 2: Incluir status equivalentes a pago (QUITADO?)
#                     # VERIFICAR NA DOC V2 O NOME CORRETO PARA "PAGO"! Supondo 'QUITADO'.
#                     'status': ['EM_ABERTO', 'ATRASADO', 'RECEBIDO'],
#                     'data_vencimento_de': data_inicio_str,
#                     'data_vencimento_ate': data_fim_str
#                 }
#                 self.stdout.write(f"Buscando C.Pagar - Página {page}...")
#                 response_pagar = call_api_with_retry(url_pagar, params=params_pagar)

#                 if response_pagar is None or response_pagar.status_code != 200:
#                     self.stderr.write(self.style.ERROR(f"Erro crítico ao buscar C.Pagar (Status: {response_pagar.status_code if response_pagar else 'N/A'}). {response_pagar.text if response_pagar else ''}"))
#                     break

#                 try:
#                     response_data = response_pagar.json()
#                     contas_pagar_ca = response_data.get('itens', [])

#                     if not contas_pagar_ca:
#                         self.stdout.write("Nenhuma C.Pagar encontrada nesta página. Finalizando busca.")
#                         break

#                     self.stdout.write(f"Processando {len(contas_pagar_ca)} C.Pagar (Pag.{page})...")
#                     for conta in contas_pagar_ca:
#                         try:
#                             fornecedor_data = conta.get('fornecedor')
#                             fornecedor_nome = fornecedor_data.get('nome', 'Fornecedor CA V2') if isinstance(fornecedor_data, dict) else 'Fornecedor CA V2'
#                             valor_str = str(conta.get('total', '0.0')).replace(',', '.')
#                             valor = Decimal(valor_str)
#                             data_venc_str = conta.get('data_vencimento')
#                             data_venc = datetime.strptime(data_venc_str, '%Y-%m-%d').date() if data_venc_str else None

#                             if not data_venc:
#                                 self.stdout.write(self.style.WARNING(f"  -> Pulando C.Pagar ID {conta.get('id', 'N/A')} sem data de vencimento."))
#                                 continue

#                             categoria_padrao, _ = Category.objects.get_or_create(name='Despesa V2 Padrão')

#                             # ALTERAÇÃO 3: Lógica para atualizar status e data de pagamento
#                             # VERIFICAR O NOME CORRETO DO STATUS PAGO NA DOC V2! Supondo 'QUITADO'.
#                             status_ca = conta.get('status_traduzido')
#                             is_paid_ca = status_ca == 'RECEBIDO' # OU 'PAGO', etc.

#                             data_pagamento_str = None
#                             if is_paid_ca:
#                                 baixas = conta.get('baixas', [])
#                                 if baixas:
#                                     data_pagamento_str = baixas[0].get('data_pagamento')

#                             data_pagamento = datetime.strptime(data_pagamento_str, '%Y-%m-%d').date() if data_pagamento_str else None

#                             if is_paid_ca and not data_pagamento:
#                                 data_pagamento = timezone.now().date()
#                                 self.stdout.write(self.style.WARNING(f"  -> C.Pagar ID {conta.get('id')} quitada sem data de pagamento na API. Usando data atual."))

#                             if not is_paid_ca:
#                                 data_pagamento = None


#                             obj, created = PayableAccount.objects.update_or_create(
#                                 user=user,
#                                 external_id=conta.get('id'),
#                                 defaults={
#                                     'name': fornecedor_nome,
#                                     'description': conta.get('descricao', f"Conta Azul V2 ID: {conta.get('id', 'N/A')}"),
#                                     'amount': valor,
#                                     'due_date': data_venc,
#                                     'category': categoria_padrao,
#                                     'is_paid': is_paid_ca, # Atualiza com o status da CA
#                                     'payment_date': data_pagamento, # Atualiza com a data de pagamento da CA
#                                     'payment_method': 'BOLETO',
#                                     'dre_area': 'OPERACIONAL',
#                                     'occurrence': 'AVULSO',
#                                     'cost_type': 'FIXO',
#                                 }
#                             )
#                             action = "criada" if created else "atualizada"
#                             status_desc = "Recebida/Paga" if is_paid_ca else "Pendente" # <-- Ajuste aqui também
#                             self.stdout.write(f"  -> C.Pagar {obj.external_id} {action}. Status: {status_desc}")


#                         except (KeyError, ValueError, TypeError, InvalidOperation) as map_error:
#                             self.stderr.write(self.style.ERROR(f"Erro mapeamento C.Pagar ID {conta.get('id', 'N/A')}: {map_error}. Dados: {conta}"))
#                             print(traceback.format_exc())
#                         except Exception as db_error:
#                             self.stderr.write(self.style.ERROR(f"Erro BD C.Pagar ID {conta.get('id', 'N/A')}: {db_error}"))
#                             print(traceback.format_exc())

#                 except ValueError as json_error:
#                     self.stderr.write(self.style.ERROR(f"Erro JSON API C.Pagar: {json_error}"))
#                     break
#                 except Exception as general_error:
#                      self.stderr.write(self.style.ERROR(f"Erro geral no processamento de C.Pagar: {general_error}"))
#                      print(traceback.format_exc())
#                      break

#                 page += 1
#                 time.sleep(1)

#             self.stdout.write(self.style.SUCCESS(f"Sincronização concluída para {user.username}."))

#         self.stdout.write(self.style.SUCCESS("--- Fim do processo de sincronização ---"))

# accounts/management/commands/sync_conta_azul.py
# accounts/management/commands/sync_conta_azul.py
import os
import time
import requests
import traceback
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from datetime import datetime, timedelta, date
from django.utils import timezone
from decimal import Decimal, InvalidOperation

from accounts.models import ContaAzulCredentials as ContaAzulToken
from accounts.models import ReceivableAccount, PayableAccount, Category, ClassificacaoAutomatica

CLIENT_ID = os.environ.get('CONTA_AZUL_CLIENT_ID')
CLIENT_SECRET = os.environ.get('CONTA_AZUL_CLIENT_SECRET')
TOKEN_URL = 'https://auth.contaazul.com/oauth2/token'
API_BASE_URL = 'https://api-v2.contaazul.com'

class Command(BaseCommand):
    help = "Sincroniza Contas (Abertas, Atrasadas e Quitadas) sem sobrepor edições manuais."
    # --- COLE O BLOCO AQUI ---
    def prever_classificacao(self, user, descricao, tipo):
        # Busca regras do usuário para o tipo (Pagar/Receber)
        regras = ClassificacaoAutomatica.objects.filter(user=user, tipo=tipo)
        descricao_lower = descricao.lower()
        
        for regra in regras:
            if regra.termo.lower() in descricao_lower:
                return regra.categoria, regra.dre_area
        return None, None
    # -------------------------
    def handle(self, *args, **options):
        User = get_user_model()
        self.stdout.write(self.style.SUCCESS("--- Iniciando sincronização Conta Azul ---"))

        if not CLIENT_ID or not CLIENT_SECRET:
            self.stderr.write(self.style.ERROR("Client ID ou Client Secret não configurados."))
            return

        for user in User.objects.filter(is_active=True):
            self.stdout.write(f"\n--- Sincronizando Conta Azul para: {user.username} ---")

            token_obj = ContaAzulToken.objects.filter(user=user).first()
            if not token_obj:
                self.stdout.write(self.style.WARNING(f"Usuário {user.username} sem credenciais Conta Azul."))
                continue

            # --- Bloco de Atualização de Token (Sem alterações) ---
            access_token = token_obj.access_token
            headers = {}
            now = timezone.now()
            if not token_obj.expires_at or token_obj.expires_at <= (now + timedelta(minutes=5)):
                self.stdout.write("⚠️ Token expirado ou próximo. Tentando atualizar...")
                if not token_obj.refresh_token:
                    self.stderr.write(self.style.ERROR(f"Refresh token não encontrado para {user.username}."))
                    continue
                auth = (CLIENT_ID, CLIENT_SECRET)
                data = {"grant_type": "refresh_token", "refresh_token": token_obj.refresh_token}
                try:
                    response = requests.post(TOKEN_URL, data=data, auth=auth)
                    response.raise_for_status()
                    new_token = response.json()
                    expires_in = new_token.get('expires_in', 3600)
                    token_obj.access_token = new_token["access_token"]
                    token_obj.refresh_token = new_token.get("refresh_token", token_obj.refresh_token)
                    token_obj.expires_at = timezone.now() + timedelta(seconds=expires_in)
                    token_obj.save()
                    access_token = token_obj.access_token
                    self.stdout.write(self.style.SUCCESS("✅ Token atualizado com sucesso."))
                except requests.exceptions.RequestException as e:
                    self.stderr.write(self.style.ERROR(f"Erro HTTP ao atualizar token: {e}. Resposta: {e.response.text if e.response else 'N/A'}"))
                    continue
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Erro inesperado ao atualizar token: {e}"))
                    continue
            else:
                self.stdout.write("✅ Token ainda válido.")

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "User-Agent": "SistemClass/1.0"
            }

            # --- Função com retry (Sem alterações) ---
            def call_api_with_retry(url, params=None, max_retries=3, initial_delay=5):
                delay = initial_delay
                for attempt in range(max_retries):
                    try:
                        response = requests.get(url, headers=headers, params=params, timeout=30)
                        if response.status_code == 429:
                            wait_time = int(response.headers.get("Retry-After", delay))
                            self.stdout.write(self.style.WARNING(f"⚠️ Limite (429). Aguardando {wait_time}s... (Tentativa {attempt + 1}/{max_retries})"))
                            time.sleep(wait_time)
                            delay = min(delay * 2, 60)
                            continue
                        if 400 <= response.status_code < 500 and response.status_code != 429:
                            response.raise_for_status()
                        elif response.status_code >= 500:
                            response.raise_for_status()
                        return response
                    except requests.exceptions.RequestException as e:
                        self.stderr.write(self.style.ERROR(f"Erro HTTP API (Tentativa {attempt + 1}/{max_retries}): {e}"))
                        if attempt == max_retries - 1: return response
                        time.sleep(delay)
                        delay = min(delay * 2, 60)
                self.stderr.write(self.style.ERROR(f"Falha API após {max_retries} tentativas: {url}"))
                return None

            # --- Período de busca de 45 dias ---
            data_fim_dt = timezone.now().date()
            data_inicio_dt = data_fim_dt - timedelta(days=90)
            data_inicio_str = data_inicio_dt.strftime('%Y-%m-%d')
            data_fim_str = data_fim_dt.strftime('%Y-%m-%d')


            # --- Sincronizar Contas a Receber (V2) ---
            page = 1
            size = 50
            self.stdout.write("--- Buscando Contas a Receber (V2 - Abertas, Atrasadas, Recebidas) ---")
            while True:
                url_receber = f"{API_BASE_URL}/v1/financeiro/eventos-financeiros/contas-a-receber/buscar"
                params_receber = {
                    'pagina': page,
                    'tamanho_pagina': size,
                    'status': ['EM_ABERTO', 'ATRASADO', 'RECEBIDO'],
                    'data_vencimento_de': data_inicio_str,
                    'data_vencimento_ate': data_fim_str
                }
                self.stdout.write(f"Buscando C.Receber - Página {page}...")
                response_receber = call_api_with_retry(url_receber, params=params_receber)

                if response_receber is None or response_receber.status_code != 200:
                    self.stderr.write(self.style.ERROR(f"Erro crítico ao buscar C.Receber. {response_receber.text if response_receber else ''}"))
                    break
                try:
                    response_data = response_receber.json()
                    contas_receber_ca = response_data.get('itens', [])
                    if not contas_receber_ca:
                        self.stdout.write("Nenhuma C.Receber encontrada nesta página. Finalizando busca.")
                        break

                    self.stdout.write(f"Processando {len(contas_receber_ca)} C.Receber (Pag.{page})...")
                    for conta in contas_receber_ca:
                        try:
                            # --- ★★★ INÍCIO DO BLOCO CORRIGIDO PARA C.RECEBER ★★★ ---
                            status_ca = conta.get('status_traduzido')
                            is_received_ca = status_ca == 'RECEBIDO'
                            data_pagamento = None # Inicializa como None por padrão

                            if is_received_ca:
                                data_pagamento_str = None
                                baixas = conta.get('baixas', [])
                                if baixas:
                                    data_pagamento_str = baixas[0].get('data_pagamento')
                                
                                # Processa a data SÓ SE ela foi encontrada
                                if data_pagamento_str:
                                    data_pagamento = datetime.strptime(data_pagamento_str, '%Y-%m-%d').date()
                                else:
                                    # Fallback: se está recebido mas não tem data, usa hoje
                                    data_pagamento = timezone.now().date()
                                    self.stdout.write(self.style.WARNING(f"  -> C.Receber ID {conta.get('id')} recebida sem data de pagamento na API. Usando data atual."))

                            # Mapeamento dos outros dados (continua igual)
                            cliente_data = conta.get('cliente')
                            cliente_nome = cliente_data.get('nome', 'Cliente CA V2') if isinstance(cliente_data, dict) else 'Cliente CA V2'
                            valor = Decimal(str(conta.get('total', '0.0')).replace(',', '.'))
                            data_venc_str = conta.get('data_vencimento')
                            data_venc = datetime.strptime(data_venc_str, '%Y-%m-%d').date() if data_venc_str else None
                            if not data_venc: continue
                            
                            # 1. Define a categoria padrão
                            # ADICIONEI user=user para garantir que a categoria seja criada para o usuário certo
                            categoria_padrao, _ = Category.objects.get_or_create(name='Receita V2 Padrão', category_type='RECEIVABLE', user=user)
                            
                            # 2. Tenta prever a classificação inteligente
                            cat_inteligente, dre_inteligente = self.prever_classificacao(user, cliente_nome, 'RECEIVABLE')
                            
                            # Define o que será usado (Inteligência tem preferência sobre o Padrão)
                            categoria_final = cat_inteligente if cat_inteligente else categoria_padrao
                            dre_final = dre_inteligente if dre_inteligente else 'BRUTA'

                            # Lógica CORRIGIDA: Busca apenas pelo external_id
                            obj, created = ReceivableAccount.objects.update_or_create(
                                external_id=conta.get('id'),  # <--- CHAVE ÚNICA DE BUSCA
                                defaults={
                                    'user': user,  # <--- Movemos o user para cá (atualiza o dono se mudar)
                                    'name': cliente_nome,
                                    'description': conta.get('descricao', ''),
                                    'amount': valor,
                                    'due_date': data_venc,
                                    'is_received': is_received_ca,
                                    'payment_date': data_pagamento,
                                    'category': categoria_final,
                                    'payment_method': 'BOLETO',
                                    'dre_area': dre_final,
                                    'occurrence': 'AVULSO',
                                }
                            )
                            
                            # Removemos o bloco "if not created", pois o update_or_create já faz tudo!
                            
                            # Apenas o log de inteligência (opcional, se quiser manter)
                            if not created and cat_inteligente and obj.category.name == 'Receita V2 Padrão':
                                 obj.category = cat_inteligente
                                 obj.dre_area = dre_inteligente
                                 obj.save()
                                 self.stdout.write(self.style.SUCCESS(f"    -> [Update] Classificação inteligente aplicada: {cat_inteligente.name}"))

                            action = "criada" if created else "atualizada"
                            status_desc = "Recebida" if is_received_ca else "Pendente"
                            self.stdout.write(f"  -> C.Receber {obj.external_id} {action}. Status: {status_desc}")

                        except Exception as e:
                            self.stderr.write(self.style.ERROR(f"Erro ao processar C.Receber ID {conta.get('id', 'N/A')}: {e}"))
                            print(traceback.format_exc())

                except Exception as e:
                     self.stderr.write(self.style.ERROR(f"Erro geral no processamento de C.Receber: {e}"))
                     print(traceback.format_exc())
                     break
                page += 1
                time.sleep(1)

            # --- Sincronizar Contas a Pagar (V2) ---
            page = 1
            self.stdout.write("--- Buscando Contas a Pagar (V2 - Abertas, Atrasadas, Pagas) ---")
            while True:
                url_pagar = f"{API_BASE_URL}/v1/financeiro/eventos-financeiros/contas-a-pagar/buscar"
                params_pagar = {
                    'pagina': page, 'tamanho_pagina': size,
                    'status': ['EM_ABERTO', 'ATRASADO', 'RECEBIDO'],
                    'data_vencimento_de': data_inicio_str, 'data_vencimento_ate': data_fim_str
                }
                self.stdout.write(f"Buscando C.Pagar - Página {page}...")
                response_pagar = call_api_with_retry(url_pagar, params=params_pagar)

                if response_pagar is None or response_pagar.status_code != 200:
                    self.stderr.write(self.style.ERROR(f"Erro crítico ao buscar C.Pagar. {response_pagar.text if response_pagar else ''}"))
                    break
                try:
                    response_data = response_pagar.json()
                    contas_pagar_ca = response_data.get('itens', [])
                    if not contas_pagar_ca:
                        self.stdout.write("Nenhuma C.Pagar encontrada nesta página. Finalizando busca.")
                        break

                    self.stdout.write(f"Processando {len(contas_pagar_ca)} C.Pagar (Pag.{page})...")
                    for conta in contas_pagar_ca:
                        try:
                            # --- ★★★ INÍCIO DO BLOCO CORRIGIDO PARA C.PAGAR ★★★ ---
                            status_ca = conta.get('status_traduzido')
                            is_paid_ca = status_ca == 'RECEBIDO'
                            data_pagamento = None # Inicializa como None por padrão

                            if is_paid_ca:
                                data_pagamento_str = None
                                baixas = conta.get('baixas', [])
                                if baixas:
                                    data_pagamento_str = baixas[0].get('data_pagamento')
                                
                                if data_pagamento_str:
                                    data_pagamento = datetime.strptime(data_pagamento_str, '%Y-%m-%d').date()
                                else:
                                    data_pagamento = timezone.now().date()
                                    self.stdout.write(self.style.WARNING(f"  -> C.Pagar ID {conta.get('id')} quitada sem data de pagamento na API. Usando data atual."))
                            
                            # Mapeamento dos outros dados (continua igual)
                            fornecedor_data = conta.get('fornecedor')
                            fornecedor_nome = fornecedor_data.get('nome', 'Fornecedor CA V2') if isinstance(fornecedor_data, dict) else 'Fornecedor CA V2'
                            valor = Decimal(str(conta.get('total', '0.0')).replace(',', '.'))
                            data_venc_str = conta.get('data_vencimento')
                            data_venc = datetime.strptime(data_venc_str, '%Y-%m-%d').date() if data_venc_str else None
                            if not data_venc: continue
                            
                            # 1. Define a categoria padrão
                            # ADICIONEI user=user aqui também
                            categoria_padrao, _ = Category.objects.get_or_create(name='Despesa V2 Padrão', category_type='PAYABLE', user=user)

                            # 2. Tenta prever a classificação inteligente
                            cat_inteligente, dre_inteligente = self.prever_classificacao(user, fornecedor_nome, 'PAYABLE')

                            # Define o que será usado (Inteligência > Padrão)
                            categoria_final = cat_inteligente if cat_inteligente else categoria_padrao
                            dre_final = dre_inteligente if dre_inteligente else 'OPERACIONAL'

                            # Lógica CORRIGIDA: Busca apenas pelo external_id
                            obj, created = PayableAccount.objects.update_or_create(
                                external_id=conta.get('id'), # <--- CHAVE ÚNICA DE BUSCA
                                defaults={
                                    'user': user, # <--- Movemos o user para cá
                                    'name': fornecedor_nome,
                                    'description': conta.get('descricao', ''),
                                    'amount': valor,
                                    'due_date': data_venc,
                                    'is_paid': is_paid_ca,
                                    'payment_date': data_pagamento,
                                    'category': categoria_final,
                                    'payment_method': 'BOLETO',
                                    'dre_area': dre_final,
                                    'occurrence': 'AVULSO',
                                    'cost_type': 'FIXO',
                                }
                            )

                            # Removemos o bloco "if not created" manual.
                            
                            # Mantemos apenas a inteligência se for update
                            if not created and cat_inteligente and obj.category.name == 'Despesa V2 Padrão':
                                obj.category = cat_inteligente
                                obj.dre_area = dre_inteligente
                                obj.save()
                                self.stdout.write(self.style.SUCCESS(f"    -> [Update] Classificação inteligente aplicada: {cat_inteligente.name}"))

                            action = "criada" if created else "atualizada"
                            status_desc = "Recebida/Paga" if is_paid_ca else "Pendente"
                            self.stdout.write(f"  -> C.Pagar {obj.external_id} {action}. Status: {status_desc}")

                        except Exception as e:
                            self.stderr.write(self.style.ERROR(f"Erro ao processar C.Pagar ID {conta.get('id', 'N/A')}: {e}"))
                            print(traceback.format_exc())

                except Exception as e:
                     self.stderr.write(self.style.ERROR(f"Erro geral no processamento de C.Pagar: {e}"))
                     print(traceback.format_exc())
                     break

                page += 1
                time.sleep(1)

            self.stdout.write(self.style.SUCCESS(f"Sincronização concluída para {user.username}."))

        self.stdout.write(self.style.SUCCESS("--- Fim do processo de sincronização ---"))