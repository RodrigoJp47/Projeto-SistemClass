# pdv/views.py

import json
from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from django.db.models import Sum, Q
import requests
from django.conf import settings
from notas_fiscais.models import NotaFiscal # Seu model de notas
from accounts.decorators import check_employee_permission

# Importações unificadas dos seus apps
from accounts.models import (
    Venda, ItemVenda, ProdutoServico, Cliente, 
    PagamentoVenda, ReceivableAccount, Category, 
    Vendedor, FechamentoCaixa, PayableAccount
)
from .models import SessaoCaixa, MovimentoCaixa

@login_required
@check_employee_permission('can_access_pdv')
def frente_caixa_view(request):
    """
    Renderiza a interface do operador (Frente de Caixa).
    """
    # Tenta pegar o caixa aberto. Se não tiver, retorna None.
    caixa_aberto = SessaoCaixa.objects.filter(usuario=request.user, status='ABERTO').last()
    
    # Carrega alguns produtos iniciais para performance (opcional)
    produtos_iniciais = ProdutoServico.objects.filter(user=request.user)[:50]
    
    context = {
        'caixa_aberto': caixa_aberto,
        'produtos_iniciais': produtos_iniciais
    }
    return render(request, 'pdv/pdv_operacao.html', context)

@login_required
def buscar_produto_api(request):
    """
    API para busca rápida por nome ou código de barras.
    """
    termo = request.GET.get('q', '')
    
    if not termo:
        return JsonResponse([], safe=False)

    # Busca por nome OU código
    produtos = ProdutoServico.objects.filter(
        user=request.user
    ).filter(
        Q(nome__icontains=termo) | Q(codigo__iexact=termo)
    )[:20]
    
    data = [{
        'id': p.id,
        'nome': p.nome,
        'preco': float(p.preco_venda),
        'codigo': p.codigo or p.id,
        'estoque': float(p.estoque_atual)
    } for p in produtos]
    
    return JsonResponse(data, safe=False)

