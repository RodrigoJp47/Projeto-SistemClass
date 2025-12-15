import requests
from datetime import datetime, timedelta
from decimal import Decimal
from .models import (
    TinyCredentials, PayableAccount, ReceivableAccount, 
    Category, BankAccount, ClassificacaoAutomatica
)

# URL Base da API do Tiny
TINY_API_URL = "https://api.tiny.com.br/api2"

def tiny_request(endpoint, token, params=None):
    if params is None:
        params = {}

    payload = {
        "token": token,
        "formato": "json",
    }
    payload.update(params)

    url = f"{TINY_API_URL}/{endpoint}"
    
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        data = response.json()
        
        retorno = data.get('retorno', {})
        
        # Tratamento de erros da API
        if retorno.get('status') == 'Erro':
            lista_erros = retorno.get('erros', [])
            msg_erro = ", ".join([e.get('erro', 'Erro desconhecido') for e in lista_erros])
            
            # Se o erro for apenas "não achou nada", retornamos vazio (sucesso sem dados)
            if "não retornou registros" in msg_erro:
                return {'contas': [], 'numero_paginas': 0}

            return {'erro': f"Tiny diz: {msg_erro}"}
            
        return retorno
    except Exception as e:
        return {'erro': f"Erro na conexão com Tiny: {str(e)}"}

def prever_classificacao_local(user, descricao, tipo):
    if not descricao:
        return None, None, None
    regras = ClassificacaoAutomatica.objects.filter(user=user, tipo=tipo)
    descricao_lower = descricao.lower()
    for regra in regras:
        if regra.termo.lower() in descricao_lower:
            return regra.categoria, regra.dre_area, regra.bank_account
    return None, None, None

def processar_contas_pagar_tiny(user, token):
    novos = 0
    atualizados = 0
    erros = []

    banco_tiny, _ = BankAccount.objects.get_or_create(
        user=user, 
        bank_name='Integração Tiny',
        defaults={'agency': '0000', 'account_number': 'TINY', 'initial_balance': 0}
    )
    cat_padrao, _ = Category.objects.get_or_create(user=user, name='Despesas Gerais (Tiny)', category_type='PAYABLE')

    # Datas: 30 dias atrás até 30 dias à frente
    hoje = datetime.now()
    data_inicio = hoje - timedelta(days=30)
    data_fim = hoje + timedelta(days=30)
    
    str_inicio = data_inicio.strftime("%d/%m/%Y")
    str_fim = data_fim.strftime("%d/%m/%Y")

    # --- CORREÇÃO: Loop por Situação ---
    # O Tiny não aceita "todos", então buscamos "aberto" e "pago" separadamente
    situacoes_para_buscar = ['aberto', 'pago']

    for situacao_atual in situacoes_para_buscar:
        pagina = 1
        total_paginas = 1 # Inicia assumindo que tem 1 página para entrar no loop

        while pagina <= total_paginas:
            params = {
                "data_ini_vencimento": str_inicio,
                "data_fim_vencimento": str_fim,
                "situacao": situacao_atual, # Busca específica
                "pagina": pagina
            }

            response = tiny_request("contas.pagar.pesquisa.php", token, params)
            
            if 'erro' in response:
                # Se der erro real (não apenas vazio), salvamos e paramos essa situação
                erros.append(f"Erro ao buscar '{situacao_atual}': {response['erro']}")
                break

            total_paginas = int(response.get('numero_paginas', 0))
            contas = response.get('contas', [])

            if not contas:
                break

            for item in contas:
                conta = item.get('conta', {})
                try:
                    id_tiny_raw = str(conta.get('id'))
                    # Prefixo para garantir unicidade
                    id_tiny_com_prefixo = f"TINY_{id_tiny_raw}"
                    
                    descricao = conta.get('historico') or conta.get('nome_cliente') or "Conta Tiny"
                    valor = Decimal(str(conta.get('valor', 0)))
                    
                    dt_venc_str = conta.get('data_vencimento')
                    try:
                        due_date = datetime.strptime(dt_venc_str, "%d/%m/%Y").date()
                    except:
                        due_date = datetime.now().date()

                    # Define status baseado no retorno da API ou no loop atual
                    sit_api = conta.get('situacao')
                    is_paid = (str(sit_api).lower() == 'pago')
                    
                    payment_date = None
                    if is_paid and conta.get('data_pagamento'):
                        try:
                            payment_date = datetime.strptime(conta.get('data_pagamento'), "%d/%m/%Y").date()
                        except:
                            pass

                    # Busca/Cria
                    conta_existente = PayableAccount.objects.filter(user=user, external_id=id_tiny_com_prefixo).first()

                    if conta_existente:
                        conta_existente.amount = valor
                        conta_existente.due_date = due_date
                        conta_existente.is_paid = is_paid
                        
                        # AJUSTE FINO: Se está pago, grava a data. Se não, limpa a data.
                        if is_paid and payment_date:
                            conta_existente.payment_date = payment_date
                        elif not is_paid:
                            conta_existente.payment_date = None
                            
                        conta_existente.save()
                        atualizados += 1
                    else:
                        cat_prevista, dre_prevista, bank_previsto = prever_classificacao_local(user, descricao, 'PAYABLE')

                        PayableAccount.objects.create(
                            user=user,
                            external_id=id_tiny_com_prefixo,
                            name=descricao[:200],
                            description=f"Importado do Tiny (ID Original: {id_tiny_raw})",
                            due_date=due_date,
                            amount=valor,
                            category=cat_prevista if cat_prevista else cat_padrao,
                            dre_area=dre_prevista if dre_prevista else 'OPERACIONAL',
                            bank_account=bank_previsto if bank_previsto else banco_tiny,
                            payment_method='BOLETO',
                            occurrence='AVULSO',
                            is_paid=is_paid,
                            payment_date=payment_date,
                            cost_type='VARIAVEL'
                        )
                        novos += 1

                except Exception as e:
                    erros.append(f"Erro ID {id_tiny_raw}: {str(e)}")
            
            pagina += 1

    return {'novos': novos, 'atualizados': atualizados, 'erros': erros}

