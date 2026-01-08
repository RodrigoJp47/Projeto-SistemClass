# # Em accounts/decorators.py
# # SUBSTITUA SUA FUNÇÃO INTEIRA POR ESTA:

# from django.shortcuts import redirect
# from django.contrib import messages
# from .models import Subscription, CompanyUserLink
# from django.utils import timezone
# from functools import wraps
# from django.contrib.auth.models import User # Adicione esta importação se faltar

# def subscription_required(view_func):
#     @wraps(view_func)
#     def _wrapped_view(request, *args, **kwargs):
#         # 1. Autenticação básica
#         if not request.user.is_authenticated:
#             return redirect('login')

#         # 2. Superusuário sempre passa
#         if request.user.is_superuser:
#             return view_func(request, *args, **kwargs)

#         subscription_to_check = None

#         # 3. Identifica de quem é a assinatura (Lógica para Funcionários)
#         try:
#             # Tenta achar link de funcionário
#             link = CompanyUserLink.objects.select_related('owner__subscription').get(employee=request.user, is_active=True)
#             subscription_to_check = link.owner.subscription
#         except CompanyUserLink.DoesNotExist:
#             # Se não é funcionário, verifica a própria assinatura
#             if hasattr(request, 'subscription'):
#                 subscription_to_check = request.user.subscription

#         # 4. Se não achou assinatura nenhuma, erro crítico
#         if not subscription_to_check:
#             messages.error(request, 'Nenhuma assinatura encontrada.')
#             return redirect('login')

#         # === LÓGICA DE BLOQUEIO / TRIAL ===
        
#         status = subscription_to_check.status
#         valid_until = subscription_to_check.valid_until
#         today = timezone.now().date()

#         # CASO A: Assinatura Ativa (Pagante)
#         if str(status).lower() in ['active', 'ativo', 'ativa']:
#             # Opcional: Se quiser checar validade mesmo para ativos (caso o webhook falhe)
#             # if valid_until and valid_until < today:
#             #     messages.error(request, 'Sua assinatura expirou. Renove para continuar.')
#             #     return redirect('assinatura')
#             pass # Acesso Liberado

#         # CASO B: Período de Teste (Trial)
#         elif status == 'trial':
#             if valid_until and valid_until >= today:
#                 # AINDA ESTÁ NO PRAZO -> Acesso Liberado
#                 pass 
#             else:
#                 # PRAZO ACABOU -> Bloqueio
#                 messages.warning(request, 'Seu período de teste de 7 dias acabou. Escolha um plano para continuar.')
#                 return redirect('assinatura') # Manda para a tela de planos
        
#         # CASO C: Pagamento Pendente (Past Due) - Geralmente damos uma colher de chá ou bloqueamos
#         elif status == 'past_due':
#              messages.warning(request, 'Há um pagamento pendente. Regularize para evitar bloqueio.')
#              # return redirect('assinatura') # Descomente se quiser bloquear direto
#              pass

#         # CASO D: Cancelada ou Expirada
#         else:
#             messages.error(request, 'Sua assinatura não está ativa.')
#             return redirect('assinatura')

#         # Se passou pelas verificações acima, armazena na request para uso nas views e libera
#         request.active_subscription = subscription_to_check
#         return view_func(request, *args, **kwargs)

#     return _wrapped_view


# # ▼▼▼ SUBSTITUA A FUNÇÃO 'check_employee_permission' PELA VERSÃO CORRIGIDA ▼▼▼
# def check_employee_permission(permission_field_name):
#     """
#     Verifica se um funcionário ('request.company_link') tem uma permissão.
#     """
#     def decorator(view_func):
#         @wraps(view_func)
#         def _wrapped_view(request, *args, **kwargs):

#             if not request.user.is_authenticated:
#                 return redirect('login')

#             # 1. Se não for funcionário (link é None), é o dono. Acesso liberado.
#             if request.company_link is None:
#                 return view_func(request, *args, **kwargs)

#             # 2. É um funcionário. Pegamos o link (sem DB hit, já veio do middleware)
#             link = request.company_link

#             # 3. Lógica de verificação
#             if hasattr(link, permission_field_name) and getattr(link, permission_field_name) is True:
#                 return view_func(request, *args, **kwargs) # Permite
#             else:
#                 # Nega o acesso
#                 messages.error(request, 'Você não tem permissão para acessar esta página.')

