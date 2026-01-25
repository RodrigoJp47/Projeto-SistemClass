

from django.shortcuts import redirect
from django.contrib import messages
from .models import Subscription, CompanyUserLink
from django.utils import timezone
from functools import wraps

def subscription_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # 1. Autenticação básica
        if not request.user.is_authenticated:
            return redirect('login')

        # 2. Superusuário sempre passa
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        subscription_to_check = None

        # --- CORREÇÃO CRÍTICA AQUI ---
        # Não buscamos no banco novamente usando request.user, pois o Middleware 
        # pode ter trocado o request.user pelo Dono.
        # Confiamos no 'company_link' que o Middleware já preparou.
        
        link = getattr(request, 'company_link', None)

        if link:
            # É UM FUNCIONÁRIO (O link veio do middleware)
            subscription_to_check = link.owner.subscription
        else:
            # É O DONO (Ou o middleware não achou link, então é o próprio user)
            if hasattr(request.user, 'subscription'):
                subscription_to_check = request.user.subscription

        # 4. Se não achou assinatura nenhuma, erro.
        if not subscription_to_check:
            messages.error(request, 'Nenhuma assinatura encontrada.')
            return redirect('login')

        # === LÓGICA DE STATUS (Mantida igual) ===
        raw_status = str(subscription_to_check.status).strip().lower()
        valid_until = subscription_to_check.valid_until
        today = timezone.now().date()

        status_ativos = ['active', 'ativo', 'ativa', 'actived']
        status_trial = ['trial', 'em teste grátis', 'teste', 'test']

        if raw_status in status_ativos:
            # CORREÇÃO: Verifica a data mesmo se o status estiver "Ativo"
            if valid_until and valid_until < today:
                messages.error(request, f'Sua assinatura venceu em {valid_until.strftime("%d/%m/%Y")}. Renove para continuar.')
                return redirect('assinatura')
            pass 
        elif raw_status in status_trial:
            if valid_until and valid_until >= today:
                pass 
            else:
                messages.warning(request, 'Seu período de teste acabou.')
                return redirect('assinatura')
        elif raw_status == 'past_due':
             messages.warning(request, 'Há um pagamento pendente.')
             pass
        else:
            messages.error(request, 'Sua assinatura não está ativa.')
            return redirect('assinatura')

        # Salva a assinatura ativa no request para uso posterior
        request.active_subscription = subscription_to_check
        
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def check_employee_permission(permission_field_name):
    """
    Verifica se um funcionário tem permissão.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            # Pega o link que o Middleware (ou o decorator anterior) garantiu
            link = getattr(request, 'company_link', None)
            
            # Se link é None, é o DONO -> Acesso Total -> Passa direto
            if link is None:
                return view_func(request, *args, **kwargs)

            # É FUNCIONÁRIO -> Verifica a permissão específica
            if hasattr(link, permission_field_name) and getattr(link, permission_field_name) is True:
                return view_func(request, *args, **kwargs) # Permite
            else:
                # NEGA O ACESSO
                messages.error(request, 'Acesso negado: Você não tem permissão para esta área.')
                
                # Redirecionamento inteligente
                if permission_field_name == 'can_access_home':
                    return redirect('logout') # Se não pode ver a home, tchau
                else:
                    return redirect('smart_redirect') # Volta para a home segura

        return _wrapped_view
    return decorator


def owner_required(view_func):
    """
    Garante que APENAS o Dono da Licença acesse. Funcionários são barrados.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        # Verifica se é funcionário pelo link do middleware
        link = getattr(request, 'company_link', None)
        
        if link:
            messages.error(request, 'Acesso restrito ao administrador da conta.')
            return redirect('smart_redirect')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def module_access_required(module_name):
    """
    Verifica se a empresa contratou o módulo específico.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # 1. Libera Superusuário
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # 2. Busca a assinatura (Tenta no request, no link ou no user)
            subscription = getattr(request, 'active_subscription', None)
            if not subscription:
                link = getattr(request, 'company_link', None)
                if link:
                    subscription = link.owner.subscription
                elif hasattr(request.user, 'subscription'):
                    subscription = request.user.subscription
            
            if not subscription:
                 return redirect('login')

            # === AQUI ESTÁ A ATUALIZAÇÃO ===
            
            # Nível 1: Financeiro
            if module_name == 'financial':
                if subscription.has_financial_module:
                    return view_func(request, *args, **kwargs)
            
            # Nível 2: Comercial (Quem tem Fiscal TAMBÉM tem Comercial)
            elif module_name == 'commercial':
                if subscription.has_commercial_module:
                    return view_func(request, *args, **kwargs)

            # Nível 3: Fiscal (Exclusivo do Plano Elite R$ 249)
            elif module_name == 'fiscal':
                if subscription.has_fiscal_module:
                    return view_func(request, *args, **kwargs)
                else:
                    messages.error(request, 'Atualize para o plano Elite Fiscal para emitir Notas Fiscais.')
                    return redirect('assinatura')
            
            # ===============================

            # Se chegou aqui, não tem permissão
            messages.error(request, f'Sua licença não inclui o acesso a {module_name}.')
            return redirect('home')

        return _wrapped_view
    return decorator