def processar_contas_receber_tiny(user, token):
    novos = 0
    atualizados = 0
    erros = []

    banco_tiny, _ = BankAccount.objects.get_or_create(
        user=user, 
        bank_name='Integração Tiny',
        defaults={'agency': '0000', 'account_number': 'TINY', 'initial_balance': 0}
    )
    cat_padrao, _ = Category.objects.get_or_create(user=user, name='Receitas de Vendas (Tiny)', category_type='RECEIVABLE')

    hoje = datetime.now()
    data_inicio = hoje - timedelta(days=30)
    data_fim = hoje + timedelta(days=30)
    
    str_inicio = data_inicio.strftime("%d/%m/%Y")
    str_fim = data_fim.strftime("%d/%m/%Y")

    # --- CORREÇÃO: Loop por Situação ---
    situacoes_para_buscar = ['aberto', 'pago']

    for situacao_atual in situacoes_para_buscar:
        pagina = 1
        total_paginas = 1

        while pagina <= total_paginas:
            params = {
                "data_ini_vencimento": str_inicio,
                "data_fim_vencimento": str_fim,
                "situacao": situacao_atual, # Busca específica
                "pagina": pagina
            }

            response = tiny_request("contas.receber.pesquisa.php", token, params)
            
            if 'erro' in response:
                erros.append(f"Erro ao buscar '{situacao_atual}': {response['erro']}")
                break

            total_paginas = int(response.get('numero_paginas', 0))
            contas = response.get('contas', [])

            if not contas:
                break

            for item in contas:
                conta = item.get('conta', {})
                try:
                    id_tiny_raw = str(conta.get('id'))
                    id_tiny_com_prefixo = f"TINY_{id_tiny_raw}"
                    
                    cliente_nome = conta.get('nome_cliente') or "Cliente Tiny"
                    historico = conta.get('historico') or ""
                    valor = Decimal(str(conta.get('valor', 0)))
                    
                    dt_venc_str = conta.get('data_vencimento')
                    try:
                        due_date = datetime.strptime(dt_venc_str, "%d/%m/%Y").date()
                    except:
                        due_date = datetime.now().date()

                    sit_api = conta.get('situacao')
                    is_received = (str(sit_api).lower() == 'pago')
                    
                    payment_date = None
                    if is_received and conta.get('data_pagamento'):
                        try:
                            payment_date = datetime.strptime(conta.get('data_pagamento'), "%d/%m/%Y").date()
                        except:
                            pass

                    conta_existente = ReceivableAccount.objects.filter(user=user, external_id=id_tiny_com_prefixo).first()

                    if conta_existente:
                        conta_existente.amount = valor
                        conta_existente.due_date = due_date
                        conta_existente.is_received = is_received
                        
                        # AJUSTE FINO: Mesmo raciocínio para recebimentos
                        if is_received and payment_date:
                            conta_existente.payment_date = payment_date
                        elif not is_received:
                            conta_existente.payment_date = None
                            
                        conta_existente.save()
                        atualizados += 1
                    else:
                        cat_prevista, dre_prevista, bank_previsto = prever_classificacao_local(user, cliente_nome, 'RECEIVABLE')

                        ReceivableAccount.objects.create(
                            user=user,
                            external_id=id_tiny_com_prefixo,
                            name=cliente_nome[:200],
                            description=f"{historico} (Tiny ID: {id_tiny_raw})",
                            due_date=due_date,
                            amount=valor,
                            category=cat_prevista if cat_prevista else cat_padrao,
                            dre_area=dre_prevista if dre_prevista else 'BRUTA',
                            bank_account=bank_previsto if bank_previsto else banco_tiny,
                            payment_method='BOLETO',
                            occurrence='AVULSO',
                            is_received=is_received,
                            payment_date=payment_date
                        )
                        novos += 1

                except Exception as e:
                    erros.append(f"Erro ID {id_tiny_raw}: {str(e)}")
            
            pagina += 1

    return {'novos': novos, 'atualizados': atualizados, 'erros': erros}

def sincronizar_tiny_completo(user):
    try:
        creds = user.tiny_creds
    except TinyCredentials.DoesNotExist:
        return {'erro': 'Credenciais do Tiny não configuradas.'}

    res_pagar = processar_contas_pagar_tiny(user, creds.token)
    if 'erro' in res_pagar: return res_pagar

    res_receber = processar_contas_receber_tiny(user, creds.token)
    if 'erro' in res_receber: return res_receber

    return {
        'pagar_novos': res_pagar['novos'],
        'pagar_atualizados': res_pagar['atualizados'],
        'receber_novos': res_receber['novos'],
        'receber_atualizados': res_receber['atualizados'],
        'erros': res_pagar['erros'] + res_receber['erros']
    }