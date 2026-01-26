
# import os
# import time
# import requests
# import traceback
# from django.core.management.base import BaseCommand
# from django.contrib.auth import get_user_model
# from django.conf import settings
# from datetime import datetime, timedelta, date
# from django.utils import timezone
# from decimal import Decimal, InvalidOperation

# from accounts.models import ContaAzulCredentials as ContaAzulToken
# from accounts.models import ReceivableAccount, PayableAccount, Category, ClassificacaoAutomatica, BankAccount

# CLIENT_ID = os.environ.get('CONTA_AZUL_CLIENT_ID')
# CLIENT_SECRET = os.environ.get('CONTA_AZUL_CLIENT_SECRET')
# TOKEN_URL = 'https://auth.contaazul.com/oauth2/token'
# API_BASE_URL = 'https://api-v2.contaazul.com'

# class Command(BaseCommand):
#     help = "Sincroniza Contas (Abertas, Atrasadas e Quitadas) sem sobrepor edições manuais."
#     # --- COLE O BLOCO AQUI ---
#     def prever_classificacao(self, user, descricao, tipo):
#         # Busca regras do usuário para o tipo (Pagar/Receber)
#         regras = ClassificacaoAutomatica.objects.filter(user=user, tipo=tipo)
#         descricao_lower = descricao.lower()
        
#         for regra in regras:
#             if regra.termo.lower() in descricao_lower:
#                 return regra.categoria, regra.dre_area, regra.bank_account  
#         return None, None, None
#     # -------------------------
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

#             # --- Bloco de Atualização de Token (Sem alterações) ---
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
#                     continue
#                 except Exception as e:
#                     self.stderr.write(self.style.ERROR(f"Erro inesperado ao atualizar token: {e}"))
#                     continue
#             else:
#                 self.stdout.write("✅ Token ainda válido.")

#             headers = {
#                 "Authorization": f"Bearer {access_token}",
#                 "Content-Type": "application/json",
#                 "User-Agent": "SistemClass/1.0"
#             }

#             # --- Função com retry (Sem alterações) ---
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
#                         if 400 <= response.status_code < 500 and response.status_code != 429:
#                             response.raise_for_status()
#                         elif response.status_code >= 500:
#                             response.raise_for_status()
#                         return response
#                     except requests.exceptions.RequestException as e:
#                         self.stderr.write(self.style.ERROR(f"Erro HTTP API (Tentativa {attempt + 1}/{max_retries}): {e}"))
#                         if attempt == max_retries - 1: return response
#                         time.sleep(delay)
#                         delay = min(delay * 2, 60)
#                 self.stderr.write(self.style.ERROR(f"Falha API após {max_retries} tentativas: {url}"))
#                 return None

#             # --- Período de busca de 45 dias ---
#             data_fim_dt = timezone.now().date()
#             data_inicio_dt = data_fim_dt - timedelta(days=90)
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
#                     'status': ['EM_ABERTO', 'ATRASADO', 'RECEBIDO'],
#                     'data_vencimento_de': data_inicio_str,
#                     'data_vencimento_ate': data_fim_str
#                 }
#                 self.stdout.write(f"Buscando C.Receber - Página {page}...")
#                 response_receber = call_api_with_retry(url_receber, params=params_receber)

#                 if response_receber is None or response_receber.status_code != 200:
#                     self.stderr.write(self.style.ERROR(f"Erro crítico ao buscar C.Receber. {response_receber.text if response_receber else ''}"))
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
#                             # --- ★★★ INÍCIO DO BLOCO CORRIGIDO PARA C.RECEBER ★★★ ---
#                             status_ca = conta.get('status_traduzido')
#                             is_received_ca = status_ca == 'RECEBIDO'
#                             data_pagamento = None # Inicializa como None por padrão

#                             if is_received_ca:
#                                 data_pagamento_str = None
#                                 baixas = conta.get('baixas', [])
#                                 if baixas:
#                                     data_pagamento_str = baixas[0].get('data_pagamento')
                                
