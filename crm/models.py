from django.db import models
from django.conf import settings
from django.utils import timezone

# IMPORTAÇÃO CORRIGIDA: Trocamos 'Produto' por 'ProdutoServico'
from accounts.models import Cliente, Vendedor, OrcamentoVenda, ProdutoServico

class FunilEtapa(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nome = models.CharField(max_length=50)
    ordem = models.PositiveIntegerField(default=0)
    cor_hexa = models.CharField(max_length=7, default="#3498db", help_text="Cor da barra lateral do card")

    class Meta:
        ordering = ['ordem']
        verbose_name = "Etapa do Funil"
        verbose_name_plural = "Etapas do Funil"

    def __str__(self):
        return f"{self.ordem} - {self.nome}"


class OrigemLead(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nome = models.CharField(max_length=50)

    def __str__(self):
        return self.nome


class Oportunidade(models.Model):
    PRIORIDADE_CHOICES = [
        ('BAIXA', 'Baixa'),
        ('MEDIA', 'Média'),
        ('ALTA', 'Alta'),
        ('URGENTE', 'Urgente'),
    ]
    
    STATUS_CHOICES = [
        ('ABERTO', 'Em Aberto'),
        ('GANHO', 'Ganho (Venda Fechada)'),
        ('PERDIDO', 'Perdido'),
        ('CONGELADO', 'Congelado/Stand-by'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    titulo = models.CharField(max_length=150, verbose_name="Título da Oportunidade", help_text="Ex: Compra de 10 Pneus")
    
    # RELACIONAMENTOS COM O APP ACCOUNTS
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='oportunidades_crm')
    vendedor = models.ForeignKey(Vendedor, on_delete=models.SET_NULL, null=True, blank=True, related_name='oportunidades_crm')
    
    # Link opcional: se essa oportunidade virou um orçamento formal
    orcamento_gerado = models.OneToOneField(OrcamentoVenda, on_delete=models.SET_NULL, null=True, blank=True, related_name='oportunidade_origem')

    # DADOS DO CRM
    etapa = models.ForeignKey(FunilEtapa, on_delete=models.PROTECT, related_name='oportunidades')
    origem = models.ForeignKey(OrigemLead, on_delete=models.SET_NULL, null=True, blank=True)
    
    valor_estimado = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    data_fechamento_estimada = models.DateField(null=True, blank=True)
    probabilidade = models.PositiveIntegerField(default=50, help_text="Em % (0 a 100)")
    
    prioridade = models.CharField(max_length=20, choices=PRIORIDADE_CHOICES, default='MEDIA')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ABERTO')
    
    motivo_perda = models.TextField(blank=True, null=True)

    # CORREÇÃO AQUI: Agora usando 'ProdutoServico'
    produtos_interesse = models.ManyToManyField(ProdutoServico, blank=True, related_name='interessados_crm')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.titulo} - {self.cliente.nome}"


class Interacao(models.Model):
    """
    Histórico de interações (Timeline)
    """
    TIPO_CHOICES = [
        ('NOTA', 'Anotação'),
        ('LIGACAO', 'Ligação'),
        ('WHATSAPP', 'WhatsApp'),
        ('EMAIL', 'E-mail'),
        ('REUNIAO', 'Reunião'),
        ('TAREFA', 'Tarefa Concluída'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    oportunidade = models.ForeignKey(Oportunidade, on_delete=models.CASCADE, related_name='interacoes')
    
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='NOTA')
    descricao = models.TextField(verbose_name="Resumo da interação")
    data_interacao = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.get_tipo_display()} em {self.data_interacao.strftime('%d/%m/%Y')}"