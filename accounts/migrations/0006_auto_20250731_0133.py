
from django.db import migrations

def update_dre_area(apps, schema_editor):
    PayableAccount = apps.get_model('accounts', 'PayableAccount')
    ReceivableAccount = apps.get_model('accounts', 'ReceivableAccount')
    
    # Mapeamento de valores antigos para novos
    mapping = {
        'DEDUCAO_RECEITA_BRUTA': 'DEDUCAO',
        'CUSTOS_CSP_CMV': 'CUSTOS',
        'DESPESAS_OPERACIONAIS': 'OPERACIONAL',
        'NAO_OPERACIONAIS': 'NAO_OPERACIONAL',
        'DISTRIBUICAO_LUCROS_SOCIOS': 'DISTRIBUICAO',
    }
    
    # Atualizar PayableAccount
    for old_value, new_value in mapping.items():
        PayableAccount.objects.filter(dre_area=old_value).update(dre_area=new_value)
    
    # Definir valor padrão para valores não mapeados
    PayableAccount.objects.exclude(dre_area__in=mapping.values()).update(dre_area='DEDUCAO')
    
    # Atualizar ReceivableAccount
    for old_value, new_value in mapping.items():
        ReceivableAccount.objects.filter(dre_area=old_value).update(dre_area=new_value)
    
    # Definir valor padrão para valores não mapeados
    ReceivableAccount.objects.exclude(dre_area__in=mapping.values()).update(dre_area='DEDUCAO')

def reverse_update_dre_area(apps, schema_editor):
    PayableAccount = apps.get_model('accounts', 'PayableAccount')
    ReceivableAccount = apps.get_model('accounts', 'ReceivableAccount')
    
    # Mapeamento inverso
    reverse_mapping = {
        'DEDUCAO': 'DEDUCAO_RECEITA_BRUTA',
        'CUSTOS': 'CUSTOS_CSP_CMV',
        'OPERACIONAL': 'DESPESAS_OPERACIONAIS',
        'NAO_OPERACIONAL': 'NAO_OPERACIONAIS',
        'DISTRIBUICAO': 'DISTRIBUICAO_LUCROS_SOCIOS',
    }
    
    for new_value, old_value in reverse_mapping.items():
        PayableAccount.objects.filter(dre_area=new_value).update(dre_area=old_value)
        ReceivableAccount.objects.filter(dre_area=new_value).update(dre_area=old_value)

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0005_auto_20250731_0113'),
    ]
    operations = [
        migrations.RunPython(update_dre_area, reverse_update_dre_area),
    ]