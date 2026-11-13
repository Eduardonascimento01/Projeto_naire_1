# Colocar o sistema no ar no PythonAnywhere (demonstração)

Este guia publica uma **versão de demonstração**, com **dados fictícios** e
banco **SQLite**, para o grupo testar pelo navegador. Ela funciona no plano
gratuito do PythonAnywhere.

> ⚠️ **Nunca use dados reais aqui.** Não importe o dump do banco nem
> cadastre pessoas reais. O sistema guarda CPF, endereço e dados de crianças
> (LGPD).

Em todo o guia, troque **`SEUUSUARIO`** pelo seu nome de usuário do
PythonAnywhere. O site vai ficar em `https://SEUUSUARIO.pythonanywhere.com`.

---

## 1. Criar a conta

1. Crie uma conta em <https://www.pythonanywhere.com> (o plano gratuito serve).
2. No painel, abra a aba **Consoles** e clique em **Bash**.
   Os comandos das próximas etapas são digitados nesse console.

## 2. Baixar o código

```bash
git clone -b deploy-pythonanywhere https://github.com/Eduardonascimento01/Projeto_naire_1.git
cd Projeto_naire_1
```

O `-b deploy-pythonanywhere` baixa o branch que tem este guia e os comandos
de demonstração. Sem ele, o Git baixa o `main`, que ainda não tem esses
arquivos (o passo 3 falharia). Quando o branch for juntado ao `main`, o
`-b deploy-pythonanywhere` deixa de ser necessário.

## 3. Criar o ambiente virtual (Python 3.12, ou 3.13)

Veja quais versões existem:

```bash
ls /usr/bin/python3.1*
```

Use a **3.12** (ou a 3.13): o sistema usa o Django 5.2 LTS, que tem suporte
oficial para as duas.

```bash
python3.12 -m venv ~/.virtualenvs/naire
source ~/.virtualenvs/naire/bin/activate
pip install --no-cache-dir -r requirements-web.txt
```

O `--no-cache-dir` economiza espaço em disco (a conta gratuita tem pouco).
O `requirements-web.txt` tem só o que o site precisa.

## 4. Criar o arquivo `.env` do servidor

Gere duas chaves aleatórias (rode o comando **duas vezes** e guarde as duas):

```bash
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

Abra o editor:

```bash
nano .env
```

Cole o conteúdo abaixo, trocando os valores:

```
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=COLE-A-PRIMEIRA-CHAVE
CRYPTOGRAPHY_KEY=COLE-A-SEGUNDA-CHAVE
DJANGO_ALLOWED_HOSTS=SEUUSUARIO.pythonanywhere.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://SEUUSUARIO.pythonanywhere.com
DJANGO_SECURE_SSL_REDIRECT=False
DB_ENGINE=sqlite
DJANGO_IP_HEADER=HTTP_X_REAL_IP
DJANGO_ADMIN_URL=INVENTE-UM-NOME/
```

Salve com **Ctrl+O** e **Enter**, e saia com **Ctrl+X**.

O que cada linha faz:

- `DJANGO_DEBUG=False`: nunca mostra código nem configurações quando dá erro.
- `CRYPTOGRAPHY_KEY`: cifra os CPFs da demonstração. Ela é diferente da
  chave oficial do grupo, porque aqui os dados são fictícios.
- `DJANGO_CSRF_TRUSTED_ORIGINS`: sem ela, o login dá erro 403.
- `DJANGO_SECURE_SSL_REDIRECT=False`: quem força o HTTPS é o
  PythonAnywhere (passo 7). Deixar o Django forçar também causa um loop
  de redirecionamento.
- `DB_ENGINE=sqlite`: usa um banco em arquivo (`demo.sqlite3`), sem MySQL.
- `DJANGO_IP_HEADER=HTTP_X_REAL_IP`: o PythonAnywhere entrega o IP verdadeiro
  de quem acessa nesse cabeçalho. Sem ele, o log e a trava de senha veriam
  todo mundo com o mesmo IP (o do servidor do PythonAnywhere), e 5 senhas
  erradas de uma pessoa travariam o login de todos.
- `DJANGO_ADMIN_URL`: o endereço do painel admin. Troque por um nome só do
  grupo (ex.: `gestao-naire-2026/`). O `/admin/` padrão é o primeiro lugar
  que robôs tentam.

## 5. Preparar o banco e os dados de teste

```bash
python manage.py migrate
python manage.py criar_tabelas_demo
python manage.py popular_demo
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

- `migrate`: cria as tabelas do Django (usuários, sessões, grupo LGPD...).
- `criar_tabelas_demo`: cria as tabelas do sistema (responsáveis, crianças...).
- `popular_demo`: cadastra pessoas, crianças, padrinhos e eventos **fictícios**.
- `createsuperuser`: cria a **sua** conta de administrador.
- `collectstatic`: junta CSS e imagens na pasta `staticfiles`.

