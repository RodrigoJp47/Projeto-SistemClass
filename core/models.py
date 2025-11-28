from django.db import models

class Empresa(models.Model):
    nome_empresa = models.CharField(max_length=100, verbose_name="Nome da Empresa")
    nome_proprietario = models.CharField(max_length=100, verbose_name="Nome do Proprietário")
    responsavel = models.CharField(max_length=100, verbose_name="Responsável pela Empresa")
    telefone = models.CharField(max_length=20, verbose_name="Telefone")
    email = models.EmailField(verbose_name="E-mail")

    def __str__(self):
        return self.nome_empresa

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"

class Quadro(models.Model):
    titulo = models.CharField(max_length=100, verbose_name="Título do Quadro")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='quadros')

    def __str__(self):
        return self.titulo

# Em core/models.py, substitua apenas a classe Cartao

class Cartao(models.Model):
    STATUS_CHOICES = [
        ('fixo', 'Informações Fixas'),
        ('fazer', 'A Fazer'),
        ('andamento', 'Em Andamento'),
        ('concluido', 'Concluído'),
    ]

    titulo = models.CharField(max_length=200, verbose_name="Título do Cartão")
    descricao = models.TextField(verbose_name="Descrição", blank=True, null=True)
    quadro = models.ForeignKey(Quadro, on_delete=models.CASCADE, related_name='cartoes')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='fazer',
        verbose_name="Status"
    )
    # NOVO CAMPO PARA O ANEXO
    anexo = models.FileField(
        upload_to='anexos/',  # Salva os arquivos na pasta media/anexos/
        blank=True,           # O campo é opcional
        null=True,            # Permite que o campo seja nulo no banco de dados
        verbose_name="Anexo (PDF, Imagem, etc.)"
    )

    def __str__(self):
        return self.titulo
    



# Em core/models.py, adicione esta nova classe no final do arquivo

class ChecklistItem(models.Model):
    TIPO_CHOICES = [
        ('agendamento', 'Agendamento'),
        ('pendencia', 'Pendência'),
    ]
    
    quadro = models.ForeignKey(Quadro, on_delete=models.CASCADE, related_name='checklist_items')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo")
    titulo = models.CharField(max_length=255, verbose_name="Título")
    concluido = models.BooleanField(default=False, verbose_name="Concluído")
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titulo
    
    class Meta:
        ordering = ['concluido', 'data_criacao'] # Garante que os concluídos fiquem por último

