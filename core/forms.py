# core/forms.py

from django import forms
from .models import Empresa, Quadro, Cartao, ChecklistItem

class EmpresaForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = '__all__' # Diz ao form para usar todos os campos do modelo Empresa

# 2. Adicione o novo formulário para Quadro
class QuadroForm(forms.ModelForm):
    class Meta:
        model = Quadro
        # Queremos apenas o campo 'titulo' no formulário,
        # pois a 'empresa' será associada automaticamente na view.
        fields = ['titulo']      

# Em core/forms.py, altere a classe CartaoForm

class CartaoForm(forms.ModelForm):
    class Meta:
        model = Cartao
        # Adicione 'anexo' à lista
        fields = ['titulo', 'descricao', 'status', 'anexo']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 4}),
        }



class ChecklistItemForm(forms.ModelForm):
    class Meta:
        model = ChecklistItem
        fields = ['titulo'] # O usuário só precisa digitar o título
        widgets = {
            'titulo': forms.TextInput(attrs={
                'placeholder': 'Adicionar um item...', 
                'class': 'form-checklist-input',
                'autocomplete': 'off'
            })
        }     