## 6. Criar o site (aba **Web**)

1. Clique em **Add a new web app** e depois em **Next**.
2. Escolha **Manual configuration**. Não escolha "Django": essa opção cria um
   projeto novo e vazio.
3. Escolha a **mesma versão de Python** da etapa 3.
4. Na página do site, preencha:
   - **Source code:** `/home/SEUUSUARIO/Projeto_naire_1`
   - **Virtualenv:** `/home/SEUUSUARIO/.virtualenvs/naire`
5. Em **Static files**, adicione:
   - **URL:** `/assets/`
   - **Directory:** `/home/SEUUSUARIO/Projeto_naire_1/staticfiles`
6. Clique no link do **WSGI configuration file**. Apague **todo** o conteúdo
   e cole:

```python
import os
import sys

path = '/home/SEUUSUARIO/Projeto_naire_1'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'setup.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

   Clique em **Save**.

## 7. Ligar o HTTPS e publicar

1. Na aba **Web**, seção **Security**, ligue **Force HTTPS**.
2. Clique no botão verde **Reload SEUUSUARIO.pythonanywhere.com**.
3. Abra `https://SEUUSUARIO.pythonanywhere.com` e entre com a conta da
   etapa 5.

## 8. Criar as contas do grupo

No console Bash, com o ambiente ativado (`source ~/.virtualenvs/naire/bin/activate`
e `cd ~/Projeto_naire_1`):

```bash
python manage.py popular_demo --usuarios ana bruno carla
```

O comando mostra uma senha para cada conta. **Ela aparece só uma vez.**
Mande para cada pessoa por mensagem **privada**.

Para quem vai testar exportar, anonimizar e excluir ofício (LGPD):

```bash
python manage.py popular_demo --usuarios dani --lgpd
```

Membros do grupo **LGPD** veem os mesmos botões de LGPD que o superusuário.
Para dar ou tirar essa permissão de uma conta que já existe, use o painel
`/admin/` → **Usuários** → escolha a conta → **Grupos**.

O painel `/admin/` completo continua só para superusuários. Para mostrar
essa parte ao grupo, apresente compartilhando a tela.

Contas que já existem não são alteradas, e os dados fictícios não são
duplicados.

---

## Manutenção

**Atualizar o site depois de mudanças no GitHub:**

```bash
cd ~/Projeto_naire_1
source ~/.virtualenvs/naire/bin/activate
git pull
pip install --no-cache-dir -r requirements-web.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Depois clique em **Reload** na aba Web.

**Atualização de segurança de 2026-11-13 (Django 5.2), só uma vez:**

1. Atualize o código e as bibliotecas (o Django sobe de 4.2 para 5.2):

   ```bash
   cd ~/Projeto_naire_1
   source ~/.virtualenvs/naire/bin/activate
   git fetch
   git checkout correcoes-seguranca   # ou o branch onde ela foi juntada
   git pull
   pip install --no-cache-dir -r requirements-web.txt
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```

2. Acrescente ao `.env` (`nano .env`) as duas linhas novas do passo 4:
   `DJANGO_IP_HEADER=HTTP_X_REAL_IP` e `DJANGO_ADMIN_URL=...`.
3. Clique em **Reload** na aba Web.
4. Confira: entre no site, abra algumas telas e aperte **F12 → Console**.
   Não deve aparecer erro com "Content-Security-Policy". O painel admin
   passa a ficar no endereço novo (`/SEU-NOME/`), e `/admin/` dá 404.
5. Depois que 2 pessoas (de casas diferentes) entrarem no site, confira os
   IPs gravados no log, no console Bash:

   ```bash
   python manage.py shell -c "from gerencias.models import TbLogAuditoria as L; print(list(L.objects.order_by('-pk').values_list('usuario', 'ip')[:10]))"
   ```

   Os IPs devem ser diferentes de pessoa pra pessoa. Se todos forem iguais,
   o `DJANGO_IP_HEADER` está errado.

O que mudou: Django 5.2 LTS (o 4.2 não recebe mais correções), lista de
fontes permitidas (CSP), log sem IP falso e sem visitante anônimo,
"esqueci minha senha" por e-mail desligado, sair só pelo botão (POST) e
ofício visível só para remetente, destinatário e LGPD.

**Algo deu errado?** Na aba Web, abra o **Error log**. As últimas linhas
mostram o erro.

**Renovação:** no plano gratuito, o site para depois de um tempo sem
renovação. Na aba Web, clique no botão que estende o prazo.

**Recomeçar a demonstração do zero:**

```bash
rm demo.sqlite3
python manage.py migrate
python manage.py criar_tabelas_demo
python manage.py popular_demo
python manage.py createsuperuser
```
