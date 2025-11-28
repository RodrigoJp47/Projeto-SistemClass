
from django.contrib import admin
from .models import NotaFiscal

@admin.register(NotaFiscal)
class NotaFiscalAdmin(admin.ModelAdmin):
    list_display = ('id', 'numero_nf', 'cliente', 'status', 'valor_total', 'data_emissao', 'user')
    list_filter = ('status', 'data_emissao', 'user')
    search_fields = ('numero_nf', 'chave_acesso', 'cliente__nome', 'user__username')
    autocomplete_fields = ('user', 'venda', 'cliente') # Facilita a busca
    readonly_fields = ('data_criacao',)
