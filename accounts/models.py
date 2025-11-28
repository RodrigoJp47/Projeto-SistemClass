from django.db import models
from django.contrib.auth.models import User
from django.conf import settings 
from django.utils import timezone

USER_TYPE_CHOICES = (
    ('BPO', 'BPO Admin'),
    ('CLIENTE', 'Cliente Final'),
)

# Adicione esse bloco (no início de models.py)
CATEGORY_TYPES = (
    ('PAYABLE', 'Contas a Pagar'),
    ('RECEIVABLE', 'Contas a Receber'),
)

# Definir escolhas no nível do módulo
PAYMENT_METHODS = (
    ('DINHEIRO', 'Dinheiro'),
    ('PIX', 'PIX'),
    ('DEBITO', 'Débito'),
    ('CREDITO', 'Crédito'),
    ('BOLETO', 'Boleto'),
)
OCCURRENCE_TYPES = (
    ('AVULSO', 'Avulso'),
    ('RECORRENTE', 'Recorrente'),
)
    
DRE_AREAS = (
    ('NAO_CONSTAR', 'Não constar DRE'),
    ('DEDUCAO', 'Dedução da Receita Bruta'),
    ('CUSTOS', 'Custos CSP/CMV'),
    ('OPERACIONAL', 'Despesas Operacionais'),
    ('DEPRECIACAO', 'Depreciação e Amortização'),
    ('NAO_OPERACIONAL', 'Não Operacional'),
    ('TRIBUTACAO', 'IRPJ e CSLL (Tributação)'),
    ('DISTRIBUICAO', 'Distribuição de Lucro Sócios'),
    ('BRUTA', 'Receitas Brutas'),
)

COST_TYPES = (
    ('FIXO', 'Fixo'),
    ('VARIAVEL', 'Variável'),
)

class Category(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100) # Removemos unique=True por enquanto
    category_type = models.CharField(max_length=10, choices=CATEGORY_TYPES) # Adicionamos o tipo
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Garante que não haja nomes duplicados PARA O MESMO TIPO
        unique_together = ('user', 'name', 'category_type')
        ordering = ['name'] # Opcional: ordena alfabeticamente

    def __str__(self):
        # Mostra o tipo junto ao nome para clareza (Ex: "Alimentação (Pagar)")
        return f"{self.name} ({self.get_category_type_display()})"

class BankAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    bank_name = models.CharField(max_length=100)
    agency = models.CharField(max_length=20)
    account_number = models.CharField(max_length=20)
    initial_balance = models.DecimalField(max_digits=10, decimal_places=2)
    opening_date = models.DateField(verbose_name="Data de Abertura", default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.bank_name

class OFXImport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE)
    bank_name = models.CharField(max_length=100)
    import_date = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to='ofx_imports/%Y/%m/%d/')

    def __str__(self):
        return f"{self.bank_name} - {self.import_date.strftime('%d/%m/%Y %H:%M')}"

class PayableAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    dre_area = models.CharField(max_length=50, choices=DRE_AREAS)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    occurrence = models.CharField(max_length=20, choices=OCCURRENCE_TYPES)
    recurrence_count = models.PositiveIntegerField(null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    cost_type = models.CharField(max_length=20, choices=COST_TYPES, default='FIXO')
    file = models.FileField(upload_to='payables/%Y/%m/%d/', null=True, blank=True)
    bank_account = models.ForeignKey(BankAccount, on_delete=models.SET_NULL, null=True)
    ofx_import = models.ForeignKey(OFXImport, on_delete=models.SET_NULL, null=True, blank=True)
    payment_date = models.DateField(null=True, blank=True, verbose_name="Data de Pagamento")
    external_id = models.CharField(max_length=255, null=True, blank=True, unique=True, db_index=True)
    fitid = models.CharField(max_length=255, null=True, blank=True, db_index=True, verbose_name="ID da Transação (FITID)")

    def __str__(self):
        return f"{self.name} - {self.amount}"

    class Meta:
        indexes = [
            models.Index(fields=['due_date']),
        ]

class ReceivableAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    dre_area = models.CharField(max_length=50, choices=DRE_AREAS)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    occurrence = models.CharField(max_length=20, choices=OCCURRENCE_TYPES)
    recurrence_count = models.PositiveIntegerField(null=True, blank=True)
    is_received = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    ofx_import = models.ForeignKey(OFXImport, on_delete=models.SET_NULL, null=True, blank=True)
    # Em models.py, dentro da classe ReceivableAccount
    payment_date = models.DateField(null=True, blank=True, verbose_name="Data de Recebimento")
    bank_account = models.ForeignKey(BankAccount, on_delete=models.SET_NULL, null=True)
    file = models.FileField(upload_to='receivables/%Y/%m/%d/', null=True, blank=True) # <-- ESTA LINHA
    external_id = models.CharField(max_length=255, null=True, blank=True, unique=True, db_index=True)
    fitid = models.CharField(max_length=255, null=True, blank=True, db_index=True, verbose_name="ID da Transação (FITID)")

    def __str__(self):
        return f"{self.name} - {self.amount}"

    class Meta:
        indexes = [
            models.Index(fields=['due_date']),
        ]

class Estado(models.Model):
    nome = models.CharField(max_length=50)
    uf = models.CharField(max_length=2, unique=True)

    def __str__(self):
        return self.uf

class Cidade(models.Model):
    nome = models.CharField(max_length=100)
    estado = models.ForeignKey(Estado, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.nome} ({self.estado.uf})'        

# --- INÍCIO DOS NOVOS MODELOS PARA O MÓDULO COMERCIAL ---

class Vendedor(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    nome = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    telefone = models.CharField(max_length=20, blank=True)
    comissao_percentual = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

class ProdutoServico(models.Model):
    TIPO_CHOICES = (
        ('PRODUTO', 'Produto'),
        ('SERVICO', 'Serviço'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    nome = models.CharField(max_length=200)
    codigo = models.CharField(max_length=50, blank=True, null=True)
    descricao = models.TextField(blank=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='PRODUTO')
    preco_venda = models.DecimalField(max_digits=10, decimal_places=2)
    preco_custo = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, verbose_name="Preço de Custo")
    estoque_atual = models.IntegerField(default=0, help_text="Apenas para produtos")
    created_at = models.DateTimeField(auto_now_add=True)
    # --- ADICIONE ESTES CAMPOS FISCAIS ABAIXO ---
    ncm = models.CharField(max_length=8, blank=True, null=True, verbose_name="NCM")
    unidade_medida = models.CharField(max_length=6, default="UN", verbose_name="Unidade (Ex: UN, CX, PC)")
    origem = models.CharField(max_length=1, default="0", verbose_name="Origem (0=Nacional)")
    cfop_padrao = models.CharField(max_length=4, blank=True, null=True, verbose_name="CFOP Padrão") # Bônus: bom ter
    # --- FIM DA ADIÇÃO ---
    # ▼▼▼ ADICIONE ESTE CAMPO NOVO (Para Serviços) ▼▼▼
    codigo_servico = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        verbose_name="Cód. Serviço (LC116)",
        help_text="Ex: 17.06 para Propaganda, 1.03 para TI. Apenas números."
    )
    # ▲▲▲ FIM DA ADIÇÃO ▲▲▲
    class Meta:
        verbose_name = "Produto ou Serviço"
        verbose_name_plural = "Produtos e Serviços"
        # Isso diz ao banco: "A combinação de USUARIO + CODIGO deve ser única"
        # Ou seja, o Cliente A pode ter codigo 01, e o Cliente B também.
        constraints = [
            models.UniqueConstraint(fields=['user', 'codigo'], name='unique_codigo_per_user')
        ]

    def __str__(self):
        return f"{self.nome} (R$ {self.preco_venda})"

class Cliente(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    nome = models.CharField(max_length=200)
    cpf_cnpj = models.CharField(max_length=20, blank=True, null=True)
    telefone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True, null=True)
    endereco = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # --- ADICIONE ESTES CAMPOS FISCAIS ABAIXO ---
    razao_social = models.CharField(max_length=200, blank=True, null=True, verbose_name="Razão Social (se PJ)")
    inscricao_estadual = models.CharField(max_length=20, blank=True, null=True, verbose_name="Inscrição Estadual")
    
    # Endereço separado (obrigatório para a API)
    logradouro = models.CharField(max_length=200, blank=True, null=True, verbose_name="Logradouro (Rua, Av.)")
    numero = models.CharField(max_length=10, blank=True, null=True, verbose_name="Número")
    bairro = models.CharField(max_length=100, blank=True, null=True)
    cep = models.CharField(max_length=9, blank=True, null=True, verbose_name="CEP")
    cidade = models.CharField(max_length=100, blank=True, null=True) # Adicionando cidade
    uf = models.CharField(max_length=2, blank=True, null=True) # Adicionando UF
    codigo_municipio = models.CharField(max_length=7, blank=True, null=True, verbose_name="Cód. Município (IBGE)")
    # --- FIM DA ADIÇÃO ---
    INDICADOR_IE_CHOICES = (
        ('1', 'Contribuinte ICMS (Tem I.E.)'),
        ('2', 'Contribuinte Isento (Tem I.E. mas é isento)'),
        ('9', 'Não Contribuinte (Pessoa Física ou Prestador de Serviço)'),
    )
    indicador_inscricao_estadual = models.CharField(
        max_length=1, 
        choices=INDICADOR_IE_CHOICES, 
        default='9', 
        verbose_name="Indicador I.E."
    )

    def __str__(self):
        return self.nome

class Venda(models.Model):
    STATUS_CHOICES = (
        ('EM_ANDAMENTO', 'Em Andamento'),
        ('FINALIZADA', 'Finalizada'),
        ('CANCELADA', 'Cancelada'),
        ('SUBSTITUIDA', 'Substituída'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    vendedor = models.ForeignKey(Vendedor, on_delete=models.SET_NULL, null=True, blank=True)
    data_venda = models.DateTimeField(auto_now_add=True)
    valor_total_bruto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    desconto_geral = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_total_liquido = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='FINALIZADA')
    cidade = models.CharField(max_length=100, blank=False, null=False)
    estado = models.CharField(max_length=2, blank=False, null=False) # Para UFs como SP, RJ, MG
    endereco = models.CharField(max_length=255, blank=True, null=True)
    
    def __str__(self):
        return f"Venda #{self.id} - {self.cliente.nome} - R$ {self.valor_total_liquido}"

class ItemVenda(models.Model):
    venda = models.ForeignKey(Venda, related_name='itens', on_delete=models.CASCADE)
    produto = models.ForeignKey(ProdutoServico, on_delete=models.PROTECT)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    desconto_item = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    @property
    def subtotal(self):
        return (self.quantidade * self.preco_unitario) - self.desconto_item

    def __str__(self):
        return f"{self.produto.nome} (x{self.quantidade})"

class PagamentoVenda(models.Model):
    venda = models.ForeignKey(Venda, related_name='pagamentos', on_delete=models.CASCADE)
    forma_pagamento = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    parcelas = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.forma_pagamento} - R$ {self.valor}"
    
# Em accounts/models.py

from django.db.models import Q, UniqueConstraint # Adicione Q e UniqueConstraint às importações do Django

# ... (todos os seus outros modelos, como PagamentoVenda, ficam aqui) ...

# --- INÍCIO DO NOVO MODELO DE METAS ---
class MetaFaturamento(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Usuário")
    vendedor = models.ForeignKey(Vendedor, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Vendedor (Opcional)")
    mes_ano = models.DateField(verbose_name="Mês e Ano da Meta")
    valor_meta = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor da Meta")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Meta de Faturamento"
        verbose_name_plural = "Metas de Faturamento"
        ordering = ['-mes_ano', 'vendedor__nome']
        constraints = [
            # Garante que só exista uma meta geral da empresa por mês
            UniqueConstraint(fields=['user', 'mes_ano'], condition=Q(vendedor__isnull=True), name='unique_company_goal_per_month'),
            # Garante que cada vendedor só tenha uma meta por mês
            UniqueConstraint(fields=['user', 'vendedor', 'mes_ano'], name='unique_seller_goal_per_month')
        ]

    def __str__(self):
        target = self.vendedor.nome if self.vendedor else "Meta Geral da Empresa"
        return f"Meta de {target} para {self.mes_ano.strftime('%B/%Y')}: R$ {self.valor_meta}"
# --- FIM DO NOVO MODELO DE METAS ---    



class Subscription(models.Model):
    STATUS_CHOICES = [
        ('active', 'Ativa'),
        ('expired', 'Expirada'),
    ]

    # Liga a assinatura a um usuário. Cada usuário terá apenas uma.
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # Status da assinatura, que você vai mudar manualmente
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='expired')
    
    # Data até quando a assinatura é válida
    valid_until = models.DateField(null=True, blank=True)

    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='CLIENTE', verbose_name="Tipo de Conta")

    employee_limit = models.PositiveIntegerField(default=0, verbose_name="Limite de Funcionários Adicionais")

    # ▼▼▼ ADICIONE ESTAS DUAS LINHAS ▼▼▼
    has_financial_module = models.BooleanField(default=True, verbose_name="Possui Módulo Financeiro?")
    has_commercial_module = models.BooleanField(default=True, verbose_name="Possui Módulo Comercial?")
    # ▲▲▲ FIM DA ADIÇÃO ▲▲▲

    def __str__(self):
        return f"Assinatura de {self.user.username}"


class CompanyProfile(models.Model):
    """ Armazena os dados cadastrais da empresa dona da licença. """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='company_profile')
    nome_empresa = models.CharField(max_length=255, verbose_name="Nome da Empresa")
    nome_fantasia = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nome Fantasia")
    cnpj = models.CharField(max_length=18, blank=True, null=True, verbose_name="CNPJ")
    email_contato = models.EmailField(max_length=255, blank=True, null=True, verbose_name="E-mail de Contato")
    telefone_contato = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone de Contato")
    endereco = models.CharField(max_length=255, blank=True, null=True, verbose_name="Logradouro")
    numero = models.CharField(max_length=10, blank=True, null=True, verbose_name="Número")
    bairro = models.CharField(max_length=100, blank=True, null=True, verbose_name="Bairro")
    cidade = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cidade")
    estado = models.CharField(max_length=2, blank=True, null=True, verbose_name="Estado (UF)")
    cep = models.CharField(max_length=10, blank=True, null=True, verbose_name="CEP")
    # --- CAMPOS FISCAIS ADICIONADOS ---
    inscricao_municipal = models.CharField(max_length=20, blank=True, null=True, verbose_name="Inscrição Municipal")
    codigo_municipio = models.CharField(max_length=7, blank=True, null=True, verbose_name="Cód. Município (IBGE)", help_text="Ex: 3106200 para Belo Horizonte")
    inscricao_estadual = models.CharField(max_length=20, blank=True, null=True, verbose_name="Inscrição Estadual")
    # ----------------------------------
    updated_at = models.DateTimeField(auto_now=True)

    # --- CAMPOS DE CERTIFICADO DIGITAL ---
    certificado_digital = models.FileField(
        upload_to='certificados/', 
        null=True, 
        blank=True, 
        verbose_name="Certificado Digital (A1 .pfx)"
    )
    senha_certificado = models.CharField(
        max_length=100, 
        null=True, 
        blank=True, 
        verbose_name="Senha do Certificado"
    )    

    # ... campos existentes ...

    # --- CONFIGURAÇÕES FISCAIS ---
    REGIME_CHOICES = (
        ('1', 'Simples Nacional'),
        ('2', 'Simples Nacional (Excesso de Sublimite)'),
        ('3', 'Regime Normal (Lucro Presumido/Real)'),
        ('4', 'MEI (Microempreendedor Individual)'), # A Focus trata MEI de forma específica dependendo da cidade
    )
    
    regime_tributario = models.CharField(
        max_length=1, 
        choices=REGIME_CHOICES, 
        default='1',
        verbose_name="Regime Tributário"
    )

    # --- NOVO CAMPO PARA NFS-e ---
    REGIME_ESPECIAL_CHOICES = (
        ('0', 'Nenhum'),
        ('1', 'Microempresa Municipal'),
        ('2', 'Estimativa'),
        ('3', 'Sociedade de Profissionais'),
        ('4', 'Cooperativa'),
        ('5', 'MEI - Simples Nacional'),
        ('6', 'ME EPP - Simples Nacional'),
    )
    regime_especial_tributacao = models.CharField(
        max_length=1,
        choices=REGIME_ESPECIAL_CHOICES,
        default='0',
        blank=True, # Permite ficar vazio no formulário
        verbose_name="Regime Especial de Tributação (NFS-e)",
        help_text="Se ocorrer erro E327, verifique este campo. MEI geralmente usa '6 - ME EPP' ou '5 - MEI'. Consulte seu contador."
    )
    # -----------------------------
    
    aliquota_iss = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=2.00, 
        verbose_name="Alíquota ISS (%)",
        help_text="Alíquota padrão para serviços. Ex: 2.00 para 2%."
    )
    
    enviar_email_automatico = models.BooleanField(
        default=True, 
        verbose_name="Enviar e-mail automático para o cliente?"
    )

    incentivador_cultural = models.BooleanField(
        default=False,
        verbose_name="Incentivador Cultural?"
    )

    # --- CONFIGURAÇÃO DE EMISSÃO E LAYOUT ---
    arquivo_logo = models.FileField(
        upload_to='logos/', 
        blank=True, 
        null=True, 
        verbose_name="Logotipo da Empresa"
    )
    
    # NFe (Produto)
    proximo_numero_nfe = models.PositiveIntegerField(
        default=1, 
        verbose_name="Próximo Nº NFe (Produto)"
    )
    serie_nfe = models.CharField(
        max_length=3, 
        default='1', 
        verbose_name="Série NFe"
    )

    # NFS-e (Serviço)
    proximo_numero_nfse = models.PositiveIntegerField(
        default=1, 
        verbose_name="Próximo Nº NFS-e (Serviço)"
    )
    serie_nfse = models.CharField(
        max_length=5, 
        default='1', 
        verbose_name="Série NFS-e"
    )
    # ----------------------------------------

    @property
    def optante_simples_nacional(self):
        """
        Retorna True se o regime tributário for Simples Nacional (1, 2) ou MEI (4).
        Retorna False se for Regime Normal (3).
        """
        return self.regime_tributario in ['1', '2', '4']
    
    class Meta:
        verbose_name = "Perfil da Empresa"
        verbose_name_plural = "Perfis de Empresas"

    def __str__(self):
        return self.nome_empresa or self.user.username
    

   
    
    

