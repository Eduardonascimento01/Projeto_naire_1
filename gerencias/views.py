import logging
import re
from datetime import datetime, date
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login, update_session_auth_hash
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

# GRUPO_LGPD: membros (e superusuários) podem exportar, anonimizar e excluir.
from gerencias.permissoes import GRUPO_LGPD, pode_usar_lgpd
from gerencias.cpf_utils import cpf_valido, hash_cpf, limpar_cpf, somente_digitos, PREFIXO_ANONIMO
from gerencias.models import (
    TbFuncionario, TbTipoFuncionario, TbCadastroResponsavel,
    TbFilhosResponsavel, TbOficios, TbMadrinhaPadrinho,
    TbApadrinhamentoCrianca, TbEvento, TbEntrega, TbLogAuditoria,
    TbFuncionarioUsuario,
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ==========================================
# DECORATORS
# ==========================================
def login_required(function=None):
    """Exige usuário autenticado E staff/superuser."""
    return user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser))(function)


def lgpd_required(view):
    """Restringe a view a superusuários e membros do grupo LGPD."""
    @wraps(view)
    def _wrapper(request, *args, **kwargs):
        if not pode_usar_lgpd(request.user):
            logger.warning("Acesso LGPD negado a %s em %s", request.user.username, request.path)
            return pagina_erro(
                request,
                mensagem="Você não tem permissão para esta ação. Fale com um administrador.",
                status=403,
            )
        return view(request, *args, **kwargs)
    return _wrapper


def admin_required(view):
    """Só administrador (superusuário). Usado no que cria logins: quem cria um
    login escolhe a senha e poderia entrar no sistema como outra pessoa."""
    @wraps(view)
    def _wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            logger.warning("Acesso de administrador negado a %s em %s", request.user.username, request.path)
            messages.error(request, 'Somente um administrador pode cadastrar funcionários e criar logins.')
            return redirect('lista_funcionarios')
        return view(request, *args, **kwargs)
    return _wrapper


