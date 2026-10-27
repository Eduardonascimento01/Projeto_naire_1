import json
import re
import logging
import uuid
from datetime import datetime, date

from django.http import JsonResponse
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Q
from django.db import transaction
from django.core.serializers.json import DjangoJSONEncoder
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.contrib.auth import get_user_model

from gerencias.forms import AccountSignupForm
from gerencias.models import (
    TbFuncionario, TbTipoFuncionario, TbCadastroResponsavel,
    TbFilhosResponsavel, TbOficios, TbMadrinhaPadrinho,
    TbApadrinhamentoCrianca, TbEvento, TbEntrega, TbLogAuditoria,
)

User = get_user_model()
logger = logging.getLogger(__name__)

# ==========================================
# HELPERS LGPD E UTILITÁRIOS
# ==========================================
def mascarar_cpf(cpf):
    """Retorna versão mascarada do CPF (não persiste; uso apenas para exibição)."""
    if not cpf:
        return ""
    cpf_str = str(cpf).strip()
    if cpf_str.startswith('ANON-'):
        return "ANON-***"
    digits = ''.join(filter(str.isdigit, cpf_str))
    if len(digits) == 11:
        return f"***.***.***-{digits[-2:]}"
    return "***.***.***-**"

def aplicar_mascara_cpf(itens):
    """Popula `cpf_mascarado` em cada item (não toca no campo `cpf` real)."""
    for item in itens:
        item.cpf_mascarado = mascarar_cpf(getattr(item, 'cpf', None))
    return itens

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

def calcular_idade(data_nascimento_str):
    """Calcula idade aceitando 'DD/MM/YYYY' ou 'YYYY-MM-DD'. Retorna None em erro."""
    if not data_nascimento_str:
        return None
    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            data_nasc = datetime.strptime(str(data_nascimento_str), fmt).date()
            hoje = date.today()
            idade = hoje.year - data_nasc.year
            if hoje.month < data_nasc.month or (hoje.month == data_nasc.month and hoje.day < data_nasc.day):
                idade -= 1
            return idade
        except (ValueError, TypeError):
            continue
    return None

def _cpf_duplicado(model, cpf, excluir_pk=None):
    """
    Fallback de deduplicação de CPF sem `cpf_hash`.
    Percorre registros e compara o CPF decifrado. Lento (O(n)) — migrar
    para cpf_hash + UniqueConstraint quando possível.
    """
    if not cpf:
        return False
    qs = model.objects.only('pk', 'cpf')
    if excluir_pk is not None:
        qs = qs.exclude(pk=excluir_pk)
    for obj in qs:
        try:
            if getattr(obj, 'cpf', None) == cpf:
                return True
        except Exception:
            continue
    return False

# ==========================================
# AUTENTICAÇÃO E PÁGINAS BASE
# ==========================================
def login_required(function=None):
    """Exige usuário autenticado E staff/superuser."""
    return user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser))(function)

class userCreateView(CreateView):
    model = User
    template_name = 'registration/signup_form.html'
    form_class = AccountSignupForm
    success_url = reverse_lazy('login')
    success_message = 'Usuário criado com sucesso!'
    
    def form_valid(self, form):
        form.instance.password = make_password(form.instance.password)
        messages.success(self.request, self.success_message)
        return super().form_valid(form)

def home(request):
    return render(request, 'gerencias/index.html')

def pagina_erro(request, mensagem="Ocorreu um erro interno no processamento.", status=500):
    return render(request, 'gerencias/pagina_erro.html', {'mensagem': mensagem}, status=status)

# ==========================================
# BLOCO FUNCIONÁRIOS
# ==========================================
@login_required
def lista_funcionarios(request):
    try:
        lista = TbFuncionario.objects.filter(flag_ativo='S')
        aplicar_mascara_cpf(lista)
        return render(request, 'gerencias/lista_funcionarios.html', {'lista': lista})
    except Exception as e:
        logger.error(f"Erro em lista_funcionarios: {e}")
        return pagina_erro(request)

@login_required
def novo_funcionario(request):
    try:
        return render(request, 'gerencias/novo_funcionario.html')
    except Exception as e:
        logger.error(f"Erro em novo_funcionario: {e}")
        return pagina_erro(request)

@login_required
def insere_novo_funcionario(request):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método HTTP inválido.", status=405)
    try:
        cpf = (request.POST.get('cpf') or '').replace('.', '').replace('-', '')
        if _cpf_duplicado(TbFuncionario, cpf):
            messages.error(request, 'Já existe um funcionário cadastrado com este CPF.')
            return redirect('novo_funcionario')
            
        rua_n = f"{request.POST.get('rua') or ''}, {request.POST.get('numero') or ''}"
        telefone = (request.POST.get('telefone') or '').replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
        
        TbFuncionario.objects.create(
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
            flag_ativo=request.POST.get('flag')
        )
        messages.success(request, "Funcionário cadastrado com sucesso!")
        return redirect('lista_funcionarios')
    except Exception as e:
        logger.error(f"Erro em insere_novo_funcionario: {e}")
        return pagina_erro(request)

@login_required
def desativa_funcionario(request, id_funcionario):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método HTTP inválido.", status=405)
    try:
        func = get_object_or_404(TbFuncionario, id_funcionario=id_funcionario)
        func.flag_ativo = 'N'
        func.save(update_fields=['flag_ativo'])
        return redirect('lista_funcionarios')
    except Exception as e:
        logger.error(f"Erro em desativa_funcionario: {e}")
        return pagina_erro(request)

@login_required
def reativa_funcionario(request, id_funcionario):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método HTTP inválido.", status=405)
    try:
        func = get_object_or_404(TbFuncionario, id_funcionario=id_funcionario)
        func.flag_ativo = 'S'
        func.save(update_fields=['flag_ativo'])
        return redirect('lista_funcionarios')
    except Exception as e:
        logger.error(f"Erro em reativa_funcionario: {e}")
        return pagina_erro(request)

