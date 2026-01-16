from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import Subscription

class Command(BaseCommand):
    help = 'Verifica e expira assinaturas vencidas automaticamente'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        
        # Lista de status que devem ser verificados
        # (Lembre-se que no banco é 'active' ou 'trial', não o texto bonitinho)
        target_statuses = ['active', 'trial'] 

        # Filtra quem está com status ativo MAS com data menor que hoje
        vencidas = Subscription.objects.filter(
            status__in=target_statuses,
            valid_until__lt=today
        )

        count = vencidas.count()

        if count > 0:
            # Atualiza todas de uma vez para 'expired'
            vencidas.update(status='expired')
            self.stdout.write(self.style.SUCCESS(f'Processo concluído: {count} assinaturas foram marcadas como Expiradas.'))
        else:
            self.stdout.write(self.style.SUCCESS('Nenhuma assinatura vencida encontrada hoje.'))