def tratar_erros(view):
    """
    Substitui o try/except que existia em cada view.

    - Http404 passa direto: o Django mostra a página 404 (não é erro do sistema).
    - Qualquer outra exceção é registrada COM traceback (logger.exception)
      e o usuário vê a página de erro amigável.
    """
    @wraps(view)
    def _wrapper(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except Http404:
            raise
        except Exception:
            logger.exception("Erro em %s", view.__name__)
            return pagina_erro(request)
    return _wrapper


def somente_post(view):
    @wraps(view)
    def _wrapper(request, *args, **kwargs):
        if request.method != 'POST':
            return pagina_erro(request, mensagem="Método HTTP inválido.", status=405)
        return view(request, *args, **kwargs)
    return _wrapper


# ==========================================
# HELPERS
# ==========================================
def _normalizar_data(data_str):
    """Aceita 'YYYY-MM-DD' ou 'DD/MM/YYYY' e devolve sempre 'DD/MM/YYYY'."""
    if not data_str:
        return ''
    data_str = str(data_str).strip()
    if len(data_str) == 10 and data_str[4] == '-':
        try:
            return datetime.strptime(data_str, '%Y-%m-%d').strftime('%d/%m/%Y')
        except ValueError:
            return data_str
    return data_str


def _parse_data_br(data_str):
    """'DD/MM/YYYY' -> datetime, ou None se inválida."""
    try:
        return datetime.strptime(str(data_str or '').strip(), '%d/%m/%Y')
    except ValueError:
        return None


def calcular_idade(data_nascimento_str):
    """Calcula idade aceitando 'DD/MM/YYYY' ou 'YYYY-MM-DD'. Retorna None em erro."""
    if not data_nascimento_str:
        return None
    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            data_nasc = datetime.strptime(str(data_nascimento_str), fmt).date()
            hoje = date.today()
            idade = hoje.year - data_nasc.year
            if (hoje.month, hoje.day) < (data_nasc.month, data_nasc.day):
                idade -= 1
            return idade
        except (ValueError, TypeError):
            continue
    return None


def _cpf_duplicado(model, cpf, excluir_pk=None):
    """
    Busca por igualdade na coluna `cpf_hash` (indexada). Não precisa
    decifrar nada nem percorrer a tabela.
    """
    h = hash_cpf(cpf)
    if not h:
        return False
    qs = model.objects.filter(cpf_hash=h)
    if excluir_pk is not None:
        qs = qs.exclude(pk=excluir_pk)
    return qs.exists()


def _ler_cpf(request, obrigatorio, permitir_mascara=False):
    """
    Lê e valida o CPF vindo do formulário.

    Retorna (cpf, erro):
      - cpf = None  -> o formulário devolveu a máscara (***): manter o CPF atual.
      - cpf = ''    -> campo vazio (só permitido se não for obrigatório).
      - cpf = '529…'-> CPF limpo e válido.
    """
    bruto = (request.POST.get('cpf') or '').strip()
    if permitir_mascara and ('*' in bruto or bruto.startswith(PREFIXO_ANONIMO)):
        return None, None
    cpf = limpar_cpf(bruto)
    if not cpf:
        return '', ('O CPF é obrigatório.' if obrigatorio else None)
    if not cpf_valido(cpf):
        return cpf, 'CPF inválido. Confira os números digitados.'
    return cpf, None


def _criar_com_cpf_unico(model, **campos):
    """
    Cria o registro. Se dois cadastros com o mesmo CPF chegarem ao mesmo
    tempo, o índice único de `cpf_hash` barra o segundo: devolvemos None.
    """
    try:
        with transaction.atomic():
            return model.objects.create(**campos)
    except IntegrityError:
        if _cpf_duplicado(model, campos.get('cpf')):
            return None
        raise


def _salvar_com_cpf_unico(obj):
    """Mesmo que _criar_com_cpf_unico, para edição. Devolve True/False."""
    try:
        with transaction.atomic():
            obj.save()
        return True
    except IntegrityError:
        if _cpf_duplicado(type(obj), obj.cpf, excluir_pk=obj.pk):
            return False
        raise


def _validar_evento(request):
    """Lê e valida os campos de evento. Retorna (dados, erro)."""
    dados = {
        'nome': (request.POST.get('nome') or '').strip(),
        'data_evento': _normalizar_data(request.POST.get('data_evento')),
        'endereco': (request.POST.get('endereco') or '').strip(),
        'bairro': (request.POST.get('bairro') or '').strip(),
        'cidade': (request.POST.get('cidade') or '').strip(),
        'estado': (request.POST.get('estado') or '').strip(),
    }
    if not all(dados.values()):
        return dados, 'Todos os campos obrigatórios devem ser preenchidos.'
    if not re.match(r'^\d{2}/\d{2}/\d{4}$', dados['data_evento']):
        return dados, 'Formato de data inválido. Use dd/mm/aaaa.'
    if _parse_data_br(dados['data_evento']) is None:
        return dados, 'Data inválida.'
    return dados, None


def _registrar_auditoria(request, acao, rota):
    TbLogAuditoria.objects.create(
        usuario=request.user.username,
        acao=acao,
        rota=rota,
        ip=request.META.get('REMOTE_ADDR'),
    )


def _definir_situacao_familia(responsavel, ativo):
    """
    Ativa ('S') ou desativa ('N') o responsável E todas as crianças da família.
    Uma família desativada não deve ter crianças "soltas" aparecendo nas listas.
    Ao desativar, as crianças também saem dos apadrinhamentos.
    Devolve (crianças atualizadas, apadrinhamentos removidos).
    """
    responsavel.flag_ativo = ativo
    responsavel.save(update_fields=['flag_ativo'])
    filhos = TbFilhosResponsavel.objects.filter(id_responsavel=responsavel)
    removidos = _remover_apadrinhamentos_das_criancas(filhos) if ativo == 'N' else 0
    criancas = filhos.update(flag_ativo=ativo, data_atualizacao=timezone.now())
    return criancas, removidos


def _remover_apadrinhamentos_das_criancas(criancas):
    """
    Tira os padrinhos das crianças informadas (desativadas). Os padrinhos
    continuam cadastrados e podem apadrinhar outras crianças. O histórico de
    entregas não é apagado. Devolve quantos apadrinhamentos foram removidos.
    """
    removidos, _ = TbApadrinhamentoCrianca.objects.filter(id_filho__in=criancas).delete()
    return removidos


def _aviso_apadrinhamentos(removidos):
    if not removidos:
        return ''
    return f' {removidos} apadrinhamento(s) removido(s); os padrinhos ficam livres para outras crianças.'


def _remover_apadrinhamentos(id_mad_pad):
    """
    Tira o padrinho/madrinha de todas as crianças que ele(a) apadrinha.
    As crianças voltam a ficar disponíveis para outro apadrinhamento.
    O histórico de entregas não é apagado.
    """
    removidos, _ = TbApadrinhamentoCrianca.objects.filter(id_mad_pad_id=id_mad_pad).delete()
    return removidos


def _buscar_por_id(model, valor):
    """
    Busca pelo número (id) que veio do formulário. Vazio ou não numérico
    devolve None (antes o Django quebrava com erro 500 ao tentar converter).
    """
    try:
        return model.objects.filter(pk=int(str(valor).strip())).first()
    except (TypeError, ValueError):
        return None


def _buscar_por_id_ou_404(model, valor):
    obj = _buscar_por_id(model, valor)
    if obj is None:
        raise Http404('Registro não encontrado.')
    return obj


def _esta_anonimizado(obj):
    """Anonimizado pela LGPD: o CPF virou 'ANON-<id>'."""
    return str(getattr(obj, 'cpf', '') or '').startswith(PREFIXO_ANONIMO)


def _bloquear_se_anonimizado(request, obj, destino, *args):
    """
    Anonimizar é irreversível (LGPD): o cadastro não pode voltar a ficar ativo
    nem ser editado (senão, por exemplo, "Criança Anonimizada" voltaria a
    aparecer como disponível para apadrinhar).
    """
    if _esta_anonimizado(obj):
        messages.error(request, 'Este cadastro foi anonimizado (LGPD): não pode ser reativado nem editado.')
        return redirect(destino, *args)
    return None


def _anonimizar_endereco(obj, estado='--'):
    obj.endereco = "Removido"
    obj.complemento = ""
    obj.bairro = "Removido"
    obj.cidade = "Removido"
    obj.estado = estado


# ==========================================
# PÁGINAS BASE
# ==========================================
def _destino_seguro(request, destino):
    """
    Só aceita voltar para uma página DESTE sistema. Sem isso, um link como
    /?next=https://site-falso.com levaria a pessoa, depois do login, para um
    site que imita o sistema (golpe de "redirecionamento aberto").
    """
    if destino and url_has_allowed_host_and_scheme(
            destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return destino
    return ''


def home(request):
    """Página inicial: o blog de notícias da ONG, aberto a todos."""
    return render(request, 'gerencias/index.html')


def entrar(request):
    """
    Tela de login da equipe (botão "Acesso à equipe" no topo do site).
    Quem tenta abrir uma página do sistema sem login também vem para cá e,
    depois de entrar, volta para a página que tinha pedido.
    """
    destino = _destino_seguro(request, request.POST.get('next') or request.GET.get('next'))
    if request.user.is_authenticated:
        return redirect(destino or 'home')
    # O AuthenticationForm passa pelo django-axes: o bloqueio depois de
    # várias senhas erradas continua valendo aqui.
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        auth_login(request, form.get_user())
        return redirect(destino or 'home')
    return render(request, 'registration/login.html', {'form': form, 'next': destino})


def pagina_erro(request, mensagem="Ocorreu um erro interno no processamento.", status=500):
    return render(request, 'gerencias/pagina_erro.html', {'mensagem': mensagem}, status=status)


# ==========================================
# BLOCO FUNCIONÁRIOS
# ==========================================
# Cada funcionário cadastrado ganha um login (auth_user), ligado a ele pela
# tabela tb_funcionario_usuario. Regras:
#  - tipo ADMIN  -> superusuário (acesso total, inclusive LGPD e /admin/);
#    os outros tipos -> acesso normal ao sistema;
#  - só um administrador (superusuário) cria, edita, desativa ou anonimiza
#    um funcionário ADMIN (senão um membro poderia se promover ou rebaixar
#    um administrador);
#  - funcionário desativado não consegue fazer login.
FORMATO_USUARIO = re.compile(r'^[\w.@+-]{3,150}$')
CAMPOS_OBRIGATORIOS_FUNCIONARIO = {
    'tp_funcionario': 'Escolha o tipo de funcionário.',
    'pnome': 'Informe o primeiro nome.',
    'snome': 'Informe o sobrenome.',
    'rua': 'Informe o logradouro.',
    'numero': 'Informe o número.',
    'bairro': 'Informe o bairro.',
    'cidade': 'Informe a cidade.',
    'estado': 'Escolha o estado.',
    'usuario': 'Escolha um nome de usuário para o login.',
    'senha': 'Crie uma senha.',
    'senha2': 'Repita a senha.',
}


def _tipo_e_admin(tipo):
    """O administrador é reconhecido pelo NOME do tipo ("ADMIN"), não pelo número:
    um banco com outra numeração não transforma ninguém em administrador sem querer."""
    return tipo is not None and (tipo.descricao or '').strip().upper().startswith('ADMIN')


def _funcionario_e_admin(funcionario):
    return _tipo_e_admin(funcionario.id_tipo)


def _bloquear_se_admin(request, funcionario):
    """Devolve uma resposta de bloqueio se quem pede não pode mexer neste funcionário."""
    if _funcionario_e_admin(funcionario) and not request.user.is_superuser:
        logger.warning("%s tentou alterar o administrador %s", request.user.username, funcionario.pk)
        messages.error(request, 'Somente um administrador pode alterar o cadastro de outro administrador.')
        return redirect('lista_funcionarios')
    return None


def _usuario_do_funcionario(funcionario):
    acesso = TbFuncionarioUsuario.objects.select_related('usuario').filter(funcionario=funcionario).first()
    return acesso.usuario if acesso else None


def _sincronizar_login(funcionario):
    """Mantém o login coerente com o cadastro: ativo, administrador e nome."""
    usuario = _usuario_do_funcionario(funcionario)
    if usuario is None:
        return
    usuario.is_active = funcionario.flag_ativo == 'S'
    usuario.is_superuser = _funcionario_e_admin(funcionario)
    usuario.is_staff = True
    usuario.first_name = (funcionario.pnome or '')[:150]
    usuario.last_name = (funcionario.snome or '')[:150]
    usuario.save(update_fields=['is_active', 'is_superuser', 'is_staff', 'first_name', 'last_name'])


def _erro_usuario(usuario):
    """Confere o nome de login. Devolve a mensagem de erro ou None."""
    if not usuario:
        return 'Escolha um nome de usuário para o login.'
    if not FORMATO_USUARIO.match(usuario):
        return 'Use de 3 a 150 caracteres: letras, números e . @ + - _ (sem espaços).'
    if User.objects.filter(username__iexact=usuario).exists():
        return 'Este nome de usuário já está em uso. Escolha outro.'
    return None


def _erros_senha(senha, senha2, usuario):
    """
    Confere a senha e a confirmação com as regras do Django (mínimo de 8
    caracteres, não só números, não muito comum, não parecida com o nome).
    `usuario` é o User (pode ainda não estar salvo). Devolve {campo: mensagem}.
    """
    erros = {}
    if not senha:
        erros['senha'] = 'Crie uma senha.'
    if not senha2:
        erros['senha2'] = 'Repita a senha.'
    elif senha and senha != senha2:
        erros['senha2'] = 'As senhas não são iguais.'
    if senha:
        try:
            validate_password(senha, user=usuario)
        except ValidationError as e:
            erros['senha'] = ' '.join(e.messages)
    return erros


def _pode_trocar_senha(request, login):
    """Só um administrador troca a senha de outra pessoa; cada um troca a própria."""
    return login is not None and (request.user.is_superuser or login.pk == request.user.pk)


def _contexto_form_funcionario(request, dados=None, erros=None):
    return {
        'tipos': TbTipoFuncionario.objects.order_by('id_tipo'),
        'pode_criar_admin': request.user.is_superuser,
        'form': dados or {},
        'erros': erros or {},
    }


@login_required
@tratar_erros
def lista_funcionarios(request):
    lista = TbFuncionario.objects.filter(flag_ativo='S')
    return render(request, 'gerencias/lista_funcionarios.html', {'lista': lista})


@login_required
@admin_required
@tratar_erros
def novo_funcionario(request):
    return render(request, 'gerencias/novo_funcionario.html', _contexto_form_funcionario(request))


@login_required
@tratar_erros
def usuario_disponivel(request):
    """Usado pelo formulário para avisar, enquanto a pessoa digita, se o login já existe."""
    usuario = (request.GET.get('usuario') or '').strip()
    valido = bool(FORMATO_USUARIO.match(usuario))
    disponivel = valido and not User.objects.filter(username__iexact=usuario).exists()
    return JsonResponse({'valido': valido, 'disponivel': disponivel})


def _validar_novo_funcionario(request):
    """Confere tudo o que veio do formulário. Devolve (dados, tipo, cpf, erros por campo)."""
    dados = {k: (v or '').strip() for k, v in request.POST.items()
             if k not in ('csrfmiddlewaretoken', 'senha', 'senha2')}
    erros = {campo: msg for campo, msg in CAMPOS_OBRIGATORIOS_FUNCIONARIO.items()
             if not (request.POST.get(campo) or '').strip()}

    tipo = None
    if 'tp_funcionario' not in erros:
        tipo = TbTipoFuncionario.objects.filter(pk=dados['tp_funcionario']).first()
        if tipo is None:
            erros['tp_funcionario'] = 'Tipo de funcionário inválido.'
        elif _tipo_e_admin(tipo) and not request.user.is_superuser:
            logger.warning("%s tentou cadastrar um administrador", request.user.username)
            erros['tp_funcionario'] = 'Somente um administrador pode cadastrar outro administrador.'

    cpf, erro_cpf = _ler_cpf(request, obrigatorio=True)
    if erro_cpf:
        erros['cpf'] = erro_cpf
    elif _cpf_duplicado(TbFuncionario, cpf):
        erros['cpf'] = 'Já existe um funcionário cadastrado com este CPF.'

    if len(somente_digitos(dados.get('telefone'))) not in (10, 11):
        erros['telefone'] = 'Informe o telefone com DDD (10 ou 11 dígitos).'

    usuario = dados.get('usuario', '')
    erro = _erro_usuario(usuario)
    if erro:
        erros['usuario'] = erro
    novo_login = User(username=usuario, first_name=dados.get('pnome', ''), last_name=dados.get('snome', ''))
    erros.update(_erros_senha(request.POST.get('senha') or '', request.POST.get('senha2') or '', novo_login))
    return dados, tipo, cpf, erros


@login_required
@admin_required
@somente_post
@tratar_erros
def insere_novo_funcionario(request):
    dados, tipo, cpf, erros = _validar_novo_funcionario(request)
    if erros:
        messages.error(request, 'Confira os campos destacados em vermelho.')
        return render(request, 'gerencias/novo_funcionario.html',
                      _contexto_form_funcionario(request, dados, erros), status=400)

    ativo = (dados.get('flag') or 'S') == 'S'
    try:
        with transaction.atomic():
            # Cadastro + login juntos: se um falhar, nenhum dos dois é gravado.
            funcionario = TbFuncionario.objects.create(
                id_tipo=tipo,
                pnome=dados['pnome'],
                snome=dados['snome'],
                cpf=cpf,
                telefone=somente_digitos(dados.get('telefone')),
                endereco=f"{dados['rua']}, {dados['numero']}",
                complemento=dados.get('comp'),
                bairro=dados['bairro'],
                cidade=dados['cidade'],
                estado=dados['estado'],
                flag_ativo='S' if ativo else 'N',
            )
            usuario = User.objects.create_user(
                username=dados['usuario'], password=request.POST['senha'],
                first_name=dados['pnome'][:150], last_name=dados['snome'][:150],
                is_staff=True, is_superuser=_tipo_e_admin(tipo), is_active=ativo,
            )
            TbFuncionarioUsuario.objects.create(funcionario=funcionario, usuario=usuario)
    except IntegrityError:
        # Dois cadastros ao mesmo tempo com o mesmo CPF ou usuário.
        messages.error(request, 'Este CPF ou nome de usuário acabou de ser cadastrado por outra pessoa.')
        return render(request, 'gerencias/novo_funcionario.html',
                      _contexto_form_funcionario(request, dados, {}), status=400)

    _registrar_auditoria(request, 'CADASTRO_FUNCIONARIO', f'/func/{funcionario.pk}')
    messages.success(request, f'Funcionário {funcionario} cadastrado. Login: {usuario.username}')
    return redirect('lista_funcionarios')


@login_required
@somente_post
@tratar_erros
def desativa_funcionario(request, id_funcionario):
    func = get_object_or_404(TbFuncionario, id_funcionario=id_funcionario)
    bloqueio = _bloquear_se_admin(request, func)
    if bloqueio:
        return bloqueio
    func.flag_ativo = 'N'
    func.save(update_fields=['flag_ativo'])
    _sincronizar_login(func)  # funcionário desativado não entra mais no sistema
    messages.success(request, f'{func} foi desativado(a). Para reativar, use o menu Funcionários > Desativados.')
    return redirect('lista_funcionarios')


@login_required
@somente_post
@tratar_erros
def reativa_funcionario(request, id_funcionario):
    func = get_object_or_404(TbFuncionario, id_funcionario=id_funcionario)
    bloqueio = _bloquear_se_anonimizado(request, func, 'lista_funcionarios_desativos')
    if bloqueio:
        return bloqueio
    bloqueio = _bloquear_se_admin(request, func)
    if bloqueio:
        return bloqueio
    func.flag_ativo = 'S'
    func.save(update_fields=['flag_ativo'])
    _sincronizar_login(func)
    messages.success(request, f'{func} foi reativado(a).')
    return redirect('lista_funcionarios')


@login_required
@tratar_erros
def lista_funcionarios_desativos(request):
    lista = TbFuncionario.objects.filter(flag_ativo='N')
    return render(request, 'gerencias/lista_funcionarios_desativados.html', {'lista': lista})


@login_required
@somente_post
@tratar_erros
def atualiza_funcionario(request):
    funcionario = _buscar_por_id_ou_404(TbFuncionario, request.POST.get('id_funcionario'))
    bloqueio = _bloquear_se_anonimizado(request, funcionario, 'lista_funcionarios')
    if bloqueio:
        return bloqueio
    bloqueio = _bloquear_se_admin(request, funcionario)
    if bloqueio:
        return bloqueio
    novo_tipo = _buscar_por_id_ou_404(TbTipoFuncionario, request.POST.get('id_tipo'))
    if _tipo_e_admin(novo_tipo) and not request.user.is_superuser:
        logger.warning("%s tentou promover %s a administrador", request.user.username, funcionario.pk)
        messages.error(request, 'Somente um administrador pode tornar alguém administrador.')
        return redirect('editar_funcionario', id_funcionario=funcionario.pk)
    funcionario.id_tipo = novo_tipo
    funcionario.pnome = request.POST.get('pnome')
    funcionario.snome = request.POST.get('snome')

    cpf, erro = _ler_cpf(request, obrigatorio=True, permitir_mascara=True)
    if erro:
        messages.error(request, erro)
        return redirect('editar_funcionario', id_funcionario=funcionario.pk)
    if cpf is not None:
        if _cpf_duplicado(TbFuncionario, cpf, excluir_pk=funcionario.pk):
            messages.error(request, 'CPF já pertence a outro funcionário.')
            return redirect('editar_funcionario', id_funcionario=funcionario.pk)
        funcionario.cpf = cpf

    funcionario.telefone = somente_digitos(request.POST.get('telefone'))
    funcionario.endereco = request.POST.get('endereco')
    funcionario.complemento = request.POST.get('complemento')
    funcionario.bairro = request.POST.get('bairro')
    funcionario.cidade = request.POST.get('cidade')
    funcionario.estado = request.POST.get('estado')
    funcionario.flag_ativo = request.POST.get('flag_ativo') or funcionario.flag_ativo
    if not _salvar_com_cpf_unico(funcionario):
        messages.error(request, 'CPF já pertence a outro funcionário.')
        return redirect('editar_funcionario', id_funcionario=funcionario.pk)
    _sincronizar_login(funcionario)
    messages.success(request, f'Cadastro de {funcionario} atualizado.')
    return redirect('lista_funcionarios')


def _tela_editar_funcionario(request, funcionario, erros_acesso=None, form_acesso=None, status=200):
    login = _usuario_do_funcionario(funcionario)
    return render(request, 'gerencias/editar_funcionario.html', {
        'dados': [funcionario],
        'pode_criar_admin': request.user.is_superuser,
        'login': login,
        'pode_trocar_senha': _pode_trocar_senha(request, login),
        'pode_criar_acesso': request.user.is_superuser,
        'trocando_a_propria': login is not None and login.pk == request.user.pk,
        'erros_acesso': erros_acesso or {},
        'form_acesso': form_acesso or {},
    }, status=status)


@login_required
@tratar_erros
def editar_funcionario(request, id_funcionario):
    funcionario = get_object_or_404(TbFuncionario, id_funcionario=id_funcionario)
    bloqueio = _bloquear_se_anonimizado(request, funcionario, 'lista_funcionarios')
    if bloqueio:
        return bloqueio
    bloqueio = _bloquear_se_admin(request, funcionario)
    if bloqueio:
        return bloqueio
    return _tela_editar_funcionario(request, funcionario)


@login_required
@admin_required
@somente_post
@tratar_erros
def criar_acesso_funcionario(request, id_funcionario):
    """Cria o login de um funcionário cadastrado antes do acesso por senha."""
    funcionario = get_object_or_404(TbFuncionario, id_funcionario=id_funcionario)
    bloqueio = _bloquear_se_anonimizado(request, funcionario, 'lista_funcionarios')
    if bloqueio:
        return bloqueio
    bloqueio = _bloquear_se_admin(request, funcionario)
    if bloqueio:
        return bloqueio
    if _usuario_do_funcionario(funcionario) is not None:
        messages.error(request, 'Este funcionário já tem acesso ao sistema.')
        return redirect('editar_funcionario', id_funcionario=funcionario.pk)

    usuario = (request.POST.get('usuario') or '').strip()
    erros = {}
    erro = _erro_usuario(usuario)
    if erro:
        erros['usuario'] = erro
    novo_login = User(username=usuario, first_name=funcionario.pnome or '', last_name=funcionario.snome or '')
    erros.update(_erros_senha(request.POST.get('senha') or '', request.POST.get('senha2') or '', novo_login))
    if erros:
        messages.error(request, 'Confira os campos de acesso destacados em vermelho.')
        return _tela_editar_funcionario(request, funcionario, erros, {'usuario': usuario}, status=400)

    try:
        with transaction.atomic():
            login = User.objects.create_user(
                username=usuario, password=request.POST['senha'],
                first_name=(funcionario.pnome or '')[:150], last_name=(funcionario.snome or '')[:150],
                is_staff=True, is_superuser=_funcionario_e_admin(funcionario),
                is_active=funcionario.flag_ativo == 'S',
            )
            TbFuncionarioUsuario.objects.create(funcionario=funcionario, usuario=login)
    except IntegrityError:
        messages.error(request, 'Este nome de usuário acabou de ser usado por outra pessoa. Escolha outro.')
        return _tela_editar_funcionario(request, funcionario, {}, {'usuario': usuario}, status=400)

    _registrar_auditoria(request, 'CRIACAO_ACESSO', f'/func/{funcionario.pk}')
    messages.success(request, f'Acesso criado para {funcionario}. Login: {login.username}')
    return redirect('editar_funcionario', id_funcionario=funcionario.pk)


@login_required
@somente_post
@tratar_erros
def trocar_senha_funcionario(request, id_funcionario):
    funcionario = get_object_or_404(TbFuncionario, id_funcionario=id_funcionario)
    bloqueio = _bloquear_se_anonimizado(request, funcionario, 'lista_funcionarios')
    if bloqueio:
        return bloqueio
    bloqueio = _bloquear_se_admin(request, funcionario)
    if bloqueio:
        return bloqueio
    login = _usuario_do_funcionario(funcionario)
    if login is None:
        messages.error(request, 'Este funcionário ainda não tem acesso. Crie o acesso primeiro.')
        return redirect('editar_funcionario', id_funcionario=funcionario.pk)
    if not _pode_trocar_senha(request, login):
        # Senão um membro poderia trocar a senha de um colega e entrar como ele.
        logger.warning("%s tentou trocar a senha de %s", request.user.username, login.username)
        messages.error(request, 'Somente um administrador pode trocar a senha de outra pessoa.')
        return redirect('editar_funcionario', id_funcionario=funcionario.pk)

    senha = request.POST.get('senha') or ''
    erros = _erros_senha(senha, request.POST.get('senha2') or '', login)
    if login.pk == request.user.pk and not login.check_password(request.POST.get('senha_atual') or ''):
        # Trocar a PRÓPRIA senha exige a atual: quem achar o computador de um
        # colega aberto não consegue trocar a senha dele.
        erros['senha_atual'] = 'A senha atual não confere.'
    if erros:
        messages.error(request, 'Confira a nova senha.')
        return _tela_editar_funcionario(request, funcionario, erros, status=400)

    login.set_password(senha)
    login.save(update_fields=['password'])
    if login.pk == request.user.pk:
        # Trocou a própria senha: continua logado (senão o Django encerraria a sessão).
        update_session_auth_hash(request, login)
    _registrar_auditoria(request, 'TROCA_SENHA', f'/func/{funcionario.pk}')
    messages.success(request, f'Senha de {login.username} alterada.')
    return redirect('editar_funcionario', id_funcionario=funcionario.pk)


# ==========================================
# BLOCO RESPONSÁVEL (FAMÍLIAS)
# ==========================================
# Campos obrigatórios do cadastro de família (os mesmos marcados no formulário).
CAMPOS_OBRIGATORIOS_RESPONSAVEL = {
    'pnome': 'Informe o primeiro nome.',
    'snome': 'Informe o sobrenome.',
    'dt_nasc': 'Informe a data de nascimento.',
    'endereco': 'Informe o endereço.',
    'bairro': 'Informe o bairro.',
    'cidade': 'Informe a cidade.',
    'estado': 'Escolha o estado.',
}
CAMPOS_OBRIGATORIOS_FILHO = {
    'pnome': 'Informe o nome da criança.',
    'snome': 'Informe o sobrenome da criança.',
    'dt_nasc': 'Informe a data de nascimento.',
    'sexo': 'Escolha o sexo.',
}
CAMPOS_FILHO = ('pnome', 'snome', 'dt_nasc', 'cpf', 'sexo', 'roupa', 'sapato', 'outra_ong')
PADRAO_CAMPO_FILHO = re.compile(r'^filho-(\d+)-\w+$')


def _validar_data_nascimento(texto):
    """Aceita dd/mm/aaaa ou aaaa-mm-dd. Devolve (data em dd/mm/aaaa, mensagem de erro ou None)."""
    normal = _normalizar_data(texto)
    data = _parse_data_br(normal)
    if data is None:
        return normal, 'Data inválida. Use dd/mm/aaaa.'
    if data.date() > date.today():
        return normal, 'A data não pode ser no futuro.'
    return normal, None


def _validar_filho(f, excluir_pk=None, cpfs_vistos=None):
    """
    Confere os dados de UMA criança (cadastro de família, adicionar criança e
    editar criança usam a mesma regra). `f` tem os campos de CAMPOS_FILHO.
    Obrigatórios: nome, sobrenome, data de nascimento e sexo. CPF, roupa e
    sapato podem ficar em branco (crianças pequenas muitas vezes não têm).
    Preenche f['cpf_limpo'] (None = manter o CPF atual, na edição) e devolve os erros.
    """
    erros = {c: msg for c, msg in CAMPOS_OBRIGATORIOS_FILHO.items() if not f.get(c)}
    if f.get('dt_nasc') and 'dt_nasc' not in erros:
        f['dt_nasc'], erro = _validar_data_nascimento(f['dt_nasc'])
        if erro:
            erros['dt_nasc'] = erro
    if f.get('sexo') and f['sexo'] not in ('M', 'F'):
        erros['sexo'] = 'Escolha o sexo.'
    if f.get('sapato') and not (f['sapato'].isdigit() and len(f['sapato']) <= 3):
        erros['sapato'] = 'Use só números (ex.: 28).'

    bruto = f.get('cpf', '')
    if excluir_pk is not None and ('*' in bruto or bruto.startswith(PREFIXO_ANONIMO)):
        f['cpf_limpo'] = None          # edição: a máscara voltou como estava, mantém o CPF
        return erros
    cpf = limpar_cpf(bruto)
    if cpf:
        vistos = cpfs_vistos if cpfs_vistos is not None else {}
        if not cpf_valido(cpf):
            erros['cpf'] = 'CPF inválido. Confira os números.'
        elif cpf in vistos:
            erros['cpf'] = f'É o mesmo CPF da criança {vistos[cpf]} deste cadastro.'
        elif _cpf_duplicado(TbFilhosResponsavel, cpf, excluir_pk=excluir_pk):
            erros['cpf'] = 'Já existe uma criança cadastrada com este CPF.'
    f['cpf_limpo'] = cpf
    return erros


def _filho_do_post(request, n):
    return {campo: (request.POST.get(f'filho-{n}-{campo}') or '').strip() for campo in CAMPOS_FILHO}


def _ler_filhos_do_formulario(request):
    """
    Lê as crianças do cadastro de família. Cada bloco do formulário manda seus
    campos com um número: filho-0-pnome, filho-0-cpf, filho-3-pnome...
    (números de blocos removidos simplesmente não aparecem).
    Devolve uma lista de dicionários, na ordem dos blocos, com os erros de cada um.
    """
    indices = sorted({int(PADRAO_CAMPO_FILHO.match(k).group(1)) for k in request.POST if PADRAO_CAMPO_FILHO.match(k)})
    filhos, cpfs_vistos = [], {}
    for n in indices:
        f = _filho_do_post(request, n)
        f['erros'] = _validar_filho(f, cpfs_vistos=cpfs_vistos)
        if f['cpf_limpo']:
            cpfs_vistos.setdefault(f['cpf_limpo'], len(filhos) + 1)
        filhos.append(f)
    return filhos


def _criar_filho(request, responsavel, f, agora):
    return TbFilhosResponsavel.objects.create(
        id_responsavel=responsavel,
        id_usuario_cad_id=request.user.id,
        pnome=f['pnome'],
        snome=f['snome'],
        data_nascimento=f['dt_nasc'],
        cpf=f['cpf_limpo'] or None,
        sexo=f['sexo'],
        numero_roupa=f['roupa'] or None,
        numero_sapato=int(f['sapato']) if f['sapato'] else None,
        cadastro_outra_ong='S' if f['outra_ong'] == 'S' else 'N',
        data_cadastro=agora,
        flag_ativo='S',
    )


def _tela_novo_responsavel(request, form=None, erros=None, filhos=None, status=200):
    return render(request, 'gerencias/novo_responsavel.html', {
        'form': form or {}, 'erros': erros or {}, 'filhos': filhos or [],
    }, status=status)


@login_required
def novo_responsavel(request):
    return _tela_novo_responsavel(request)


@login_required
@tratar_erros
def insere_novo_responsavel(request):
    """Cadastra a família: o responsável e as crianças, tudo junto."""
    if request.method != 'POST':
        return redirect('novo_responsavel')

    dados = {k: (v or '').strip() for k, v in request.POST.items()
             if k != 'csrfmiddlewaretoken' and not k.startswith('filho-')}
    erros = {c: msg for c, msg in CAMPOS_OBRIGATORIOS_RESPONSAVEL.items() if not dados.get(c)}
    cpf, erro = _ler_cpf(request, obrigatorio=True)
    if erro:
        erros['cpf'] = erro
    elif _cpf_duplicado(TbCadastroResponsavel, cpf):
        erros['cpf'] = 'Já existe um responsável cadastrado com este CPF.'
    data_nascimento = ''
    if dados.get('dt_nasc'):
        data_nascimento, erro = _validar_data_nascimento(dados['dt_nasc'])
        if erro:
            erros['dt_nasc'] = erro

    filhos = _ler_filhos_do_formulario(request)
    if erros or any(f['erros'] for f in filhos):
        messages.error(request, 'Confira os campos destacados em vermelho.')
        return _tela_novo_responsavel(request, dados, erros, filhos, status=400)

    agora = timezone.now()
    try:
        # Responsável e crianças juntos: se algo falhar, nada é gravado
        # (nada de família pela metade no banco).
        with transaction.atomic():
            responsavel = TbCadastroResponsavel.objects.create(
                id_usuario_cad_id=request.user.id,
                pnome=dados['pnome'],
                snome=dados['snome'],
                cpf=cpf,
                data_nascimento=data_nascimento,
                flag_responsavel_trabalha=dados.get('resp_trabalha') or 'N',
                flag_conjuge=dados.get('flag_conjuge') or 'N',
                flag_conjuge_trabalha=dados.get('conjuge_trabalha') or 'N',
                endereco=dados['endereco'],
                complemento=dados.get('complemento'),
                bairro=dados['bairro'],
                cidade=dados['cidade'],
                estado=dados['estado'],
                observacoes=dados.get('obs'),
                data_cadastro=agora,
                # Explícitos de propósito: sem eles o ORM mandaria NULL e o
                # cadastro sumiria de todas as listas.
                flag_ativo='S',
                flag_validado='N',
            )
            for f in filhos:
                _criar_filho(request, responsavel, f, agora)
    except IntegrityError:
        # Raro: outra pessoa cadastrou um destes CPFs no mesmo instante.
        messages.error(request, 'Um dos CPFs acabou de ser cadastrado por outra pessoa. Confira e tente de novo.')
        return _tela_novo_responsavel(request, dados, {}, filhos, status=400)

    _registrar_auditoria(request, 'CADASTRO_FAMILIA', f'/resp/{responsavel.pk}')
    messages.success(request, f'Família de {responsavel} cadastrada com {len(filhos)} criança(s). '
                              'Ela aparece em "não validados" até ser validada.')
    return redirect('lista_responsavel_nval')


@login_required
@tratar_erros
def lista_responsavel(request):
    responsavel = TbCadastroResponsavel.objects.filter(flag_ativo='S', flag_validado='S')
    return render(request, 'gerencias/lista_responsavel.html', {'dados': responsavel, 'titulo': 'Responsáveis Validados'})


@login_required
@tratar_erros
def lista_responsavel_nval(request):
    responsavel = TbCadastroResponsavel.objects.filter(flag_ativo='S', flag_validado='N')
    return render(request, 'gerencias/lista_responsavel_nval.html', {'dados': responsavel, 'titulo': 'Responsáveis não Validados'})


@login_required
@tratar_erros
def lista_responsavel_des(request):
    responsavel = TbCadastroResponsavel.objects.filter(flag_ativo='N')
    return render(request, 'gerencias/lista_responsavel_des.html', {'dados': responsavel, 'titulo': 'Responsáveis Desativados'})


@login_required
@tratar_erros
def edit_responsavel(request, id_responsavel):
    responsavel = get_object_or_404(TbCadastroResponsavel, pk=id_responsavel)
    bloqueio = _bloquear_se_anonimizado(request, responsavel, 'lista_responsavel_des')
    if bloqueio:
        return bloqueio
    return render(request, 'gerencias/editar_responsavel.html', {'dados': [responsavel], 'titulo': 'Responsável'})


@login_required
@somente_post
@tratar_erros
def atualiza_responsavel(request):
    responsavel = _buscar_por_id_ou_404(TbCadastroResponsavel, request.POST.get('id_responsavel'))
    bloqueio = _bloquear_se_anonimizado(request, responsavel, 'lista_responsavel_des')
    if bloqueio:
        return bloqueio
    # Mesmos obrigatórios do cadastro (a data em branco mantém a que já existe).
    faltando = [msg for campo, msg in CAMPOS_OBRIGATORIOS_RESPONSAVEL.items()
                if campo != 'dt_nasc' and not (request.POST.get(campo) or '').strip()]
    if faltando:
        messages.error(request, ' '.join(faltando))
        return redirect('edit_responsavel', id_responsavel=responsavel.pk)
    responsavel.pnome = request.POST.get('pnome').strip()
    responsavel.snome = request.POST.get('snome').strip()

    cpf, erro = _ler_cpf(request, obrigatorio=True, permitir_mascara=True)
    if erro:
        messages.error(request, erro)
        return redirect('edit_responsavel', id_responsavel=responsavel.pk)
    if cpf is not None:
        if _cpf_duplicado(TbCadastroResponsavel, cpf, excluir_pk=responsavel.pk):
            messages.error(request, 'CPF já pertence a outro responsável.')
            return redirect('edit_responsavel', id_responsavel=responsavel.pk)
        responsavel.cpf = cpf

    if (request.POST.get('dt_nasc') or '').strip():  # em branco não apaga a data que já existe
        dt_nasc, erro = _validar_data_nascimento(request.POST['dt_nasc'])
        if erro:
            messages.error(request, f'Data de nascimento: {erro}')
            return redirect('edit_responsavel', id_responsavel=responsavel.pk)
        responsavel.data_nascimento = dt_nasc
    responsavel.flag_responsavel_trabalha = request.POST.get('resp_trabalha')
    responsavel.flag_conjuge = request.POST.get('flag_conjuge')
    responsavel.flag_conjuge_trabalha = request.POST.get('conjuge_trabalha')
    responsavel.endereco = request.POST.get('endereco')
    responsavel.complemento = request.POST.get('complemento')
    responsavel.bairro = request.POST.get('bairro')
    responsavel.cidade = request.POST.get('cidade')
    responsavel.estado = request.POST.get('estado')
    responsavel.flag_validado = request.POST.get('validado') or responsavel.flag_validado
    ativo_antes = responsavel.flag_ativo
    responsavel.flag_ativo = request.POST.get('ativo') or responsavel.flag_ativo
    responsavel.ultima_atualizacao = timezone.now()
    if not _salvar_com_cpf_unico(responsavel):
        messages.error(request, 'CPF já pertence a outro responsável.')
        return redirect('edit_responsavel', id_responsavel=responsavel.pk)
    if responsavel.flag_ativo != ativo_antes:
        # Mudou a situação no formulário: as crianças acompanham o responsável.
        criancas, removidos = _definir_situacao_familia(responsavel, responsavel.flag_ativo)
        situacao = 'desativada' if responsavel.flag_ativo == 'N' else 'reativada'
        messages.success(request, f'Família de {responsavel} {situacao} ({criancas} criança(s) também).'
                                  + _aviso_apadrinhamentos(removidos))
    return redirect('lista_responsavel')


@login_required
@somente_post
@tratar_erros
def valida_responsavel(request, id_responsavel):
    responsavel = get_object_or_404(TbCadastroResponsavel, pk=id_responsavel)
    responsavel.flag_validado = 'S'
    responsavel.save(update_fields=['flag_validado'])
    return redirect('lista_responsavel')


@login_required
@somente_post
@tratar_erros
def desativa_responsavel(request, id_responsavel):
    responsavel = get_object_or_404(TbCadastroResponsavel, pk=id_responsavel)
    with transaction.atomic():
        criancas, removidos = _definir_situacao_familia(responsavel, 'N')
    messages.success(request, f'Família de {responsavel} desativada ({criancas} criança(s) também desativada(s)).'
                              + _aviso_apadrinhamentos(removidos))
    return redirect('lista_responsavel')


@login_required
@somente_post
@tratar_erros
def reativa_responsavel(request, id_responsavel):
    responsavel = get_object_or_404(TbCadastroResponsavel, pk=id_responsavel)
    bloqueio = _bloquear_se_anonimizado(request, responsavel, 'lista_responsavel_des')
    if bloqueio:
        return bloqueio
    with transaction.atomic():
        criancas, _ = _definir_situacao_familia(responsavel, 'S')
    messages.success(request, f'Família de {responsavel} reativada ({criancas} criança(s) também reativada(s)).')
    return redirect('lista_responsavel')


# ==========================================
# BLOCO FILHOS (CRIANÇAS)
# ==========================================
@login_required
@tratar_erros
def lista_filhos(request, id_responsavel):
    registros = TbFilhosResponsavel.objects.select_related('id_responsavel').filter(
        id_responsavel=id_responsavel, flag_ativo='S'
    ).order_by('-data_cadastro')
    responsavel = TbCadastroResponsavel.objects.filter(id_responsavel=id_responsavel).first()
    responsavel_nome = f"{responsavel.pnome} {responsavel.snome}" if responsavel else ""
    contexto = {
        'lista': registros,
        'id_responsavel': id_responsavel,
        'responsavel_nome': responsavel_nome,
        'titulo': 'Crianças Cadastradas',
    }
    return render(request, 'gerencias/lista_filhos.html', contexto)


@login_required
@tratar_erros
def lista_filhos_total(request):
    lista = TbFilhosResponsavel.objects.select_related('id_responsavel').all().order_by('id_responsavel')
    return render(request, 'gerencias/lista_filhos_total.html', {'lista': lista})


@login_required
@somente_post
@tratar_erros
def desativar_filho(request, id_responsavel):
    filho = _buscar_por_id_ou_404(TbFilhosResponsavel, request.POST.get('id_filho'))
    with transaction.atomic():
        filho.flag_ativo = 'N'
        filho.save(update_fields=['flag_ativo'])
        removidos = _remover_apadrinhamentos_das_criancas([filho])
    messages.success(request, f'{filho} foi desativado(a).' + _aviso_apadrinhamentos(removidos))
    return redirect('lista_filhos', id_responsavel=id_responsavel)


@login_required
@somente_post
@tratar_erros
def reativar_filho(request, id_filho):
    filho = get_object_or_404(TbFilhosResponsavel, id_filho=id_filho)
    bloqueio = _bloquear_se_anonimizado(request, filho, 'lista_filhos', filho.id_responsavel_id)
    if bloqueio:
        return bloqueio
    filho.flag_ativo = 'S'
    filho.save(update_fields=['flag_ativo'])
    return redirect('lista_filhos', id_responsavel=filho.id_responsavel_id)


def _tela_filho(request, template, responsavel, filho_form, erros=None, registro=None, status=200):
    return render(request, template, {
        'dados': registro or responsavel,
        'responsavel': responsavel,
        'id_responsavel': responsavel.pk,
        'filho': filho_form,
        'erros': erros or {},
        'titulo': 'Editar Criança' if registro else 'Nova Criança',
    }, status=status)


@login_required
@tratar_erros
def novo_filho(request, id_responsavel):
    responsavel = get_object_or_404(TbCadastroResponsavel, id_responsavel=id_responsavel)
    filho = {'snome': responsavel.snome or ''}     # o sobrenome da família já vem preenchido
    return _tela_filho(request, 'gerencias/novo_filho.html', responsavel, filho)


@login_required
@tratar_erros
def editar_filho(request, id_filho):
    registro = get_object_or_404(TbFilhosResponsavel, id_filho=id_filho)
    bloqueio = _bloquear_se_anonimizado(request, registro, 'lista_filhos', registro.id_responsavel_id)
    if bloqueio:
        return bloqueio
    filho = {
        'pnome': registro.pnome or '', 'snome': registro.snome or '',
        'dt_nasc': registro.data_nascimento or '', 'cpf': registro.cpf_mascarado,
        'sexo': registro.sexo or '', 'roupa': registro.numero_roupa or '',
        'sapato': '' if registro.numero_sapato is None else str(registro.numero_sapato),
        'outra_ong': registro.cadastro_outra_ong or 'N',
    }
    return _tela_filho(request, 'gerencias/editar_filho.html', registro.id_responsavel, filho, registro=registro)


@login_required
@somente_post
@tratar_erros
def insere_novo_filho(request):
    """Adiciona UMA criança a uma família já cadastrada (mesmas regras do cadastro de família)."""
    responsavel = _buscar_por_id_ou_404(TbCadastroResponsavel, request.POST.get('responsavel'))
    f = _filho_do_post(request, 0)
    erros = _validar_filho(f)
    if erros:
        messages.error(request, 'Confira os campos destacados em vermelho.')
        return _tela_filho(request, 'gerencias/novo_filho.html', responsavel, f, erros, status=400)
    try:
        with transaction.atomic():
            novo = _criar_filho(request, responsavel, f, timezone.now())
    except IntegrityError:
        messages.error(request, 'Este CPF acabou de ser cadastrado por outra pessoa. Confira e tente de novo.')
        return _tela_filho(request, 'gerencias/novo_filho.html', responsavel, f, status=400)
    messages.success(request, f'{novo} foi cadastrado(a) na família de {responsavel}.')
    return redirect('lista_filhos', id_responsavel=responsavel.pk)


@login_required
@somente_post
@tratar_erros
def atualiza_filho(request, id_filho):
    filho = get_object_or_404(TbFilhosResponsavel, id_filho=id_filho)
    bloqueio = _bloquear_se_anonimizado(request, filho, 'lista_filhos', filho.id_responsavel_id)
    if bloqueio:
        return bloqueio
    # O responsável vem do próprio registro, não do formulário (não dá para
    # "mudar" a criança de família alterando um campo escondido).
    responsavel = filho.id_responsavel
    f = _filho_do_post(request, 0)
    erros = _validar_filho(f, excluir_pk=filho.pk)
    if erros:
        messages.error(request, 'Confira os campos destacados em vermelho.')
        return _tela_filho(request, 'gerencias/editar_filho.html', responsavel, f, erros, registro=filho, status=400)

    filho.pnome = f['pnome']
    filho.snome = f['snome']
    filho.data_nascimento = f['dt_nasc']
    if f['cpf_limpo'] is not None:          # None = a máscara voltou como estava: mantém o CPF
        filho.cpf = f['cpf_limpo'] or None
    filho.sexo = f['sexo']
    # Em branco = apagar (antes o número antigo voltava, não dava para deixar vazio).
    filho.numero_roupa = f['roupa'] or None
    filho.numero_sapato = int(f['sapato']) if f['sapato'] else None
    filho.cadastro_outra_ong = 'S' if f['outra_ong'] == 'S' else 'N'
    filho.data_atualizacao = timezone.now()
    if not _salvar_com_cpf_unico(filho):
        messages.error(request, 'Este CPF acabou de ser cadastrado por outra pessoa. Confira e tente de novo.')
        return _tela_filho(request, 'gerencias/editar_filho.html', responsavel, f, registro=filho, status=400)

    _registrar_auditoria(request, 'EDICAO_CRIANCA', f'/filho/edit/{id_filho}')
    messages.success(request, 'Dados da criança atualizados com sucesso.')
    return redirect('lista_filhos', id_responsavel=responsavel.pk)


@login_required
@tratar_erros
def buscar_filhos(request):
    resultados = []
    termo_busca = ''
    tipo_busca = 'nome'
    if request.method == 'POST':
        termo_busca = request.POST.get('termo_busca', '').strip()
        tipo_busca = request.POST.get('tipo_busca', 'nome')
        if termo_busca:
            ativos = TbFilhosResponsavel.objects.select_related('id_responsavel').filter(flag_ativo='S')
            if tipo_busca == 'nome':
                resultados = list(ativos.filter(Q(pnome__icontains=termo_busca) | Q(snome__icontains=termo_busca)))
            elif tipo_busca == 'idade':
                try:
                    idade_busca = int(termo_busca)
                    resultados = [f for f in ativos if calcular_idade(f.data_nascimento) == idade_busca]
                except ValueError:
                    termo_busca = 'Por favor, digite um número válido'

    for filho in resultados:
        filho.idade = calcular_idade(filho.data_nascimento)

    return render(request, 'gerencias/buscar_filhos.html', {
        'resultados': resultados,
        'termo_busca': termo_busca,
        'tipo_busca': tipo_busca,
        'total_resultados': len(resultados),
    })


# ==========================================
# BLOCO OFÍCIOS
# ==========================================
@login_required
@somente_post
@tratar_erros
def insere_novo_oficio(request):
    remetente = request.user.username
    destinatario = (request.POST.get('destinatario') or '').strip()
    texto = (request.POST.get('mensagem') or '').strip()
    if not destinatario or not texto:
        messages.error(request, 'Preencha o destinatário e a mensagem do ofício.')
        return redirect('novo_oficio')
    mensagem = f"Mensagem de {remetente} para {destinatario}: {texto}"
    TbOficios.objects.create(
        id_usuario_id=request.user.id,
        destinatario=destinatario,
        mensagem=mensagem,
        data_criacao=timezone.now(),
    )
    return redirect('lista_oficio')


@login_required
@tratar_erros
def novo_oficio(request):
    return render(request, 'gerencias/novo_oficio.html', {
        'usuario': request.user,
        'id_usuario_cad': request.user.id,
        'username': request.user.username,
    })


def _oficios_visiveis(user):
    """
    Quem vê cada ofício: quem enviou, o funcionário cujo login é o
    destinatário, e quem tem permissão LGPD (superusuário ou grupo LGPD).
    Antes, qualquer funcionário lia o ofício de qualquer outro.
    """
    oficios = TbOficios.objects.select_related('id_usuario')
    if pode_usar_lgpd(user):
        return oficios.all()
    return oficios.filter(Q(id_usuario_id=user.id) | Q(destinatario__iexact=user.username))


@login_required
@tratar_erros
def lista_oficio(request):
    lista = _oficios_visiveis(request.user).order_by('-data_criacao')
    primeiro = lista.first()
    return render(request, 'gerencias/lista_oficios.html', {
        'id_oficio': primeiro.id_oficio if primeiro else None,
        'lista': lista,
        'total': lista.count(),
    })


@login_required
@tratar_erros
def exibe_oficio(request, id_oficio):
    # 404 (e não 403) pra não confirmar que o ofício de outra pessoa existe.
    oficio = get_object_or_404(_oficios_visiveis(request.user), id_oficio=id_oficio)
    return render(request, 'gerencias/exibe_oficio.html', {
        'oficio': oficio,
        'id_oficio': id_oficio,
        'mensagem': oficio.mensagem,
        'remetente': oficio.id_usuario.username,
    })


@login_required
@lgpd_required
@somente_post
@tratar_erros
def excluir_oficio(request, id_oficio):
    TbOficios.objects.filter(id_oficio=id_oficio).delete()
    _registrar_auditoria(request, 'EXCLUSAO_OFICIO', f'/oficio/{id_oficio}')
    return redirect('lista_oficio')


# ==========================================
# BLOCO MADRINHAS E PADRINHOS
# ==========================================
def _ler_flag_anonimo(request):
    # Os templates enviam o campo como "anonimo"; aceitamos os dois nomes.
    return request.POST.get('flag_anonimo') or request.POST.get('anonimo') or 'N'


@login_required
@tratar_erros
def novo_madrinha_padrinho(request):
    return render(request, 'gerencias/novo_madrinha_padrinho.html', {
        'usuario': request.user,
        'id_usuario_cad': request.user.id,
    })


@login_required
@somente_post
@tratar_erros
def inserir_madrinha_padrinho(request):
    cpf, erro = _ler_cpf(request, obrigatorio=False)
    if erro:
        messages.error(request, erro)
        return redirect('novo_madrinha_padrinho')
    if _cpf_duplicado(TbMadrinhaPadrinho, cpf):
        messages.error(request, 'Já existe um padrinho/madrinha cadastrado com este CPF.')
        return redirect('lista_madrinha_padrinho')

    flag_anonimo = _ler_flag_anonimo(request)
    if flag_anonimo == 'S':
        pnome, snome = 'Anônimo', ''
    else:
        pnome = (request.POST.get('pnome') or '').strip()
        snome = (request.POST.get('snome') or '').strip()
        if not pnome:
            messages.error(request, 'Informe o nome do padrinho/madrinha (ou marque a opção de anônimo).')
            return redirect('novo_madrinha_padrinho')

    novo = _criar_com_cpf_unico(
        TbMadrinhaPadrinho,
        id_usuario_cad_id=request.user.id,
        cpf=cpf or None,
        flag_anonimo=flag_anonimo,
        pnome=pnome,
        snome=snome,
        endereco=request.POST.get('endereco'),
        complemento=request.POST.get('complemento'),
        bairro=request.POST.get('bairro'),
        cidade=request.POST.get('cidade'),
        estado=request.POST.get('estado'),
        flag_ativo=request.POST.get('flag_ativo') or 'S',
        data_cadastro=timezone.now(),
    )
    if novo is None:
        messages.error(request, 'Já existe um padrinho/madrinha cadastrado com este CPF.')
    return redirect('lista_madrinha_padrinho')


@login_required
@tratar_erros
def lista_madrinha_padrinho(request):
    termo = request.GET.get('q', '').strip()
    lista = TbMadrinhaPadrinho.objects.filter(flag_ativo='S').order_by('-data_cadastro')
    if termo:
        filtro = Q(pnome__icontains=termo) | Q(snome__icontains=termo)
        # Se o termo for um CPF (com ou sem pontos), busca também pelo hash.
        h = hash_cpf(termo)
        if h:
            filtro |= Q(cpf_hash=h)
        lista = lista.filter(filtro)
    return render(request, 'gerencias/listar_madrinhas_padrinhos.html', {'dados': lista, 'termo_busca': termo})


@login_required
@tratar_erros
def lista_madrinha_padrinho_desativados(request):
    lista = TbMadrinhaPadrinho.objects.filter(flag_ativo='N').order_by('-data_cadastro')
    return render(request, 'gerencias/listar_madrinhas_padrinhos_desativados.html', {'dados': lista})


@login_required
@tratar_erros
def editar_madrinha_padrinho(request, id_mad_pad):
    registro = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)
    bloqueio = _bloquear_se_anonimizado(request, registro, 'lista_madrinha_padrinho_desativados')
    if bloqueio:
        return bloqueio
    return render(request, 'gerencias/editar_madrinha_padrinho.html', {'registro': registro})


@login_required
@somente_post
@tratar_erros
def atualiza_madrinha_padrinho(request, id_mad_pad):
    registro = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)
    bloqueio = _bloquear_se_anonimizado(request, registro, 'lista_madrinha_padrinho_desativados')
    if bloqueio:
        return bloqueio

    cpf, erro = _ler_cpf(request, obrigatorio=False, permitir_mascara=True)
    if erro:
        messages.error(request, erro)
        return redirect('editar_madrinha_padrinho', id_mad_pad=registro.pk)
    if cpf is not None:
        if _cpf_duplicado(TbMadrinhaPadrinho, cpf, excluir_pk=registro.pk):
            messages.error(request, 'CPF já pertence a outro padrinho/madrinha.')
            return redirect('editar_madrinha_padrinho', id_mad_pad=registro.pk)
        registro.cpf = cpf or None

    registro.flag_anonimo = _ler_flag_anonimo(request)
    if registro.flag_anonimo != 'S' and not (request.POST.get('pnome') or '').strip():
        messages.error(request, 'Informe o nome do padrinho/madrinha (ou marque a opção de anônimo).')
        return redirect('editar_madrinha_padrinho', id_mad_pad=registro.pk)
    registro.pnome = request.POST.get('pnome', '').strip()
    registro.snome = request.POST.get('snome', '').strip()
    registro.endereco = request.POST.get('endereco', '').strip()
    registro.complemento = request.POST.get('complemento', '').strip()
    registro.bairro = request.POST.get('bairro', '').strip()
    registro.cidade = request.POST.get('cidade', '').strip()
    registro.estado = request.POST.get('estado', '').strip()
    ativo_antes = registro.flag_ativo
    registro.flag_ativo = request.POST.get('flag_ativo') or registro.flag_ativo
    registro.atualizacao_cad = timezone.now()
    if not _salvar_com_cpf_unico(registro):
        messages.error(request, 'CPF já pertence a outro padrinho/madrinha.')
        return redirect('editar_madrinha_padrinho', id_mad_pad=registro.pk)
    if registro.flag_ativo == 'N' and ativo_antes != 'N':
        removidos = _remover_apadrinhamentos(registro.pk)
        messages.success(request, f'Dados atualizados. {registro} ficou inativo(a) e saiu de '
                                  f'{removidos} apadrinhamento(s); essas crianças estão disponíveis de novo.')
    else:
        messages.success(request, 'Dados atualizados com sucesso!')
    return redirect('lista_madrinha_padrinho')