@login_required
def lista_funcionarios_desativos(request):
    try:
        lista = TbFuncionario.objects.filter(flag_ativo='N')
        aplicar_mascara_cpf(lista)
        return render(request, 'gerencias/lista_funcionarios_desativados.html', {'lista': lista})
    except Exception as e:
        logger.error(f"Erro em lista_funcionarios_desativos: {e}")
        return pagina_erro(request)

@login_required
def atualiza_funcionario(request):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método HTTP inválido.", status=405)
    try:
        funcionario = get_object_or_404(TbFuncionario, id_funcionario=request.POST.get('id_funcionario'))
        funcionario.id_tipo = get_object_or_404(TbTipoFuncionario, id_tipo=request.POST.get('id_tipo'))
        funcionario.pnome = request.POST.get('pnome')
        funcionario.snome = request.POST.get('snome')
        
        cpf_form = request.POST.get('cpf', '')
        if '*' not in cpf_form:
            novo_cpf = cpf_form.replace('.', '').replace('-', '')
            if _cpf_duplicado(TbFuncionario, novo_cpf, excluir_pk=funcionario.pk):
                messages.error(request, 'CPF já pertence a outro funcionário.')
                return redirect('lista_funcionarios')
            funcionario.cpf = novo_cpf
            
        funcionario.telefone = (request.POST.get('telefone') or '').replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
        funcionario.endereco = request.POST.get('endereco')
        funcionario.complemento = request.POST.get('complemento')
        funcionario.bairro = request.POST.get('bairro')
        funcionario.cidade = request.POST.get('cidade')
        funcionario.estado = request.POST.get('estado')
        funcionario.flag_ativo = request.POST.get('flag_ativo')
        funcionario.save()
        return redirect('lista_funcionarios')
    except Exception as e:
        logger.error(f"Erro em atualiza_funcionario: {e}")
        return pagina_erro(request)

@login_required
def editar_funcionario(request, id_funcionario):
    try:
        dados = [get_object_or_404(TbFuncionario, id_funcionario=id_funcionario)]
        aplicar_mascara_cpf(dados)
        return render(request, 'gerencias/editar_funcionario.html', {'dados': dados})
    except Exception as e:
        logger.error(f"Erro em editar_funcionario: {e}")
        return pagina_erro(request)

# ==========================================
# BLOCO RESPONSÁVEL (FAMÍLIAS)
# ==========================================
@login_required
def novo_responsavel(request):
    return render(request, 'gerencias/novo_responsavel.html')

@login_required
def insere_novo_responsavel(request):
    if request.method != 'POST':
        return render(request, 'gerencias/novo_responsavel.html')
    try:
        cpf = (request.POST.get('cpf') or '').replace('.', '').replace('-', '')
        if _cpf_duplicado(TbCadastroResponsavel, cpf):
            messages.error(request, 'Já existe um responsável cadastrado com este CPF.')
            return redirect('novo_responsavel')
            
        dt_nasc = _normalizar_data(request.POST.get('dt_nasc'))
        TbCadastroResponsavel.objects.create(
            id_usuario_cad_id=request.user.id,
            pnome=request.POST.get('pnome'),
            snome=request.POST.get('snome'),
            cpf=cpf,
            data_nascimento=dt_nasc,
            flag_responsavel_trabalha=request.POST.get('resp_trabalha'),
            flag_conjuge=request.POST.get('flag_conjuge'),
            flag_conjuge_trabalha=request.POST.get('conjuge_trabalha'),
            endereco=request.POST.get('endereco'),
            complemento=request.POST.get('complemento'),
            bairro=request.POST.get('bairro'),
            cidade=request.POST.get('cidade'),
            estado=request.POST.get('estado'),
            observacoes=request.POST.get('obs'),
            data_cadastro=timezone.now()
        )
        messages.success(request, 'Responsável cadastrado com sucesso.')
        return redirect('lista_responsavel')
    except Exception as e:
        logger.error(f"Erro em insere_novo_responsavel: {e}")
        return pagina_erro(request)

@login_required
def lista_responsavel(request):
    try:
        responsavel = TbCadastroResponsavel.objects.filter(flag_ativo='S', flag_validado='S')
        aplicar_mascara_cpf(responsavel)
        return render(request, 'gerencias/lista_responsavel.html', {'dados': responsavel, 'titulo': 'Responsáveis Validados'})
    except Exception as e:
        logger.error(f"Erro em lista_responsavel: {e}")
        return pagina_erro(request)

@login_required
def lista_responsavel_nval(request):
    try:
        responsavel = TbCadastroResponsavel.objects.filter(flag_ativo='S', flag_validado='N')
        aplicar_mascara_cpf(responsavel)
        return render(request, 'gerencias/lista_responsavel_nval.html', {'dados': responsavel, 'titulo': 'Responsáveis não Validados'})
    except Exception as e:
        logger.error(f"Erro em lista_responsavel_nval: {e}")
        return pagina_erro(request)

@login_required
def lista_responsavel_des(request):
    try:
        responsavel = TbCadastroResponsavel.objects.filter(flag_ativo='N')
        aplicar_mascara_cpf(responsavel)
        return render(request, 'gerencias/lista_responsavel_des.html', {'dados': responsavel, 'titulo': 'Responsáveis Desativados'})
    except Exception as e:
        logger.error(f"Erro em lista_responsavel_des: {e}")
        return pagina_erro(request)

@login_required
def edit_responsavel(request, id_responsavel):
    try:
        responsavel = get_object_or_404(TbCadastroResponsavel, pk=id_responsavel)
        dados = [responsavel]
        aplicar_mascara_cpf(dados)
        return render(request, 'gerencias/editar_responsavel.html', {'dados': dados, 'titulo': 'Responsável'})
    except Exception as e:
        logger.error(f"Erro em edit_responsavel: {e}")
        return pagina_erro(request)