#                                 # Processa a data SÓ SE ela foi encontrada
#                                 if data_pagamento_str:
#                                     data_pagamento = datetime.strptime(data_pagamento_str, '%Y-%m-%d').date()
#                                 else:
#                                     # Fallback: se está recebido mas não tem data, usa hoje
#                                     data_pagamento = timezone.now().date()
#                                     self.stdout.write(self.style.WARNING(f"  -> C.Receber ID {conta.get('id')} recebida sem data de pagamento na API. Usando data atual."))

#                             # Mapeamento dos outros dados (continua igual)
#                             cliente_data = conta.get('cliente')
#                             cliente_nome = cliente_data.get('nome', 'Cliente CA V2') if isinstance(cliente_data, dict) else 'Cliente CA V2'
#                             valor = Decimal(str(conta.get('total', '0.0')).replace(',', '.'))
#                             data_venc_str = conta.get('data_vencimento')
#                             data_venc = datetime.strptime(data_venc_str, '%Y-%m-%d').date() if data_venc_str else None
#                             if not data_venc: continue
                            
#                             # 1. Verifica se já existe para PRESERVAR classificações manuais
#                             try:
#                                 obj_existente = ReceivableAccount.objects.get(external_id=conta.get('id'))
#                                 existe = True
#                             except ReceivableAccount.DoesNotExist:
#                                 obj_existente = None
#                                 existe = False

#                             # 2. Previsão Inteligente
#                             cat_inteligente, dre_inteligente, banco_inteligente = self.prever_classificacao(user, cliente_nome, 'RECEIVABLE')
#                             # categoria_padrao, _ = Category.objects.get_or_create(name='Receita V2 Padrão', category_type='RECEIVABLE', user=user)
#                             categoria_padrao, _ = Category.objects.get_or_create(name='Receitas de Vendas', category_type='RECEIVABLE', user=user)

#                             # 3. Define Categoria/DRE/Banco (BLINDAGEM)
#                             if existe:
#                                 # Se já existe, MANTÉM o que está no banco (não sobrescreve edição manual)
#                                 cat_final = obj_existente.category
#                                 dre_final = obj_existente.dre_area
#                                 bank_final = obj_existente.bank_account
#                             else:
#                                 # Se é novo, usa inteligência ou padrão
#                                 cat_final = cat_inteligente if cat_inteligente else categoria_padrao
#                                 dre_final = dre_inteligente if dre_inteligente else 'BRUTA'
#                                 bank_final = banco_inteligente

#                             # 4. Atualiza ou Cria (Agora seguro)
#                             obj, created = ReceivableAccount.objects.update_or_create(
#                                 external_id=conta.get('id'),
#                                 defaults={
#                                     'user': user,
#                                     'name': cliente_nome,
#                                     'description': conta.get('descricao', ''),
#                                     'amount': valor,
#                                     'due_date': data_venc,
#                                     'is_received': is_received_ca,
#                                     'payment_date': data_pagamento,
#                                     'payment_method': 'BOLETO',
#                                     'occurrence': 'AVULSO',
#                                     # Usa as variáveis blindadas acima
#                                     'category': cat_final,
#                                     'dre_area': dre_final,
#                                     'bank_account': bank_final, 
#                                 }
#                             )
                            
#                             # 5. Refinamento: Se existe mas ainda é "Padrão", permite inteligência atualizar
#                             # if not created and obj.category.name == 'Receita V2 Padrão' and cat_inteligente:
#                             if not created and obj.category.name == 'Receitas de Vendas' and cat_inteligente:
#                                  obj.category = cat_inteligente
#                                  obj.dre_area = dre_inteligente if dre_inteligente else obj.dre_area
#                                  if banco_inteligente: obj.bank_account = banco_inteligente
#                                  obj.save()
#                                  self.stdout.write(self.style.SUCCESS(f"    -> [Smart Update] Categoria atualizada de Padrão para {cat_inteligente.name}"))

#                             action = "criada" if created else "atualizada (Blindada)"
#                             status_desc = "Recebida" if is_received_ca else "Pendente"
#                             self.stdout.write(f"  -> C.Receber {obj.external_id} {action}. Status: {status_desc}")