@login_required
@somente_post
@tratar_erros
def reativar_madrinha_padrinho(request, id_mad_pad):
    registro = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)
    bloqueio = _bloquear_se_anonimizado(request, registro, 'lista_madrinha_padrinho_desativados')
    if bloqueio:
        return bloqueio
    registro.flag_ativo = 'S'
    registro.atualizacao_cad = timezone.now()
    registro.save(update_fields=['flag_ativo', 'atualizacao_cad'])
    messages.success(request, 'Registro reativado com sucesso!')
    return redirect('lista_madrinha_padrinho')


@login_required
@tratar_erros
def apadrinhar_crianca(request, id_mad_pad):
    registro = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)
    criancas = TbFilhosResponsavel.objects.filter(flag_ativo='S').order_by('pnome')
    return render(request, 'gerencias/apadrinhar_crianca.html', {
        'registro': registro,
        'criancas': criancas,
        'titulo': 'Apadrinhar Criança',
    })


@login_required
@somente_post
@tratar_erros
def vincular_mad_pad_crianca(request):
    madrinha = _buscar_por_id_ou_404(TbMadrinhaPadrinho, request.POST.get('id_mad_pad'))
    crianca = _buscar_por_id_ou_404(TbFilhosResponsavel, request.POST.get('id_filho'))
    TbApadrinhamentoCrianca.objects.create(
        id_mad_pad_id=madrinha.id_mad_pad,
        id_filho_id=crianca.id_filho,
        data_cadastro=timezone.now(),
    )
    return redirect('lista_apadrinhamento')


