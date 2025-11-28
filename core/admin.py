from django.contrib import admin
from .models import Empresa, Quadro, Cartao, ChecklistItem

# Register your models here.

# A linha abaixo "registra" seu modelo Empresa na área de administração
admin.site.register(Empresa)
admin.site.register(Quadro)   # 2. Registre o Quadro
admin.site.register(Cartao)  # 3. Registre o Cartao
admin.site.register(ChecklistItem)