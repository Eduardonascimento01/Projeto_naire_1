# Sistema de Gestão - ONG NAIRE

Sistema web desenvolvido em Python/Django para gestão de apadrinhamentos, entregas e voluntários da ONG NAIRE. Esta versão conta com uma arquitetura focada em **Segurança da Informação** e adequação total à **LGPD (Lei Geral de Proteção de Dados)**.

## 🛡️ Destaques de Segurança e Privacidade
* **Privacy by Design:** Criptografia AES em repouso no banco de dados para dados sensíveis (CPFs).
* **Direitos do Titular (LGPD Cap. III):** Ferramentas nativas para Portabilidade de Dados (Exportação JSON) e Direito ao Esquecimento (Anonimização em Cascata).
* **Controle de Acesso (RBAC):** Sistema restrito com validação de privilégios (`is_staff` e `is_superuser`).
* **Proteção Ativa:** Defesa contra ataques de Força Bruta (Brute Force) via `django-axes` e mitigação de SQL Injection via ORM.
* **Auditoria de Logs & IA:** Middleware invisível para rastreabilidade de acessos e algoritmo *Isolation Forest* (Machine Learning) para detecção de anomalias e comportamentos suspeitos.

## 🚀 Como rodar o projeto localmente (Windows)

**Antes de começar, instale:** Python 3.12, MySQL 8 (com o MySQL Workbench) e Git.

1. Baixe o projeto e entre na pasta:
   ```
   git clone https://github.com/Eduardonascimento01/Projeto_naire_1.git
   cd Projeto_naire_1
   ```

2. Crie e ative o ambiente virtual **com Python 3.12** (recomendado; a 3.13 também funciona):
   ```
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   Se o PowerShell bloquear a ativação, rode uma vez:
   `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

   O projeto usa o Django 5.2 LTS. O `django-cryptography` (que cifra os CPFs) só funciona no Django 5 graças à ponte `setup/compat_baseconv.py`: não apague esse arquivo.

3. Instale as dependências:
   `pip install -r requirements.txt`

4. Crie o arquivo de configuração:
   `copy .env.example .env`

   Abra o `.env` e preencha `DB_PASSWORD` com a senha do seu MySQL local.
   A `CRYPTOGRAPHY_KEY` é a chave oficial do grupo: peça a um integrante.

5. Crie o banco e importe os dados de exemplo (todos fictícios).
   As tabelas do sistema (`tb_...`) **não** são criadas pelo `migrate`: elas vêm dos arquivos da pasta `Dump_banco`.
   - No MySQL Workbench: **Server > Data Import > Import from Dump Project Folder** e escolha a pasta `Dump_banco`.
   - Em **Default Target Schema**, crie ou escolha `bd_naire2` e clique em **Start Import**.

6. Prepare a criptografia dos CPFs (**obrigatório na primeira vez**, nesta ordem):
   ```
   Get-Content Dump_banco\migracao_cpf_hash.sql | mysql -u root -p bd_naire2
   python criptografar_banco.py
   python manage.py migrate
   python manage.py preencher_cpf_hash
   ```
   O primeiro comando é para o PowerShell. No Prompt de Comando (cmd), use:
   `mysql -u root -p bd_naire2 < Dump_banco\migracao_cpf_hash.sql`

7. Crie o seu usuário administrador e ligue o servidor:
   ```
   python manage.py createsuperuser
   python manage.py runserver
   ```
   Abra no navegador: http://127.0.0.1:8000

Depois, no Admin, adicione ao grupo **LGPD** os usuários que podem exportar, anonimizar e excluir dados.

## 🧪 Pentest e Auditoria Automatizada
Para rodar os testes de segurança automáticos, execute o script no terminal:
`.\atualizar_sistema.ps1`

**Atenção:** no final, o script pergunta se deve enviar o código ao GitHub e faz `git push`. Responda **N** se quiser só testar.

## 📋 Relatório de erros do projeto
Para verificar a sintaxe dos arquivos Python, executar as checagens do Django e rodar os testes existentes:

`python relatorio_erros.py`

O resultado é salvo em `relatorio_erros.md`. O comando retorna código de saída diferente de zero se alguma etapa falhar; para escolher outro caminho para o relatório, use `python relatorio_erros.py --saida caminho\relatorio.md`.

Essa verificação não executa o pentest nem altera o banco de dados.

## 🌐 Demonstração online (PythonAnywhere)
Para publicar uma versão de teste com dados fictícios, siga o guia [DEPLOY_PYTHONANYWHERE.md](DEPLOY_PYTHONANYWHERE.md).

## ✅ Testes automatizados
Os testes usam SQLite em memória (não precisam de MySQL e não tocam no banco real):

`python manage.py test --settings=setup.settings_test`

## 🔑 Quem já tinha o banco antes do CPF criptografado
Se você já usava o sistema com o banco antigo, faça **backup** antes e rode só o passo 6 acima (a ordem completa também está no topo de `Dump_banco/migracao_cpf_hash.sql`).
