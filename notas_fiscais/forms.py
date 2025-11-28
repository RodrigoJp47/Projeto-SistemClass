# notas_fiscais/forms.py
from django import forms
from .models import NotaFiscal

class EmissaoNotaFiscalForm(forms.Form):
    # Estes são exemplos de campos. A API que você contratar
    # vai ditar exatamente quais campos são necessários.
    
    natureza_operacao = forms.CharField(
        label="Natureza da Operação",
        initial="Venda de mercadoria",
        widget=forms.TextInput(attrs={'class': 'form-field'})
    )
    
    cfop = forms.CharField(
        label="CFOP",
        initial="5102", # Exemplo: Venda de mercadoria adquirida ou recebida de terceiros
        widget=forms.TextInput(attrs={'class': 'form-field'})
    )

    informacoes_adicionais = forms.CharField(
        label="Informações Adicionais (Opcional)",
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-field', 'rows': 3})
    )