@login_required
@tratar_erros
def lista_apadrinhamento(request):
    apadrinhamento = TbApadrinhamentoCrianca.objects.select_related('id_mad_pad', 'id_filho').all().order_by('-data_cadastro')
    return render(request, 'gerencias/lista_apadrinhamentos.html', {'registros': apadrinhamento})


# ==========================================
# BLOCO EVENTOS E ENTREGAS
# ==========================================
@login_required
@tratar_erros
def listar_eventos(request):
    # data_evento é texto 'dd/mm/aaaa'. Ordenar como texto põe 31/01 depois
    # de 01/12, por isso ordenamos pela data convertida (mais recente primeiro).
    # Datas inválidas vão para o fim da lista.
    eventos = TbEvento.objects.all()
    lista = sorted(
        eventos,
        key=lambda e: _parse_data_br(e.data_evento) or datetime.min,
        reverse=True,
    )
    return render(request, 'gerencias/listar_eventos.html', {'lista': lista})


@login_required
@tratar_erros
def novo_evento(request):
    return render(request, 'gerencias/novo_evento.html')


@login_required
@somente_post
@tratar_erros
def atualiza_evento(request, id_evento):
    evento = get_object_or_404(TbEvento, id_evento=id_evento)
    dados, erro = _validar_evento(request)
    if erro:
        messages.error(request, erro)
        return redirect('editar_evento', id_evento=id_evento)
    for campo, valor in dados.items():
        setattr(evento, campo, valor)
    evento.flag_finalizado = request.POST.get('flag_finalizado') or evento.flag_finalizado
    evento.save()
    return redirect('listar_eventos')


