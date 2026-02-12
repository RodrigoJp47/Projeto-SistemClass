from django import forms
from django.contrib.auth.models import User # Para buscar/criar usuários
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.contrib.auth.forms import PasswordChangeForm
from .models import (
    PayableAccount, ReceivableAccount, Category, BankAccount, OFXImport, CentroCusto,
    Vendedor, ProdutoServico, Cliente, Contract, CompanyProfile, CompanyDocument 
)
import datetime
from decimal import Decimal, InvalidOperation # Adicione esta importação
import re


# --- SEUS FORMULÁRIOS EXISTENTES ---

# Dicionário de meses em português
MESES_PORTUGUES = {
    1: 'Janeiro',
    2: 'Fevereiro',
    3: 'Março',
    4: 'Abril',
    5: 'Maio',
    6: 'Junho',
    7: 'Julho',
    8: 'Agosto',
    9: 'Setembro',
    10: 'Outubro',
    11: 'Novembro',
    12: 'Dezembro',
}

class OFXImportForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        # Capturamos o usuário que a 'view' nos enviou
        user = kwargs.pop('user', None) 
        
        # Chamamos o construtor original para o form funcionar normalmente
        super(OFXImportForm, self).__init__(*args, **kwargs)
        
        # Se o usuário existir, filtramos o campo 'bank_account'
        if user:
            self.fields['bank_account'].queryset = BankAccount.objects.filter(user=user)
    # --- FIM DA CORREÇÃO ---

    class Meta:
        model = OFXImport
        fields = ['bank_account', 'file']
        widgets = {
            'bank_account': forms.Select(attrs={'class': 'form-field'}),
            'file': forms.FileInput(attrs={'accept': '.ofx', 'class': 'form-field'}),
        }
        labels = {
            'bank_account': 'Conta Bancária',
            'file': 'Arquivo OFX',
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if not file.name.lower().endswith('.ofx'):
                raise forms.ValidationError('Apenas arquivos OFX são permitidos.')
            if file.size > 5 * 1024 * 1024:  # Limite de 5MB
                raise forms.ValidationError('O arquivo deve ter no máximo 5MB.')
        return file

class PayableAccountForm(forms.ModelForm):
    new_category = forms.CharField(max_length=100, required=False, label="Nova Categoria")
    new_centro_custo = forms.CharField(max_length=100, required=False, label="Novo Centro de Custo")

    class Meta:
        model = PayableAccount
        fields = ['name', 'description', 'due_date', 'amount', 'category', 'new_category', 'centro_custo', 'new_centro_custo', 'dre_area', 'payment_method', 'occurrence', 'recurrence_count', 'cost_type', 'file', 'bank_account']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-field'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-field'}),
            'amount': forms.TextInput(attrs={'class': 'form-field inline-field', 'placeholder': 'Ex: 10.589,58'}),
            'category': forms.Select(attrs={'class': 'form-field inline-field'}),
            'new_category': forms.TextInput(attrs={'class': 'form-field inline-field'}),
            'centro_custo': forms.Select(attrs={'class': 'form-field inline-field'}),
            'new_centro_custo': forms.TextInput(attrs={'class': 'form-field inline-field'}),  
            'occurrence': forms.Select(attrs={'class': 'form-field inline-field'}),
            'recurrence_count': forms.NumberInput(attrs={'class': 'form-field inline-field', 'min': 1}),
            'cost_type': forms.Select(attrs={'class': 'form-field inline-field'}),
            'file': forms.FileInput(attrs={'accept': 'application/pdf', 'class': 'form-field'}),
            'dre_area': forms.Select(attrs={'class': 'form-field'}),
            'bank_account': forms.Select(attrs={'class': 'form-field'}),
        }
        labels = {
            'name': 'Nome',
            'description': 'Descrição',
            'due_date': 'Data de Vencimento',
            'amount': 'Valor',
            'category': 'Categoria',
            'centro_custo': 'Centro de Custo',
            'new_category': 'Nova Categoria',
            'dre_area': 'Área-DRE',
            'payment_method': 'Forma de Pagamento',
            'occurrence': 'Ocorrência',
            'recurrence_count': 'Quantidade de Recorrências',
            'bank_account': 'Conta Bancária',
            'cost_type': 'Tipo de Custo',
            'file': 'Anexar Arquivo (PDF)',
            'bank_account': 'Conta Bancária',
        }

    # Adicione esse bloco (o novo __init__ com o filtro de Banco)
    def __init__(self, *args, **kwargs):
        # Capturamos o 'user' que a view vai nos mandar
        user = kwargs.pop('user', None) 
        
        super().__init__(*args, **kwargs) # Chama o construtor original

        # Se o usuário foi passado (enviado pela view)...
        if user: 
            # ...filtramos a lista de CATEGORIAS para este usuário.
            self.fields['category'].queryset = Category.objects.filter(user=user, category_type='PAYABLE')
            
            # ▼▼▼ ESTA É A NOVA LINHA ADICIONADA ▼▼▼
            # ...E filtramos a lista de CONTAS BANCÁRIAS para este usuário.
            self.fields['bank_account'].queryset = BankAccount.objects.filter(user=user)

            self.fields['centro_custo'].queryset = CentroCusto.objects.filter(user=user)
            
        else: 
            # Se nenhum usuário for passado, não mostramos nenhuma categoria ou banco.
            self.fields['category'].queryset = Category.objects.none()
            self.fields['bank_account'].queryset = BankAccount.objects.none() # <-- NOVA LINHA ADICIONADA
            self.fields['centro_custo'].queryset = CentroCusto.objects.none()

        # O resto do seu método (configurações de campos) continua igual.
        self.fields['dre_area'].required = False
        self.fields['category'].required = False
        self.fields['centro_custo'].required = False
        self.fields['recurrence_count'].required = False
        self.fields['recurrence_count'].widget.attrs['min'] = 1
        self.fields['file'].required = False
        self.fields['bank_account'].required = True

        # Lista do que NÃO deve aparecer no Contas a Pagar
        excluir_opcoes = ['BRUTA', 'OUTRAS_RECEITAS'] 
        
        opcoes_dre_filtradas = [
            opcao for opcao in self.fields['dre_area'].choices 
            if opcao[0] not in excluir_opcoes
        ]
        self.fields['dre_area'].choices = opcoes_dre_filtradas

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if not file.name.lower().endswith('.pdf'):
                raise forms.ValidationError('Apenas arquivos PDF são permitidos.')
            if file.size > 5 * 1024 * 1024:  # Limite de 5MB
                raise forms.ValidationError('O arquivo deve ter no máximo 5MB.')
        return file

