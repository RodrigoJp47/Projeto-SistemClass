# accounts/context_processors.py

from .models import AnuncioGlobal
from .models import CompanyUserLink

def global_announcement(request):
    """
    Busca o anúncio global ativo mais recente e o injeta
    no contexto de TODOS os templates.
    """
    
    # Se o usuário não estiver logado, não retorna nada
    if not request.user.is_authenticated:
        return {}

    # Busca o primeiro anúncio que esteja marcado como "ativo"
    # e que seja o mais recente (graças ao 'ordering' no modelo)
    anuncio = AnuncioGlobal.objects.filter(is_active=True).first()
    
    return {
        'global_announcement': anuncio
    }

# 2. <-- ADICIONE TODA A FUNÇÃO ABAIXO -->
def employee_context(request):
    """
    Injeta o 'company_link' do funcionário (se existir) 
    em todos os templates.
    """
    
    # O middleware já definiu 'request.company_link'
    link = getattr(request, 'company_link', None)
    
    if link:
        # É um funcionário
        return {
            'is_employee': True,
            'employee_perms': link  # O objeto CompanyUserLink com todas as permissões
        }
    else:
        # É o dono da conta
        return {
            'is_employee': False,
            'employee_perms': None
        }