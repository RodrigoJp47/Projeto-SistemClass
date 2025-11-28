import requests
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('NFE_TOKEN_HOMOLOGACAO')
BASE_URL = "https://homologacao.focusnfe.com.br"
CNPJ = "62175444000115"

print(f"--- CONFIG ---")
print(f"URL: {BASE_URL}")
print(f"Token: {TOKEN[:4]}...{TOKEN[-4:] if TOKEN else 'None'}")
print(f"CNPJ Alvo: {CNPJ}")
print("--------------\n")

def test_endpoint(method, endpoint, payload=None):
    url = f"{BASE_URL}{endpoint}"
    print(f"Testing {method} {url}...")
    try:
        if method == 'GET':
            response = requests.get(url, auth=(TOKEN, ""))
        elif method == 'POST':
            response = requests.post(url, json=payload, auth=(TOKEN, ""))
        elif method == 'PUT':
            response = requests.put(url, json=payload, auth=(TOKEN, ""))
            
        print(f"Status: {response.status_code}")
        print(f"Body: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 20)

# 1. Teste Básico: Consultar a própria empresa (se o token for dela)
# Se o token for de integrador, isso retorna os dados da empresa.
# Se o token for da empresa, isso retorna os dados dela mesma.
test_endpoint('GET', f"/v2/empresas/{CNPJ}")

# 2. Teste de Criação (Simulado - vai falhar se já existe, mas queremos ver se dá 404)
payload_teste = {
    "nome": "EMPRESA TESTE DEBUG",
    "cnpj": CNPJ,
    "logradouro": "Rua Teste",
    "numero": "123",
    "bairro": "Centro",
    "municipio": "São Paulo",
    "uf": "SP",
    "cep": "01001000"
}
# test_endpoint('POST', "/v2/empresas", payload_teste)

# 3. Teste de Hooks (Geralmente acessível)
test_endpoint('GET', "/v2/hooks")