@login_required
def atualiza_responsavel(request):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método HTTP inválido.", status=405)
    try:
        responsavel = get_object_or_404(TbCadastroResponsavel, pk=request.POST.get('id_responsavel'))
        responsavel.pnome = request.POST.get('pnome')
        responsavel.snome = request.POST.get('snome')
        
        cpf_form = request.POST.get('cpf', '')
        if '*' not in cpf_form:
            novo_cpf = cpf_form.replace('.', '').replace('-', '')
            if _cpf_duplicado(TbCadastroResponsavel, novo_cpf, excluir_pk=responsavel.pk):
                messages.error(request, 'CPF já pertence a outro responsável.')
                return redirect('lista_responsavel')
            responsavel.cpf = novo_cpf
            
        responsavel.data_nascimento = _normalizar_data(request.POST.get('dt_nasc'))
        responsavel.flag_responsavel_trabalha = request.POST.get('resp_trabalha')
        responsavel.flag_conjuge = request.POST.get('flag_conjuge')
        responsavel.flag_conjuge_trabalha = request.POST.get('conjuge_trabalha')
        responsavel.endereco = request.POST.get('endereco')
        responsavel.complemento = request.POST.get('complemento')
        responsavel.bairro = request.POST.get('bairro')
        responsavel.cidade = request.POST.get('cidade')
        responsavel.estado = request.POST.get('estado')
        responsavel.flag_validado = request.POST.get('validado')
        responsavel.flag_ativo = request.POST.get('ativo')
        responsavel.save()
        return redirect('lista_responsavel')
    except Exception as e:
        logger.error(f"Erro em atualiza_responsavel: {e}")
        return pagina_erro(request)

@login_required
def valida_responsavel(request, id_responsavel):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método HTTP inválido.", status=405)
    try:
        responsavel = get_object_or_404(TbCadastroResponsavel, pk=id_responsavel)
        responsavel.flag_validado = 'S'
        responsavel.save(update_fields=['flag_validado'])
        return redirect('lista_responsavel')
    except Exception as e:
        logger.error(f"Erro em valida_responsavel: {e}")
        return pagina_erro(request)

@login_required
def desativa_responsavel(request, id_responsavel):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método HTTP inválido.", status=405)
    try:
        responsavel = get_object_or_404(TbCadastroResponsavel, pk=id_responsavel)
        responsavel.flag_ativo = 'N'
        responsavel.save(update_fields=['flag_ativo'])
        return redirect('lista_responsavel')
    except Exception as e:
        logger.error(f"Erro em desativa_responsavel: {e}")
        return pagina_erro(request)

@login_required
def reativa_responsavel(request, id_responsavel):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método HTTP inválido.", status=405)
    try:
        responsavel = get_object_or_404(TbCadastroResponsavel, pk=id_responsavel)
        responsavel.flag_ativo = 'S'
        responsavel.save(update_fields=['flag_ativo'])
        return redirect('lista_responsavel')
    except Exception as e:
        logger.error(f"Erro em reativa_responsavel: {e}")
        return pagina_erro(request)

# ==========================================
# BLOCO FILHOS (CRIANÇAS)
# ==========================================
@login_required
def lista_filhos(request, id_responsavel):
    try:
        registros = TbFilhosResponsavel.objects.select_related('id_responsavel').filter(
            id_responsavel=id_responsavel, flag_ativo='S'
        ).order_by('-data_cadastro')
        aplicar_mascara_cpf(registros)
        
        responsavel = TbCadastroResponsavel.objects.filter(id_responsavel=id_responsavel).first()
        responsavel_nome = f"{responsavel.pnome} {responsavel.snome}" if responsavel else ""
        contexto = {
            'lista': registros,
            'id_responsavel': id_responsavel,
            'responsavel_nome': responsavel_nome,
            'titulo': 'Crianças Cadastradas'
        }
        return render(request, 'gerencias/lista_filhos.html', contexto)
    except Exception as e:
        logger.error(f"Erro em lista_filhos: {e}")
        return pagina_erro(request)

@login_required
def lista_filhos_total(request):
    try:
        lista = TbFilhosResponsavel.objects.select_related('id_responsavel').all().order_by('id_responsavel')
        aplicar_mascara_cpf(lista)
        return render(request, 'gerencias/lista_filhos_total.html', {'lista': lista})
    except Exception as e:
        logger.error(f"Erro em lista_filhos_total: {e}")
        return pagina_erro(request)

@login_required
def desativa_filhos_responsavel(request, id_responsavel):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
        TbFilhosResponsavel.objects.filter(id_responsavel=id_responsavel).update(flag_ativo='N')
        return redirect('lista_filhos', id_responsavel=id_responsavel)
    except Exception as e:
        logger.error(f"Erro em desativa_filhos_responsavel: {e}")
        return pagina_erro(request)

@login_required
def reativa_filhos_responsavel(request, id_responsavel):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
        TbFilhosResponsavel.objects.filter(id_responsavel=id_responsavel).update(flag_ativo='S')
        return redirect('lista_filhos', id_responsavel=id_responsavel)
    except Exception as e:
        logger.error(f"Erro em reativa_filhos_responsavel: {e}")
        return pagina_erro(request)

@login_required
def desativar_filho(request, id_responsavel):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
        filho = get_object_or_404(TbFilhosResponsavel, id_filho=request.POST.get('id_filho'))
        filho.flag_ativo = 'N'
        filho.save(update_fields=['flag_ativo'])
        return redirect('lista_filhos', id_responsavel=id_responsavel)
    except Exception as e:
        logger.error(f"Erro em desativar_filho: {e}")
        return pagina_erro(request)

@login_required
def reativar_filho(request, id_filho):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
        filho = get_object_or_404(TbFilhosResponsavel, id_filho=id_filho)
        filho.flag_ativo = 'S'
        id_responsavel = filho.id_responsavel_id
        filho.save(update_fields=['flag_ativo'])
        return redirect('lista_filhos', id_responsavel=id_responsavel)
    except Exception as e:
        logger.error(f"Erro em reativar_filho: {e}")
        return pagina_erro(request)

