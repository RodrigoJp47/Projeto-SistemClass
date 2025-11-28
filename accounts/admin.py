

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
# ADICIONADO BPOClientLink e User/BaseUserAdmin
from .models import Subscription, BPOClientLink, AnuncioGlobal 

from .models import Category, PayableAccount, ReceivableAccount, BankAccount, Cliente, Venda, Vendedor, ProdutoServico, CompanyProfile
from .models import ContaAzulCredentials
# -----------------------------------------------------------------
# NOVO: Mostra a Assinatura (e o Tipo de Conta) direto no User
# -----------------------------------------------------------------
class SubscriptionInline(admin.StackedInline):
    model = Subscription
    can_delete = False
    verbose_name_plural = 'Assinatura / Tipo de Conta'

class CustomUserAdmin(BaseUserAdmin):
    inlines = (SubscriptionInline,)

# Tenta desregistrar o User padrão e registrar o novo
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, CustomUserAdmin)



# -----------------------------------------------------------------
# NOVO: Registra o modelo BPOClientLink
# -----------------------------------------------------------------
@admin.register(BPOClientLink)
class BPOClientLinkAdmin(admin.ModelAdmin):
    list_display = ('bpo_admin', 'client', 'created_at')
    list_filter = ('bpo_admin',)
    search_fields = ('bpo_admin__username', 'client__username')
    # Autocomplete facilita muito para achar os usuários
    autocomplete_fields = ['bpo_admin', 'client']

# -----------------------------------------------------------------
# SEU CÓDIGO (MELHORADO): Registra a Subscription 
# -----------------------------------------------------------------
@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    # Campos que aparecerão na lista de assinaturas
    list_display = ('user', 'user_type', 'status', 'valid_until', 'has_financial_module', 'has_commercial_module') # <-- ADICIONADO
    
    # Campos que você poderá editar diretamente na lista!
    list_editable = ('user_type', 'status', 'valid_until', 'has_financial_module', 'has_commercial_module') # <-- ADICIONADO
    
    # Filtro rápido na lateral direita
    list_filter = ('user_type', 'status', 'has_financial_module', 'has_commercial_module') # <-- ADICIONADO
    
    # Barra de pesquisa (igual ao seu)
    search_fields = ('user__username', 'user__email')
    
    # Autocomplete para o campo 'user' (opcional, mas recomendado)
    autocomplete_fields = ['user']



admin.site.register(Category)
admin.site.register(PayableAccount)
admin.site.register(ReceivableAccount)
admin.site.register(BankAccount)    

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cpf_cnpj', 'email', 'telefone', 'user')
    # O search_fields é o que faz o autocomplete funcionar
    search_fields = ('nome', 'cpf_cnpj', 'email')
    list_filter = ('user',)

@admin.register(Venda)
class VendaAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'vendedor', 'data_venda', 'valor_total_liquido', 'status', 'user')
    # O search_fields é o que faz o autocomplete funcionar
    search_fields = ('id', 'cliente__nome') 
    list_filter = ('status', 'data_venda', 'user')
    autocomplete_fields = ('cliente', 'vendedor') # Boa prática aqui também


@admin.register(Vendedor)
class VendedorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'email', 'comissao_percentual', 'user')
    # Este search_fields é o que permite ao VendaAdmin fazer o autocomplete
    search_fields = ('nome', 'email')
    list_filter = ('user',)


@admin.register(ContaAzulCredentials)
class ContaAzulCredentialsAdmin(admin.ModelAdmin):
    # Campos que aparecerão na lista de credenciais
    list_display = ('get_username', 'expires_at')
    # Permite pesquisar pelo nome ou email do utilizador
    search_fields = ('user__username', 'user__email')
    # Adiciona um link para a página de edição do utilizador
    readonly_fields = ('user_link',)

    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Utilizador (Cliente)'

    def user_link(self, obj):
        from django.utils.html import format_html
        from django.urls import reverse
        link = reverse("admin:auth_user_change", args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', link, obj.user.username)
    user_link.short_description = "Link do Utilizador"




# Adicionar ao FINAL de accounts/admin.py

@admin.register(AnuncioGlobal)
class AnuncioGlobalAdmin(admin.ModelAdmin):
    list_display = ('mensagem', 'is_active', 'created_at', 'link_url')
    list_editable = ('is_active',)
    list_filter = ('is_active',)
    search_fields = ('titulo', 'mensagem')
    readonly_fields = ('created_at',)

# accounts/admin.py

# ... (cole isto no final do arquivo)

@admin.register(ProdutoServico)
class ProdutoServicoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'preco_venda', 'ncm', 'estoque_atual', 'user')
    search_fields = ('nome', 'codigo', 'ncm')
    list_filter = ('tipo', 'user')

    # Isso organiza o formulário de edição para você
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('user', 'nome', 'codigo', 'tipo', 'descricao')
        }),
        ('Valores e Estoque', {
            'fields': ('preco_venda', 'preco_custo', 'estoque_atual')
        }),
        ('Dados Fiscais (Obrigatório para NF-e)', {
            'fields': ('ncm', 'unidade_medida', 'origem', 'cfop_padrao')
        }),
    )




@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'nome_empresa', 'cnpj', 'email_contato')
    search_fields = ('user__username', 'nome_empresa', 'cnpj')    





    
