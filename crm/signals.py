from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import OrcamentoVenda

@receiver(post_save, sender=OrcamentoVenda)
def atualizar_valor_crm(sender, instance, created, **kwargs):
    """
    Sempre que um orçamento for salvo, atualiza o valor e o status da Oportunidade vinculada.
    """
    if hasattr(instance, 'oportunidade_origem') and instance.oportunidade_origem:
        oportunidade = instance.oportunidade_origem
        
        # 1. Atualiza o valor do CRM com o valor real do Orçamento
        oportunidade.valor_estimado = instance.valor_total
        
        # 2. Opcional: Se o orçamento for ACEITO, move o card para "Fechamento" (ou Ganho)
        # if instance.status == 'ACEITO':
        #     oportunidade.status = 'GANHO'
            
        oportunidade.save()