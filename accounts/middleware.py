from django.contrib.auth.models import User
from django.utils.deprecation import MiddlewareMixin
from accounts.models import CompanyUserLink, Subscription
import logging

logger = logging.getLogger(__name__)

class BPOManagementMiddleware(MiddlewareMixin):
    """
    Middleware que trata dois casos:
    1. BPO Admin gerenciando um cliente (via sessão).
    2. Funcionário acessando dados do dono da licença (via CompanyUserLink).
    """
    def process_request(self, request):
        # Garante que os atributos sempre existam em todos os requests
        request.is_managing = False     # É um BPO gerenciando?
        request.company_link = None     # É um funcionário? (Se sim, armazena o link)
        request.real_user = request.user # Por padrão, o usuário real é o usuário logado

        if not request.user.is_authenticated:
            return

        # Caso 1: BPO Admin gerenciando cliente
        if 'real_user_id' in request.session and 'managed_user_id' in request.session:
            try:
                real_user = User.objects.get(id=request.session['real_user_id'])
                managed_user = User.objects.get(id=request.session['managed_user_id'])
                
                request.real_user = real_user   # O BPO
                request.user = managed_user     # O Cliente
                request.is_managing = True
                request.company_link = None     # BPOs não são funcionários
                return
            except User.DoesNotExist:
                logger.warning("Falha no BPO Middleware: Usuário não encontrado. Limpando sessão BPO.")
                request.session.pop('real_user_id', None)
                request.session.pop('managed_user_id', None)

        # Caso 2: Funcionário vinculado a um dono
        try:
            # Tenta encontrar um link de funcionário para o usuário logado
            link = CompanyUserLink.objects.select_related('owner').get(employee=request.user, is_active=True)
            
            request.company_link = link         # <-- A MUDANÇA IMPORTANTE
            request.real_user = request.user    # O Funcionário
            request.user = link.owner           # O Dono da Licença
            # request.is_employee não é mais necessário, usamos 'company_link'
        except CompanyUserLink.DoesNotExist:
            # É o dono da conta logado (ou um BPO não-gerenciando)
            # request.company_link continua None
            pass