@login_required
@somente_post
@tratar_erros
def insere_novo_evento(request):
    dados, erro = _validar_evento(request)
    if erro:
        messages.error(request, erro)
        return redirect('novo_evento')
    TbEvento.objects.create(
        **dados,
        flag_finalizado=request.POST.get('flag_finalizado') or 'N',
        data_cadastro=timezone.now(),
    )
    return redirect('listar_eventos')


@login_required
@tratar_erros
def editar_evento(request, id_evento):
    evento = get_object_or_404(TbEvento, id_evento=id_evento)
    return render(request, 'gerencias/editar_evento.html', {'registro': evento})


@login_required
@somente_post
@tratar_erros
def finalizar_evento(request, id_evento):
    """Encerra o evento e, junto, todas as entregas dele que ainda estavam pendentes."""
    evento = get_object_or_404(TbEvento, id_evento=id_evento)
    with transaction.atomic():
        evento.flag_finalizado = 'S'
        evento.save(update_fields=['flag_finalizado'])
        finalizadas = (TbEntrega.objects.filter(id_evento=evento.id_evento)
                       .exclude(flag_finalizado='S')
                       .update(flag_finalizado='S', data_chegada=timezone.now()))
    texto = f'Evento "{evento.nome}" finalizado.'
    if finalizadas:
        texto += f' {finalizadas} entrega(s) dele também foram finalizadas.'
    messages.success(request, texto)
    return redirect('listar_eventos')