@login_required
def lista_filhos_responsavel(request):
    try:
        id_resp = request.POST.get('id_responsavel') or request.GET.get('id_responsavel')
        registros = TbFilhosResponsavel.objects.filter(
            id_responsavel=id_resp, flag_ativo='S'
        ).order_by('-data_cadastro')
        aplicar_mascara_cpf(registros)
        return render(request, 'gerencias/lista_responsavel.html', {'dados': registros, 'titulo': 'Responsáveis Ativos'})
    except Exception as e:
        logger.error(f"Erro em lista_filhos_responsavel: {e}")
        return pagina_erro(request)

@login_required
def novo_filho(request, id_responsavel):
    try:
        responsavel = get_object_or_404(TbCadastroResponsavel, id_responsavel=id_responsavel)
        return render(request, 'gerencias/novo_filho.html', {
            'dados': responsavel,
            'id_responsavel': id_responsavel,
            'titulo': 'Crianças Cadastradas'
        })
    except Exception as e:
        logger.error(f"Erro em novo_filho: {e}")
        return pagina_erro(request)

@login_required
def editar_filho(request, id_filho):
    try:
        registro = get_object_or_404(TbFilhosResponsavel, id_filho=id_filho)
        aplicar_mascara_cpf([registro])
        return render(request, 'gerencias/editar_filho.html', {
            'dados': registro,
            'id_responsavel': registro.id_responsavel_id,
            'titulo': 'Editar Criança'
        })
    except Exception as e:
        logger.error(f"Erro em editar_filho: {e}")
        return pagina_erro(request)

@login_required
def insere_novo_filho(request):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
        id_responsavel = request.POST.get('responsavel')
        responsavel = get_object_or_404(TbCadastroResponsavel, id_responsavel=id_responsavel)
        cpf = (request.POST.get('cpf') or '').replace('.', '').replace('-', '')
        
        if cpf and _cpf_duplicado(TbFilhosResponsavel, cpf):
            messages.error(request, 'Já existe uma criança cadastrada com este CPF.')
            return redirect('lista_filhos', id_responsavel=id_responsavel)
            
        TbFilhosResponsavel.objects.create(
            id_responsavel_id=responsavel.id_responsavel,
            id_usuario_cad_id=request.user.id,
            pnome=request.POST.get('pnome'),
            snome=request.POST.get('snome'),
            data_nascimento=_normalizar_data(request.POST.get('dt_nasc')),
            cpf=cpf,
            sexo=request.POST.get('sexo'),
            numero_roupa=request.POST.get('roupa'),
            numero_sapato=request.POST.get('sapato') or None,
            cadastro_outra_ong=request.POST.get('outra_ong'),
            data_cadastro=timezone.now()
        )
        return redirect('lista_filhos', id_responsavel=id_responsavel)
    except Exception as e:
        logger.error(f"Erro em insere_novo_filho: {e}")
        return pagina_erro(request)

@login_required
def atualiza_filho(request, id_filho):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
        filho = get_object_or_404(TbFilhosResponsavel, id_filho=id_filho)
        id_responsavel = request.POST.get('responsavel')
        filho.pnome = request.POST.get('pnome')
        filho.snome = request.POST.get('snome')
        
        dt_nasc = _normalizar_data(request.POST.get('dt_nasc'))
        if dt_nasc:
            filho.data_nascimento = dt_nasc
            
        cpf_limpo = (request.POST.get('cpf') or '').replace('.', '').replace('-', '')
        if cpf_limpo and '*' not in cpf_limpo:
            if _cpf_duplicado(TbFilhosResponsavel, cpf_limpo, excluir_pk=filho.pk):
                messages.error(request, 'CPF já pertence a outra criança.')
                return redirect('lista_filhos', id_responsavel=id_responsavel)
            filho.cpf = cpf_limpo
            
        filho.sexo = request.POST.get('sexo')
        filho.numero_roupa = request.POST.get('roupa')
        sapato = request.POST.get('sapato')
        if sapato:
            filho.numero_sapato = sapato
        filho.cadastro_outra_ong = request.POST.get('outra_ong')
        filho.save()
        
        TbLogAuditoria.objects.create(
            usuario=request.user.username,
            acao='EDICAO_CRIANCA',
            rota=f'/filho/edit/{id_filho}',
            ip=request.META.get('REMOTE_ADDR')
        )
        messages.success(request, 'Dados da criança atualizados com sucesso.')
        return redirect('lista_filhos', id_responsavel)
    except Exception as e:
        logger.error(f"Erro em atualiza_filho: {e}")
        return pagina_erro(request)

@login_required
def buscar_filhos(request):
    resultados = []
    termo_busca = ''
    tipo_busca = 'nome'
    if request.method == 'POST':
        termo_busca = request.POST.get('termo_busca', '').strip()
        tipo_busca = request.POST.get('tipo_busca', 'nome')
        if termo_busca:
            if tipo_busca == 'nome':
                qs = TbFilhosResponsavel.objects.select_related('id_responsavel').filter(
                    Q(pnome__icontains=termo_busca) | Q(snome__icontains=termo_busca),
                    flag_ativo='S'
                )
                resultados = list(qs)
            elif tipo_busca == 'idade':
                try:
                    idade_busca = int(termo_busca)
                    todos_filhos = TbFilhosResponsavel.objects.select_related('id_responsavel').filter(flag_ativo='S')
                    for filho in todos_filhos:
                        if calcular_idade(filho.data_nascimento) == idade_busca:
                            resultados.append(filho)
                except ValueError:
                    resultados = []
                    termo_busca = 'Por favor, digite um número válido'
                    
    for filho in resultados:
        filho.idade = calcular_idade(filho.data_nascimento)
    aplicar_mascara_cpf(resultados)
    
    contexto = {
        'resultados': resultados,
        'termo_busca': termo_busca,
        'tipo_busca': tipo_busca,
        'total_resultados': len(resultados)
    }
    return render(request, 'gerencias/buscar_filhos.html', contexto)

