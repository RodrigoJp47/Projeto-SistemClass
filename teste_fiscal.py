import os
import django
import sys

# Adiciona o diretório atual ao caminho do Python
sys.path.append(os.path.abspath(os.curdir))

# O nome da sua pasta de configurações é 'setup'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings') 

django.setup()

from accounts.models import CompanyProfile
from accounts.services_asaas import AsaasMarketplaceService

def validar_certificado():
    # Busca o perfil do Laboratório Online (ou use o CNPJ para filtrar)
    profile = CompanyProfile.objects.filter(nome_empresa__icontains="LABORATORIO").first()
    
    if not profile:
        print("❌ Perfil não encontrado no banco de dados.")
        return

    service = AsaasMarketplaceService()
    resultado = service.consultar_status_fiscal(profile)

    if resultado["success"]:
        print("\n✅ Conexão com Asaas OK!")
        print(f"📊 Dados Fiscais no Asaas: {resultado['data']}")
    else:
        print(f"❌ Falha ao consultar: {resultado['error']}")

if __name__ == "__main__":
    validar_certificado()