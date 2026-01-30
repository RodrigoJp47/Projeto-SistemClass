import openpyxl
from openpyxl.styles import Font
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from django.utils import timezone

def gerar_excel_generic(queryset, tipo_relatorio):
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"relatorio_{tipo_relatorio}_{timezone.now().strftime('%d_%m_%Y')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Relatório"

    # Define cabeçalhos baseados no tipo
    # Adicionadas as colunas novas aqui também para manter consistência
    if tipo_relatorio == 'pagar':
        headers = ['Nome', 'Descrição', 'Vencimento', 'Valor', 'Status', 'Categoria', 'Área-DRE', 'Centro de Custo', 'Banco', 'Forma Pag.']
    else: # receber
        headers = ['Nome', 'Descrição', 'Vencimento', 'Valor', 'Status', 'Categoria', 'Área-DRE', 'Centro de Custo', 'Banco', 'Forma Pag.']

    ws.append(headers)
    
    # Estiliza cabeçalho
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for conta in queryset:
        status_text = ""
        if tipo_relatorio == 'pagar':
            status_text = "Pago" if conta.is_paid else "Aberto"
        else:
            status_text = "Recebido" if conta.is_received else "Aberto"

        banco = str(conta.bank_account) if conta.bank_account else "-"
        categoria = str(conta.category.name) if conta.category else "-"
        c_custo = str(conta.centro_custo.nome) if hasattr(conta, 'centro_custo') and conta.centro_custo else "-"
        # Pega a forma de pagamento legível (ex: "Boleto" em vez de "BOLETO")
        forma_pag = conta.get_payment_method_display() if hasattr(conta, 'get_payment_method_display') else conta.payment_method
        dre_area = conta.get_dre_area_display() if hasattr(conta, 'get_dre_area_display') else "-"
        row = [
            conta.name,
            conta.description,
            conta.due_date,
            conta.amount,
            status_text,
            categoria,
            dre_area,
            c_custo,
            banco,
            forma_pag
        ]
        ws.append(row)

    wb.save(response)
    return response

def gerar_pdf_generic(queryset, tipo_relatorio):
    response = HttpResponse(content_type='application/pdf')
    filename = f"relatorio_{tipo_relatorio}_{timezone.now().strftime('%d_%m_%Y')}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"' 

    titulo_texto = "Contas a Pagar" if tipo_relatorio == 'pagar' else "Contas a Receber"

    doc = SimpleDocTemplate(
        response, 
        pagesize=landscape(A4), 
        title=f"Relatório de {titulo_texto}" 
    )
    
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph(f"Relatório de {titulo_texto}", styles['Title']))
    elements.append(Spacer(1, 12))

    # --- ATUALIZAÇÃO: AGORA COM 10 COLUNAS ---
    headers = ['Nome', 'Desc.', 'Venc.', 'Valor', 'Status', 'Cat.', 'DRE', 'C. Custo', 'Banco', 'Forma']
    data = [headers]

    total = 0
    for conta in queryset:
        status_text = ""
        if tipo_relatorio == 'pagar':
            status_text = "Pago" if conta.is_paid else "Aberto"
        else:
            status_text = "Recebido" if conta.is_received else "Aberto"
        
        categoria = str(conta.category.name) if conta.category else "-"
        c_custo = str(conta.centro_custo.nome) if hasattr(conta, 'centro_custo') and conta.centro_custo else "-"
        banco = str(conta.bank_account) if conta.bank_account else "-"
        forma_pag = conta.get_payment_method_display() if hasattr(conta, 'get_payment_method_display') else conta.payment_method
        
        # Obtendo o texto amigável da Área-DRE
        dre_area = conta.get_dre_area_display() if hasattr(conta, 'get_dre_area_display') else "-"

        # Truncar textos para manter a integridade visual da tabela
        nome_curto = conta.name[:18] + '..' if len(conta.name) > 18 else conta.name
        desc_curta = conta.description[:20] + '..' if len(conta.description) > 20 else conta.description
        cat_curta = categoria[:12]
        dre_curta = dre_area[:12]
        cc_curto = c_custo[:12]
        banco_curto = banco[:12]

        data.append([
            nome_curto,
            desc_curta,
            conta.due_date.strftime('%d/%m/%Y'),
            f"R$ {conta.amount:,.2f}",
            status_text,
            cat_curta,
            dre_curta,
            cc_curto,
            banco_curto,
            forma_pag
        ])
        total += conta.amount

    # Linha de Total ajustada para 10 colunas
    # TOTAL: na coluna de índice 2 e valor na coluna de índice 3
    data.append(['', '', 'TOTAL:', f"R$ {total:,.2f}", '', '', '', '', '', ''])

    # --- AJUSTE DE LARGURA DAS COLUNAS (Soma total ~780 pontos para caber no A4 Landscape) ---
    col_widths = [95, 110, 60, 80, 45, 75, 80, 80, 85, 65]

    table = Table(data, colWidths=col_widths)
    
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7), # Reduzido para 7 para garantir que os dados caibam
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        
        # Estilo para a linha de total
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('ALIGN', (2, -1), (2, -1), 'RIGHT'), 
    ])
    table.setStyle(style)
    elements.append(table)

    doc.build(elements)
    return response