@login_required
@somente_post
@tratar_erros
def finalizar_entrega(request, id_entrega):
    """Marca UMA entrega como feita (o presente chegou à criança)."""
    entrega = get_object_or_404(TbEntrega, id_entrega=id_entrega)
    if entrega.flag_finalizado != 'S':
        entrega.flag_finalizado = 'S'
        entrega.data_chegada = timezone.now()
        entrega.save(update_fields=['flag_finalizado', 'data_chegada'])
    messages.success(request, f'Entrega {entrega.id_entrega} finalizada.')
    return redirect('listar_entregas')


@login_required
@somente_post
@tratar_erros
def reabrir_entrega(request, id_entrega):
    """Desfaz uma finalização feita por engano: a entrega volta a ficar pendente."""
    entrega = get_object_or_404(TbEntrega, id_entrega=id_entrega)
    evento = TbEvento.objects.filter(id_evento=entrega.id_evento).first()
    if evento is not None and evento.flag_finalizado == 'S':
        messages.error(request, f'O evento "{evento.nome}" já foi finalizado. '
                                'Uma entrega de evento finalizado não pode voltar a ficar pendente.')
        return redirect('listar_entregas')
    if entrega.flag_finalizado == 'S':
        entrega.flag_finalizado = 'N'
        entrega.data_chegada = None
        entrega.save(update_fields=['flag_finalizado', 'data_chegada'])
    messages.success(request, f'Entrega {entrega.id_entrega} voltou a ficar pendente.')
    return redirect('listar_entregas')


