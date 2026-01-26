

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
            
            # --- [NOVO] Função auxiliar para buscar data real nas baixas ---
            def buscar_data_real(endpoint_tipo, id_conta):
                # endpoint_tipo deve ser 'contas-a-receber' ou 'contas-a-pagar'
                try:
                    url_detalhe = f"{API_BASE_URL}/v1/financeiro/eventos-financeiros/{endpoint_tipo}/{id_conta}"
                    # Reutilizamos sua função de retry para garantir a conexão
                    resp = call_api_with_retry(url_detalhe)
                    if resp and resp.status_code == 200:
                        dados = resp.json()
                        baixas = dados.get('baixas', [])
                        if baixas:
                            # Retorna a data da última baixa encontrada
                            return baixas[-1].get('data_pagamento')
                except:
                    pass
                return None
            # ---------------------------------------------------------------

            # --- CONFIGURAÇÃO DE DATAS ---
            # Voltamos ao padrão seguro: Busca por vencimento com janela larga
            # Isso pega o que venceu recentemente E o que estava atrasado (dentro de 15 dias)
            dias_busca = 15
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
                                # --- ADICIONE ESTE BLOCO DEBUG TEMPORÁRIO ---
                                if is_received:
                                    self.stdout.write(self.style.WARNING(f"--- DEBUG JSON CONTA {conta.get('id')} ---"))
                                    self.stdout.write(str(conta)) # Vai imprimir tudo que a API mandou
                                    self.stdout.write(self.style.WARNING("-----------------------------------"))
                            
                                data_pagamento = None

                                if is_received:
                                    data_pagamento = None
                                    # 1. Tenta pegar direto da listagem (rápido)
                                    baixas = conta.get('baixas', [])
                                    dt_str = baixas[0].get('data_pagamento') if baixas else (conta.get('data_pagamento') or conta.get('data_compensacao'))
                                    
                                    if dt_str:
                                        try: data_pagamento = datetime.strptime(dt_str, '%Y-%m-%d').date()
                                        except: data_pagamento = None
                                    
                                    # 2. [NOVO] Se não veio data, usa a função de busca detalhada (lento mas preciso)
                                    if not data_pagamento:
                                        dt_real_str = buscar_data_real('contas-a-receber', conta.get('id'))
                                        if dt_real_str:
                                            try: data_pagamento = datetime.strptime(dt_real_str, '%Y-%m-%d').date()
                                            except: pass

                                    # 3. Fallback: Se tudo falhar, usa Vencimento
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
                                # LOG VISUAL (LINHAS AMARELAS)
                                acao = "Criada" if created else "Atualizada"
                                # Se a variável do nome for 'cliente_nome' use ela, se for 'nome' troque abaixo
                                nome_exibicao = locals().get('cliente_nome') or locals().get('nome') or 'Cliente'
                                valor_exibicao = locals().get('valor') or locals().get('vlr') or 0
                                
                                self.stdout.write(self.style.WARNING(f"    -> {acao}: {nome_exibicao} | R$ {valor_exibicao}"))
                                
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
                                    data_pagamento = None
                                    # 1. Tenta pegar direto da listagem
                                    baixas = conta.get('baixas', [])
                                    dt_str = baixas[0].get('data_pagamento') if baixas else (conta.get('data_pagamento') or conta.get('data_compensacao'))
                                    
                                    if dt_str:
                                        try: data_pagamento = datetime.strptime(dt_str, '%Y-%m-%d').date()
                                        except: data_pagamento = None
                                    
                                    # 2. [NOVO] Se não veio data, usa a função de busca detalhada
                                    if not data_pagamento:
                                        # ATENÇÃO: endpoint muda para 'contas-a-pagar'
                                        dt_real_str = buscar_data_real('contas-a-pagar', conta.get('id'))
                                        if dt_real_str:
                                            try: data_pagamento = datetime.strptime(dt_real_str, '%Y-%m-%d').date()
                                            except: pass
                                    
                                    # 3. Fallback: Se tudo falhar, usa Vencimento
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
                                # LOG VISUAL (LINHAS AMARELAS)
                                acao = "Criada" if created else "Atualizada"
                                # Se a variável do nome for 'fornecedor_nome' use ela, se for 'nome' troque abaixo
                                nome_exibicao = locals().get('fornecedor_nome') or locals().get('nome') or 'Fornecedor'
                                valor_exibicao = locals().get('valor') or locals().get('vlr') or 0

                                self.stdout.write(self.style.WARNING(f"    -> {acao}: {nome_exibicao} | R$ {valor_exibicao}"))

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