# --- NOVAS FUNÇÕES PARA ORÇAMENTO ANUAL ---

def gerar_excel_orcamento(dados_orcamento, ano):
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"relatorio_orcamento_{ano}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    wb = openpyxl.Workbook()
    
    # --- ABA 1: DESPESAS ---
    ws_despesa = wb.active
    ws_despesa.title = "Despesas"
    
    # Cabeçalhos
    headers = ['Categoria']
    meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
    for mes in meses:
        headers.extend([f'{mes} (Prev)', f'{mes} (Real)'])
    headers.extend(['Total Prev.', 'Total Real.'])
    
    ws_despesa.append(headers)
    for cell in ws_despesa[1]: cell.font = Font(bold=True)

    # Dados Despesas
    for cat_name, data in dados_orcamento['despesas'].items():
        row = [cat_name]
        for i in range(12):
            row.append(data['orcado_mensal'][i])
            row.append(data['realizado_mensal'][i])
        row.append(data['total_orcado_ano'])
        row.append(data['total_realizado_ano'])
        ws_despesa.append(row)

    # --- ABA 2: RECEITAS ---
    ws_receita = wb.create_sheet(title="Receitas")
    ws_receita.append(headers)
    for cell in ws_receita[1]: cell.font = Font(bold=True)

    # Dados Receitas
    for cat_name, data in dados_orcamento['receitas'].items():
        row = [cat_name]
        for i in range(12):
            row.append(data['orcado_mensal'][i])
            row.append(data['realizado_mensal'][i])
        row.append(data['total_orcado_ano'])
        row.append(data['total_realizado_ano'])
        ws_receita.append(row)

    wb.save(response)
    return response

def gerar_pdf_orcamento(dados_orcamento, ano):
    response = HttpResponse(content_type='application/pdf')
    filename = f"relatorio_orcamento_{ano}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    doc = SimpleDocTemplate(response, pagesize=landscape(A4), title=f"Relatório Orçamentário {ano}")
    elements = []
    styles = getSampleStyleSheet()

    # Título Principal
    elements.append(Paragraph(f"Relatório Orçamentário Anual - {ano}", styles['Title']))
    elements.append(Spacer(1, 12))

    # --- Tabela de Resumo (Totais por Categoria) ---
    # Nota: Não colocamos mês a mês no PDF pois ficaria ilegível (26 colunas).
    # O PDF foca no acumulado anual.
    
    headers = ['Tipo', 'Categoria', 'Total Planejado', 'Total Realizado', 'Diferença', 'Status']
    data = [headers]

    # Processa Receitas
    for cat_name, info in dados_orcamento['receitas'].items():
        prev = info['total_orcado_ano']
        real = info['total_realizado_ano']
        diff = real - prev
        status = "Acima da Meta" if diff >= 0 else "Abaixo da Meta"
        
        data.append([
            "Receita",
            cat_name[:25],
            f"R$ {prev:,.2f}",
            f"R$ {real:,.2f}",
            f"R$ {diff:,.2f}",
            status
        ])

    # Separador visual
    data.append(['', '', '', '', '', ''])

    # Processa Despesas
    for cat_name, info in dados_orcamento['despesas'].items():
        prev = info['total_orcado_ano']
        real = info['total_realizado_ano']
        diff = prev - real # Para despesa, positivo é bom (gastou menos que o orçado)
        status = "Dentro do Orçamento" if diff >= 0 else "Estourou Orçamento"

        data.append([
            "Despesa",
            cat_name[:25],
            f"R$ {prev:,.2f}",
            f"R$ {real:,.2f}",
            f"R$ {diff:,.2f}",
            status
        ])

    # Estilo da tabela
    col_widths = [60, 200, 100, 100, 100, 120]
    table = Table(data, colWidths=col_widths)
    
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ])
    
    # Colore linhas de Receita de verde claro e Despesa de vermelho claro (opcional)
    # Aqui deixamos padrão para simplificar.

    table.setStyle(style)
    elements.append(table)
    
    doc.build(elements)
    return response