@login_required
@tratar_erros
def listar_entregas(request):
    entregas = list(TbEntrega.objects.all().order_by('-id_evento'))
    # A tabela de entregas guarda só os números (id) do evento, do apoiador e da
    # criança. Buscamos os nomes de uma vez (3 consultas no total, não 3 por linha).
    eventos = TbEvento.objects.in_bulk({e.id_evento for e in entregas})
    apoiadores = TbMadrinhaPadrinho.objects.only('id_mad_pad', 'pnome', 'snome').in_bulk(
        {e.id_mad_pad for e in entregas if e.id_mad_pad})
    criancas = TbFilhosResponsavel.objects.only('id_filho', 'pnome', 'snome').in_bulk(
        {e.id_crianca for e in entregas if e.id_crianca})
    for entrega in entregas:
        entrega.evento = eventos.get(entrega.id_evento)
        entrega.apoiador = apoiadores.get(entrega.id_mad_pad)
        entrega.crianca = criancas.get(entrega.id_crianca)
    return render(request, 'gerencias/listar_entregas.html', {'lista': entregas})


def _ler_entrega(request):
    return (_buscar_por_id(TbEvento, request.POST.get('id_evento')),
            _buscar_por_id(TbMadrinhaPadrinho, request.POST.get('id_mad_pad')),
            _buscar_por_id(TbFilhosResponsavel, request.POST.get('id_crianca')))


