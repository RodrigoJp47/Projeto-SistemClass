

import os
import json
import re
import google.generativeai as genai
from pypdf import PdfReader

# Mantendo EXATAMENTE como você enviou
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-flash-latest')

def extrair_dados_boleto(arquivo_pdf):
    if not GEMINI_API_KEY:
        return {'erro': 'Chave API não configurada.'}

    try:
        print("--- [SistemClass] Iniciando leitura (Modelo: flash-latest) ---")
        arquivo_pdf.seek(0)
        reader = PdfReader(arquivo_pdf)
        
        texto_bruto = ""
        # Lemos até 2 páginas conforme sua lógica original [cite: 1]
        for page in reader.pages[:2]:
            texto_extraido = page.extract_text()
            if texto_extraido:
                texto_bruto += texto_extraido + "\n"
        
        # Limpeza simples para não quebrar o processamento
        texto_limpo = " ".join(texto_bruto.split())

        # Prompt ajustado para o flash-latest ser mais preciso
        prompt = f"""
        Você é um especialista em BPO Financeiro.
        Analise o texto e retorne APENAS um JSON estrito.

        REGRAS:
        1. VALOR: Valor total do documento (float).
        2. VENCIMENTO: Data no formato YYYY-MM-DD.
        3. FORNECEDOR: Nome do beneficiário/cedente ou órgão federal.
        4. CODIGO_BARRAS: Apenas os números da linha digitável (47 ou 48 dígitos).

        Texto: {texto_limpo[:5000]}

        Retorne apenas:
        {{
            "valor": float,
            "vencimento": "YYYY-MM-DD",
            "fornecedor": "string",
            "codigo_barras": "string"
        }}
        """

        print("--- [SistemClass] Enviando para Gemini ---")
        response = model.generate_content(prompt)
        res_text = response.text.strip()
        
        # Tratamento robusto para extrair o JSON se a IA colocar crases ou texto extra
        if "{" in res_text:
            res_text = res_text[res_text.find("{"):res_text.rfind("}")+1]
            
        dados = json.loads(res_text)
        
        # Ajuste de valor caso venha como string formatada (ex: "660,43")
        if isinstance(dados.get('valor'), str):
            val_limpo = dados['valor'].replace('R$', '').replace('.', '').replace(',', '.').strip()
            dados['valor'] = float(val_limpo)

        print(f"--- [SistemClass] Sucesso! Fornecedor: {dados.get('fornecedor')} ---")
        return dados

    except Exception as e:
        print(f"--- [ERRO] {str(e)} ---")
        return {
            'erro': f'Erro na leitura: {str(e)}',
            'valor': 0.0,
            'vencimento': None,
            'fornecedor': 'Erro',
            'codigo_barras': ''
        }