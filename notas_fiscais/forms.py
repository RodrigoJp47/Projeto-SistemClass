# notas_fiscais/forms.py
from django import forms
from .models import NotaFiscal

class EmissaoNotaFiscalForm(forms.Form):
    # Opções que alimentam a "seta" (Select)
    CHOICES_NFE = [('Venda de mercadoria', 'Venda de mercadoria'), ('Outra', 'Outra')]
    CHOICES_NFSE = [('1', 'Prestação de Serviço')]

    natureza_operacao = forms.ChoiceField(
        label="Natureza da Operação",
        choices=CHOICES_NFE, 
        widget=forms.Select(attrs={'class': 'form-field'})
    )
    
    cfop = forms.CharField(
        label="CFOP",
        initial="5102",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-field'})
    )

    informacoes_adicionais = forms.CharField(
        label="Informações Adicionais (Opcional)",
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-field', 'rows': 3})
    )