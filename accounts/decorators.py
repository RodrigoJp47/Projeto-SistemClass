# Em accounts/decorators.py
# SUBSTITUA SUA FUNÇÃO INTEIRA POR ESTA:

from django.shortcuts import redirect
from django.contrib import messages
from .models import Subscription, CompanyUserLink
from django.utils import timezone
from functools import wraps
from django.contrib.auth.models import User # Adicione esta importação se faltar

def subscription_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # 1. Verifica se o usuário está autenticado
        if not request.user.is_authenticated:
            return redirect('login')

        # 2. Permite acesso de superusuário
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        # Flag e variável para armazenar a assinatura
        is_employee_user = False
        subscription_to_check = None

        # 3. Lógica principal: Descobrir qual assinatura verificar
        try:
            # Tenta encontrar um vínculo de funcionário
            link = CompanyUserLink.objects.select_related('owner__subscription').get(employee=request.user, is_active=True)
            # Se encontrou, a assinatura a ser verificada é a do DONO
            subscription_to_check = link.owner.subscription
            is_employee_user = True
            
        except CompanyUserLink.DoesNotExist:
            # Não é um funcionário, então verifica a assinatura PRÓPRIA
            is_employee_user = False
            try:
                subscription_to_check = request.user.subscription
            except Subscription.DoesNotExist:
                # É um usuário normal (não-funcionário) SEM assinatura.
                # Esta é a situação que o get_or_create estava "corrigindo" errado.
                messages.error(request, 'Assinatura não encontrada. Por favor, contate o suporte.')
                return redirect('assinatura')
                
        except Subscription.DoesNotExist:
            # É um funcionário (is_employee_user=True), mas o DONO não tem uma assinatura.
            messages.error(request, 'A assinatura principal (do dono) desta conta não foi encontrada.')
            return redirect('assinatura')
        except Exception as e:
            # Captura outros erros inesperados (ex: related object 'subscription' não existe)
            messages.error(request, f'Ocorreu um erro ao verificar seu vínculo de funcionário: {e}')
            return redirect('login')


        # 4. Agora que temos a 'subscription_to_check', validamos ela
        is_active = (
            subscription_to_check.status == 'active' and
            subscription_to_check.valid_until and
            subscription_to_check.valid_until >= timezone.now().date()
        )

        if is_active:
            # Injeta a assinatura válida no request para a view usar
            request.active_subscription = subscription_to_check
            return view_func(request, *args, **kwargs)
        else:
            # Assinatura (do dono ou própria) está expirada ou inativa
            if is_employee_user:
                messages.warning(request, 'A assinatura principal desta conta expirou ou não está ativa. Peça ao administrador para verificar.')
            else:
                messages.warning(request, 'Sua assinatura expirou ou não está ativa. Por favor, renove para continuar.')
            return redirect('assinatura')

    return _wrapped_view


# ▼▼▼ SUBSTITUA A FUNÇÃO 'check_employee_permission' PELA VERSÃO CORRIGIDA ▼▼▼
def check_employee_permission(permission_field_name):
    """
    Verifica se um funcionário ('request.company_link') tem uma permissão.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):

            if not request.user.is_authenticated:
                return redirect('login')

            # 1. Se não for funcionário (link é None), é o dono. Acesso liberado.
            if request.company_link is None:
                return view_func(request, *args, **kwargs)

            # 2. É um funcionário. Pegamos o link (sem DB hit, já veio do middleware)
            link = request.company_link

            # 3. Lógica de verificação
            if hasattr(link, permission_field_name) and getattr(link, permission_field_name) is True:
                return view_func(request, *args, **kwargs) # Permite
            else:
                # Nega o acesso
                messages.error(request, 'Você não tem permissão para acessar esta página.')

                # Se for barrado da 'home', desloga (evita loop)
                if permission_field_name == 'can_access_home':
                    messages.warning(request, 'Sua conta não tem permissão para a página principal. Fale com o administrador.')
                    return redirect('logout')
                else:
                    # Se for barrado de qualquer outra página, manda para o smart_redirect
                    return redirect('smart_redirect')

        return _wrapped_view
    return decorator


def owner_required(view_func):
    """
    Garante que APENAS o Dono da Licença (não-funcionário) acesse a view.
    (Verifica 'request.company_link' do middleware)
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        # Se company_link NÃO for None, significa que é um funcionário
        if request.company_link:
            messages.error(request, 'Acesso restrito. Esta página é acessível apenas pelo administrador da conta.')
            # Manda para o único lugar seguro: o redirecionador
            return redirect('smart_redirect')

        # Se company_link for None, é o dono. Permite o acesso.
        return view_func(request, *args, **kwargs)

    return _wrapped_view


# Em accounts/decorators.py (No final do arquivo)

def module_access_required(module_name):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            
            # 1. Superusuário tem acesso total (CORREÇÃO DE SEGURANÇA)
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # 2. Verifica se a assinatura ativa existe
            if not hasattr(request, 'active_subscription'):
                messages.error(request, 'Sessão inválida ou assinatura não verificada.')
                return redirect('login')
                
            subscription = request.active_subscription

            # 3. Verifica o módulo financeiro
            if module_name == 'financial':
                if subscription.has_financial_module:
                    return view_func(request, *args, **kwargs)
                else:
                    messages.error(request, 'Sua licença não inclui o Módulo Financeiro.')
                    return redirect('home')
            
            # 4. Verifica o módulo comercial
            elif module_name == 'commercial':
                if subscription.has_commercial_module:
                    return view_func(request, *args, **kwargs)
                else:
                    messages.error(request, 'Sua licença não inclui o Módulo Comercial.')
                    return redirect('home')

            return view_func(request, *args, **kwargs)

        return _wrapped_view
    return decorator