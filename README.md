# SistemClass - ERP & Gestão Empresarial (SaaS)

Sistema de gestão completo (ERP) desenvolvido em **Django**, focado em atender micro e pequenas empresas no modelo SaaS (Software as a Service). O projeto conta com arquitetura multi-tenant, controle financeiro rigoroso, gestão comercial e múltiplas integrações bancárias via API.

🔗 **Demo/Deploy:** [www.sistemclass.com.br]

## 🚀 Funcionalidades Principais

### 💰 Módulo Financeiro
* **Gestão de Contas:** Contas a Pagar e Receber com recorrência.
* **Conciliação Bancária:** Importação automática de arquivos OFX.
* **Relatórios Gerenciais:** Fluxo de Caixa Analítico e DRE (Demonstrativo do Resultado do Exercício).
* **Gestão de Tarefas:** Controle de pendências financeiras.

### 📈 Módulo Comercial
* **CRM / Pipeline:** Gestão visual de oportunidades de venda.
* **Frente de Caixa (PDV):** Interface para vendas rápidas e emissão de comprovantes.
* **Precificação Inteligente:** Cálculo automático de preço de venda baseada em custos fixos/variáveis e margem de lucro.
* **Gestão de Contratos:** Criação e controle de vigência de contratos.
* **Metas:** Definição e acompanhamento de metas por vendedor.

### ⚙️ Arquitetura e SaaS
* **Multi-tenant:** Estrutura preparada para múltiplos clientes com isolamento de dados.
* **Controle de Acesso (RBAC):** Permissões granulares para Donos, Funcionários, BPOs e Clientes.
* **Assinaturas:** Gestão automática de planos e bloqueios via integração com Stripe.

## 🔌 Integrações (APIs)
O sistema possui módulos de integração robustos com players do mercado:
* **Pagamentos & Bancos:** Stripe (Checkout e Webhooks), Asaas, Mercado Pago, Banco Inter (API v2 com Certificado Digital).
* **ERPs & Contabilidade:** Omie, Conta Azul, Tiny e Nibo.

## 🛠️ Tecnologias Utilizadas
* **Backend:** Python 3, Django 4, Django REST Framework.
* **Banco de Dados:** PostgreSQL.
* **Frontend:** HTML5, CSS3, JavaScript, Bootstrap.
* **Infraestrutura:** Render (Deploy e CI/CD).
* **Outros:** WeasyPrint (Geração de PDF), Pandas (Análise de dados).

## 📸 Screenshots
*<img width="1360" height="768" alt="image" src="https://github.com/user-attachments/assets/f7edba18-2ea0-4e7c-bbe9-659c58b5dec3" />
<img width="1360" height="768" alt="image" src="https://github.com/user-attachments/assets/24b256e5-06fb-4bfb-852f-022411831684" />
<img width="1360" height="768" alt="image" src="https://github.com/user-attachments/assets/4e396ee1-c884-4666-bed7-741bc2790bce" />
<img width="1360" height="768" alt="image" src="https://github.com/user-attachments/assets/f8c72b0f-8219-44f7-b5d7-569f1979274d" />
<img width="1360" height="768" alt="image" src="https://github.com/user-attachments/assets/2be76ee9-fdeb-4553-9b16-6fd7ae6443ce" />




*

## 👤 Autor
**Rodrigo Abreu**
Desenvolvedor Python Full Stack
