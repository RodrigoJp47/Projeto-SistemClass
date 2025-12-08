from django.db import models

# Create your models here.
# pdv/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone

class SessaoCaixa(models.Model):
    STATUS_CHOICES = (
        ('ABERTO', 'Aberto'),
        ('FECHADO', 'Fechado'),
    )

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    data_abertura = models.DateTimeField(auto_now_add=True)
    data_fechamento = models.DateTimeField(null=True, blank=True)
    saldo_inicial = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    saldo_final = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ABERTO')
    observacoes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Caixa {self.id} - {self.usuario} ({self.status})"

    def fechar(self, valor_final):
        self.saldo_final = valor_final
        self.data_fechamento = timezone.now()
        self.status = 'FECHADO'
        self.save()

class MovimentoCaixa(models.Model):
    TIPO_CHOICES = (
        ('SUPRIMENTO', 'Suprimento (Entrada)'),
        ('SANGRIA', 'Sangria (Saída)'),
        ('VENDA', 'Venda PDV'),
    )

    sessao = models.ForeignKey(SessaoCaixa, on_delete=models.CASCADE, related_name='movimentos')
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    descricao = models.CharField(max_length=255)
    data_movimento = models.DateTimeField(auto_now_add=True)
    
    # Opcional: Linkar com a Venda se o movimento for gerado por uma venda
    venda_origem = models.ForeignKey('accounts.Venda', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.get_tipo_display()} - R$ {self.valor}"