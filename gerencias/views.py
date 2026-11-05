import logging
import re
from datetime import datetime, date
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from gerencias.cpf_utils import cpf_valido, hash_cpf, limpar_cpf, somente_digitos, PREFIXO_ANONIMO
from gerencias.models import (
    TbFuncionario, TbTipoFuncionario, TbCadastroResponsavel,
    TbFilhosResponsavel, TbOficios, TbMadrinhaPadrinho,
    TbApadrinhamentoCrianca, TbEvento, TbEntrega, TbLogAuditoria,
)

logger = logging.getLogger(__name__)

# Nome do grupo (Admin > Grupos) cujos membros podem exportar, anonimizar
# e excluir. Superusuários também podem.
GRUPO_LGPD = 'LGPD'


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
        user = request.user
        if not (user.is_superuser or user.groups.filter(name=GRUPO_LGPD).exists()):
            logger.warning("Acesso LGPD negado a %s em %s", user.username, request.path)
            return pagina_erro(
                request,
                mensagem="Você não tem permissão para esta ação. Fale com um administrador.",
                status=403,
            )
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


def _anonimizar_endereco(obj, estado='--'):
    obj.endereco = "Removido"
    obj.complemento = ""
    obj.bairro = "Removido"
    obj.cidade = "Removido"
    obj.estado = estado


# ==========================================
# PÁGINAS BASE
# ==========================================
def home(request):
    return render(request, 'gerencias/index.html')


def pagina_erro(request, mensagem="Ocorreu um erro interno no processamento.", status=500):
    return render(request, 'gerencias/pagina_erro.html', {'mensagem': mensagem}, status=status)


# ==========================================
# BLOCO FUNCIONÁRIOS
# ==========================================
@login_required
@tratar_erros
def lista_funcionarios(request):
    lista = TbFuncionario.objects.filter(flag_ativo='S')
    return render(request, 'gerencias/lista_funcionarios.html', {'lista': lista})


@login_required
@tratar_erros
def novo_funcionario(request):
    return render(request, 'gerencias/novo_funcionario.html')


@login_required
@somente_post
@tratar_erros
def insere_novo_funcionario(request):
    cpf, erro = _ler_cpf(request, obrigatorio=True)
    if erro:
        messages.error(request, erro)
        return redirect('novo_funcionario')
    if _cpf_duplicado(TbFuncionario, cpf):
        messages.error(request, 'Já existe um funcionário cadastrado com este CPF.')
        return redirect('novo_funcionario')

    rua_n = f"{request.POST.get('rua') or ''}, {request.POST.get('numero') or ''}"
    telefone = somente_digitos(request.POST.get('telefone'))

    novo = _criar_com_cpf_unico(
        TbFuncionario,
        id_tipo_id=request.POST.get('tp_funcionario'),
        pnome=request.POST.get('pnome'),
        snome=request.POST.get('snome'),
        cpf=cpf,
        telefone=telefone,
        endereco=rua_n,
        complemento=request.POST.get('comp'),
        bairro=request.POST.get('bairro'),
        cidade=request.POST.get('cidade'),
        estado=request.POST.get('estado'),
        flag_ativo=request.POST.get('flag') or 'S',
    )
    if novo is None:
        messages.error(request, 'Já existe um funcionário cadastrado com este CPF.')
        return redirect('novo_funcionario')
    messages.success(request, "Funcionário cadastrado com sucesso!")
    return redirect('lista_funcionarios')


@login_required
@somente_post
@tratar_erros
def desativa_funcionario(request, id_funcionario):
    func = get_object_or_404(TbFuncionario, id_funcionario=id_funcionario)
    func.flag_ativo = 'N'
    func.save(update_fields=['flag_ativo'])
    return redirect('lista_funcionarios')


@login_required
@somente_post
@tratar_erros
def reativa_funcionario(request, id_funcionario):
    func = get_object_or_404(TbFuncionario, id_funcionario=id_funcionario)
    func.flag_ativo = 'S'
    func.save(update_fields=['flag_ativo'])
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
    funcionario = get_object_or_404(TbFuncionario, id_funcionario=request.POST.get('id_funcionario'))
    funcionario.id_tipo = get_object_or_404(TbTipoFuncionario, id_tipo=request.POST.get('id_tipo'))
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
    return redirect('lista_funcionarios')