# ==========================================
# BLOCO OFÍCIOS
# ==========================================
@login_required
def insere_novo_oficio(request):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
        remetente = request.user.username
        destinatario = request.POST.get('destinatario')
        mensagem = f"Mensagem de {remetente} para {destinatario}: {request.POST.get('mensagem')}"
        TbOficios.objects.create(
            id_usuario_id=request.user.id,
            destinatario=destinatario,
            mensagem=mensagem,
            data_criacao=timezone.now()
        )
        return redirect('lista_oficio')
    except Exception as e:
        logger.error(f"Erro em insere_novo_oficio: {e}")
        return pagina_erro(request)

@login_required
def novo_oficio(request):
    try:
        return render(request, 'gerencias/novo_oficio.html', {
            'usuario': request.user,
            'id_usuario_cad': request.user.id,
            'username': request.user.username
        })
    except Exception as e:
        logger.error(f"Erro em novo_oficio: {e}")
        return pagina_erro(request)

@login_required
def lista_oficio(request):
    try:
        lista = TbOficios.objects.select_related('id_usuario').all().order_by('-data_criacao')
        primeiro_id = lista.first().id_oficio if lista.exists() else None
        return render(request, 'gerencias/lista_oficios.html', {
            'id_oficio': primeiro_id,
            'lista': lista,
            'total': lista.count()
        })
    except Exception as e:
        logger.error(f"Erro em lista_oficio: {e}")
        return pagina_erro(request)

@login_required
def exibe_oficio(request, id_oficio):
    try:
        oficio = get_object_or_404(TbOficios, id_oficio=id_oficio)
        return render(request, 'gerencias/exibe_oficio.html', {
            'oficio': oficio,
            'id_oficio': id_oficio,
            'mensagem': oficio.mensagem,
            'remetente': oficio.id_usuario.username
        })
    except Exception as e:
        logger.error(f"Erro em exibe_oficio: {e}")
        return pagina_erro(request)

@login_required
def excluir_oficio(request, id_oficio):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
        TbOficios.objects.filter(id_oficio=id_oficio).delete()
        return redirect('lista_oficio')
    except Exception as e:
        logger.error(f"Erro em excluir_oficio: {e}")
        return pagina_erro(request)

# ==========================================
# BLOCO MADRINHAS E PADRINHOS
# ==========================================
@login_required
def novo_madrinha_padrinho(request):
    try:
        id_usuario = request.POST.get('id_usuario_cad', request.user.id) if request.method == 'POST' else request.user.id
        return render(request, 'gerencias/novo_madrinha_padrinho.html', {
            'usuario': request.user,
            'id_usuario_cad': id_usuario
        })
    except Exception as e:
        logger.error(f"Erro em novo_madrinha_padrinho: {e}")
        return pagina_erro(request)

@login_required
def inserir_madrinha_padrinho(request):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
        cpf = (request.POST.get('cpf') or '').replace('.', '').replace('-', '')
        if cpf and _cpf_duplicado(TbMadrinhaPadrinho, cpf):
            messages.error(request, 'Já existe um padrinho/madrinha cadastrado com este CPF.')
            return redirect('lista_madrinha_padrinho')
            
        flag_anonimo = request.POST.get('flag_anonimo', 'N')
        if flag_anonimo == 'S':
            pnome, snome = 'Anônimo', ''
        else:
            pnome = request.POST.get('pnome')
            snome = request.POST.get('snome')
            
        TbMadrinhaPadrinho.objects.create(
            id_usuario_cad_id=request.user.id,
            cpf=cpf,
            flag_anonimo=flag_anonimo,
            pnome=pnome,
            snome=snome,
            endereco=request.POST.get('endereco'),
            complemento=request.POST.get('complemento'),
            bairro=request.POST.get('bairro'),
            cidade=request.POST.get('cidade'),
            estado=request.POST.get('estado'),
            flag_ativo=request.POST.get('flag_ativo'),
            data_cadastro=timezone.now()
        )
        return redirect('lista_madrinha_padrinho')
    except Exception as e:
        logger.error(f"Erro em inserir_madrinha_padrinho: {e}")
        return pagina_erro(request)

@login_required
def lista_madrinha_padrinho(request):
    try:
        termo = request.GET.get('q', '').strip()
        if termo:
            lista = TbMadrinhaPadrinho.objects.filter(
                Q(pnome__icontains=termo),
                flag_ativo='S'
            ).order_by('-data_cadastro')
            
            if not lista.exists():
                qs = TbMadrinhaPadrinho.objects.filter(flag_ativo='S').order_by('-data_cadastro')
                lista = [m for m in qs if getattr(m, 'cpf', None) == termo]
        else:
            lista = TbMadrinhaPadrinho.objects.filter(flag_ativo='S').order_by('-data_cadastro')
            
        aplicar_mascara_cpf(lista)
        return render(request, 'gerencias/listar_madrinhas_padrinhos.html', {'dados': lista, 'termo_busca': termo})
    except Exception as e:
        logger.error(f"Erro em lista_madrinha_padrinho: {e}")
        return pagina_erro(request)

@login_required
def lista_madrinha_padrinho_desativados(request):
    try:
        lista = TbMadrinhaPadrinho.objects.filter(flag_ativo='N').order_by('-data_cadastro')
        aplicar_mascara_cpf(lista)
        return render(request, 'gerencias/listar_madrinhas_padrinhos_desativados.html', {'dados': lista})
    except Exception as e:
        logger.error(f"Erro em lista_madrinha_padrinho_desativados: {e}")
        return pagina_erro(request)

@login_required
def editar_madrinha_padrinho(request, id_mad_pad):
    try:
        registro = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)
        aplicar_mascara_cpf([registro])
        return render(request, 'gerencias/editar_madrinha_padrinho.html', {'registro': registro})
    except Exception as e:
        logger.error(f"Erro em editar_madrinha_padrinho: {e}")
        return pagina_erro(request)