#                 # Se for barrado da 'home', desloga (evita loop)
#                 if permission_field_name == 'can_access_home':
#                     messages.warning(request, 'Sua conta não tem permissão para a página principal. Fale com o administrador.')
#                     return redirect('logout')
#                 else:
#                     # Se for barrado de qualquer outra página, manda para o smart_redirect
#                     return redirect('smart_redirect')

#         return _wrapped_view
#     return decorator


# def owner_required(view_func):
#     """
#     Garante que APENAS o Dono da Licença (não-funcionário) acesse a view.
#     (Verifica 'request.company_link' do middleware)
#     """
#     @wraps(view_func)
#     def _wrapped_view(request, *args, **kwargs):
#         if not request.user.is_authenticated:
#             return redirect('login')

#         # Se company_link NÃO for None, significa que é um funcionário
#         if request.company_link:
#             messages.error(request, 'Acesso restrito. Esta página é acessível apenas pelo administrador da conta.')
#             # Manda para o único lugar seguro: o redirecionador
#             return redirect('smart_redirect')

#         # Se company_link for None, é o dono. Permite o acesso.
#         return view_func(request, *args, **kwargs)

#     return _wrapped_view


# # Em accounts/decorators.py (No final do arquivo)

# def module_access_required(module_name):
#     def decorator(view_func):
#         @wraps(view_func)
#         def _wrapped_view(request, *args, **kwargs):
            
#             # 1. Superusuário tem acesso total (CORREÇÃO DE SEGURANÇA)
#             if request.user.is_superuser:
#                 return view_func(request, *args, **kwargs)

#             # 2. Verifica se a assinatura ativa existe
#             if not hasattr(request, 'active_subscription'):
#                 messages.error(request, 'Sessão inválida ou assinatura não verificada.')
#                 return redirect('login')
                
#             subscription = request.active_subscription

#             # 3. Verifica o módulo financeiro
#             if module_name == 'financial':
#                 if subscription.has_financial_module:
#                     return view_func(request, *args, **kwargs)
#                 else:
#                     messages.error(request, 'Sua licença não inclui o Módulo Financeiro.')
#                     return redirect('home')
            
#             # 4. Verifica o módulo comercial
#             elif module_name == 'commercial':
#                 if subscription.has_commercial_module:
#                     return view_func(request, *args, **kwargs)
#                 else:
#                     messages.error(request, 'Sua licença não inclui o Módulo Comercial.')
#                     return redirect('home')

#             return view_func(request, *args, **kwargs)

#         return _wrapped_view
#     return decorator

from django.shortcuts import redirect
from django.contrib import messages
from .models import Subscription, CompanyUserLink
from django.utils import timezone
from functools import wraps
from django.contrib.auth.models import User