#                         except Exception as e:
#                             self.stderr.write(self.style.ERROR(f"Erro ao processar C.Receber ID {conta.get('id', 'N/A')}: {e}"))
#                             print(traceback.format_exc())

#                 except Exception as e:
#                      self.stderr.write(self.style.ERROR(f"Erro geral no processamento de C.Receber: {e}"))
#                      print(traceback.format_exc())
#                      break
#                 page += 1
#                 time.sleep(1)

#             # --- Sincronizar Contas a Pagar (V2) ---
#             page = 1
#             self.stdout.write("--- Buscando Contas a Pagar (V2 - Abertas, Atrasadas, Pagas) ---")
#             while True:
#                 url_pagar = f"{API_BASE_URL}/v1/financeiro/eventos-financeiros/contas-a-pagar/buscar"
#                 params_pagar = {
#                     'pagina': page, 'tamanho_pagina': size,
#                     'status': ['EM_ABERTO', 'ATRASADO', 'RECEBIDO'],
#                     'data_vencimento_de': data_inicio_str, 'data_vencimento_ate': data_fim_str
#                 }
#                 self.stdout.write(f"Buscando C.Pagar - Página {page}...")
#                 response_pagar = call_api_with_retry(url_pagar, params=params_pagar)

#                 if response_pagar is None or response_pagar.status_code != 200:
#                     self.stderr.write(self.style.ERROR(f"Erro crítico ao buscar C.Pagar. {response_pagar.text if response_pagar else ''}"))
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
#                             # --- ★★★ INÍCIO DO BLOCO CORRIGIDO PARA C.PAGAR ★★★ ---
#                             status_ca = conta.get('status_traduzido')
#                             is_paid_ca = status_ca == 'RECEBIDO'
#                             data_pagamento = None # Inicializa como None por padrão

#                             if is_paid_ca:
#                                 data_pagamento_str = None
#                                 baixas = conta.get('baixas', [])
#                                 if baixas:
#                                     data_pagamento_str = baixas[0].get('data_pagamento')
                                
#                                 if data_pagamento_str:
#                                     data_pagamento = datetime.strptime(data_pagamento_str, '%Y-%m-%d').date()
#                                 else:
#                                     data_pagamento = timezone.now().date()
#                                     self.stdout.write(self.style.WARNING(f"  -> C.Pagar ID {conta.get('id')} quitada sem data de pagamento na API. Usando data atual."))
                            
#                             # Mapeamento dos outros dados (continua igual)
#                             fornecedor_data = conta.get('fornecedor')
#                             fornecedor_nome = fornecedor_data.get('nome', 'Fornecedor CA V2') if isinstance(fornecedor_data, dict) else 'Fornecedor CA V2'
#                             valor = Decimal(str(conta.get('total', '0.0')).replace(',', '.'))
#                             data_venc_str = conta.get('data_vencimento')
#                             data_venc = datetime.strptime(data_venc_str, '%Y-%m-%d').date() if data_venc_str else None
#                             if not data_venc: continue
                            
#                             # 1. Verifica se já existe para PRESERVAR classificações manuais
#                             try:
#                                 obj_existente = PayableAccount.objects.get(external_id=conta.get('id'))
#                                 existe = True
#                             except PayableAccount.DoesNotExist:
#                                 obj_existente = None
#                                 existe = False

#                             # 2. Previsão Inteligente
#                             cat_inteligente, dre_inteligente, banco_inteligente = self.prever_classificacao(user, fornecedor_nome, 'PAYABLE')
#                             # categoria_padrao, _ = Category.objects.get_or_create(name='Despesa V2 Padrão', category_type='PAYABLE', user=user)
#                             categoria_padrao, _ = Category.objects.get_or_create(name='Despesas Operacionais (-)', category_type='PAYABLE', user=user)