@login_required
def atualiza_madrinha_padrinho(request, id_mad_pad):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
        registro = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)
        cpf_form = request.POST.get('cpf', '')
        if '*' not in cpf_form:
            novo_cpf = cpf_form.replace('.', '').replace('-', '')
            if novo_cpf and _cpf_duplicado(TbMadrinhaPadrinho, novo_cpf, excluir_pk=registro.pk):
                messages.error(request, 'CPF já pertence a outro padrinho/madrinha.')
                return redirect('lista_madrinha_padrinho')
            registro.cpf = novo_cpf
            
        registro.flag_anonimo = request.POST.get('flag_anonimo', 'N')
        registro.pnome = request.POST.get('pnome', '').strip()
        registro.snome = request.POST.get('snome', '').strip()
        registro.endereco = request.POST.get('endereco', '').strip()
        registro.complemento = request.POST.get('complemento', '').strip()
        registro.bairro = request.POST.get('bairro', '').strip()
        registro.cidade = request.POST.get('cidade', '').strip()
        registro.estado = request.POST.get('estado', '').strip()
        registro.flag_ativo = request.POST.get('flag_ativo')
        registro.save()
        messages.success(request, 'Dados atualizados com sucesso!')
        return redirect('lista_madrinha_padrinho')
    except Exception as e:
        logger.error(f"Erro em atualiza_madrinha_padrinho: {e}")
        return pagina_erro(request)

@login_required
def reativar_madrinha_padrinho(request, id_mad_pad):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
        registro = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)
        registro.flag_ativo = 'S'
        registro.atualizacao_cad = timezone.now()
        registro.save(update_fields=['flag_ativo', 'atualizacao_cad'])
        messages.success(request, 'Registro reativado com sucesso!')
        return redirect('lista_madrinha_padrinho')
    except Exception as e:
        logger.error(f"Erro em reativar_madrinha_padrinho: {e}")
        return pagina_erro(request)

@login_required
def api_salvar_madrinha_padrinho(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método inválido'}, status=405)
    try:
        dados = json.loads(request.body)
        cpf = (dados.get('cpf') or '').replace('.', '').replace('-', '')
        if cpf and _cpf_duplicado(TbMadrinhaPadrinho, cpf):
            return JsonResponse(
                {'success': False, 'message': 'Já existe um cadastro com este CPF.'},
                status=400
            )
        novo = TbMadrinhaPadrinho.objects.create(
            id_usuario_cad_id=request.user.id,
            cpf=cpf,
            flag_anonimo=dados.get('flag_anonimo', 'N'),
            pnome=dados.get('pnome'),
            snome=dados.get('snome'),
            endereco=dados.get('endereco'),
            complemento=dados.get('complemento'),
            bairro=dados.get('bairro'),
            cidade=dados.get('cidade'),
            estado=dados.get('estado'),
            data_cadastro=timezone.now(),
            flag_ativo='S'
        )
        return JsonResponse({'success': True, 'id': novo.id_mad_pad, 'message': 'Cadastro realizado'})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'JSON inválido'}, status=400)
    except Exception as e:
        logger.error(f"Erro em api_salvar_madrinha_padrinho: {e}")
        return JsonResponse({'success': False, 'message': 'Ocorreu um erro interno.'}, status=500)

@login_required
def apadrinhar_crianca(request, id_mad_pad):
    try:
        registro = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)
        criancas = TbFilhosResponsavel.objects.filter(flag_ativo='S').order_by('pnome')
        aplicar_mascara_cpf([registro])
        aplicar_mascara_cpf(criancas)
        return render(request, 'gerencias/apadrinhar_crianca.html', {
            'registro': registro,
            'criancas': criancas,
            'titulo': 'Apadrinhar Criança'
        })
    except Exception as e:
        logger.error(f"Erro em apadrinhar_crianca: {e}")
        return pagina_erro(request)

@login_required
def vincular_mad_pad_crianca(request):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
        madrinha = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=request.POST.get('id_mad_pad'))
        crianca = get_object_or_404(TbFilhosResponsavel, id_filho=request.POST.get('id_filho'))
        TbApadrinhamentoCrianca.objects.create(
            id_mad_pad_id=madrinha.id_mad_pad,
            id_filho_id=crianca.id_filho,
            data_cadastro=timezone.now()
        )
        return redirect('lista_apadrinhamento')
    except Exception as e:
        logger.error(f"Erro em vincular_mad_pad_crianca: {e}")
        return pagina_erro(request)

@login_required
def lista_apadrinhamento(request):
    try:
        apadrinhamento = TbApadrinhamentoCrianca.objects.select_related('id_mad_pad', 'id_filho').all().order_by('-data_cadastro')
        return render(request, 'gerencias/lista_apadrinhamentos.html', {'registros': apadrinhamento})
    except Exception as e:
        logger.error(f"Erro em lista_apadrinhamento: {e}")
        return pagina_erro(request)

# ==========================================
# BLOCO EVENTOS E ENTREGAS
# ==========================================
@login_required
def listar_eventos(request):
    try:
        lista = TbEvento.objects.all().order_by('-data_evento')
        return render(request, 'gerencias/listar_eventos.html', {'lista': lista})
    except Exception as e:
        logger.error(f"Erro em listar_eventos: {e}")
        return pagina_erro(request)

@login_required
def novo_evento(request):
    try:
        return render(request, 'gerencias/novo_evento.html')
    except Exception as e:
        logger.error(f"Erro em novo_evento: {e}")
        return pagina_erro(request)

@login_required
def atualiza_evento(request, id_evento):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
        evento = get_object_or_404(TbEvento, id_evento=id_evento)
        evento.nome = request.POST.get('nome')
        evento.data_evento = request.POST.get('data_evento')
        evento.endereco = request.POST.get('endereco')
        evento.bairro = request.POST.get('bairro')
        evento.cidade = request.POST.get('cidade')
        evento.estado = request.POST.get('estado')
        evento.flag_finalizado = request.POST.get('flag_finalizado')
        evento.save()
        return redirect('listar_eventos')
    except Exception as e:
        logger.error(f"Erro em atualiza_evento: {e}")
        return pagina_erro(request)