@login_required
@tratar_erros
def editar_funcionario(request, id_funcionario):
    dados = [get_object_or_404(TbFuncionario, id_funcionario=id_funcionario)]
    return render(request, 'gerencias/editar_funcionario.html', {'dados': dados})


# ==========================================
# BLOCO RESPONSÁVEL (FAMÍLIAS)
# ==========================================
@login_required
def novo_responsavel(request):
    return render(request, 'gerencias/novo_responsavel.html')


@login_required
@tratar_erros
def insere_novo_responsavel(request):
    if request.method != 'POST':
        return render(request, 'gerencias/novo_responsavel.html')

    cpf, erro = _ler_cpf(request, obrigatorio=True)
    if erro:
        messages.error(request, erro)
        return redirect('novo_responsavel')
    if _cpf_duplicado(TbCadastroResponsavel, cpf):
        messages.error(request, 'Já existe um responsável cadastrado com este CPF.')
        return redirect('novo_responsavel')

    novo = _criar_com_cpf_unico(
        TbCadastroResponsavel,
        id_usuario_cad_id=request.user.id,
        pnome=request.POST.get('pnome'),
        snome=request.POST.get('snome'),
        cpf=cpf,
        data_nascimento=_normalizar_data(request.POST.get('dt_nasc')),
        flag_responsavel_trabalha=request.POST.get('resp_trabalha'),
        flag_conjuge=request.POST.get('flag_conjuge'),
        flag_conjuge_trabalha=request.POST.get('conjuge_trabalha'),
        endereco=request.POST.get('endereco'),
        complemento=request.POST.get('complemento'),
        bairro=request.POST.get('bairro'),
        cidade=request.POST.get('cidade'),
        estado=request.POST.get('estado'),
        observacoes=request.POST.get('obs'),
        data_cadastro=timezone.now(),
        # Explícitos de propósito: sem eles o ORM mandaria NULL e o
        # cadastro sumiria de todas as listas.
        flag_ativo='S',
        flag_validado='N',
    )
    if novo is None:
        messages.error(request, 'Já existe um responsável cadastrado com este CPF.')
        return redirect('novo_responsavel')
    messages.success(request, 'Responsável cadastrado com sucesso. Ele aparece em "não validados" até ser validado.')
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
    return render(request, 'gerencias/editar_responsavel.html', {'dados': [responsavel], 'titulo': 'Responsável'})


@login_required
@somente_post
@tratar_erros
def atualiza_responsavel(request):
    responsavel = get_object_or_404(TbCadastroResponsavel, pk=request.POST.get('id_responsavel'))
    responsavel.pnome = request.POST.get('pnome')
    responsavel.snome = request.POST.get('snome')

    cpf, erro = _ler_cpf(request, obrigatorio=True, permitir_mascara=True)
    if erro:
        messages.error(request, erro)
        return redirect('edit_responsavel', id_responsavel=responsavel.pk)
    if cpf is not None:
        if _cpf_duplicado(TbCadastroResponsavel, cpf, excluir_pk=responsavel.pk):
            messages.error(request, 'CPF já pertence a outro responsável.')
            return redirect('edit_responsavel', id_responsavel=responsavel.pk)
        responsavel.cpf = cpf

    dt_nasc = _normalizar_data(request.POST.get('dt_nasc'))
    if dt_nasc:  # campo em branco não apaga a data que já existe
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
    responsavel.flag_ativo = request.POST.get('ativo') or responsavel.flag_ativo
    responsavel.ultima_atualizacao = timezone.now()
    if not _salvar_com_cpf_unico(responsavel):
        messages.error(request, 'CPF já pertence a outro responsável.')
        return redirect('edit_responsavel', id_responsavel=responsavel.pk)
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
    responsavel.flag_ativo = 'N'
    responsavel.save(update_fields=['flag_ativo'])
    return redirect('lista_responsavel')


@login_required
@somente_post
@tratar_erros
def reativa_responsavel(request, id_responsavel):
    responsavel = get_object_or_404(TbCadastroResponsavel, pk=id_responsavel)
    responsavel.flag_ativo = 'S'
    responsavel.save(update_fields=['flag_ativo'])
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
    filho = get_object_or_404(TbFilhosResponsavel, id_filho=request.POST.get('id_filho'))
    filho.flag_ativo = 'N'
    filho.save(update_fields=['flag_ativo'])
    return redirect('lista_filhos', id_responsavel=id_responsavel)