class ReceivableAccountForm(forms.ModelForm):
    new_category = forms.CharField(max_length=100, required=False, label="Nova Categoria")

    class Meta:
        model = ReceivableAccount
        fields = ['name', 'description', 'due_date', 'amount', 'category', 'dre_area', 'payment_method', 'occurrence', 'recurrence_count', 'bank_account', 'file']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-field'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-field'}),
            'amount': forms.TextInput(attrs={'class': 'form-field', 'placeholder': 'Ex: 10.589,58'}),
            'category': forms.Select(attrs={'class': 'form-field inline-field'}),
            'new_category': forms.TextInput(attrs={'class': 'form-field inline-field'}),
            'occurrence': forms.Select(attrs={'class': 'form-field inline-field'}),
            'recurrence_count': forms.NumberInput(attrs={'class': 'form-field inline-field', 'min': 1}),
            'dre_area': forms.Select(attrs={'class': 'form-field'}),
            'bank_account': forms.Select(attrs={'class': 'form-field'}),
            'file': forms.FileInput(attrs={'accept': 'application/pdf', 'class': 'form-field'}),
        }
        labels = {
            'name': 'Nome',
            'description': 'Descrição',
            'due_date': 'Data de Vencimento',
            'amount': 'Valor',
            'category': 'Categoria',
            'dre_area': 'Área-DRE',
            'payment_method': 'Forma de Pagamento',
            'occurrence': 'Ocorrência',
            'recurrence_count': 'Quantidade de Recorrências',
            'bank_account': 'Conta Bancária',
            'file': 'Anexar Arquivo (PDF)',
        }

    # Adicione esse bloco (o novo __init__ com o filtro de Banco)
    def __init__(self, *args, **kwargs):
        # Capturamos o 'user' que a view vai nos mandar
        user = kwargs.pop('user', None) 
        
        super().__init__(*args, **kwargs) # Chama o construtor original

        # Se o usuário foi passado (enviado pela view)...
        if user: 
            # ...filtramos a lista de CATEGORIAS para este usuário.
            self.fields['category'].queryset = Category.objects.filter(user=user, category_type='RECEIVABLE')
            
            # ▼▼▼ ESTA É A NOVA LINHA ADICIONADA ▼▼▼
            # ...E filtramos a lista de CONTAS BANCÁRIAS para este usuário.
            self.fields['bank_account'].queryset = BankAccount.objects.filter(user=user)
            
        else: 
            # Se nenhum usuário for passado, não mostramos nenhuma categoria ou banco.
            self.fields['category'].queryset = Category.objects.none()
            self.fields['bank_account'].queryset = BankAccount.objects.none() # <-- NOVA LINHA ADICIONADA

        # O resto do seu método (configurações de campos) continua igual.
        self.fields['category'].required = False
        self.fields['recurrence_count'].required = False
        self.fields['recurrence_count'].widget.attrs['min'] = 1
        self.fields['file'].required = False
# --- INÍCIO DOS NOVOS FORMULÁRIOS PARA O MÓDULO COMERCIAL ---

def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if not file.name.lower().endswith('.pdf'):
                raise forms.ValidationError('Apenas arquivos PDF são permitidos.')
            if file.size > 5 * 1024 * 1024:  # Limite de 5MB
                raise forms.ValidationError('O arquivo deve ter no máximo 5MB.')
        return file

