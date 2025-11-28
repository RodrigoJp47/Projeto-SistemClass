from django.db import models
from django.conf import settings
from accounts.models import Cliente, Venda

class NotaFiscal(models.Model):
    STATUS_CHOICES = (
        ('PENDENTE', 'Pendente'),
        ('PROCESSANDO', 'Processando'), # Adicionado status Processando
        ('EMITIDA', 'Emitida'),
        ('CANCELADA', 'Cancelada'),
        ('ERRO', 'Erro de Emissão'),
    )
    MODELO_CHOICES = (
        ('NFE', 'Produto (NF-e)'),
        ('NFSE', 'Serviço (NFS-e)'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Usuário da Licença")
    venda = models.OneToOneField(Venda, on_delete=models.SET_NULL, null=True, blank=True, related_name="nota_fiscal")
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, verbose_name="Cliente")
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDENTE')
    
    # --- ESTE ERA O CAMPO QUE FALTAVA PARA O ERRO ATUAL ---
    ref_id = models.CharField(max_length=100, verbose_name="ID de Referência (API)", null=True, blank=True, db_index=True)
    modelo = models.CharField(max_length=10, choices=MODELO_CHOICES, default='NFE')
    numero_nf = models.CharField(max_length=20, verbose_name="Número da NF-e", null=True, blank=True)
    serie = models.CharField(max_length=5, verbose_name="Série", null=True, blank=True)
    chave_acesso = models.CharField(max_length=44, verbose_name="Chave de Acesso", null=True, blank=True, db_index=True)
    
    valor_total = models.DecimalField(max_digits=12, decimal_places=2)
    data_emissao = models.DateTimeField(verbose_name="Data de Emissão", null=True, blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    
    # --- ESTES SÃO OS CAMPOS CORRIGIDOS PARA A API (URLs em vez de Arquivos) ---
    url_xml = models.URLField(max_length=500, null=True, blank=True, verbose_name="URL do XML")
    url_pdf = models.URLField(max_length=500, null=True, blank=True, verbose_name="URL do DANFE (PDF)")
    
    mensagem_erro = models.TextField(verbose_name="Mensagem de Erro/Retorno", null=True, blank=True)

    class Meta:
        verbose_name = "Nota Fiscal"
        verbose_name_plural = "Notas Fiscais"
        ordering = ['-data_criacao']

    def __str__(self):
        return f"NF-e {self.numero_nf or self.id} - {self.cliente.nome}"