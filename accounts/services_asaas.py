import requests
import logging
import re
import json
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)

class AsaasMarketplaceService:
    def __init__(self):
        self.api_key = settings.ASAAS_MASTER_API_KEY 
        self.base_url = settings.ASAAS_API_URL
        self.timeout = 30

    def safe_json(self, response):
        """Amortecedor de erros: tenta decodificar JSON; se falhar, evita o erro 'char 0'."""
        try:
            return response.json()
        except (ValueError, json.JSONDecodeError):
            return {
                "non_json_error": True,
                "status_code": response.status_code,
                "raw_text": response.text[:500]
            }

    def get_common_headers(self, api_key=None):
        """Padroniza os headers para todas as chamadas, garantindo resposta em JSON."""
        return {
            "access_token": api_key or self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SistemClass-Integrator/1.0"
        }

    # --- GERENCIAMENTO DE SUBCONTAS (ORIGINAL PRESERVADO) ---

    def criar_subconta(self, profile):
        cnpj_limpo = re.sub(r'\D', '', profile.cnpj or '')
        headers = self.get_common_headers()

        # 1. Tenta criar a conta
        payload = {
            "name": profile.nome_empresa,
            "email": profile.email_contato,
            "cpfCnpj": cnpj_limpo,
            "companyType": self._get_company_type(profile.regime_tributario),
            "mobilePhone": re.sub(r'\D', '', profile.telefone_contato or ''),
            "address": profile.endereco,
            "addressNumber": profile.numero or "S/N",
            "province": profile.bairro,
            "postalCode": re.sub(r'\D', '', profile.cep or ''),
            "incomeValue": 5000.00, 
        }

        response = requests.post(f"{self.base_url}/accounts", json=payload, headers=headers, timeout=self.timeout)
        data = self.safe_json(response)

        # 2. SE JÁ EXISTIR, BUSCA E SINCRONIZA ID E API KEY
        if response.status_code == 400 and "já está em uso" in str(data):
            print(f"🔄 CNPJ já em uso. Sincronizando ID e API Key para: {cnpj_limpo}")
            url_busca = f"{self.base_url}/accounts?cpfCnpj={cnpj_limpo}" # Usando cpfCnpj como filtro de busca
            res_busca = requests.get(url_busca, headers=headers)
            dados_busca = self.safe_json(res_busca)
            
            if res_busca.status_code == 200 and dados_busca.get('data'):
                conta_existente = dados_busca['data'][0]
                
                # Atualizamos o objeto profile com os dados encontrados
                profile.asaas_subaccount_id = conta_existente.get('id')
                
                # Se o Asaas retornar a API Key na busca, salvamos. 
                # Se não retornar, o próximo passo (fiscal) usará a Master Key se necessário.
                if conta_existente.get('apiKey'):
                    profile.asaas_api_key = conta_existente.get('apiKey')
                
                profile.save()
                
                return {
                    "success": True, 
                    "id": conta_existente.get('id'), 
                    "apiKey": profile.asaas_api_key,
                    "sincronizado": True
                }

        # 3. SE CRIAR NOVA COM SUCESSO
        if response.status_code == 200 and not data.get("non_json_error"):
            profile.asaas_subaccount_id = data.get("id")
            profile.asaas_api_key = data.get("apiKey")
            profile.save()
            return {"success": True, "id": data.get("id"), "apiKey": data.get("apiKey")}
        
        # 4. Erro real de validação
        erro_msg = data.get("errors", [{}])[0].get('description', "Erro desconhecido")
        return {"success": False, "error": erro_msg}

    def _get_company_type(self, regime):
        if regime == '4': return "INDIVIDUAL"
        return "LIMITED"

    def configurar_dados_fiscais(self, profile, certificado_binario=None):
        print(f"\n🚀 [DEBUG ASAAS] Iniciando configuração fiscal...")
        sub_api_key = profile.asaas_api_key
        
        # 1. Recuperar API Key se necessário (Omitido aqui por brevidade, mantenha sua lógica de recuperação)
        if not sub_api_key:
            # ... (mantenha seu código que gera a sub_api_key) ...
            pass

        headers = {
            "access_token": sub_api_key,
            "Accept": "application/json"
        }

        # --- PASSO NOVO: ATUALIZAR DADOS COMERCIAIS (Ativa o Fiscal no Sandbox) ---
        # Muitas vezes o 404 ocorre porque o Asaas não sabe o ramo de atividade da subconta
        print("🛠️ [DEBUG ASAAS] Atualizando informações comerciais da subconta...")
        url_business = f"{self.base_url}/myAccount/commercialInfo"
        payload_business = {
            "companyType": self._get_company_type(profile.regime_tributario),
            "site": "https://sistemclass.com.br"
        }
        requests.post(url_business, json=payload_business, headers=headers)

        # --- PASSO 2: CONFIGURAÇÃO FISCAL ---
        url = f"{self.base_url}/config/fiscal"
        
        payload = {
            'email': str(profile.email_contato or ''),
            'municipalServiceId': str(profile.codigo_municipio or ''),
            'municipalInscription': str(re.sub(r'\D', '', profile.inscricao_municipal or '')),
            'simplesNacional': 'true' if profile.optante_simples_nacional else 'false',
            'certificatePassword': str(profile.senha_certificado or ''),
            'regime': 'SIMPLES_NACIONAL' if profile.regime_tributario in ['1', '2', '4'] else 'REAL_LUCRO_PRESUMIDO',
            'issAlid': str(profile.aliquota_iss or '2.0'),
            'nextServiceInvoiceNumber': str(profile.proximo_numero_nfse or '1'),
            'serviceInvoiceSeries': str(profile.serie_nfse or '1'),
        }

        files = {'certificateFile': ('certificado.pfx', certificado_binario, 'application/x-pkcs12')}
        
        try:
            # Tentativa 1: Endpoint de Subconta via API KEY
            response = requests.post(url, data=payload, files=files, headers=headers, timeout=self.timeout)
            
            # SE AINDA DER 404, tentamos o Plano B (Endpoint via Master Key)
            if response.status_code == 404:
                print("🔄 [DEBUG ASAAS] Endpoint /config/fiscal não achado. Tentando via Master Key...")
                url_master = f"{self.base_url}/accounts/{profile.asaas_subaccount_id}/config/fiscal"
                response = requests.post(url_master, data=payload, files=files, headers={"access_token": self.api_key}, timeout=self.timeout)

            data = self.safe_json(response)
            
            if response.status_code in [200, 201]:
                return {"success": True}
            else:
                erro_msg = data.get("errors", [{}])[0].get('description', response.text)
                return {"success": False, "error": f"Erro {response.status_code}: {erro_msg}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_or_create_asaas_customer(self, profile, cliente):
        documento = re.sub(r'\D', '', cliente.cpf_cnpj or '')
        headers = self.get_common_headers(profile.asaas_api_key)

        url_busca = f"{self.base_url}/customers?cpfCnpj={documento}"
        res_busca = requests.get(url_busca, headers=headers, timeout=self.timeout)
        dados = self.safe_json(res_busca)

        if res_busca.status_code == 200 and dados.get('data'):
            return dados['data'][0]['id']

        payload = {
            "name": cliente.nome,
            "cpfCnpj": documento,
            "email": cliente.email,
            "mobilePhone": re.sub(r'\D', '', cliente.telefone or ''),
            "address": cliente.logradouro,
            "addressNumber": cliente.numero,
            "province": cliente.bairro,
            "postalCode": re.sub(r'\D', '', cliente.cep or ''),
            "externalReference": str(cliente.id),
            "notificationDisabled": True
        }

        res_criacao = requests.post(f"{self.base_url}/customers", json=payload, headers=headers, timeout=self.timeout)
        return self.safe_json(res_criacao).get('id')

    def emitir_nota_com_cobranca(self, profile, venda, dados_nota):
        """Emissão vinculada a produtos (Laboratório)."""
        url = f"{self.base_url}/payments"
        headers = self.get_common_headers(profile.asaas_api_key)

        items_nf = []
        for item in venda.itens.all():
            items_nf.append({
                "description": item.produto.nome,
                "quantity": float(item.quantidade),
                "value": float(item.preco_unitario),
                "ncm": re.sub(r'\D', '', item.produto.ncm or ''),
            })

        payload = {
            "customer": dados_nota['asaas_customer_id'],
            "billingType": "BOLETO",
            "value": float(venda.valor_total_liquido),
            "dueDate": timezone.now().strftime("%Y-%m-%d"),
            "externalReference": str(venda.id),
            "description": f"Venda de Produtos #{venda.id} - Laboratorio",
            "invoice": {
                "description": f"Nota Fiscal de Produto ref. Venda #{venda.id}",
                "effectiveDate": timezone.now().strftime("%Y-%m-%d"),
                "status": "POWERED_BY_ASAAS",
                "items": items_nf
            }
        }

        response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        return self.safe_json(response)
    
    def resolve_municipal_service(self, profile, codigo_servico):
        """Busca o ID interno do Asaas para o código de serviço municipal (ex: 1.01)."""
        url = f"{self.base_url}/invoices/municipalServices"
        headers = self.get_common_headers(profile.asaas_api_key)
        params = {"description": codigo_servico} 
        
        res = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        dados = self.safe_json(res)
        
        if res.status_code == 200 and not dados.get('non_json_error') and dados.get('data'):
            return dados['data'][0].get('id'), dados['data'][0].get('description')
        return None, "Servico municipal nao identificado"

    def agendar_nfse_por_payment(self, profile, pay_id, venda):
        """Agendamento oficial de NFS-e (Serviço) usando IDs internos do Asaas."""
        url = f"{self.base_url}/invoices"
        headers = self.get_common_headers(profile.asaas_api_key)
        
        item = venda.itens.first()
        cod_servico = (item.produto.codigo_servico or "1.01").strip()
        
        # BUSCA O ID REAL DO ASAAS (Ex: Converte '1.01' para '1234')
        m_id, m_name = self.resolve_municipal_service(profile, cod_servico)
        
        payload = {
            "payment": pay_id,
            "serviceDescription": f"Servicos de tecnologia ref. Venda #{venda.id} - SistemClass",
            "value": float(venda.valor_total_liquido),
            "effectiveDate": timezone.now().strftime("%Y-%m-%d"),
            "municipalServiceId": m_id, 
            "municipalServiceCode": cod_servico,
            "municipalServiceName": m_name,
            "taxes": {
                "iss": float(profile.aliquota_iss or 2.0)
            }
        }

        response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        return self.safe_json(response)