# Em accounts/forms.py

class ProdutoServicoForm(forms.ModelForm):
    class Meta:
        model = ProdutoServico
        # Seus campos...
        fields = ['nome', 'codigo', 'descricao', 'tipo', 'preco_venda', 'preco_custo', 'estoque_atual', 'ncm', 'unidade_medida', 'origem', 'codigo_servico'] 
        labels = {
            'nome': 'Nome do Produto/Serviço',
            'codigo': 'Código',
            'descricao': 'Descrição',
            'tipo': 'Tipo',
            'preco_venda': 'Preço de Venda',
            'preco_custo': 'Preço de Custo',
            'estoque_atual': 'Estoque Atual'
        }
        widgets = {
            # Alteramos autocomplete para 'new-password' para forçar o navegador a limpar
            'nome': forms.TextInput(attrs={'class': 'form-field', 'autocomplete': 'off'}),
            'codigo': forms.TextInput(attrs={'class': 'form-field', 'autocomplete': 'new-password'}), 
            'descricao': forms.Textarea(attrs={'rows': 3, 'class': 'form-field'}),
            'tipo': forms.Select(attrs={'class': 'form-field'}),
            'preco_venda': forms.TextInput(attrs={'class': 'form-field'}),
            'preco_custo': forms.TextInput(attrs={'class': 'form-field'}),
            'estoque_atual': forms.NumberInput(attrs={'class': 'form-field'}),
        }

    # 1. Adicionamos o __init__ para receber o usuário da view
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None) # Pega o usuário enviado pela view
        super().__init__(*args, **kwargs)

    # 2. Adicionamos a validação manual do código
    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo')
        if codigo and self.user:
            # Verifica se JÁ EXISTE este código para ESTE usuário específico
            # O .exclude(pk=self.instance.pk) serve para permitir edição do próprio produto
            exists = ProdutoServico.objects.filter(user=self.user, codigo=codigo).exclude(pk=self.instance.pk).exists()
            if exists:
                raise forms.ValidationError("Já existe um produto cadastrado com este código.")
        return codigo
class VendedorForm(forms.ModelForm):
    class Meta:
        model = Vendedor
        fields = ['nome', 'email', 'telefone', 'comissao_percentual']
        labels = {
            'nome': 'Nome do Vendedor',
            'email': 'E-mail',
            'telefone': 'Telefone',
            'comissao_percentual': 'Comissão (%)'
        }

# Em accounts/forms.py

class ClienteForm(forms.ModelForm):
    codigo_municipio = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-field', 'placeholder': 'Cód. IBGE'})
    )

    class Meta:
        model = Cliente
        fields = [
            'nome', 'cpf_cnpj', 'email', 'telefone', 
            'cep', 'logradouro', 'numero', 'bairro', 'cidade', 'uf', 'codigo_municipio'
        ]
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-field'}),
            'cpf_cnpj': forms.TextInput(attrs={'class': 'form-field'}),
            'email': forms.EmailInput(attrs={'class': 'form-field'}),
            'telefone': forms.TextInput(attrs={'class': 'form-field'}),
            'cep': forms.TextInput(attrs={'class': 'form-field', 'id': 'id_cep'}),
            'logradouro': forms.TextInput(attrs={'class': 'form-field', 'id': 'id_logradouro'}),
            'numero': forms.TextInput(attrs={'class': 'form-field', 'id': 'id_numero'}),
            'bairro': forms.TextInput(attrs={'class': 'form-field', 'id': 'id_bairro'}),
            'cidade': forms.TextInput(attrs={'class': 'form-field', 'id': 'id_cidade'}),
            'uf': forms.TextInput(attrs={'class': 'form-field', 'id': 'id_uf', 'maxlength': '2'}),
        }

    def __init__(self, *args, **kwargs):
        # Captura o usuário que vamos passar na view
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_cpf_cnpj(self):
        cpf = self.cleaned_data.get('cpf_cnpj')
        # Se estamos criando um novo (self.instance.pk é None) e temos um usuário
        if self.user and cpf:
            # Verifica se JÁ EXISTE um cliente com este CPF para ESTE USUÁRIO
            # O .exclude(pk=self.instance.pk) permite que você edite o próprio cliente sem dar erro
            exists = Cliente.objects.filter(user=self.user, cpf_cnpj=cpf).exclude(pk=self.instance.pk).exists()
            if exists:
                raise forms.ValidationError("Você já possui um cliente cadastrado com este CPF/CNPJ.")
        return cpf

from .models import MetaFaturamento # Adicione MetaFaturamento às importações

# Em accounts/forms.py
from decimal import Decimal, InvalidOperation

# ...