@login_required
@require_POST
def finalizar_venda_pdv(request):
    """
    Processa a venda, baixa estoque e gera financeiro.
    NÃO emite nota fiscal aqui (para não travar).
    """
    try:
        data = json.loads(request.body)
        
        # 1. Recupera a sessão do caixa aberto
        sessao = SessaoCaixa.objects.filter(usuario=request.user, status='ABERTO').last()
        if not sessao:
            return JsonResponse({'success': False, 'error': 'Nenhum caixa aberto encontrado. Abra o caixa (F10) primeiro.'})

        with transaction.atomic():
            # --- 2. Dados Básicos ---
            cliente_id = data.get('cliente_id')
            cliente = None
            if cliente_id:
                cliente = Cliente.objects.filter(id=cliente_id).first()
            
            # Cria a Venda
            venda = Venda.objects.create(
                user=request.user,
                cliente=cliente, # Aceita None (Consumidor Final)
                data_venda=timezone.now(),
                valor_total_bruto=Decimal(str(data['total_bruto'])),
                valor_total_liquido=Decimal(str(data['total_liquido'])),
                desconto_geral=Decimal(str(data.get('desconto', 0))),
                status='FINALIZADA'
            )

            # --- 3. Itens e Estoque ---
            itens_objs = []
            
            for item in data['itens']:
                produto = ProdutoServico.objects.get(id=item['produto_id'])
                qtd = Decimal(str(item['quantidade']))
                preco = Decimal(str(item['preco_unitario']))
                
                itens_objs.append(ItemVenda(
                    venda=venda,
                    produto=produto,
                    quantidade=qtd,
                    preco_unitario=preco
                ))

                # Baixa de Estoque Otimizada (Evita erro se 2 venderem juntos)
                if produto.tipo == 'PRODUTO':
                    ProdutoServico.objects.filter(id=produto.id).update(
                        estoque_atual=F('estoque_atual') - qtd
                    )

            ItemVenda.objects.bulk_create(itens_objs)

            # --- 4. Financeiro (Múltiplos Pagamentos) ---
            # O front agora envia uma lista: [{'forma': 'DINHEIRO', 'valor': 50.00}, ...]
            lista_pagamentos = data.get('pagamentos', [])
            
            # Se por acaso vier vazio (compatibilidade), cria uma lista com o total
            if not lista_pagamentos:
                 lista_pagamentos = [{
                     'forma': data.get('forma_pagamento', 'DINHEIRO'),
                     'valor': data.get('total_liquido')
                 }]

            # Categoria para o Financeiro
            cat_venda, _ = Category.objects.get_or_create(
                name="Vendas PDV", 
                defaults={'user': request.user, 'category_type': 'RECEIVABLE'}
            )
            nome_cliente = cliente.nome if cliente else 'Consumidor Final'

            # Loop para registrar cada pagamento individualmente
            for pg in lista_pagamentos:
                metodo = pg['forma']
                valor_pg = Decimal(str(pg['valor']))

                # A. Registra na Venda
                PagamentoVenda.objects.create(
                    venda=venda,
                    forma_pagamento=metodo,
                    valor=valor_pg,
                    parcelas=1
                )

                # B. Movimento no Caixa (Só gera movimento físico se for DINHEIRO ou CHEQUE, opcionalmente)
                # Aqui vamos registrar tudo para você ter controle, mas você pode filtrar depois
                MovimentoCaixa.objects.create(
                    sessao=sessao,
                    tipo='VENDA',
                    valor=valor_pg,
                    descricao=f"Venda #{venda.id} - {metodo}",
                    venda_origem=venda
                )

                # C. Contas a Receber (Financeiro Geral)
                ReceivableAccount.objects.create(
                    user=request.user,
                    name=f"Venda PDV #{venda.id} ({metodo})",
                    description=f"Cliente: {nome_cliente}",
                    due_date=timezone.now().date(),
                    payment_date=timezone.now().date(),
                    amount=valor_pg,
                    category=cat_venda,
                    dre_area='BRUTA',
                    payment_method=metodo,
                    occurrence='AVULSO',
                    is_received=True,
                    bank_account=None 
                )

        return JsonResponse({
            'success': True, 
            'venda_id': venda.id,
            'message': 'Venda realizada com sucesso!'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# --- FUNÇÕES AUXILIARES DO CAIXA ---

@login_required
@require_POST
def registrar_movimento_caixa(request):
    """API para Sangria e Suprimento"""
    try:
        data = json.loads(request.body)
        sessao = SessaoCaixa.objects.get(id=data['sessao_id'], usuario=request.user, status='ABERTO')
        
        MovimentoCaixa.objects.create(
            sessao=sessao,
            tipo=data['tipo'], # 'SANGRIA' ou 'SUPRIMENTO'
            valor=Decimal(str(data['valor'])),
            descricao=data['descricao']
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def fechar_caixa_pdv(request):
    """API para Fechar o Caixa"""
    try:
        data = json.loads(request.body)
        sessao = SessaoCaixa.objects.get(id=data['sessao_id'], usuario=request.user, status='ABERTO')
        
        valor_conferido = Decimal(str(data['valor_final']))
        sessao.fechar(valor_conferido)
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def abrir_caixa_pdv(request):
    """API para abrir uma nova sessão de caixa"""
    try:
        data = json.loads(request.body)
        saldo_inicial = data.get('saldo_inicial', 0)
        
        if SessaoCaixa.objects.filter(usuario=request.user, status='ABERTO').exists():
            return JsonResponse({'success': False, 'error': 'Já existe um caixa aberto.'})

        sessao = SessaoCaixa.objects.create(
            usuario=request.user,
            saldo_inicial=saldo_inicial,
            status='ABERTO'
        )
        return JsonResponse({'success': True, 'sessao_id': sessao.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    



# pdv/views.py

# (Certifique-se de que get_object_or_404 está importado lá em cima)

def imprimir_cupom_view(request, venda_id):
    """Gera o HTML simplificado para impressão térmica"""
    venda = get_object_or_404(Venda, id=venda_id)
    
    # Tenta pegar dados da empresa (se houver perfil configurado)
    empresa = getattr(request.user, 'company_profile', None)
    
    context = {
        'venda': venda,
        'empresa': empresa,
        'data_hora': timezone.now()
    }
    return render(request, 'pdv/cupom_print.html', context)





@login_required
def emitir_nfce_pdv(request, venda_id):
    """
    Recebe o ID da venda e envia para a API da Focus NFe (Modelo 65 - NFC-e).
    Não trava o caixa pois é chamado via AJAX (fetch) pelo Javascript.
    """
    try:
        venda = Venda.objects.get(id=venda_id, user=request.user)
        
        # 1. Tenta pegar o perfil da empresa (Dados Cadastrais)
        try:
            perfil = request.user.company_profile
        except:
            return JsonResponse({'success': False, 'message': 'Perfil da empresa não configurado.'})

        # 2. Configuração de Ambiente (Produção ou Homologação)
        # Ajuste conforme suas variáveis do settings.py
        if settings.DEBUG: # Ou use uma variável especifica como settings.FOCUS_ENV == 'homologacao'
            BASE_URL = "https://homologacao.focusnfe.com.br"
            API_TOKEN = getattr(settings, 'NFE_TOKEN_HOMOLOGACAO', '') 
        else:
            BASE_URL = "https://api.focusnfe.com.br"
            API_TOKEN = getattr(settings, 'NFE_TOKEN_PRODUCAO', '')

        # Se o token estiver no perfil da empresa em vez do settings, troque acima por: perfil.api_token

        # 3. Cria o registro da Nota no Banco (Status: Processando)
        nota, created = NotaFiscal.objects.get_or_create(
            venda=venda,
            defaults={
                'user': request.user,
                'cliente': venda.cliente,
                'valor_total': venda.valor_total_liquido,
                'status': 'PROCESSANDO',
                'modelo': '65', # 65 = NFC-e
                'natureza_operacao': 'Venda Consumidor Final'
            }
        )
        
        # Se a nota já estava emitida/autorizada, não envia de novo
        if nota.status == 'AUTORIZADA':
            return JsonResponse({'success': True, 'message': 'Nota já autorizada anteriormente.'})

        # 4. Mapeamento de Pagamento (Do seu sistema para o código da SEFAZ)
        # 01=Dinheiro, 03=Crédito, 04=Débito, 17=PIX
        mapa_pagamento = {
            'DINHEIRO': '01',
            'CARTAO_CREDITO': '03',
            'CARTAO_DEBITO': '04',
            'PIX': '17'
        }
        
        # Pega o primeiro pagamento (ou principal) para simplificar
        # Se você implementou pagamentos mistos, o ideal é somar, mas para MVP vamos no principal
        pg_principal = venda.pagamentos.first()
        forma_sefaz = mapa_pagamento.get(pg_principal.forma_pagamento, '99') if pg_principal else '01'

        # 5. Monta os Itens
        itens_api = []
        for item in venda.itens.all():
            itens_api.append({
                "numero_item": len(itens_api) + 1,
                "codigo_produto": item.produto.codigo or str(item.produto.id),
                "descricao": item.produto.nome,
                "cfop": "5102", # Ajuste se necessário (Venda Mercadoria)
                "icms_situacao_tributaria": "102", # Simples Nacional (Ajuste se for Regime Normal)
                "unidade_comercial": "UN", # item.produto.unidade_medida
                "quantidade_comercial": float(item.quantidade),
                "valor_unitario_comercial": float(item.preco_unitario),
                "ncm": item.produto.ncm.replace(".", "") if item.produto.ncm else "00000000",
                # "cest": item.produto.cest (se tiver)
            })

        # 6. Payload Final (JSON para Focus)
        dados_nfce = {
            "natureza_operacao": "Venda ao Consumidor",
            "data_emissao": timezone.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "tipo_documento": 1,
            "finalidade_emissao": 1,
            "cnpj_emitente": perfil.cnpj.replace(".", "").replace("/", "").replace("-", ""),
            "itens": itens_api,
            "formas_pagamento": [{
                "forma_pagamento": forma_sefaz,
                "valor_pagamento": float(venda.valor_total_liquido)
            }],
            # Se for Homologação, a Focus ignora o CPF do cliente geralmente, mas em produção envia:
            "cpf_destinatario": venda.cliente.cpf_cnpj.replace(".","").replace("-","") if (venda.cliente and venda.cliente.cpf_cnpj) else None,
            "presenca_comprador": 1, # 1 = Presencial
            "modalidade_frete": 9 # 9 = Sem frete
        }

        # 7. Envia para a API (POST)
        url = f"{BASE_URL}/v2/nfce?ref={nota.id}" # ?ref ajuda a Focus a evitar duplicidade
        response = requests.post(url, json=dados_nfce, auth=(API_TOKEN, ""))
        
        resp_data = response.json()
        
        if response.status_code in [200, 201, 202]:
            nota.status = resp_data.get('status', 'PROCESSANDO')
            nota.save()
            return JsonResponse({'success': True, 'message': 'NFC-e enviada para processamento!'})
        else:
            nota.status = 'ERRO'
            nota.mensagem_erro = resp_data.get('mensagem', 'Erro desconhecido na API')
            nota.save()
            return JsonResponse({'success': False, 'message': f"Erro Focus: {nota.mensagem_erro}"})

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def dados_conferencia_caixa(request):
    """
    Calcula os totais da sessão atual para exibir no relatório.
    """
    try:
        # 1. Pega a sessão aberta
        sessao = SessaoCaixa.objects.filter(usuario=request.user, status='ABERTO').last()
        if not sessao:
            return JsonResponse({'success': False, 'error': 'Nenhum caixa aberto.'})

        # 2. Calcula Sangrias e Suprimentos
        # (Somamos todos os movimentos dessa sessão filtrando pelo tipo)
        total_sangria = MovimentoCaixa.objects.filter(
            sessao=sessao, tipo='SANGRIA'
        ).aggregate(total=Sum('valor'))['total'] or 0
        
        total_suprimento = MovimentoCaixa.objects.filter(
            sessao=sessao, tipo='SUPRIMENTO'
        ).aggregate(total=Sum('valor'))['total'] or 0

        # 3. Calcula Vendas por Método de Pagamento
        # Filtramos os pagamentos das vendas que pertencem a esta sessão (via MovimentoCaixa ou Data)
        # A forma mais precisa aqui é pegar os movimentos de venda desta sessão e buscar os pagamentos delas
        vendas_ids = MovimentoCaixa.objects.filter(
            sessao=sessao, tipo='VENDA'
        ).values_list('venda_origem', flat=True)
        
        pagamentos = PagamentoVenda.objects.filter(venda__id__in=vendas_ids)
        
        # Agregação
        venda_dinheiro = pagamentos.filter(forma_pagamento='DINHEIRO').aggregate(t=Sum('valor'))['t'] or 0
        venda_pix = pagamentos.filter(forma_pagamento='PIX').aggregate(t=Sum('valor'))['t'] or 0
        venda_credito = pagamentos.filter(forma_pagamento='CARTAO_CREDITO').aggregate(t=Sum('valor'))['t'] or 0
        venda_debito = pagamentos.filter(forma_pagamento='CARTAO_DEBITO').aggregate(t=Sum('valor'))['t'] or 0

        # 4. Matemática da Gaveta (O número MÁGICO)
        # Dinheiro que tem que ter fisicamente = Inicial + Entradas(Suprimento) - Saídas(Sangria) + Vendas(Dinheiro)
        saldo_fisico = (sessao.saldo_inicial or 0) + total_suprimento - total_sangria + venda_dinheiro
        
        # Faturamento Total (Tudo que vendeu, independente da forma)
        faturamento_total = venda_dinheiro + venda_pix + venda_credito + venda_debito

        return JsonResponse({
            'success': True,
            'dados': {
                'saldo_inicial': float(sessao.saldo_inicial),
                'suprimentos': float(total_suprimento),
                'sangrias': float(total_sangria),
                'vendas': {
                    'dinheiro': float(venda_dinheiro),
                    'pix': float(venda_pix),
                    'credito': float(venda_credito),
                    'debito': float(venda_debito)
                },
                'total_faturamento': float(faturamento_total),
                'saldo_gaveta': float(saldo_fisico) # É ESSE VALOR QUE TEM QUE BATER NA CONTAGEM
            }
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})