# --- NOVAS FUNÇÕES PARA DRE E FLUXO DE CAIXA ---

def gerar_excel_dre(dados_dre, periodo_str):
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"relatorio_dre_{timezone.now().strftime('%d_%m_%Y')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "DRE Gerencial"

    # Cabeçalho
    ws.append([f"DRE Gerencial - Período: {periodo_str}"])
    ws.append([]) # Linha em branco
    
    headers = ['Estrutura', 'Valor (R$)', 'Análise Vertical (%)']
    ws.append(headers)
    for cell in ws[3]: cell.font = Font(bold=True)

    # Lista ordenada das linhas da DRE
    ordem_dre = [
        ('Receita Bruta', 'receita_bruta'),
        ('(-) Impostos', 'impostos'),
        ('(=) Receita Líquida', 'receita_liquida'),
        ('(-) Custos (CMV/CSP)', 'custos'),
        ('(=) Lucro Bruto', 'lucro_bruto'),
        ('(-) Despesas Operacionais', 'despesas_operacionais'),
        ('(=) EBITDA', 'ebitda'),
        ('(-) Depreciação/Amortização', 'depreciacao'),
        ('(=) EBIT', 'ebit'),
        ('(-) Resultado Financeiro/Não Op.', 'nao_operacionais'),
        ('(=) LAIR', 'lair'),
        ('(-) IRPJ/CSLL', 'tributacao'),
        ('(=) Lucro Líquido', 'lucro_liquido'),
        ('(-) Distribuição de Lucros', 'distribuicao_lucro'),
        ('(=) Resultado Final', 'resultado_final'),
    ]

    receita_liquida = dados_dre.get('receita_liquida', 0)

    for label, key in ordem_dre:
        valor = dados_dre.get(key, 0)
        av = (valor / receita_liquida * 100) if receita_liquida and receita_liquida > 0 else 0
        
        # Formatação visual para totais (linhas que começam com (=))
        is_total = label.startswith('(=)')
        
        ws.append([label, valor, f"{av:.2f}%"])

    # Formatar coluna de valor
    for row in ws.iter_rows(min_row=4, max_col=2, max_row=19):
        for cell in row:
            if isinstance(cell.value, (int, float)):
                cell.number_format = '"R$ "#,##0.00'

    wb.save(response)
    return response