class CompanyDocument(models.Model):
    """ Armazena documentos anexados pelo dono da licença. """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='company_documents')
    descricao = models.CharField(max_length=255, verbose_name="Descrição do Documento")
    arquivo = models.FileField(upload_to='company_documents/%Y/%m/%d/', verbose_name="Arquivo")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.descricao} - {self.user.username}"

    class Meta:
        verbose_name = "Documento da Empresa"
        verbose_name_plural = "Documentos da Empresa"
        ordering = ['-created_at']

# Adicione este código no final do arquivo accounts/models.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_subscription_for_new_user(sender, instance, created, **kwargs):
    if created:
        # Verifica se o usuário é funcionário de alguém
        is_employee = CompanyUserLink.objects.filter(employee=instance).exists()
        if not is_employee:
            Subscription.objects.create(user=instance, status='expired')
 


# Adicionar ao final de models.py

class Orcamento(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Usuário")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name="Categoria")
    mes_ano = models.DateField(verbose_name="Mês e Ano")
    valor_orcado = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor Orçado")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Orçamento"
        verbose_name_plural = "Orçamentos"
        ordering = ['-mes_ano', 'category__name']
        # Garante que só exista um valor orçado por usuário/categoria/mês
        constraints = [
            models.UniqueConstraint(fields=['user', 'category', 'mes_ano'], name='unique_budget_per_category_month')
        ]

    def __str__(self):
        return f"Orçamento de {self.category.name} para {self.mes_ano.strftime('%B/%Y')}: R$ {self.valor_orcado}"   


# Adicionar ao final de models.py

class Precificacao(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    produto = models.ForeignKey(ProdutoServico, on_delete=models.CASCADE)
    preco_custo = models.DecimalField(max_digits=10, decimal_places=2)
    perc_despesas_fixas = models.DecimalField(max_digits=5, decimal_places=2)
    perc_comissao = models.DecimalField(max_digits=5, decimal_places=2)
    perc_impostos = models.DecimalField(max_digits=5, decimal_places=2)
    perc_lucro = models.DecimalField(max_digits=5, decimal_places=2)
    preco_venda_sugerido = models.DecimalField(max_digits=10, decimal_places=2)
    is_price_updated = models.BooleanField(default=False, verbose_name="Preço Atualizado no Cadastro")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de Precificação"
        verbose_name_plural = "Registros de Precificação"
        ordering = ['-created_at']

    def __str__(self):
        return f"Precificação de {self.produto.name} em {self.created_at.strftime('%d/%m/%Y')}"         

# Adicionar ao final de models.py

class OrcamentoVenda(models.Model):
    STATUS_CHOICES = (
        ('PENDENTE', 'Pendente'),
        ('ACEITO', 'Aceito'),
        ('NEGADO', 'Negado'),
        ('CONVERTIDO', 'Convertido em Venda'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, verbose_name="Cliente")
    vendedor = models.ForeignKey(Vendedor, on_delete=models.SET_NULL, null=True, blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_validade = models.DateField(verbose_name="Validade da Proposta")
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDENTE')
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")

    class Meta:
        verbose_name = "Orçamento de Venda"
        verbose_name_plural = "Orçamentos de Venda"
        ordering = ['-data_criacao']

    def __str__(self):
        return f"Orçamento #{self.id} para {self.cliente.nome}"

class ItemOrcamento(models.Model):
    orcamento = models.ForeignKey(OrcamentoVenda, related_name='itens', on_delete=models.CASCADE)
    produto = models.ForeignKey(ProdutoServico, on_delete=models.PROTECT)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    
    @property
    def subtotal(self):
        return self.quantidade * self.preco_unitario

    def __str__(self):
        return f"{self.quantidade}x {self.produto.nome} no Orçamento #{self.orcamento.id}"
    

# Adicionar ao final de accounts/models.py

class Contract(models.Model):
    STATUS_CHOICES = (
        ('PENDENTE', 'Pendente'),
        ('ATIVO', 'Ativo'),
        ('CONCLUIDO', 'Concluído'),
        ('CANCELADO', 'Cancelado'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200, verbose_name="Título do Contrato")
    # Usa o seu modelo 'Cliente' já existente
    client = models.ForeignKey(Cliente, on_delete=models.PROTECT, verbose_name="Cliente") 
    start_date = models.DateField(verbose_name="Data de Início")
    end_date = models.DateField(verbose_name="Data de Término", null=True, blank=True)
    value = models.DecimalField(verbose_name="Valor do Contrato", max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE', verbose_name="Status")
    document = models.FileField(upload_to='contracts/%Y/%m/%d/', null=True, blank=True, verbose_name="Documento (PDF)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Contrato"
        verbose_name_plural = "Contratos"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.client.nome}"


class ContaAzulCredentials(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='contaazul_creds' # Adiciona um related_name
    )
    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"Credenciais Conta Azul de {self.user.username}"
    


# --- NOVO MODELO: ADICIONE AO FINAL DE models.py ---

from django.db.models import Q, UniqueConstraint # Garanta que Q e UniqueConstraint estão importados

class BPOClientLink(models.Model):
    """
    Este modelo liga um BPO Admin (usuário mestre) 
    aos usuários de seus Clientes Finais.
    """
    bpo_admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name='managed_clients', verbose_name="BPO Admin (Usuário Mestre)")
    client = models.OneToOneField(User, on_delete=models.CASCADE, related_name='managed_by_bpo', verbose_name="Cliente (Usuário Gerenciado)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Um BPO só pode adicionar um cliente uma vez
        unique_together = ('bpo_admin', 'client')
        # Um cliente só pode ser gerenciado por um BPO (OneToOne já garante isso)
        verbose_name = "Link BPO-Cliente"
        verbose_name_plural = "Links BPO-Cliente"

    def __str__(self):
        return f"{self.bpo_admin.username} gerencia {self.client.username}"

# --- FIM DO NOVO MODELO ---    


# Adicionar ao FINAL de models.py
class CompanyUserLink(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='employees', verbose_name="Dono da Licença")
    employee = models.OneToOneField(User, on_delete=models.CASCADE, related_name='company_owner_link', verbose_name="Funcionário")
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    # --- Permissões Módulo Financeiro ---
    can_access_home = models.BooleanField(default=True, verbose_name="Acesso à Home")
    can_access_contas_pagar = models.BooleanField(default=False, verbose_name="Acesso a Contas a Pagar")
    can_access_contas_receber = models.BooleanField(default=False, verbose_name="Acesso a Contas a Receber")
    can_access_tarefas = models.BooleanField(default=False, verbose_name="Acesso a Gestão de Tarefas")
    can_access_orcamento_anual = models.BooleanField(default=False, verbose_name="Acesso a Orçamento Anual")
    can_access_painel_financeiro = models.BooleanField(default=False, verbose_name="Acesso a Painel Financeiro (Dashboards)")
    can_access_fornecedores = models.BooleanField(default=False, verbose_name="Acesso a Fornecedores")
    can_access_clientes_financeiro = models.BooleanField(default=False, verbose_name="Acesso a Clientes (Financeiro)")
    
    # --- Permissões Módulo Comercial ---
    can_access_painel_vendas = models.BooleanField(default=False, verbose_name="Acesso a Painel de Vendas")
    can_access_notas_fiscais = models.BooleanField(default=False, verbose_name="Acesso a Notas Fiscais")
    can_access_orcamentos_venda = models.BooleanField(default=False, verbose_name="Acesso a Orçamentos")
    can_access_contratos = models.BooleanField(default=False, verbose_name="Acesso a Gestão de Contratos")
    can_access_cadastros_comercial = models.BooleanField(default=False, verbose_name="Acesso a Cadastros (Comercial)")
    can_access_vendas = models.BooleanField(default=False, verbose_name="Acesso a Vendas")
    can_access_metas_comerciais = models.BooleanField(default=False, verbose_name="Acesso a Gestão de Metas")
    can_access_precificacao = models.BooleanField(default=False, verbose_name="Acesso a Precificação")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('owner', 'employee') # Garante que um dono só adicione um funcionário uma vez
        verbose_name = "Vínculo Dono-Funcionário"
        verbose_name_plural = "Vínculos Dono-Funcionário"

    def __str__(self):
        status = "Ativo" if self.is_active else "Inativo"
        return f"{self.employee.username} (Funcionário de {self.owner.username}) - {status}"




from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings 


# Adicionar ao FINAL de accounts/models.py

class AnuncioGlobal(models.Model):
    """
    Modelo para armazenar anúncios globais que serão exibidos
    para todos os usuários logados.
    """
    titulo = models.CharField(max_length=100, verbose_name="Título (Opcional)", blank=True, null=True)
    mensagem = models.TextField(verbose_name="Mensagem do Anúncio")
    link_url = models.URLField(verbose_name="URL do Link (Opcional)", blank=True, null=True, help_text="Ex: /nova-feature/ ou https://site.com/promo")
    is_active = models.BooleanField(default=False, verbose_name="Está Ativo?", help_text="Apenas UM anúncio pode estar ativo por vez. O mais recente será exibido.")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")

    class Meta:
        verbose_name = "Anúncio Global"
        verbose_name_plural = "Anúncios Globais"
        ordering = ['-created_at'] # Ordena do mais novo para o mais antigo

    def __str__(self):
        return self.mensagem[:50] + "..." # Mostra os primeiros 50 caracteres