@login_required
def insere_novo_evento(request):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
        nome = request.POST.get('nome')
        data_evento = request.POST.get('data_evento')
        endereco = request.POST.get('endereco')
        bairro = request.POST.get('bairro')
        cidade = request.POST.get('cidade')
        estado = request.POST.get('estado')
        flag_finalizado = request.POST.get('flag_finalizado', 'N')
        
        if not all([nome, data_evento, endereco, bairro, cidade, estado]):
            messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
            return redirect('novo_evento')
            
        if not re.match(r'^\d{2}/\d{2}/\d{4}$', data_evento):
            messages.error(request, 'Formato de data inválido. Use dd/mm/aaaa.')
            return redirect('novo_evento')
            
        try:
            datetime.strptime(data_evento, '%d/%m/%Y')
        except ValueError:
            messages.error(request, 'Data inválida.')
            return redirect('novo_evento')
            
        TbEvento.objects.create(
            nome=nome,
            data_evento=data_evento,
            endereco=endereco,
            bairro=bairro,
            cidade=cidade,
            estado=estado,
            flag_finalizado=flag_finalizado,
            data_cadastro=timezone.now()
        )
        return redirect('listar_eventos')
    except Exception as e:
        logger.error(f"Erro em insere_novo_evento: {e}")
        return pagina_erro(request)

@login_required
def editar_evento(request, id_evento):
    try:
        evento = get_object_or_404(TbEvento, id_evento=id_evento)
        return render(request, 'gerencias/editar_evento.html', {'registro': evento})
    except Exception as e:
        logger.error(f"Erro em editar_evento: {e}")
        return pagina_erro(request)

@login_required
def finalizar_evento(request, id_evento):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
        evento = get_object_or_404(TbEvento, id_evento=id_evento)
        evento.flag_finalizado = 'S'
        evento.save(update_fields=['flag_finalizado'])
        return redirect('listar_eventos')
    except Exception as e:
        logger.error(f"Erro em finalizar_evento: {e}")
        return pagina_erro(request)

@login_required
def listar_entregas(request):
    try:
        entregas = TbEntrega.objects.all().order_by('-id_evento')
        return render(request, 'gerencias/listar_entregas.html', {'lista': entregas})
    except Exception as e:
        logger.error(f"Erro em listar_entregas: {e}")
        return pagina_erro(request)

@login_required
def nova_entrega(request):
    try:
        evento = TbEvento.objects.all().order_by('-id_evento')
        criancas = TbFilhosResponsavel.objects.filter(flag_ativo='S').order_by('pnome')
        madrinhas_padrinhos = TbMadrinhaPadrinho.objects.filter(flag_ativo='S').order_by('pnome')
        aplicar_mascara_cpf(criancas)
        aplicar_mascara_cpf(madrinhas_padrinhos)
        
        return render(request, 'gerencias/nova_entrega.html', {
            'evento': evento,
            'criancas': criancas,
            'mad_pad': madrinhas_padrinhos
        })
    except Exception as e:
        logger.error(f"Erro em nova_entrega: {e}")
        return pagina_erro(request)

@login_required
def insere_nova_entrega(request):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
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
            data_cadastro=timezone.now()
        )
        return redirect('listar_entregas')
    except Exception as e:
        logger.error(f"Erro em insere_nova_entrega: {e}")
        return pagina_erro(request)

@login_required
def editar_entrega(request, id_entrega):
    try:
        entrega = get_object_or_404(TbEntrega, id_entrega=id_entrega)
        eventos = TbEvento.objects.all().order_by('-id_evento')
        criancas = TbFilhosResponsavel.objects.filter(flag_ativo='S').order_by('pnome')
        madrinhas_padrinhos = TbMadrinhaPadrinho.objects.filter(flag_ativo='S').order_by('pnome')
        aplicar_mascara_cpf(criancas)
        aplicar_mascara_cpf(madrinhas_padrinhos)
        
        return render(request, 'gerencias/editar_entrega.html', {
            'entrega': entrega,
            'eventos': eventos,
            'criancas': criancas,
            'madrinhas_padrinhos': madrinhas_padrinhos
        })
    except Exception as e:
        logger.error(f"Erro em editar_entrega: {e}")
        return pagina_erro(request)

@login_required
def atualiza_entrega(request, id_entrega):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
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
    except Exception as e:
        logger.error(f"Erro em atualiza_entrega: {e}")
        return pagina_erro(request)

# ==========================================
# BLOCO DIREITOS DO TITULAR (LGPD)
# ==========================================
@login_required
def exportar_dados_titular(request, id_mad_pad):
    try:
        titular = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)
        dados = {
            "Nome": titular.pnome,
            "Sobrenome": titular.snome,
            "Endereco": f"{titular.endereco}, {titular.complemento} - {titular.bairro}, {titular.cidade}/{titular.estado}",
            "Data_Cadastro": titular.data_cadastro,
            "Status_Ativo": titular.flag_ativo,
            "Criancas_Apadrinhadas": []
        }
        vinculos = TbApadrinhamentoCrianca.objects.select_related('id_filho').filter(id_mad_pad=id_mad_pad)
        for v in vinculos:
            dados["Criancas_Apadrinhadas"].append({
                "Nome_Crianca": v.id_filho.pnome,
                "Data_Vinculo": v.data_cadastro
            })
        response = JsonResponse(dados, encoder=DjangoJSONEncoder, json_dumps_params={'ensure_ascii': False, 'indent': 4})
        response['Content-Disposition'] = f'attachment; filename="dados_padrinho_{id_mad_pad}.json"'
        return response
    except Exception as e:
        logger.error(f"Erro em exportar_dados_titular: {e}")
        return pagina_erro(request)

