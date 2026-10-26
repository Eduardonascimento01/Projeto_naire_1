# Sistema de Gestão - ONG NAIRE

Sistema web desenvolvido em Python/Django para gestão de apadrinhamentos, entregas e voluntários da ONG NAIRE. Esta versão conta com uma arquitetura focada em **Segurança da Informação** e adequação total à **LGPD (Lei Geral de Proteção de Dados)**.

## 🛡️ Destaques de Segurança e Privacidade
* **Privacy by Design:** Criptografia AES em repouso no banco de dados para dados sensíveis (CPFs).
* **Direitos do Titular (LGPD Cap. III):** Ferramentas nativas para Portabilidade de Dados (Exportação JSON) e Direito ao Esquecimento (Anonimização em Cascata).
* **Controle de Acesso (RBAC):** Sistema restrito com validação de privilégios (`is_staff` e `is_superuser`).
* **Proteção Ativa:** Defesa contra ataques de Força Bruta (Brute Force) via `django-axes` e mitigação de SQL Injection via ORM.
* **Auditoria de Logs & IA:** Middleware invisível para rastreabilidade de acessos e algoritmo *Isolation Forest* (Machine Learning) para detecção de anomalias e comportamentos suspeitos.

## 🚀 Como rodar o projeto localmente

1. Clone o repositório:
`git clone [URL_DO_SEU_REPOSITORIO]`

2. Crie e ative o ambiente virtual:
`python -m venv .venv`
`.\.venv\Scripts\Activate.ps1`

3. Instale as dependências:
`pip install -r requirements.txt`

4. Configure as Variáveis de Ambiente:
Faça uma cópia do arquivo `.env.example`, renomeie para `.env` e preencha com as senhas do seu banco de dados MySQL local.

5. Crie as tabelas e rode o servidor:
`python manage.py migrate`
`python manage.py runserver`

## 🧪 Pentest e Auditoria Automatizada
Para rodar a esteira de testes de segurança, execute o script no terminal:
`.\atualizar_sistema.ps1`