def gerar_pdf_dre(dados_dre, periodo_str):
    response = HttpResponse(content_type='application/pdf')
    filename = f"relatorio_dre_{timezone.now().strftime('%d_%m_%Y')}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    doc = SimpleDocTemplate(response, pagesize=A4, title="Relatório DRE")
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph(f"DRE Gerencial - {periodo_str}", styles['Title']))
    elements.append(Spacer(1, 20))

    data = [['Estrutura', 'Valor', 'A.V. %']]
    
    ordem_dre = [
        ('Receita Bruta', 'receita_bruta'),
        ('(-) Impostos', 'impostos'),
        ('(=) Receita Líquida', 'receita_liquida'),
        ('(-) Custos (CMV/CSP)', 'custos'),
        ('(=) Lucro Bruto', 'lucro_bruto'),
        ('(-) Despesas Operacionais', 'despesas_operacionais'),
        ('(=) EBITDA', 'ebitda'),
        ('(-) Depreciação', 'depreciacao'),
        ('(=) EBIT', 'ebit'),
        ('(-) Não Operacionais', 'nao_operacionais'),
        ('(=) LAIR', 'lair'),
        ('(-) IRPJ/CSLL', 'tributacao'),
        ('(=) Lucro Líquido', 'lucro_liquido'),
        ('(-) Distribuição', 'distribuicao_lucro'),
        ('(=) Resultado Final', 'resultado_final'),
    ]

    receita_liquida = dados_dre.get('receita_liquida', 0)

    # Estilos condicionais para a tabela
    table_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'), # Alinha textos da primeira coluna à esquerda
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]

    for index, (label, key) in enumerate(ordem_dre):
        valor = dados_dre.get(key, 0)
        av = (valor / receita_liquida * 100) if receita_liquida and receita_liquida > 0 else 0
        
        # Se for linha de total (=), coloca em negrito e fundo cinza claro
        if label.startswith('(=)'):
            row_idx = index + 1
            table_styles.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))
            table_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.lightgrey))

        data.append([
            label,
            f"R$ {valor:,.2f}",
            f"{av:.2f}%"
        ])

    table = Table(data, colWidths=[250, 120, 80])
    table.setStyle(TableStyle(table_styles))
    elements.append(table)
    
    doc.build(elements)
    return response

def gerar_excel_fluxo_caixa(dados_fc, periodo_str):
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"relatorio_fluxo_caixa_{timezone.now().strftime('%d_%m_%Y')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Fluxo de Caixa"

    ws.append([f"Fluxo de Caixa Realizado - {periodo_str}"])
    ws.append([])

    # Cabeçalhos (Meses)
    headers = ['Indicador'] + dados_fc['labels'] + ['TOTAL']
    ws.append(headers)
    for cell in ws[3]: cell.font = Font(bold=True)

    # Linhas
    # Entradas
    row_entradas = ['Entradas'] + dados_fc['entradas'] + [sum(dados_fc['entradas'])]
    ws.append(row_entradas)
    
    # Saídas
    row_saidas = ['Saídas'] + dados_fc['saidas'] + [sum(dados_fc['saidas'])]
    ws.append(row_saidas)
    
    # Saldo
    saldo_total = sum(dados_fc['geracao_caixa'])
    row_saldo = ['Saldo (Geração de Caixa)'] + dados_fc['geracao_caixa'] + [saldo_total]
    ws.append(row_saldo)

    wb.save(response)
    return response

def gerar_pdf_fluxo_caixa(dados_fc, periodo_str):
    response = HttpResponse(content_type='application/pdf')
    filename = f"relatorio_fluxo_caixa_{timezone.now().strftime('%d_%m_%Y')}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    doc = SimpleDocTemplate(response, pagesize=landscape(A4), title="Relatório Fluxo de Caixa")
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph(f"Fluxo de Caixa Realizado - {periodo_str}", styles['Title']))
    elements.append(Spacer(1, 20))

    # Tabela Transposta (Meses nas linhas) se houver muitos meses, 
    # ou Tabela normal se couber. Vamos fazer normal, assumindo até 12 colunas no landscape.
    
    # Prepara cabeçalho
    headers = ['Mês', 'Entradas', 'Saídas', 'Saldo']
    data = [headers]

    # Preenche dados mês a mês
    total_entradas = 0
    total_saidas = 0
    total_saldo = 0

    for i, mes in enumerate(dados_fc['labels']):
        ent = dados_fc['entradas'][i]
        sai = dados_fc['saidas'][i]
        sal = dados_fc['geracao_caixa'][i]
        
        total_entradas += ent
        total_saidas += sai
        total_saldo += sal

        data.append([
            mes,
            f"R$ {ent:,.2f}",
            f"R$ {sai:,.2f}",
            f"R$ {sal:,.2f}"
        ])

    # Linha Total
    data.append([
        'TOTAL',
        f"R$ {total_entradas:,.2f}",
        f"R$ {total_saidas:,.2f}",
        f"R$ {total_saldo:,.2f}"
    ])

    table = Table(data, colWidths=[100, 150, 150, 150])
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        # Total Row Style
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ])
    table.setStyle(style)
    elements.append(table)

    doc.build(elements)
    return response