@login_required
def anonimizar_titular(request, id_mad_pad):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
        with transaction.atomic():
            titular = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)
            titular.pnome, titular.snome = "Titular", "Anonimizado (LGPD)"
            sufixo = str(uuid.uuid4())[:6].upper()
            titular.cpf = f"ANON-{sufixo}"
            titular.endereco = "Dado Removido"
            titular.complemento = ""
            if hasattr(titular, 'telefone'):
                titular.telefone = "Removido"
            titular.flag_anonimo, titular.flag_ativo = 'S', 'N'
            titular.save()
            TbEntrega.objects.filter(id_mad_pad=id_mad_pad).update(
                endereco="Endereço Anonimizado (LGPD)",
                bairro="Anonimizado"
            )
            TbLogAuditoria.objects.create(
                usuario=request.user.username,
                acao='ANONIMIZACAO_LGPD',
                rota=f'/padrinhos/{id_mad_pad}',
                ip=request.META.get('REMOTE_ADDR')
            )
        messages.success(request, 'Dados do titular anonimizados com sucesso.')
        return redirect('lista_madrinha_padrinho')
    except Exception as e:
        logger.error(f"Erro em anonimizar_titular: {e}")
        return pagina_erro(request)

# ==========================================
# LGPD - FUNCIONÁRIOS E RESPONSÁVEIS
# ==========================================
@login_required
def exportar_dados_funcionario(request, id_funcionario):
    try:
        func = get_object_or_404(TbFuncionario, id_funcionario=id_funcionario)
        dados = {
            "Nome": func.pnome,
            "Sobrenome": func.snome,
            "Telefone": func.telefone,
            "Endereco": func.endereco,
            "Bairro": func.bairro,
            "Cidade": func.cidade,
            "Estado": func.estado,
            "Status_Ativo": func.flag_ativo
        }
        response = JsonResponse(dados, encoder=DjangoJSONEncoder, json_dumps_params={'ensure_ascii': False, 'indent': 4})
        response['Content-Disposition'] = f'attachment; filename="dados_funcionario_{id_funcionario}.json"'
        return response
    except Exception as e:
        logger.error(f"Erro em exportar_dados_funcionario: {e}")
        return pagina_erro(request)

@login_required
def anonimizar_funcionario(request, id_funcionario):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
        with transaction.atomic():
            func = get_object_or_404(TbFuncionario, id_funcionario=id_funcionario)
            func.pnome, func.snome = "Funcionário", "Anonimizado (LGPD)"
            sufixo = str(uuid.uuid4())[:6].upper()
            func.cpf = f"ANON-{sufixo}"
            func.telefone = "Removido"
            func.endereco = "Removido"
            func.complemento = ""
            func.flag_ativo = 'N'
            func.save()
            TbLogAuditoria.objects.create(
                usuario=request.user.username,
                acao='ANONIMIZACAO_FUNC',
                rota=f'/func/{id_funcionario}',
                ip=request.META.get('REMOTE_ADDR')
            )
        messages.success(request, 'Dados do funcionário anonimizados.')
        return redirect('lista_funcionarios')
    except Exception as e:
        logger.error(f"Erro em anonimizar_funcionario: {e}")
        return pagina_erro(request)

@login_required
def exportar_dados_responsavel(request, id_responsavel):
    try:
        resp = get_object_or_404(TbCadastroResponsavel, id_responsavel=id_responsavel)
        dados = {
            "Nome": resp.pnome,
            "Sobrenome": resp.snome,
            "Data_Nascimento": resp.data_nascimento,
            "Endereco": resp.endereco,
            "Bairro": resp.bairro,
            "Cidade": resp.cidade,
            "Status_Ativo": resp.flag_ativo,
            "Dependentes": []
        }
        filhos = TbFilhosResponsavel.objects.filter(id_responsavel=id_responsavel)
        for filho in filhos:
            dados["Dependentes"].append({
                "Nome": filho.pnome,
                "Data_Nascimento": filho.data_nascimento,
                "Sexo": filho.sexo
            })
        response = JsonResponse(dados, encoder=DjangoJSONEncoder, json_dumps_params={'ensure_ascii': False, 'indent': 4})
        response['Content-Disposition'] = f'attachment; filename="dados_familia_{id_responsavel}.json"'
        return response
    except Exception as e:
        logger.error(f"Erro em exportar_dados_responsavel: {e}")
        return pagina_erro(request)

@login_required
def anonimizar_responsavel(request, id_responsavel):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.", status=405)
    try:
        with transaction.atomic():
            resp = get_object_or_404(TbCadastroResponsavel, id_responsavel=id_responsavel)
            resp.pnome, resp.snome = "Responsável", "Anonimizado (LGPD)"
            sufixo_pai = str(uuid.uuid4())[:6].upper()
            resp.cpf = f"ANON-{sufixo_pai}"
            resp.data_nascimento = "01/01/1900"
            resp.endereco = "Removido"
            resp.complemento = ""
            resp.flag_ativo = 'N'
            resp.save()
            
            filhos = list(TbFilhosResponsavel.objects.filter(id_responsavel=id_responsavel))
            for filho in filhos:
                filho.pnome, filho.snome = "Criança", "Anonimizada"
                sufixo_filho = str(uuid.uuid4())[:6].upper()
                filho.cpf = f"ANON-{sufixo_filho}"
                filho.data_nascimento = "01/01/1900"
                filho.flag_ativo = 'N'
                filho.save()
                
            if filhos:
                TbEntrega.objects.filter(id_crianca__in=filhos).update(
                    endereco="Endereço Anonimizado (LGPD)",
                    bairro="Anonimizado"
                )
                
            TbLogAuditoria.objects.create(
                usuario=request.user.username,
                acao='ANONIMIZACAO_CASCATA',
                rota=f'/resp/{id_responsavel}',
                ip=request.META.get('REMOTE_ADDR')
            )
        messages.success(request, 'Responsável e dependentes anonimizados.')
        return redirect('lista_responsavel')
    except Exception as e:
        logger.error(f"Erro em anonimizar_responsavel: {e}")
        return pagina_erro(request)