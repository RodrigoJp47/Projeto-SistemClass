# # notas_fiscais/forms.py
# from django import forms
# from .models import NotaFiscal

# class EmissaoNotaFiscalForm(forms.Form):
#     # Opções que alimentam a "seta" (Select)
#     CHOICES_NFE = [('Venda de mercadoria', 'Venda de mercadoria'), ('Outra', 'Outra')]
#     CHOICES_NFSE = [('1', 'Prestação de Serviço')]

#     natureza_operacao = forms.ChoiceField(
#         label="Natureza da Operação",
#         choices=CHOICES_NFE, 
#         widget=forms.Select(attrs={'class': 'form-field'})
#     )
    
#     cfop = forms.CharField(
#         label="CFOP",
#         initial="5102",
#         required=False,
#         widget=forms.TextInput(attrs={'class': 'form-field'})
#     )

#     informacoes_adicionais = forms.CharField(
#         label="Informações Adicionais (Opcional)",
#         required=False,
#         widget=forms.Textarea(attrs={'class': 'form-field', 'rows': 3})
#     )

from django import forms

class EmissaoNotaFiscalForm(forms.Form):
    CHOICES_NFE = [('Venda de mercadoria', 'Venda de mercadoria'), ('Outra', 'Outra')]
    CHOICES_NFSE = [('1', 'Prestação de Serviço')]

    natureza_operacao = forms.ChoiceField(
        label="Natureza da Operação",
        choices=[], # Começa vazio
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

    def __init__(self, *args, **kwargs):
        # Removemos o argumento personalizado para não dar erro no pai
        eh_servico = kwargs.pop('eh_servico', False)
        super().__init__(*args, **kwargs)
        
        # Define as escolhas dinamicamente com base no tipo
        if eh_servico:
            self.fields['natureza_operacao'].choices = self.CHOICES_NFSE
            self.fields['natureza_operacao'].initial = '1'
        else:
            self.fields['natureza_operacao'].choices = self.CHOICES_NFE