#                             # 3. Define Categoria/DRE/Banco (BLINDAGEM)
#                             if existe:
#                                 # Se já existe, MANTÉM o que está no banco
#                                 cat_final = obj_existente.category
#                                 dre_final = obj_existente.dre_area
#                                 bank_final = obj_existente.bank_account
#                             else:
#                                 # Se é novo, usa inteligência ou padrão
#                                 cat_final = cat_inteligente if cat_inteligente else categoria_padrao
#                                 dre_final = dre_inteligente if dre_inteligente else 'OPERACIONAL'
#                                 bank_final = banco_inteligente

#                             # 4. Atualiza ou Cria
#                             obj, created = PayableAccount.objects.update_or_create(
#                                 external_id=conta.get('id'),
#                                 defaults={
#                                     'user': user,
#                                     'name': fornecedor_nome,
#                                     'description': conta.get('descricao', ''),
#                                     'amount': valor,
#                                     'due_date': data_venc,
#                                     'is_paid': is_paid_ca,
#                                     'payment_date': data_pagamento,
#                                     'payment_method': 'BOLETO',
#                                     'occurrence': 'AVULSO',
#                                     'cost_type': 'FIXO',
#                                     # Usa as variáveis blindadas acima
#                                     'category': cat_final,
#                                     'dre_area': dre_final,
#                                     'bank_account': bank_final,
#                                 }
#                             )

#                             # 5. Refinamento: Se existe mas ainda é "Padrão", permite inteligência atualizar
#                             # if not created and obj.category.name == 'Despesa V2 Padrão' and cat_inteligente:
#                             if not created and obj.category.name == 'Despesas Operacionais (-)' and cat_inteligente:
#                                 obj.category = cat_inteligente
#                                 obj.dre_area = dre_inteligente if dre_inteligente else obj.dre_area
#                                 if banco_inteligente: obj.bank_account = banco_inteligente
#                                 obj.save()
#                                 self.stdout.write(self.style.SUCCESS(f"    -> [Smart Update] Categoria atualizada de Padrão para {cat_inteligente.name}"))

#                             action = "criada" if created else "atualizada (Blindada)"
#                             status_desc = "Recebida/Paga" if is_paid_ca else "Pendente"
#                             self.stdout.write(f"  -> C.Pagar {obj.external_id} {action}. Status: {status_desc}")

#                         except Exception as e:
#                             self.stderr.write(self.style.ERROR(f"Erro ao processar C.Pagar ID {conta.get('id', 'N/A')}: {e}"))
#                             print(traceback.format_exc())

#                 except Exception as e:
#                      self.stderr.write(self.style.ERROR(f"Erro geral no processamento de C.Pagar: {e}"))
#                      print(traceback.format_exc())
#                      break

#                 page += 1
#                 time.sleep(1)

#             self.stdout.write(self.style.SUCCESS(f"Sincronização concluída para {user.username}."))

#         self.stdout.write(self.style.SUCCESS("--- Fim do processo de sincronização ---"))

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
from accounts.models import ReceivableAccount, PayableAccount, Category, ClassificacaoAutomatica, BankAccount

CLIENT_ID = os.environ.get('CONTA_AZUL_CLIENT_ID')
CLIENT_SECRET = os.environ.get('CONTA_AZUL_CLIENT_SECRET')
TOKEN_URL = 'https://auth.contaazul.com/oauth2/token'
API_BASE_URL = 'https://api-v2.contaazul.com'