def subscription_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # 1. Autenticação básica
        if not request.user.is_authenticated:
            return redirect('login')

        # 2. Superusuário sempre passa (Admin geral)
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        subscription_to_check = None

        # 3. Identifica de quem é a assinatura (Lógica para Funcionários)
        try:
            # Tenta achar link de funcionário ativo
            link = CompanyUserLink.objects.select_related('owner__subscription').get(employee=request.user, is_active=True)
            subscription_to_check = link.owner.subscription
            # Salva o link no request para usar nos outros decorators
            request.company_link = link 
        except CompanyUserLink.DoesNotExist:
            # Se não é funcionário, verifica a própria assinatura (Dono)
            request.company_link = None # Marca como dono
            if hasattr(request.user, 'subscription'):
                subscription_to_check = request.user.subscription

        # 4. Se não achou assinatura nenhuma (nem dono, nem funcionário), erro.
        if not subscription_to_check:
            messages.error(request, 'Nenhuma assinatura encontrada para este usuário.')
            return redirect('login')

        # === LÓGICA DE BLOQUEIO / TRIAL (CORREÇÃO DE STATUS) ===
        
        # Normaliza o status para garantir que funcione com 'Ativa', 'active', 'Active', 'trial', etc.
        raw_status = str(subscription_to_check.status).strip().lower()
        valid_until = subscription_to_check.valid_until
        today = timezone.now().date()

        # Lista de termos aceitos para CONTA ATIVA
        status_ativos = ['active', 'ativo', 'ativa', 'actived']
        
        # Lista de termos aceitos para TRIAL
        status_trial = ['trial', 'em teste grátis', 'teste', 'test']

        # CASO A: Assinatura Ativa (Pagante)
        if raw_status in status_ativos:
            # Usuário pagante entra sempre (independente da data valid_until, 
            # pois o webhook cuida do cancelamento se parar de pagar)
            pass 

        # CASO B: Período de Teste (Trial)
        elif raw_status in status_trial:
            # No trial, a data é MANDATÓRIA.
            if valid_until and valid_until >= today:
                # AINDA ESTÁ NO PRAZO -> Acesso Liberado
                pass 
            else:
                # PRAZO ACABOU -> Bloqueio
                messages.warning(request, 'Seu período de teste de 7 dias acabou. Assine um plano para continuar.')
                return redirect('assinatura') # Manda para a tela de planos
        
        # CASO C: Pagamento Pendente (Past Due)
        elif raw_status == 'past_due':
             messages.warning(request, 'Há um pagamento pendente. Regularize para evitar o bloqueio total.')
             # Deixamos passar, mas com aviso. Se quiser bloquear, mude para redirect('assinatura')
             pass

        # CASO D: Cancelada ou Expirada
        else:
            # Se caiu aqui, o status é 'canceled', 'expired' ou algo desconhecido
            messages.error(request, 'Sua assinatura não está ativa. Status atual: ' + raw_status)
            return redirect('assinatura')

        # Se passou pelas verificações acima, libera o acesso
        request.active_subscription = subscription_to_check
        return view_func(request, *args, **kwargs)

    return _wrapped_view


# --- MANTENHA AS OUTRAS FUNÇÕES ---

def check_employee_permission(permission_field_name):
    """
    Verifica se um funcionário ('request.company_link') tem uma permissão específica.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):

            if not request.user.is_authenticated:
                return redirect('login')

            # O 'request.company_link' é setado no decorator anterior (subscription_required)
            # Se ele não existir aqui, tentamos buscar novamente por segurança
            link = getattr(request, 'company_link', None)
            
            if link is None:
                # Se link é None, pode ser o Dono (acesso total) ou o middleware falhou.
                # Vamos assumir que se passou pelo subscription_required e não tem link, é o Dono.
                return view_func(request, *args, **kwargs)

            # É funcionário -> Verifica a permissão no campo booleano
            if hasattr(link, permission_field_name) and getattr(link, permission_field_name) is True:
                return view_func(request, *args, **kwargs) # Permite
            else:
                messages.error(request, 'Você não tem permissão para acessar esta página.')
                if permission_field_name == 'can_access_home':
                    messages.warning(request, 'Sua conta não tem permissão para a página principal.')
                    return redirect('logout')
                else:
                    return redirect('smart_redirect') # Volta para onde tem permissão

        return _wrapped_view
    return decorator


def owner_required(view_func):
    """
    Garante que APENAS o Dono da Licença acesse.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        # Tenta verificar se é funcionário
        is_employee = CompanyUserLink.objects.filter(employee=request.user).exists()
        
        if is_employee:
            messages.error(request, 'Acesso restrito ao administrador da conta.')
            return redirect('smart_redirect')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def module_access_required(module_name):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Tenta pegar a assinatura que o subscription_required já validou
            subscription = getattr(request, 'active_subscription', None)

            # Se por algum motivo o decorator de subscription não rodou antes, buscamos agora:
            if not subscription:
                if hasattr(request.user, 'subscription'):
                    subscription = request.user.subscription
                else:
                    # Tenta via link de funcionário (fallback)
                    try:
                        link = CompanyUserLink.objects.get(employee=request.user)
                        subscription = link.owner.subscription
                    except:
                        return redirect('login')

            if module_name == 'financial':
                if subscription.has_financial_module:
                    return view_func(request, *args, **kwargs)
                else:
                    messages.error(request, 'Sua licença não inclui o Módulo Financeiro.')
                    return redirect('home')
            
            elif module_name == 'commercial':
                if subscription.has_commercial_module:
                    return view_func(request, *args, **kwargs)
                else:
                    messages.error(request, 'Sua licença não inclui o Módulo Comercial.')
                    return redirect('home')

            return view_func(request, *args, **kwargs)

        return _wrapped_view
    return decorator