@login_required
@somente_post
@tratar_erros
def reativar_filho(request, id_filho):
    filho = get_object_or_404(TbFilhosResponsavel, id_filho=id_filho)
    filho.flag_ativo = 'S'
    filho.save(update_fields=['flag_ativo'])
    return redirect('lista_filhos', id_responsavel=filho.id_responsavel_id)


@login_required
@tratar_erros
def novo_filho(request, id_responsavel):
    responsavel = get_object_or_404(TbCadastroResponsavel, id_responsavel=id_responsavel)
    return render(request, 'gerencias/novo_filho.html', {
        'dados': responsavel,
        'id_responsavel': id_responsavel,
        'titulo': 'Crianças Cadastradas',
    })


@login_required
@tratar_erros
def editar_filho(request, id_filho):
    registro = get_object_or_404(TbFilhosResponsavel, id_filho=id_filho)
    return render(request, 'gerencias/editar_filho.html', {
        'dados': registro,
        'id_responsavel': registro.id_responsavel_id,
        'titulo': 'Editar Criança',
    })


@login_required
@somente_post
@tratar_erros
def insere_novo_filho(request):
    responsavel = get_object_or_404(TbCadastroResponsavel, id_responsavel=request.POST.get('responsavel'))
    id_responsavel = responsavel.id_responsavel

    cpf, erro = _ler_cpf(request, obrigatorio=False)
    if erro:
        messages.error(request, erro)
        return redirect('novo_filho', id_responsavel=id_responsavel)
    if _cpf_duplicado(TbFilhosResponsavel, cpf):
        messages.error(request, 'Já existe uma criança cadastrada com este CPF.')
        return redirect('lista_filhos', id_responsavel=id_responsavel)

    novo = _criar_com_cpf_unico(
        TbFilhosResponsavel,
        id_responsavel_id=id_responsavel,
        id_usuario_cad_id=request.user.id,
        pnome=request.POST.get('pnome'),
        snome=request.POST.get('snome'),
        data_nascimento=_normalizar_data(request.POST.get('dt_nasc')),
        cpf=cpf or None,
        sexo=request.POST.get('sexo'),
        numero_roupa=request.POST.get('roupa'),
        numero_sapato=request.POST.get('sapato') or None,
        cadastro_outra_ong=request.POST.get('outra_ong') or 'N',
        data_cadastro=timezone.now(),
        flag_ativo='S',
    )
    if novo is None:
        messages.error(request, 'Já existe uma criança cadastrada com este CPF.')
    return redirect('lista_filhos', id_responsavel=id_responsavel)


@login_required
@somente_post
@tratar_erros
def atualiza_filho(request, id_filho):
    filho = get_object_or_404(TbFilhosResponsavel, id_filho=id_filho)
    # O responsável vem do próprio registro, não do formulário (não dá para
    # "mudar" a criança de família alterando um campo escondido).
    id_responsavel = filho.id_responsavel_id
    filho.pnome = request.POST.get('pnome')
    filho.snome = request.POST.get('snome')

    dt_nasc = _normalizar_data(request.POST.get('dt_nasc'))
    if dt_nasc:
        filho.data_nascimento = dt_nasc

    cpf, erro = _ler_cpf(request, obrigatorio=False, permitir_mascara=True)
    if erro:
        messages.error(request, erro)
        return redirect('editar_filho', id_filho=filho.pk)
    if cpf:  # None = manteve a máscara; '' = campo vazio -> mantém o atual
        if _cpf_duplicado(TbFilhosResponsavel, cpf, excluir_pk=filho.pk):
            messages.error(request, 'CPF já pertence a outra criança.')
            return redirect('editar_filho', id_filho=filho.pk)
        filho.cpf = cpf

    filho.sexo = request.POST.get('sexo')
    filho.numero_roupa = request.POST.get('roupa')
    sapato = request.POST.get('sapato')
    if sapato:
        filho.numero_sapato = sapato
    filho.cadastro_outra_ong = request.POST.get('outra_ong') or filho.cadastro_outra_ong
    filho.data_atualizacao = timezone.now()
    if not _salvar_com_cpf_unico(filho):
        messages.error(request, 'CPF já pertence a outra criança.')
        return redirect('editar_filho', id_filho=filho.pk)

    _registrar_auditoria(request, 'EDICAO_CRIANCA', f'/filho/edit/{id_filho}')
    messages.success(request, 'Dados da criança atualizados com sucesso.')
    return redirect('lista_filhos', id_responsavel=id_responsavel)


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
    destinatario = request.POST.get('destinatario')
    mensagem = f"Mensagem de {remetente} para {destinatario}: {request.POST.get('mensagem')}"
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