class Command(BaseCommand):
    help = "Sincroniza Contas (Abertas, Atrasadas e Quitadas) com Busca Dupla (Vencimento e Pagamento)."

    # Mantenha os imports e variáveis globais como estão no topo do arquivo...

    # --- SUBSTITUA A PARTIR DAQUI (Dentro da class Command) ---

    def prever_classificacao(self, user, descricao, tipo):
        # Proteção extra: se a descrição vier vazia, retorna nada imediatamente
        if not descricao:
            return None, None, None, None

        regras = ClassificacaoAutomatica.objects.filter(user=user, tipo=tipo)
        descricao_lower = descricao.lower()
        
        for regra in regras:
            if regra.termo.lower() in descricao_lower:
                return regra.categoria, regra.dre_area, regra.bank_account, regra.centro_custo  
        return None, None, None, None

    def handle(self, *args, **options):
        User = get_user_model()
        self.stdout.write(self.style.SUCCESS("--- Iniciando sincronização Conta Azul (Correção API) ---"))

        if not CLIENT_ID or not CLIENT_SECRET:
            self.stderr.write(self.style.ERROR("Client ID ou Client Secret não configurados."))
            return

        for user in User.objects.filter(is_active=True):
            self.stdout.write(f"\n--- Sincronizando Conta Azul para: {user.username} ---")

            token_obj = ContaAzulToken.objects.filter(user=user).first()
            if not token_obj:
                self.stdout.write(self.style.WARNING(f"Usuário {user.username} sem credenciais Conta Azul."))
                continue

            # --- Atualização de Token ---
            access_token = token_obj.access_token
            headers = {}
            now = timezone.now()
            if not token_obj.expires_at or token_obj.expires_at <= (now + timedelta(minutes=5)):
                self.stdout.write("⚠️ Token expirado ou próximo. Tentando atualizar...")
                if not token_obj.refresh_token:
                    continue
                auth = (CLIENT_ID, CLIENT_SECRET)
                data = {"grant_type": "refresh_token", "refresh_token": token_obj.refresh_token}
                try:
                    response = requests.post(TOKEN_URL, data=data, auth=auth)
                    response.raise_for_status()
                    new_token = response.json()
                    token_obj.access_token = new_token["access_token"]
                    token_obj.refresh_token = new_token.get("refresh_token", token_obj.refresh_token)
                    token_obj.expires_at = timezone.now() + timedelta(seconds=new_token.get('expires_in', 3600))
                    token_obj.save()
                    access_token = token_obj.access_token
                    self.stdout.write("✅ Token atualizado.")
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Erro token: {e}"))
                    continue

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "User-Agent": "SistemClass/1.0"
            }

            def call_api_with_retry(url, params=None):
                for attempt in range(3):
                    try:
                        r = requests.get(url, headers=headers, params=params, timeout=30)
                        if r.status_code == 429:
                            time.sleep(5)
                            continue
                        if r.status_code >= 400:
                            r.raise_for_status()
                        return r
                    except Exception:
                        if attempt == 2: return None
                        time.sleep(2)
                return None

            # --- CONFIGURAÇÃO DE DATAS ---
            # Voltamos ao padrão seguro: Busca por vencimento com janela larga
            # Isso pega o que venceu recentemente E o que estava atrasado (dentro de 90 dias)
            dias_busca = 90 
            data_fim_dt = timezone.now().date()
            data_inicio_dt = data_fim_dt - timedelta(days=dias_busca)
            
            data_inicio_str = data_inicio_dt.strftime('%Y-%m-%d')
            data_fim_str = data_fim_dt.strftime('%Y-%m-%d')
            # Pega também o futuro próximo (30 dias) para manter o financeiro previsto em dia
            data_futura_str = (data_fim_dt + timedelta(days=30)).strftime('%Y-%m-%d')

            # =========================================================================
            # CONTAS A RECEBER
            # =========================================================================
            # Removemos a estratégia "Por Pagamento" pois a API não aceita.
            # Usamos uma janela única e robusta de vencimento.
            estrategias_receber = [
                {
                    'nome': 'Geral (Vencimento)',
                    'params': {
                        'status': ['EM_ABERTO', 'ATRASADO', 'RECEBIDO'], 
                        'data_vencimento_de': data_inicio_str, 
                        'data_vencimento_ate': data_futura_str
                    }
                }
            ]
            
            self.stdout.write("--- Buscando Contas a Receber ---")
            
            for estrategia in estrategias_receber:
                page = 1
                while True:
                    url = f"{API_BASE_URL}/v1/financeiro/eventos-financeiros/contas-a-receber/buscar"
                    params = {'pagina': page, 'tamanho_pagina': 50}
                    params.update(estrategia['params'])

                    resp = call_api_with_retry(url, params=params)
                    if not resp: break

                    try:
                        items = resp.json().get('itens', [])
                        if not items: break

                        self.stdout.write(f"  Processando {len(items)} itens (Pág {page})...")
                        
                        for conta in items:
                            try:
                                status_ca = conta.get('status_traduzido')
                                is_received = status_ca == 'RECEBIDO'
                                data_pagamento = None

                                if is_received:
                                    # Lógica robusta de data
                                    baixas = conta.get('baixas', [])
                                    dt_str = baixas[0].get('data_pagamento') if baixas else (conta.get('data_pagamento') or conta.get('data_compensacao'))
                                    
                                    if dt_str:
                                        try: data_pagamento = datetime.strptime(dt_str, '%Y-%m-%d').date()
                                        except: data_pagamento = None
                                    
                                    # Se não achou data nenhuma, usa vencimento ou hoje
                                    if not data_pagamento:
                                        venc_str = conta.get('data_vencimento')
                                        if venc_str:
                                            try: data_pagamento = datetime.strptime(venc_str, '%Y-%m-%d').date()
                                            except: data_pagamento = timezone.now().date()
                                        else:
                                            data_pagamento = timezone.now().date()

                                # CORREÇÃO DO NONE: Usa 'or' para garantir string
                                cli_data = conta.get('cliente') or {}
                                cliente_nome = cli_data.get('nome') or 'Cliente CA V2'
                                
                                valor = Decimal(str(conta.get('total', '0.0')).replace(',', '.'))
                                dt_venc = conta.get('data_vencimento')
                                if not dt_venc: continue
                                data_venc = datetime.strptime(dt_venc, '%Y-%m-%d').date()
                                
                                # 1. Blindagem
                                try:
                                    obj_existente = ReceivableAccount.objects.get(external_id=conta.get('id'))
                                    existe = True
                                except ReceivableAccount.DoesNotExist:
                                    obj_existente = None
                                    existe = False

                                # 2. Previsão (Agora segura contra None)
                                cat_s, dre_s, bank_s, cc_s = self.prever_classificacao(user, cliente_nome, 'RECEIVABLE')
                                cat_padrao, _ = Category.objects.get_or_create(name='Receitas de Vendas', category_type='RECEIVABLE', user=user)

                                # 3. Definição
                                if existe:
                                    cat_final, dre_final, bank_final = obj_existente.category, obj_existente.dre_area, obj_existente.bank_account
                                else:
                                    cat_final = cat_s if cat_s else cat_padrao
                                    dre_final = dre_s if dre_s else 'BRUTA'
                                    bank_final = bank_s

                                # 4. Salvar
                                obj, created = ReceivableAccount.objects.update_or_create(
                                    external_id=conta.get('id'),
                                    defaults={
                                        'user': user,
                                        'name': cliente_nome,
                                        'description': conta.get('descricao') or '', # Proteção contra None
                                        'amount': valor,
                                        'due_date': data_venc,
                                        'is_received': is_received,
                                        'payment_date': data_pagamento,
                                        'category': cat_final,
                                        'dre_area': dre_final,
                                        'bank_account': bank_final, 
                                        'occurrence': 'AVULSO',
                                        'payment_method': 'BOLETO'
                                    }
                                )
                                
                                # 5. Smart Update
                                if not created and obj.category.name == 'Receitas de Vendas' and cat_s:
                                     obj.category = cat_s
                                     obj.dre_area = dre_s or obj.dre_area
                                     if bank_s: obj.bank_account = bank_s
                                     obj.save()

                            except Exception as e:
                                pass # Ignora erros pontuais para não travar o loop

                    except Exception:
                         break
                    page += 1
                    time.sleep(0.5)

            # =========================================================================
            # CONTAS A PAGAR
            # =========================================================================
            estrategias_pagar = [
                {
                    'nome': 'Geral (Vencimento)',
                    'params': {
                        'status': ['EM_ABERTO', 'ATRASADO', 'RECEBIDO'], 
                        'data_vencimento_de': data_inicio_str, 
                        'data_vencimento_ate': data_futura_str
                    }
                }
            ]

            self.stdout.write("--- Buscando Contas a Pagar ---")

            for estrategia in estrategias_pagar:
                page = 1
                while True:
                    url = f"{API_BASE_URL}/v1/financeiro/eventos-financeiros/contas-a-pagar/buscar"
                    params = {'pagina': page, 'tamanho_pagina': 50}
                    params.update(estrategia['params'])

                    resp = call_api_with_retry(url, params=params)
                    if not resp: break

                    try:
                        items = resp.json().get('itens', [])
                        if not items: break

                        self.stdout.write(f"  Processando {len(items)} itens (Pág {page})...")
                        
                        for conta in items:
                            try:
                                status_ca = conta.get('status_traduzido')
                                is_paid = status_ca == 'RECEBIDO'
                                data_pagamento = None

                                if is_paid:
                                    baixas = conta.get('baixas', [])
                                    dt_str = baixas[0].get('data_pagamento') if baixas else (conta.get('data_pagamento') or conta.get('data_compensacao'))
                                    
                                    if dt_str:
                                        try: data_pagamento = datetime.strptime(dt_str, '%Y-%m-%d').date()
                                        except: data_pagamento = None
                                    
                                    if not data_pagamento:
                                        venc_str = conta.get('data_vencimento')
                                        if venc_str:
                                            try: data_pagamento = datetime.strptime(venc_str, '%Y-%m-%d').date()
                                            except: data_pagamento = timezone.now().date()
                                        else:
                                            data_pagamento = timezone.now().date()
                                
                                # CORREÇÃO DO NONE: Proteção no nome do fornecedor
                                forn_data = conta.get('fornecedor') or {}
                                fornecedor_nome = forn_data.get('nome') or 'Fornecedor CA V2'

                                valor = Decimal(str(conta.get('total', '0.0')).replace(',', '.'))
                                dt_venc = conta.get('data_vencimento')
                                if not dt_venc: continue
                                data_venc = datetime.strptime(dt_venc, '%Y-%m-%d').date()
                                
                                # 1. Blindagem
                                try:
                                    obj_existente = PayableAccount.objects.get(external_id=conta.get('id'))
                                    existe = True
                                except PayableAccount.DoesNotExist:
                                    obj_existente = None
                                    existe = False

                                # 2. Previsão
                                cat_s, dre_s, bank_s, cc_s = self.prever_classificacao(user, fornecedor_nome, 'PAYABLE')
                                cat_padrao, _ = Category.objects.get_or_create(name='Despesas Operacionais (-)', category_type='PAYABLE', user=user)

                                # 3. Definição
                                if existe:
                                    cat_final, dre_final, bank_final = obj_existente.category, obj_existente.dre_area, obj_existente.bank_account
                                else:
                                    cat_final = cat_s if cat_s else cat_padrao
                                    dre_final = dre_s if dre_s else 'OPERACIONAL'
                                    bank_final = bank_s

                                # 4. Salvar
                                obj, created = PayableAccount.objects.update_or_create(
                                    external_id=conta.get('id'),
                                    defaults={
                                        'user': user,
                                        'name': fornecedor_nome,
                                        'description': conta.get('descricao') or '', # Proteção contra None
                                        'amount': valor,
                                        'due_date': data_venc,
                                        'is_paid': is_paid,
                                        'payment_date': data_pagamento,
                                        'category': cat_final,
                                        'dre_area': dre_final,
                                        'bank_account': bank_final,
                                        'occurrence': 'AVULSO',
                                        'cost_type': 'FIXO',
                                        'payment_method': 'BOLETO'
                                    }
                                )

                                # 5. Smart Update
                                if not created and obj.category.name == 'Despesas Operacionais (-)' and cat_s:
                                    obj.category = cat_s
                                    obj.dre_area = dre_s or obj.dre_area
                                    if bank_s: obj.bank_account = bank_s
                                    obj.save()

                            except Exception as e:
                                pass

                    except Exception:
                         break
                    page += 1
                    time.sleep(0.5)

            self.stdout.write(self.style.SUCCESS(f"Sincronização concluída para {user.username}."))

        self.stdout.write(self.style.SUCCESS("--- Fim do processo de sincronização ---"))