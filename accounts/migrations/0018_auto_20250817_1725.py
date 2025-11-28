# accounts/migrations/00XX_auto_... .py

from django.db import migrations
import os

def create_superuser(apps, schema_editor):
    User = apps.get_model('auth', 'User')

    ADMIN_USER = os.environ.get('ADMIN_USER')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL')
    ADMIN_PASS = os.environ.get('ADMIN_PASS')

    # Só cria o superusuário se ele não existir
    if not User.objects.filter(username=ADMIN_USER).exists():
        User.objects.create_superuser(
            username=ADMIN_USER,
            email=ADMIN_EMAIL,
            password=ADMIN_PASS
        )
        print(f'Superusuário {ADMIN_USER} criado com sucesso.')
    else:
        print(f'Superusuário {ADMIN_USER} já existe.')

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0017_alter_payableaccount_payment_method_and_more'), # ATENÇÃO: Verifique o nome da sua última migração
    ]

    operations = [
        migrations.RunPython(create_superuser),
    ]