def _aviso_entrega_incompleta(evento, madrinha, crianca):
    faltando = [nome for nome, obj in (('o evento', evento), ('o padrinho/madrinha', madrinha),
                                       ('a criança', crianca)) if obj is None]
    return 'Escolha ' + ', '.join(faltando) + ' para registrar a entrega.'


def _contexto_entrega():
    return {
        'criancas': TbFilhosResponsavel.objects.filter(flag_ativo='S').order_by('pnome'),
        'mad_pad': TbMadrinhaPadrinho.objects.filter(flag_ativo='S').order_by('pnome'),
    }


@login_required
@tratar_erros
def nova_entrega(request):
    contexto = _contexto_entrega()
    contexto['evento'] = TbEvento.objects.all().order_by('-id_evento')
    return render(request, 'gerencias/nova_entrega.html', contexto)


@login_required
@somente_post
@tratar_erros
def insere_nova_entrega(request):
    evento, madrinha, crianca = _ler_entrega(request)
    if not (evento and madrinha and crianca):
        messages.error(request, _aviso_entrega_incompleta(evento, madrinha, crianca))
        return redirect('nova_entrega')
    TbEntrega.objects.create(
        id_evento=evento.id_evento,
        id_mad_pad=madrinha.id_mad_pad,
        id_crianca=crianca.id_filho,
        endereco=evento.endereco,
        cidade=evento.cidade,
        bairro=evento.bairro,
        estado=evento.estado,
        data_cadastro=timezone.now(),
        flag_finalizado='N',
    )
    return redirect('listar_entregas')


@login_required
@tratar_erros
def editar_entrega(request, id_entrega):
    entrega = get_object_or_404(TbEntrega, id_entrega=id_entrega)
    contexto = _contexto_entrega()
    return render(request, 'gerencias/editar_entrega.html', {
        'entrega': entrega,
        'eventos': TbEvento.objects.all().order_by('-id_evento'),
        'criancas': contexto['criancas'],
        'madrinhas_padrinhos': contexto['mad_pad'],
    })


@login_required
@somente_post
@tratar_erros
def atualiza_entrega(request, id_entrega):
    entrega = get_object_or_404(TbEntrega, id_entrega=id_entrega)
    evento, madrinha_padrinho, crianca = _ler_entrega(request)
    if not (evento and madrinha_padrinho and crianca):
        messages.error(request, _aviso_entrega_incompleta(evento, madrinha_padrinho, crianca))
        return redirect('editar_entrega', id_entrega=id_entrega)

    entrega.id_evento = evento.id_evento
    entrega.id_mad_pad = madrinha_padrinho.id_mad_pad
    entrega.id_crianca = crianca.id_filho
    entrega.endereco = evento.endereco
    entrega.bairro = evento.bairro
    entrega.cidade = evento.cidade
    entrega.estado = evento.estado
    entrega.save()
    return redirect('listar_entregas')


# ==========================================
# BLOCO DIREITOS DO TITULAR (LGPD)
# Todas as views abaixo exigem o grupo LGPD (ou superusuário).
# ==========================================
def _resposta_json_download(dados, nome_arquivo):
    response = JsonResponse(dados, encoder=DjangoJSONEncoder, json_dumps_params={'ensure_ascii': False, 'indent': 4})
    response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    return response


@login_required
@lgpd_required
@tratar_erros
def exportar_dados_titular(request, id_mad_pad):
    titular = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)
    dados = {
        "Nome": titular.pnome,
        "Sobrenome": titular.snome,
        "Endereco": f"{titular.endereco}, {titular.complemento} - {titular.bairro}, {titular.cidade}/{titular.estado}",
        "Data_Cadastro": titular.data_cadastro,
        "Status_Ativo": titular.flag_ativo,
        "Criancas_Apadrinhadas": [
            {"Nome_Crianca": v.id_filho.pnome, "Data_Vinculo": v.data_cadastro}
            for v in TbApadrinhamentoCrianca.objects.select_related('id_filho').filter(id_mad_pad=id_mad_pad)
        ],
    }
    _registrar_auditoria(request, 'EXPORTACAO_LGPD', f'/padrinhos/{id_mad_pad}')
    return _resposta_json_download(dados, f"dados_padrinho_{id_mad_pad}.json")


@login_required
@lgpd_required
@somente_post
@tratar_erros
def anonimizar_titular(request, id_mad_pad):
    with transaction.atomic():
        titular = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)
        titular.pnome, titular.snome = "Titular", "Anonimizado (LGPD)"
        # Usar o próprio id garante que o valor é único, sem sorteio.
        titular.cpf = f"{PREFIXO_ANONIMO}{titular.pk}"
        _anonimizar_endereco(titular)
        titular.flag_anonimo, titular.flag_ativo = 'S', 'N'
        titular.atualizacao_cad = timezone.now()
        titular.save()  # o save() zera o cpf_hash automaticamente
        _remover_apadrinhamentos(titular.pk)
        TbEntrega.objects.filter(id_mad_pad=id_mad_pad).update(
            endereco="Endereço Anonimizado (LGPD)",
            bairro="Anonimizado",
        )
        _registrar_auditoria(request, 'ANONIMIZACAO_LGPD', f'/padrinhos/{id_mad_pad}')
    messages.success(request, 'Dados do titular anonimizados com sucesso.')
    return redirect('lista_madrinha_padrinho')


@login_required
@lgpd_required
@tratar_erros
def exportar_dados_funcionario(request, id_funcionario):
    func = get_object_or_404(TbFuncionario, id_funcionario=id_funcionario)
    dados = {
        "Nome": func.pnome,
        "Sobrenome": func.snome,
        "Telefone": func.telefone,
        "Endereco": func.endereco,
        "Bairro": func.bairro,
        "Cidade": func.cidade,
        "Estado": func.estado,
        "Status_Ativo": func.flag_ativo,
    }
    _registrar_auditoria(request, 'EXPORTACAO_FUNC', f'/func/{id_funcionario}')
    return _resposta_json_download(dados, f"dados_funcionario_{id_funcionario}.json")


@login_required
@lgpd_required
@somente_post
@tratar_erros
def anonimizar_funcionario(request, id_funcionario):
    func = get_object_or_404(TbFuncionario, id_funcionario=id_funcionario)
    bloqueio = _bloquear_se_admin(request, func)
    if bloqueio:
        return bloqueio
    with transaction.atomic():
        func.pnome, func.snome = "Funcionário", "Anonimizado (LGPD)"
        func.cpf = f"{PREFIXO_ANONIMO}{func.pk}"
        func.telefone = "Removido"
        _anonimizar_endereco(func)
        func.flag_ativo = 'N'
        func.save()
        usuario = _usuario_do_funcionario(func)
        if usuario is not None:
            # O login também perde os dados pessoais e deixa de funcionar.
            usuario.username = f'anonimizado-{func.pk}'
            usuario.first_name = usuario.last_name = usuario.email = ''
            usuario.is_active = False
            usuario.set_unusable_password()
            usuario.save()
        _registrar_auditoria(request, 'ANONIMIZACAO_FUNC', f'/func/{id_funcionario}')
    messages.success(request, 'Dados do funcionário anonimizados.')
    return redirect('lista_funcionarios')


@login_required
@lgpd_required
@tratar_erros
def exportar_dados_responsavel(request, id_responsavel):
    resp = get_object_or_404(TbCadastroResponsavel, id_responsavel=id_responsavel)
    dados = {
        "Nome": resp.pnome,
        "Sobrenome": resp.snome,
        "Data_Nascimento": resp.data_nascimento,
        "Endereco": resp.endereco,
        "Bairro": resp.bairro,
        "Cidade": resp.cidade,
        "Status_Ativo": resp.flag_ativo,
        "Dependentes": [
            {"Nome": f.pnome, "Data_Nascimento": f.data_nascimento, "Sexo": f.sexo}
            for f in TbFilhosResponsavel.objects.filter(id_responsavel=id_responsavel)
        ],
    }
    _registrar_auditoria(request, 'EXPORTACAO_RESP', f'/resp/{id_responsavel}')
    return _resposta_json_download(dados, f"dados_familia_{id_responsavel}.json")


@login_required
@lgpd_required
@somente_post
@tratar_erros
def anonimizar_responsavel(request, id_responsavel):
    with transaction.atomic():
        resp = get_object_or_404(TbCadastroResponsavel, id_responsavel=id_responsavel)
        resp.pnome, resp.snome = "Responsável", "Anonimizado (LGPD)"
        resp.cpf = f"{PREFIXO_ANONIMO}{resp.pk}"
        resp.data_nascimento = "01/01/1900"
        _anonimizar_endereco(resp)
        resp.observacoes = ""
        resp.url_image_familia = None
        resp.flag_ativo = 'N'
        resp.ultima_atualizacao = timezone.now()
        resp.save()

        filhos = list(TbFilhosResponsavel.objects.filter(id_responsavel=id_responsavel))
        for filho in filhos:
            filho.pnome, filho.snome = "Criança", "Anonimizada"
            filho.cpf = f"{PREFIXO_ANONIMO}{filho.pk}"
            filho.data_nascimento = "01/01/1900"
            filho.url_imagem = None
            filho.flag_ativo = 'N'
            filho.data_atualizacao = timezone.now()
            filho.save()

        if filhos:
            _remover_apadrinhamentos_das_criancas(filhos)
            # id_crianca é um IntegerField: precisa receber os NÚMEROS dos ids,
            # não os objetos (que causavam TypeError e erro 500).
            TbEntrega.objects.filter(id_crianca__in=[f.id_filho for f in filhos]).update(
                endereco="Endereço Anonimizado (LGPD)",
                bairro="Anonimizado",
            )

        _registrar_auditoria(request, 'ANONIMIZACAO_CASCATA', f'/resp/{id_responsavel}')
    messages.success(request, 'Responsável e dependentes anonimizados.')
    return redirect('lista_responsavel')