# --- INÍCIO DA VERSÃO CORRIGIDA ---
class MetaFaturamentoForm(forms.ModelForm):
    # 1. Definimos o campo 'alvo' e o 'valor_meta' manualmente
    alvo = forms.ChoiceField(label="Definir meta para")
    
    # Ao definir como CharField, evitamos a validação padrão de número do Django,
    # permitindo que nosso método 'clean' trate a string "1.500,50"
    valor_meta = forms.CharField(
        label="Valor da Meta",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 1.500,50'})
    )

    class Meta:
        model = MetaFaturamento
        fields = ['mes_ano'] # 'alvo' e 'valor_meta' já foram definidos acima
        widgets = {
            'mes_ano': forms.DateInput(attrs={'type': 'month', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            vendedores = Vendedor.objects.filter(user=user).order_by('nome')
            alvo_choices = [('empresa', 'Meta Geral da Empresa')] + [(v.id, v.nome) for v in vendedores]
            self.fields['alvo'].choices = alvo_choices
    
    # 2. O método clean_valor_meta agora funcionará corretamente
    def clean_valor_meta(self):
        valor_str = self.cleaned_data.get('valor_meta')
        if valor_str:
            valor_sem_ponto = valor_str.replace('.', '')
            valor_com_ponto = valor_sem_ponto.replace(',', '.')
            try:
                return Decimal(valor_com_ponto)
            except InvalidOperation:
                raise forms.ValidationError("Por favor, insira um número válido (ex: 1.500,50).")
        return None
# --- FIM DA VERSÃO CORRIGIDA ---

# Em accounts/forms.py (Substitua a classe CustomUserCreationForm inteira)

class CustomUserCreationForm(UserCreationForm):
    # Definimos o campo explicitamente para ser obrigatório e ter o ID correto para o JavaScript
    cnpj = forms.CharField(
        label="CNPJ",
        required=True,
        max_length=18,
        widget=forms.TextInput(attrs={
            'class': 'form-field', 
            'placeholder': '00.000.000/0000-00',
            'id': 'id_cnpj', # Este ID conecta com o JavaScript que te mandei antes
            'autocomplete': 'off'
        })
    )
    email = forms.EmailField(
        label="E-mail", 
        required=True, 
        widget=forms.EmailInput(attrs={'class': 'form-field'})
    )

    class Meta(UserCreationForm.Meta):
        # A ordem aqui define a ordem que aparece na tela
        fields = UserCreationForm.Meta.fields + ('email', 'cnpj')

    def clean_cnpj(self):
        # Remove qualquer caractere que não seja número
        cnpj = re.sub(r'\D', '', self.cleaned_data.get('cnpj', ''))

        # 1. Valida tamanho
        if len(cnpj) != 14:
            raise forms.ValidationError("O CNPJ deve conter exatamente 14 dígitos.")

        # 2. Valida números repetidos (Ex: 11.111.111/1111-11)
        if cnpj in [str(i)*14 for i in range(10)]:
            raise forms.ValidationError("Número de CNPJ inválido.")

        # 3. Validação matemática dos dígitos verificadores
        def calcular_digito(cnpj_parcial, pesos):
            soma = sum(int(digito) * peso for digito, peso in zip(cnpj_parcial, pesos))
            resto = soma % 11
            return '0' if resto < 2 else str(11 - resto)

        # Valida primeiro dígito
        pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        if cnpj[12] != calcular_digito(cnpj[:12], pesos1):
            raise forms.ValidationError("CNPJ inválido (Dígito verificador incorreto).")

        # Valida segundo dígito
        pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        if cnpj[13] != calcular_digito(cnpj[:13], pesos2):
            raise forms.ValidationError("CNPJ inválido (Dígito verificador incorreto).")

        # 4. Verifica duplicidade no banco (ignorando a própria empresa na edição)
        if CompanyProfile.objects.filter(cnpj=cnpj).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Este CNPJ já está cadastrado em nossa base.")

        return cnpj

    def save(self, commit=True):
        """Salva o Usuário e cria automaticamente o Perfil da Empresa"""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        
        if commit:
            user.save()
            # AQUI ESTÁ O SEGRED: Criamos o perfil da empresa vinculado ao usuário
            # Se o perfil já tiver sido criado por algum Signal, usamos get_or_create
            profile, created = CompanyProfile.objects.get_or_create(user=user)
            
            # Atualizamos os dados do perfil com o CNPJ do formulário
            profile.cnpj = self.cleaned_data['cnpj']
            profile.nome_empresa = f"Empresa {user.username}" # Define um nome provisório
            profile.email_contato = user.email
            profile.save()
            
        return user

from .models import Orcamento # Adicione Orcamento às importações

class OrcamentoForm(forms.ModelForm):
    # Usamos CharField para tratar a formatação de moeda (ex: 1.500,50)
    valor_orcado = forms.CharField(
        label="Valor Orçado",
        widget=forms.TextInput(attrs={'placeholder': 'Ex: 1.500,50'})
    )

    class Meta:
        model = Orcamento
        fields = ['category', 'mes_ano', 'valor_orcado']
        labels = {
            'category': 'Categoria',
            'mes_ano': 'Mês/Ano',
        }
        widgets = {
            'mes_ano': forms.DateInput(attrs={'type': 'month'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            # Popula o dropdown apenas com as categorias do usuário
            self.fields['category'].queryset = Category.objects.all().order_by('name')

    def clean_valor_orcado(self):
        valor_str = self.cleaned_data.get('valor_orcado')
        if valor_str:
            valor_sem_ponto = valor_str.replace('.', '')
            valor_com_ponto = valor_sem_ponto.replace(',', '.')
            try:
                return Decimal(valor_com_ponto)
            except InvalidOperation:
                raise forms.ValidationError("Por favor, insira um número válido (ex: 1.500,50).")
        return None        
    


# Adicionar ao final de accounts/forms.py

class ContractForm(forms.ModelForm):
    value = forms.CharField(label="Valor", widget=forms.TextInput(attrs={'placeholder': 'Ex: 1.500,50', 'class': 'form-field'}))
    class Meta:
        model = Contract
        # Exclui 'user' e 'created_at' que são automáticos
        fields = ['title', 'client', 'start_date', 'end_date', 'value', 'status', 'document', 'reajuste_percentual', 'frequencia_pagamento', 'quantidade_parcelas', 'dia_vencimento']
        
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-field'}),
            'client': forms.Select(attrs={'class': 'form-field'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-field'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-field'}),
            'value': forms.TextInput(attrs={'class': 'form-field', 'placeholder': 'Ex: 1.500,50'}),
            'status': forms.Select(attrs={'class': 'form-field'}),
            'document': forms.FileInput(attrs={'accept': 'application/pdf', 'class': 'form-field'}),
            'reajuste_percentual': forms.TextInput(attrs={'class': 'form-field', 'placeholder': '0.00%'}),
            'frequencia_pagamento': forms.Select(attrs={'class': 'form-field'}),
            'quantidade_parcelas': forms.NumberInput(attrs={'class': 'form-field', 'min': '1'}),
            'dia_vencimento': forms.NumberInput(attrs={'class': 'form-field', 'min': '1', 'max': '31', 'placeholder': 'Dia'}),
        }
        
        labels = {
            'title': 'Título do Contrato',
            'client': 'Cliente',
            'start_date': 'Data de Início',
            'end_date': 'Data de Término',
            'value': 'Valor',
            'status': 'Status',
            'document': 'Anexar Documento (PDF)',
            'reajuste_percentual': 'Reajuste (%)',
            'frequencia_pagamento': 'Frequência',
            'quantidade_parcelas': 'Duração (Meses)',
            'dia_vencimento': 'Dia Cobrança',
        }

    def __init__(self, *args, **kwargs):
        # Filtra o dropdown de 'client' para mostrar apenas os clientes do usuário logado
        # (Igual ao seu OFXImportForm)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['client'].queryset = Cliente.objects.filter(user=user).order_by('nome')

    def clean_value(self):
        valor_str = self.cleaned_data.get('value')
        try:
            # Se o front-end já enviou "10000.00", apenas converte direto
            return Decimal(str(valor_str).replace(',', '.'))
        except (InvalidOperation, TypeError):
            raise forms.ValidationError("Por favor, insira um número válido (ex: 1.500,50).")


    def clean_document(self):
        # Validação de arquivo (Igual ao seu PayableAccountForm)
        file = self.cleaned_data.get('document')
        if file:
            if not file.name.lower().endswith('.pdf'):
                raise forms.ValidationError('Apenas arquivos PDF são permitidos.')
            if file.size > 5 * 1024 * 1024:  # Limite de 5MB
                raise forms.ValidationError('O arquivo deve ter no máximo 5MB.')
        return file


class EmployeeCreationForm(forms.ModelForm):
    first_name = forms.CharField(label="Nome", max_length=150, required=True)
    email = forms.EmailField(label="E-mail", required=True)
    password = forms.CharField(label="Senha", widget=forms.PasswordInput)
    password_confirm = forms.CharField(label="Confirmar Senha", widget=forms.PasswordInput)
    # --- Permissões Financeiro ---
    can_access_home = forms.BooleanField(label="Home (Página Principal)", required=False, initial=True)
    can_access_contas_pagar = forms.BooleanField(label="Contas a Pagar", required=False)
    can_access_contas_receber = forms.BooleanField(label="Contas a Receber", required=False)
    can_access_tarefas = forms.BooleanField(label="Gestão de Tarefas", required=False)
    can_access_orcamento_anual = forms.BooleanField(label="Orçamento Anual", required=False)
    can_access_painel_financeiro = forms.BooleanField(label="Painel Financeiro", required=False)
    can_access_fornecedores = forms.BooleanField(label="Fornecedores", required=False)
    can_access_clientes_financeiro = forms.BooleanField(label="Clientes (Financeiro)", required=False)
    can_access_fluxo_caixa = forms.BooleanField(label="Fluxo de Caixa Analítico", required=False)

    # --- Permissões Comercial ---
    can_access_painel_vendas = forms.BooleanField(label="Painel de Vendas", required=False)
    can_access_notas_fiscais = forms.BooleanField(label="Notas Fiscais", required=False)
    can_access_orcamentos_venda = forms.BooleanField(label="Orçamentos", required=False)
    can_access_contratos = forms.BooleanField(label="Gestão de Contratos", required=False)
    can_access_cadastros_comercial = forms.BooleanField(label="Cadastros (Comercial)", required=False)
    can_access_vendas = forms.BooleanField(label="Vendas", required=False)
    can_access_metas_comerciais = forms.BooleanField(label="Gestão de Metas", required=False)
    can_access_precificacao = forms.BooleanField(label="Precificação", required=False)
    can_access_pdv = forms.BooleanField(label="Acesso ao PDV (Frente de Caixa)", required=False)
    can_access_crm = forms.BooleanField(label="Acesso ao CRM (Pipeline)", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Para todos os campos gerais, desligamos o autocomplete
        for name, field in self.fields.items():
            field.initial = None
            field.widget.attrs['autocomplete'] = 'off'

        # 2. TRUQUE DO E-MAIL (Estratégia "Nuclear")
        # O campo inicia como 'somente leitura' para o navegador não preencher.
        # Quando você clica nele (onfocus), ele libera para digitar.
        self.fields['email'].widget.attrs.update({
            'autocomplete': 'new-password', # Diz ao navegador que não é login antigo
            'readonly': 'readonly',         # Bloqueia preenchimento automático
            'onfocus': "this.removeAttribute('readonly');" # Desbloqueia ao clicar
        })

        # 3. TRUQUE DA SENHA
        # 'new-password' força o navegador a entender que é uma NOVA senha, não a sua salva.
        self.fields['password'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['password_confirm'].widget.attrs['autocomplete'] = 'new-password'

    class Meta:
        model = User
        fields = ('first_name', 'email')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este e-mail já está em uso.")
        return email

    def clean_password_confirm(self):
        password = self.cleaned_data.get("password")
        password_confirm = self.cleaned_data.get("password_confirm")
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("As senhas não coincidem.")
        if len(password) < 8:
            raise forms.ValidationError("A senha deve ter pelo menos 8 caracteres.")
        return password_confirm


# Adicione ao FINAL de accounts/forms.py

class CompanyProfileForm(forms.ModelForm):
    # Definimos apenas uma vez fora do Meta para controle total
    optante_simples_nacional = forms.BooleanField(
        required=False, 
        label="Optante pelo Simples Nacional?",
        widget=forms.CheckboxInput(attrs={'style': 'width: 20px; height: 20px;'})
    )

    class Meta:
        model = CompanyProfile
        # AJUSTE CRUCIAL: Adicionamos todos os campos técnicos ao EXCLUDE
        # Isso impede o erro de "campo obrigatório" para campos que o usuário não vê.
        exclude = (
            'user', 
            'updated_at', 
            'asaas_subaccount_id', 
            'asaas_wallet_id', 
            'asaas_api_key', 
            'provider_fiscal'
        )
        
        widgets = {
            'nome_empresa': forms.TextInput(attrs={'class': 'form-field'}),
            'nome_fantasia': forms.TextInput(attrs={'class': 'form-field'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-field'}),
            'email_contato': forms.EmailInput(attrs={'class': 'form-field'}),
            'telefone_contato': forms.TextInput(attrs={'class': 'form-field'}),
            'endereco': forms.TextInput(attrs={'class': 'form-field'}),
            'numero': forms.TextInput(attrs={'class': 'form-field'}),
            'bairro': forms.TextInput(attrs={'class': 'form-field'}),
            'cidade': forms.TextInput(attrs={'class': 'form-field'}),
            'estado': forms.TextInput(attrs={'class': 'form-field', 'maxlength': 2}),
            'cep': forms.TextInput(attrs={'class': 'form-field'}),
            'inscricao_municipal': forms.TextInput(attrs={'class': 'form-field', 'placeholder': 'Obrigatório para NFS-e'}),
            'inscricao_estadual': forms.TextInput(attrs={'class': 'form-field', 'placeholder': 'Deixe em branco para preencher com zeros'}),
            'codigo_municipio': forms.TextInput(attrs={'class': 'form-field', 'placeholder': 'Código IBGE (7 dígitos)'}),
            'senha_certificado': forms.PasswordInput(attrs={'class': 'form-field', 'placeholder': 'Senha do arquivo .pfx', 'autocomplete': 'new-password'}),
            'certificado_digital': forms.FileInput(attrs={'class': 'form-field', 'accept': '.pfx'}),
            'regime_tributario': forms.Select(attrs={'class': 'form-field'}),
            'aliquota_iss': forms.NumberInput(attrs={'class': 'form-field', 'step': '0.01', 'placeholder': 'Ex: 2.00'}),
            'enviar_email_automatico': forms.CheckboxInput(attrs={'style': 'width: 20px; height: 20px; margin-top: 10px;'}),
            'regime_especial_tributacao': forms.Select(attrs={'class': 'form-field'}),
            'incentivador_cultural': forms.CheckboxInput(attrs={'style': 'width: 20px; height: 20px;'}),
            'arquivo_logo': forms.FileInput(attrs={'class': 'form-field', 'accept': 'image/*'}),
            'proximo_numero_nfe': forms.NumberInput(attrs={'class': 'form-field'}),
            'serie_nfe': forms.TextInput(attrs={'class': 'form-field'}),
            'proximo_numero_nfse': forms.NumberInput(attrs={'class': 'form-field'}),
            'serie_nfse': forms.TextInput(attrs={'class': 'form-field'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Deixando campos não obrigatórios para não travar o form
        self.fields['regime_especial_tributacao'].required = False
        self.fields['inscricao_estadual'].required = False
        
        # Sincroniza o valor inicial da checkbox customizada com o model
        if self.instance and self.instance.pk:
            # Aqui acessamos a @property que você tem no seu model
            self.fields['optante_simples_nacional'].initial = self.instance.optante_simples_nacional

class CompanyDocumentForm(forms.ModelForm):
    class Meta:
        model = CompanyDocument
        fields = ('descricao', 'arquivo')
        widgets = {
            'descricao': forms.TextInput(attrs={
                'class': 'form-field', 
                'placeholder': 'Ex: Cartão CNPJ'
            }),
            'arquivo': forms.FileInput(attrs={
                'class': 'form-field'
            }),
        }
        labels = {
            'descricao': 'Descrição',
            'arquivo': 'Anexar Arquivo',
        }




# Adicione ao final ou onde estão os outros forms
from .models import InterCredentials

class InterCredentialsForm(forms.ModelForm):
    class Meta:
        model = InterCredentials
        fields = ['client_id', 'client_secret', 'certificado_crt', 'chave_key']
        widgets = {
            'client_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cole o Client ID'}),
            'client_secret': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cole o Client Secret'}),
        }        



from .models import MercadoPagoCredentials # Não esqueça de importar o novo modelo

class MercadoPagoCredentialsForm(forms.ModelForm):
    class Meta:
        model = MercadoPagoCredentials
        fields = ['public_key', 'access_token']
        labels = {
            'public_key': 'Chave Pública (Public Key) - Opcional',
            'access_token': 'Token de Acesso (Access Token) - Obrigatório',
        }
        widgets = {
            'public_key': forms.TextInput(attrs={
                'class': 'form-field', 
                'placeholder': 'APP_USR-...'
            }),
            'access_token': forms.TextInput(attrs={
                'class': 'form-field', 
                'placeholder': 'APP_USR-...'
            }),
        }
        help_texts = {
            'access_token': 'Cole aqui o seu Access Token de Produção obtido no painel de desenvolvedores do Mercado Pago.'
        }


# accounts/forms.py

# ... (outros imports)
from .models import AsaasCredentials # Não esqueça de importar

class AsaasCredentialsForm(forms.ModelForm):
    class Meta:
        model = AsaasCredentials
        fields = ['access_token', 'is_sandbox']
        labels = {
            'access_token': 'Chave de API (API Key)',
            'is_sandbox': 'Ativar Modo Sandbox (Testes)',
        }
        widgets = {
            'access_token': forms.TextInput(attrs={
                'class': 'form-field', 
                'placeholder': '$aact_...',
                'autocomplete': 'off'
            }),
            'is_sandbox': forms.CheckboxInput(attrs={
                'style': 'width: 20px; height: 20px; margin-top: 10px;'
            }),
        }
        help_texts = {
            'access_token': 'Cole aqui sua chave de API (começa com $aact).',
            'is_sandbox': 'Mantenha marcado se estiver usando uma conta criada em sandbox.asaas.com.'
        }


# accounts/forms.py

class BPOAddClientForm(forms.ModelForm):
    # 1. Definimos os campos explicitamente para adicionar os Widgets (configurações visuais)
    first_name = forms.CharField(
        label="Nome do Cliente/Empresa", 
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-field', # Mantém seu estilo CSS
            'placeholder': 'Nome da Empresa ou Cliente'
        })
    )

    email = forms.EmailField(
        label="E-mail de Login", 
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-field',
            'autocomplete': 'off', # Tenta desligar o autocompletar padrão
            'placeholder': 'exemplo@email.com'
        })
    )

    password = forms.CharField(
        label="Senha Inicial", 
        widget=forms.PasswordInput(attrs={
            'class': 'form-field',
            'autocomplete': 'new-password', # O MAIS IMPORTANTE: Diz ao navegador "isso é uma senha nova, não use a minha salva"
            'placeholder': 'Digite a senha inicial'
        })
    )

    class Meta:
        model = User
        fields = ('first_name', 'email', 'password')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # TRUQUE EXTRA (Nuclear): Se o navegador for teimoso (como o Chrome), 
        # isso força o campo a ficar "somente leitura" até você clicar nele.
        # Isso impede 100% que o navegador preencha o e-mail sozinho ao carregar a página.
        self.fields['email'].widget.attrs.update({
            'readonly': 'readonly',
            'onfocus': "this.removeAttribute('readonly');"
        })

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este e-mail já está cadastrado no sistema.")
        return email
    


from .models import OmieCredentials # Não esqueça de adicionar OmieCredentials no import do .models

class OmieCredentialsForm(forms.ModelForm):
    class Meta:
        model = OmieCredentials
        fields = ['app_key', 'app_secret']
        labels = {
            'app_key': 'App Key (Chave da Aplicação)',
            'app_secret': 'App Secret (Segredo da Aplicação)',
        }
        widgets = {
            'app_key': forms.TextInput(attrs={
                'class': 'form-field', 
                'placeholder': 'Ex: 38392...',
                'autocomplete': 'off'
            }),
            'app_secret': forms.TextInput(attrs={
                'class': 'form-field', 
                'placeholder': 'Ex: 484a9...',
                'autocomplete': 'off'
            }),
        }
        help_texts = {
            'app_key': 'Disponível no painel do desenvolvedor Omie (Configurações > API).',
        }    



# accounts/forms.py
from .models import NiboCredentials # Não esqueça de importar no topo

class NiboCredentialsForm(forms.ModelForm):
    class Meta:
        model = NiboCredentials
        fields = ['api_token', 'organization_id']
        labels = {
            'api_token': 'Token de API (API Token)',
            'organization_id': 'ID da Organização (Organization ID)',
        }
        widgets = {
            'api_token': forms.TextInput(attrs={
                'class': 'form-field', 
                'placeholder': 'Cole seu Token aqui...',
                'autocomplete': 'off'
            }),
            'organization_id': forms.TextInput(attrs={
                'class': 'form-field', 
                'placeholder': 'Ex: 123456-abcdef...',
                'autocomplete': 'off'
            }),
        }
        help_texts = {
            'api_token': 'Obtenha o Token no painel de integrações do Nibo.',
        }




# Adicione ao final de accounts/forms.py (não esqueça de importar o model no topo)
from .models import TinyCredentials

class TinyCredentialsForm(forms.ModelForm):
    class Meta:
        model = TinyCredentials
        fields = ['token']
        labels = {
            'token': 'Token de API (Chave de Acesso)',
        }
        widgets = {
            'token': forms.TextInput(attrs={
                'class': 'form-field', 
                'placeholder': 'Cole seu Token do Tiny aqui...',
                'autocomplete': 'off',
                'style': 'width: 100%;'
            }),
        }
        help_texts = {
            'token': 'No Tiny, vá em Configurações > Aba E-commerce > API > Token.',
        }        

# Adicione isso ao final do accounts/forms.py
from .models import CompanyUserLink

class EmployeePermissionsForm(forms.ModelForm):
    class Meta:
        model = CompanyUserLink
        fields = [
            'can_access_home',
            'can_access_contas_pagar',
            'can_access_contas_receber',
            'can_access_tarefas',
            'can_access_orcamento_anual',
            'can_access_painel_financeiro',
            'can_access_fornecedores',
            'can_access_clientes_financeiro',
            'can_access_fluxo_caixa',
            'can_access_crm',
            'can_access_pdv',
            'can_access_painel_vendas',
            'can_access_notas_fiscais',
            'can_access_orcamentos_venda',
            'can_access_contratos',
            'can_access_cadastros_comercial',
            'can_access_vendas',
            'can_access_metas_comerciais',
            'can_access_precificacao',
        ]
        # Opcional: Melhora os labels para ficarem mais legíveis
        labels = {
            'can_access_home': 'Acesso à Home',
            'can_access_contas_pagar': 'Contas a Pagar',
            'can_access_contas_receber': 'Contas a Receber',
            'can_access_tarefas': 'Tarefas',
            'can_access_orcamento_anual': 'Orçamento Anual',
            'can_access_painel_financeiro': 'Painel Financeiro (Dashboards)',
            'can_access_fornecedores': 'Fornecedores',
            'can_access_clientes_financeiro': 'Clientes (Financeiro)',
            'can_access_crm': 'Acesso ao CRM / Pipeline',
            'can_access_pdv': 'Frente de Caixa (PDV)',
            'can_access_painel_vendas': 'Painel de Vendas',
            'can_access_notas_fiscais': 'Notas Fiscais',
            'can_access_orcamentos_venda': 'Orçamentos',
            'can_access_contratos': 'Contratos',
            'can_access_cadastros_comercial': 'Cadastros (Produtos/Vendedores)',
            'can_access_vendas': 'Vendas (Listagem)',
            'can_access_metas_comerciais': 'Metas Comerciais',
            'can_access_precificacao': 'Precificação',
        }


