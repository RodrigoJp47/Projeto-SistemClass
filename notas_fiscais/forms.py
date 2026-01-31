
# from django import forms

# class EmissaoNotaFiscalForm(forms.Form):
#     CHOICES_NFE = [('Venda de mercadoria', 'Venda de mercadoria'), ('Outra', 'Outra')]
#     CHOICES_NFSE = [('1', 'Prestação de Serviço')]

#     natureza_operacao = forms.ChoiceField(
#         label="Natureza da Operação",
#         choices=[], # Começa vazio
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

#     def __init__(self, *args, **kwargs):
#         # Removemos o argumento personalizado para não dar erro no pai
#         eh_servico = kwargs.pop('eh_servico', False)
#         super().__init__(*args, **kwargs)
        
#         # Define as escolhas dinamicamente com base no tipo
#         if eh_servico:
#             self.fields['natureza_operacao'].choices = self.CHOICES_NFSE
#             self.fields['natureza_operacao'].initial = '1'
#         else:
#             self.fields['natureza_operacao'].choices = self.CHOICES_NFE

from django import forms

class EmissaoNotaFiscalForm(forms.Form):
    # Opções para NF-e (Produtos)
    CHOICES_NFE = [
        ('Venda de mercadoria', 'Venda de mercadoria'),
        ('Remessa', 'Remessa'),
        ('Outra', 'Outra')
    ]

    # Opções para NFS-e (Serviços - Padrão Nacional)
    # 1: Tributação no município | 2: Tributação fora do município
    CHOICES_NFSE = [
        ('1', '1 - Tributação no município (Operação Nacional)'),
        ('2', '2 - Tributação fora do município'),
        ('3', '3 - Isenção'),
        ('4', '4 - Imunidade'),
        ('5', '5 - Exigibilidade suspensa por decisão judicial'),
    ]

    natureza_operacao = forms.ChoiceField(
        label="Natureza da Operação",
        choices=[], # Alimentado dinamicamente no __init__
        widget=forms.Select(attrs={'class': 'form-select'}) # 'form-select' costuma ser o padrão Bootstrap
    )
    
    cfop = forms.CharField(
        label="CFOP",
        initial="5102",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 5102'})
    )

    informacoes_adicionais = forms.CharField(
        label="Informações Adicionais (Opcional)",
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )

    def __init__(self, *args, **kwargs):
        eh_servico = kwargs.pop('eh_servico', False)
        super().__init__(*args, **kwargs)
        
        if eh_servico:
            self.fields['natureza_operacao'].choices = self.CHOICES_NFSE
            self.fields['natureza_operacao'].initial = '1'
            self.fields['natureza_operacao'].help_text = "Selecione a regra de tributação do serviço."
            # O CFOP não é usado na NFS-e Nacional via API Focus v2 nesta estrutura
            self.fields['cfop'].widget = forms.HiddenInput()
        else:
            self.fields['natureza_operacao'].choices = self.CHOICES_NFE
            self.fields['cfop'].required = True