@login_required
@tratar_erros
def lista_oficio(request):
    lista = TbOficios.objects.select_related('id_usuario').all().order_by('-data_criacao')
    primeiro = lista.first()
    return render(request, 'gerencias/lista_oficios.html', {
        'id_oficio': primeiro.id_oficio if primeiro else None,
        'lista': lista,
        'total': lista.count(),
    })


@login_required
@tratar_erros
def exibe_oficio(request, id_oficio):
    oficio = get_object_or_404(TbOficios, id_oficio=id_oficio)
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
        pnome = request.POST.get('pnome')
        snome = request.POST.get('snome')

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
    return render(request, 'gerencias/editar_madrinha_padrinho.html', {'registro': registro})


@login_required
@somente_post
@tratar_erros
def atualiza_madrinha_padrinho(request, id_mad_pad):
    registro = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)

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
    registro.pnome = request.POST.get('pnome', '').strip()
    registro.snome = request.POST.get('snome', '').strip()
    registro.endereco = request.POST.get('endereco', '').strip()
    registro.complemento = request.POST.get('complemento', '').strip()
    registro.bairro = request.POST.get('bairro', '').strip()
    registro.cidade = request.POST.get('cidade', '').strip()
    registro.estado = request.POST.get('estado', '').strip()
    registro.flag_ativo = request.POST.get('flag_ativo') or registro.flag_ativo
    registro.atualizacao_cad = timezone.now()
    if not _salvar_com_cpf_unico(registro):
        messages.error(request, 'CPF já pertence a outro padrinho/madrinha.')
        return redirect('editar_madrinha_padrinho', id_mad_pad=registro.pk)
    messages.success(request, 'Dados atualizados com sucesso!')
    return redirect('lista_madrinha_padrinho')


@login_required
@somente_post
@tratar_erros
def reativar_madrinha_padrinho(request, id_mad_pad):
    registro = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)
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
    madrinha = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=request.POST.get('id_mad_pad'))
    crianca = get_object_or_404(TbFilhosResponsavel, id_filho=request.POST.get('id_filho'))
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
    evento = get_object_or_404(TbEvento, id_evento=id_evento)
    evento.flag_finalizado = 'S'
    evento.save(update_fields=['flag_finalizado'])
    return redirect('listar_eventos')


@login_required
@tratar_erros
def listar_entregas(request):
    entregas = TbEntrega.objects.all().order_by('-id_evento')
    return render(request, 'gerencias/listar_entregas.html', {'lista': entregas})


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
    evento = get_object_or_404(TbEvento, id_evento=request.POST.get('id_evento'))
    madrinha = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=request.POST.get('id_mad_pad'))
    crianca = get_object_or_404(TbFilhosResponsavel, id_filho=request.POST.get('id_crianca'))
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
    evento = get_object_or_404(TbEvento, id_evento=request.POST.get('id_evento'))
    madrinha_padrinho = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=request.POST.get('id_mad_pad'))
    crianca = get_object_or_404(TbFilhosResponsavel, id_filho=request.POST.get('id_crianca'))

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
    with transaction.atomic():
        func = get_object_or_404(TbFuncionario, id_funcionario=id_funcionario)
        func.pnome, func.snome = "Funcionário", "Anonimizado (LGPD)"
        func.cpf = f"{PREFIXO_ANONIMO}{func.pk}"
        func.telefone = "Removido"
        _anonimizar_endereco(func)
        func.flag_ativo = 'N'
        func.save()
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
            # id_crianca é um IntegerField: precisa receber os NÚMEROS dos ids,
            # não os objetos (que causavam TypeError e erro 500).
            TbEntrega.objects.filter(id_crianca__in=[f.id_filho for f in filhos]).update(
                endereco="Endereço Anonimizado (LGPD)",
                bairro="Anonimizado",
            )

        _registrar_auditoria(request, 'ANONIMIZACAO_CASCATA', f'/resp/{id_responsavel}')
    messages.success(request, 'Responsável e dependentes anonimizados.')
    return redirect('lista_responsavel')
