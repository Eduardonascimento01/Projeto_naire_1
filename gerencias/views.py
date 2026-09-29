from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.contrib.auth import get_user_model

User = get_user_model()

from gerencias.forms import AccountSignupForm
from gerencias.models import (
    Conn,
    TbFuncionario,
    TbTipoFuncionario,
    TbCadastroResponsavel,
    TbFilhosResponsavel,
    TbOficios,
    TbMadrinhaPadrinho,
    TbApadrinhamentoCrianca,
    TbEvento,
    TbEntrega,
)
import json
import re
from datetime import datetime, date


# Função auxiliar para sanitizar valores e prevenir injeção de SQL (SQL Injection)
def escapar(valor):
    if valor is None:
        return 'NULL'
    texto_limpo = str(valor).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{texto_limpo}'"


# Classe para criação de novos usuários com senha criptografada (Bcrypt/PBKDF2)
class userCreateView(CreateView):
    model = User
    template_name = 'registration/signup_form.html'
    form_class = AccountSignupForm
    success_url = reverse_lazy('login')
    success_message = 'Usuário criado com sucesso!'

    def form_valid(self, form):
        # Criptografa a senha utilizando o algoritmo principal definido no settings.py (Bcrypt)
        form.instance.password = make_password(form.instance.password)
        form.save()
        messages.success(self.request, self.success_message)
        return super(userCreateView, self).form_valid(form)


# Classe auxiliar para estrutura de apadrinhamento
class Apad:
    def __init__(self, id_apad="", madrinha="", crianca="", data_cadastro="", flag_ativo=""):
        self.id_apad = id_apad
        self.madrinha = madrinha
        self.crianca = crianca
        self.data_cadastro = data_cadastro
        self.flag_ativo = flag_ativo


# Página inicial do sistema
def home(request):
    return render(request, 'gerencias/index.html')


# Página padrão para exibição amigável de erros
def pagina_erro(request, mensagem="Ocorreu um erro inesperado no processamento."):
    contexto = {'mensagem': mensagem}
    return render(request, 'gerencias/pagina_erro.html', contexto)


# ==========================================
# BLOCO FUNCIONÁRIOS
# ==========================================

@login_required
def lista_funcionarios(request):
    try:
        lista = Conn.executa_query(
            "SELECT * FROM tb_funcionario WHERE flag_ativo = 'S'"
        )
        return render(request, 'gerencias/lista_funcionarios.html', {'lista': lista})
    except Exception as e:
        mensagem = f"Erro ao listar funcionários: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def novo_funcionario(request):
    try:
        return render(request, 'gerencias/novo_funcionario.html')
    except Exception as e:
        mensagem = f"Erro ao acessar a página de cadastro de funcionário: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def insere_novo_funcionario(request):
    try:
        if request.method == 'POST':
            tp_m = request.POST.get('tp_funcionario')
            pnome = request.POST.get('pnome')
            snome = request.POST.get('snome')
            cpf = (request.POST.get('cpf') or '').replace('.', '').replace('-', '')  # Remove máscara do CPF
            telefone = (request.POST.get('telefone') or '').replace('(', '').replace(')', '').replace('-', '').replace(' ', '')  # Remove máscara do telefone
            rua = request.POST.get('rua') or ''
            numero = request.POST.get('numero') or ''
            rua_n = f"{rua} - {numero}"
            comp = request.POST.get('comp')
            bairro = request.POST.get('bairro')
            cidade = request.POST.get('cidade')
            estado = request.POST.get('estado')
            flag = request.POST.get('flag')

            sql1 = "INSERT INTO tb_funcionario (id_tipo, pnome, snome, cpf, telefone, endereco, complemento, bairro, cidade, estado, flag_ativo) "
            sql2 = f"VALUES({escapar(tp_m)}, {escapar(pnome)}, {escapar(snome)}, {escapar(cpf)}, {escapar(telefone)}, {escapar(rua_n)}, {escapar(comp)}, {escapar(bairro)}, {escapar(cidade)}, {escapar(estado)}, {escapar(flag)})"
            result = Conn.executa_insert(sql1 + sql2)

            func = Conn.executa_query(
                f"SELECT * FROM tb_funcionario WHERE id_funcionario = {escapar(result)}"
            )
            return render(request, 'gerencias/lista_funcionarios.html', {'lista': func})
        else:
            mensagem = f"Erro ao inserir novo funcionário: Método HTTP inválido. Esperado POST, recebido {request.method}."
            return pagina_erro(request, mensagem=mensagem)
    except Exception as e:
        mensagem = f"Erro ao inserir novo funcionário: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def desativa_funcionario(request, id_funcionario):
    try:
        if request.method == 'POST':
            sql = f"UPDATE tb_funcionario SET flag_ativo = 'N' WHERE id_funcionario = {escapar(id_funcionario)}"
            Conn.executa_insert(sql)
            func = Conn.executa_query(
                "SELECT * FROM tb_funcionario WHERE flag_ativo = 'S'"
            )
            return render(request, 'gerencias/lista_funcionarios.html', {'lista': func})
        else:
            mensagem = f"Erro ao desativar funcionário: Método HTTP inválido. Esperado POST, recebido {request.method}."
            return pagina_erro(request, mensagem=mensagem)
    except Exception as e:
        mensagem = f"Erro ao desativar funcionário: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def reativa_funcionario(request, id_funcionario):
    try:
        if request.method == 'POST':
            sql = f"UPDATE tb_funcionario SET flag_ativo = 'S' WHERE id_funcionario = {escapar(id_funcionario)}"
            Conn.executa_insert(sql)
            func = Conn.executa_query(
                f"SELECT * FROM tb_funcionario WHERE id_funcionario = {escapar(id_funcionario)}"
            )
            return render(request, 'gerencias/lista_funcionarios.html', {'lista': func})
        else:
            mensagem = f"Erro ao reativar funcionário: Método HTTP inválido. Esperado POST, recebido {request.method}."
            return pagina_erro(request, mensagem=mensagem)
    except Exception as e:
        mensagem = f"Erro ao reativar funcionário: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def lista_funcionarios_desativos(request):
    try:
        lista = TbFuncionario.objects.filter(flag_ativo='N')
        return render(request, 'gerencias/lista_funcionarios_desativados.html', {'lista': lista})
    except Exception as e:
        mensagem = f"Erro ao listar funcionários desativados: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def atualiza_funcionario(request):
    if request.method == 'POST':
        try:
            funcionario = get_object_or_404(TbFuncionario, id_funcionario=request.POST.get('id_funcionario'))
            id_tipo = request.POST.get('id_tipo')
            tipo_funcionario = get_object_or_404(TbTipoFuncionario, id_tipo=id_tipo)
            funcionario.id_tipo = tipo_funcionario
            funcionario.pnome = request.POST.get('pnome')
            funcionario.snome = request.POST.get('snome')
            funcionario.cpf = (request.POST.get('cpf') or '').replace('.', '').replace('-', '')
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
            mensagem = f"Erro ao atualizar funcionário: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao atualizar funcionário: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def editar_funcionario(request, id_funcionario):
    dados = TbFuncionario.objects.filter(id_funcionario=id_funcionario)
    return render(request, 'gerencias/editar_funcionario.html', {'dados': dados})


# ==========================================
# BLOCO RESPONSÁVEL (FAMÍLIAS)
# ==========================================

@login_required
def novo_responsavel(request):
    return render(request, 'gerencias/novo_responsavel.html')


@login_required
def insere_novo_responsavel(request):
    if request.method == 'POST':
        try:
            id_fun_cad = request.POST.get('id_usuario_cad')
            nome = request.POST.get('pnome')
            sobrenome = request.POST.get('snome')
            cpf = (request.POST.get('cpf') or '').replace('.', '').replace('-', '')
            dt_nasc = (request.POST.get('dt_nasc') or '').replace('-', '')
            if len(dt_nasc) == 8:
                a = dt_nasc[0:4]
                m = dt_nasc[4:6]
                d = dt_nasc[6:8]
                dt_nasc = f"{d}/{m}/{a}"  # Formata a data no padrão 'dd/mm/aaaa'
            resp_trabalha = request.POST.get('resp_trabalha')
            flag_conjuge = request.POST.get('flag_conjuge')
            conjuge_trabalha = request.POST.get('conjuge_trabalha')
            endereco = request.POST.get('endereco')
            comp = request.POST.get('complemento')
            bairro = request.POST.get('bairro')
            cidade = request.POST.get('cidade')
            estado = request.POST.get('estado')
            obs = request.POST.get('obs')

            sql1 = "INSERT INTO tb_cadastro_responsavel (id_usuario_cad, pnome, snome, cpf, data_nascimento, flag_responsavel_trabalha, flag_conjuge, flag_conjuge_trabalha, endereco, complemento, bairro, cidade, estado, observacoes) "
            sql2 = f"VALUES({escapar(id_fun_cad)}, {escapar(nome)}, {escapar(sobrenome)}, {escapar(cpf)}, {escapar(dt_nasc)}, {escapar(resp_trabalha)}, {escapar(flag_conjuge)}, {escapar(conjuge_trabalha)}, {escapar(endereco)}, {escapar(comp)}, {escapar(bairro)}, {escapar(cidade)}, {escapar(estado)}, {escapar(obs)})"
            Conn.executa_insert(sql1 + sql2)
            return redirect('lista_responsavel')

        except Exception as e:
            mensagem = f"Erro ao inserir responsável: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        return render(request, 'gerencias/novo_responsavel.html')


@login_required
def lista_responsavel(request):
    try:
        responsavel = TbCadastroResponsavel.objects.filter(flag_ativo='S', flag_validado='S')
        contexto = {
            'dados': responsavel,
            'titulo': 'Responsáveis Validados'
        }
        return render(request, 'gerencias/lista_responsavel.html', contexto)
    except Exception as e:
        mensagem = f"Erro ao listar responsáveis: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def lista_responsavel_nval(request):
    try:
        responsavel = TbCadastroResponsavel.objects.filter(flag_ativo='S', flag_validado='N')
        contexto = {
            'dados': responsavel,
            'titulo': 'Responsáveis não Validados'
        }
        return render(request, 'gerencias/lista_responsavel_nval.html', contexto)
    except Exception as e:
        mensagem = f"Erro ao listar responsáveis não validados: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def lista_responsavel_des(request):
    try:
        responsavel = TbCadastroResponsavel.objects.filter(flag_ativo='N')
        contexto = {
            'dados': responsavel,
            'titulo': 'Responsáveis Desativados'
        }
        return render(request, 'gerencias/lista_responsavel_des.html', contexto)
    except Exception as e:
        mensagem = f"Erro ao listar responsáveis desativados: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def edit_responsavel(request, id_responsavel):
    if request.method == 'POST':
        try:
            responsavel = TbCadastroResponsavel.objects.filter(pk=id_responsavel)
            contexto = {
                'dados': responsavel,
                'titulo': 'Responsável'
            }
            return render(request, 'gerencias/editar_responsavel.html', contexto)
        except Exception as e:
            mensagem = f"Erro ao acessar a página de edição de responsável: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao acessar a página de edição de responsável: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def atualiza_responsavel(request):
    if request.method == 'POST':
        try:
            responsavel = get_object_or_404(TbCadastroResponsavel, pk=request.POST.get('id_responsavel'))
            responsavel.pnome = request.POST.get('pnome')
            responsavel.snome = request.POST.get('snome')
            responsavel.cpf = (request.POST.get('cpf') or '').replace(".", "").replace("-", "")
            responsavel.data_nascimento = request.POST.get('dt_nasc')
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
            mensagem = f"Erro ao atualizar responsável: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao atualizar responsável: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def valida_responsavel(request, id_responsavel):
    if request.method == 'POST':
        try:
            responsavel = get_object_or_404(TbCadastroResponsavel, pk=id_responsavel)
            responsavel.flag_validado = 'S'
            responsavel.save()
            registros = TbCadastroResponsavel.objects.filter(flag_ativo='N').order_by('-ultima_atualizacao')
            contexto = {
                'dados': registros,
                'titulo': 'Responsáveis Inativos'
            }
            return render(request, 'gerencias/lista_responsavel.html', contexto)
        except Exception as e:
            mensagem = f"Erro ao validar responsável: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao validar responsável: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def desativa_responsavel(request, id_responsavel):
    if request.method == 'POST':
        try:
            responsavel = get_object_or_404(TbCadastroResponsavel, pk=id_responsavel)
            responsavel.flag_ativo = 'N'
            responsavel.save()
            registros = TbCadastroResponsavel.objects.filter(flag_ativo='N').order_by('-ultima_atualizacao')
            contexto = {
                'dados': registros,
                'titulo': 'Responsáveis Inativos'
            }
            return render(request, 'gerencias/lista_responsavel.html', contexto)
        except Exception as e:
            mensagem = f"Erro ao desativar responsável: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao desativar responsável: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def reativa_responsavel(request, id_responsavel):
    if request.method == 'POST':
        try:
            responsavel = get_object_or_404(TbCadastroResponsavel, pk=id_responsavel)
            responsavel.flag_ativo = 'S'
            responsavel.save()
            registros = TbCadastroResponsavel.objects.filter(flag_ativo='S').order_by('-ultima_atualizacao')
            contexto = {
                'dados': registros,
                'titulo': 'Responsáveis Ativos'
            }
            return render(request, 'gerencias/lista_responsavel.html', contexto)
        except Exception as e:
            mensagem = f"Erro ao reativar responsável: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao reativar responsável: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


# ==========================================
# BLOCO FILHOS (CRIANÇAS)
# ==========================================

@login_required
def lista_filhos(request, id_responsavel):
    try:
        registros = TbFilhosResponsavel.objects.filter(id_responsavel=id_responsavel, flag_ativo='S').order_by('-data_cadastro')
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
        mensagem = f"Erro ao listar filhos do responsável: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def lista_filhos_total(request):
    try:
        lista = Conn.executa_query(
            "SELECT * FROM tb_filhos_responsavel ORDER BY id_responsavel"
        )
        return render(request, 'gerencias/lista_filhos_total.html', {'lista': lista})
    except Exception as e:
        mensagem = f"Erro ao listar todas as crianças: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def desativa_filhos_responsavel(request, id_responsavel):
    if request.method == 'POST':
        try:
            lista = TbFilhosResponsavel.objects.filter(id_responsavel=id_responsavel)
            for filho in lista:
                filho.flag_ativo = 'N'
                filho.save()
            return redirect('lista_filhos', id_responsavel=id_responsavel)
        except Exception as e:
            mensagem = f"Erro ao desativar filhos do responsável: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao desativar filhos do responsável: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def reativa_filhos_responsavel(request, id_responsavel):
    if request.method == 'POST':
        try:
            lista = TbFilhosResponsavel.objects.filter(id_responsavel=id_responsavel)
            for filho in lista:
                filho.flag_ativo = 'S'
                filho.save()
            return redirect('lista_filhos', id_responsavel=id_responsavel)
        except Exception as e:
            mensagem = f"Erro ao reativar filhos do responsável: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao reativar filhos do responsável: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def desativar_filho(request, id_responsavel):
    if request.method == 'POST':
        try:
            id_filho = request.POST.get('id_filho')
            filho = TbFilhosResponsavel.objects.filter(id_filho=id_filho).first()
            if filho:
                filho.flag_ativo = 'N'
                filho.save()
            return redirect('lista_filhos', id_responsavel=id_responsavel)
        except Exception as e:
            mensagem = f"Erro ao desativar criança com ID {id_filho}.\n {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao desativar criança: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def reativar_filho(request, id_filho):
    if request.method == 'POST':
        try:
            filho = TbFilhosResponsavel.objects.filter(id_filho=id_filho).first()
            filho.flag_ativo = 'S'
            id_responsavel = filho.id_responsavel.id_responsavel
            filho.save()
            return redirect('lista_filhos', id_responsavel=id_responsavel)
        except Exception as e:
            mensagem = f"Erro ao reativar criança com ID {id_filho}.\n {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao reativar criança: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def lista_filhos_responsavel(request):
    try:
        registros = TbFilhosResponsavel.objects.filter(
            id_responsavel=request.POST.get('id_responsavel'),
            flag_ativo='S'
        ).order_by('-data_cadastro')
        contexto = {
            'dados': registros,
            'titulo': 'Responsáveis Ativos'
        }
        return render(request, 'gerencias/lista_responsavel.html', contexto)
    except Exception as e:
        mensagem = f"Erro ao listar filhos do responsável: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def novo_filho(request, id_responsavel):
    if request.method == 'POST':
        try:
            registro = TbFilhosResponsavel.objects.filter(id_responsavel=id_responsavel).first()
            contexto = {
                'dados': registro,
                'id_responsavel': id_responsavel,
                'titulo': 'Crianças Cadastradas'
            }
            return render(request, 'gerencias/novo_filho.html', contexto)
        except Exception as e:
            mensagem = f"Erro ao acessar a página de cadastro de criança: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao acessar a página de cadastro de criança: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def editar_filho(request, id_filho):
    if request.method == 'POST':
        try:
            registro = TbFilhosResponsavel.objects.filter(id_filho=id_filho).first()
            contexto = {
                'dados': registro,
                'id_responsavel': registro.id_responsavel,
                'titulo': 'Editar Criança'
            }
            return render(request, 'gerencias/editar_filho.html', contexto)
        except Exception as e:
            mensagem = f"Erro ao acessar a página de edição de criança: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao acessar a página de edição de criança: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def insere_novo_filho(request):
    if request.method == 'POST':
        try:
            id_responsavel = request.POST.get('responsavel')
            id_usuario_cad = request.user.id
            pnome = request.POST.get('pnome')
            snome = request.POST.get('snome')
            dt_nasc = (request.POST.get('dt_nasc') or '').replace('-', '')
            if len(dt_nasc) == 8:
                a = dt_nasc[0:4]
                m = dt_nasc[4:6]
                d = dt_nasc[6:8]
                dt_nasc = f"{d}/{m}/{a}"
            cpf = (request.POST.get('cpf') or '').replace('.', '').replace('-', '')
            sexo = request.POST.get('sexo')
            roupa = request.POST.get('roupa')
            sapato = request.POST.get('sapato')
            outra_ong = request.POST.get('outra_ong')

            sql1 = "INSERT INTO tb_filhos_responsavel (id_responsavel, id_usuario_cad, pnome, snome, data_nascimento, cpf, sexo, numero_roupa, numero_sapato, cadastro_outra_ong) "
            sql2 = f"VALUES({escapar(id_responsavel)}, {escapar(id_usuario_cad)}, {escapar(pnome)}, {escapar(snome)}, {escapar(dt_nasc)}, {escapar(cpf)}, {escapar(sexo)}, {escapar(roupa)}, {escapar(sapato)}, {escapar(outra_ong)})"

            result = Conn.executa_insert(sql1 + sql2)
            if result:
                return redirect('lista_filhos', id_responsavel)
            return redirect('lista_filhos', id_responsavel)
        except Exception as e:
            mensagem = f"Erro ao inserir nova criança: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao inserir nova criança: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


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
                # Sanitiza o termo de busca para evitar SQL Injection na consulta LIKE
                termo_seguro = termo_busca.replace("\\", "\\\\").replace("'", "\\'").replace("%", "\\%")
                resultados = Conn.executa_query(
                    f"SELECT * FROM tb_filhos_responsavel WHERE flag_ativo = 'S' AND CONCAT(pnome, ' ', snome) LIKE '%{termo_seguro}%'"
                )
                contexto = {
                    'resultados': resultados,
                    'termo_busca': termo_busca,
                    'tipo_busca': tipo_busca,
                    'total_resultados': len(resultados),
                }
                return render(request, 'gerencias/buscar_filhos.html', contexto)
            elif tipo_busca == 'idade':
                try:
                    idade_busca = int(termo_busca)
                    todos_filhos = TbFilhosResponsavel.objects.select_related('id_responsavel')

                    for filho in todos_filhos:
                        idade = calcular_idade(filho.data_nascimento)
                        if idade == idade_busca:
                            resultados.append(filho)

                except ValueError:
                    resultados = []
                    termo_busca = 'Por favor, digite um número válido para idade'

    # Adiciona a idade calculada a cada resultado
    for filho in resultados:
        filho.idade = calcular_idade(filho.data_nascimento)

    contexto = {
        'resultados': resultados,
        'termo_busca': termo_busca,
        'tipo_busca': tipo_busca,
        'total_resultados': len(resultados),
    }

    return render(request, 'gerencias/buscar_filhos.html', contexto)


# Função auxiliar para calcular a idade exata a partir da data de nascimento
def calcular_idade(data_nascimento_str):
    if not data_nascimento_str:
        return None
    try:
        data_nasc = datetime.strptime(data_nascimento_str, '%d/%m/%Y').date()
        hoje = date.today()
        idade = hoje.year - data_nasc.year
        if hoje.month < data_nasc.month or (hoje.month == data_nasc.month and hoje.day < data_nasc.day):
            idade -= 1
        return idade
    except Exception:
        return None


# ==========================================
# BLOCO OFÍCIOS
# ==========================================

@login_required
def insere_novo_oficio(request):
    if request.method == 'POST':
        try:
            criador = request.POST.get('responsavel')
            remetente = request.POST.get('remetente')
            destinatario = request.POST.get('destinatario')
            mensagem = request.POST.get('mensagem')
            mensagem = f"Mensagem de {remetente} para {destinatario}: {mensagem}"
            sql1 = "INSERT INTO tb_oficios (id_usuario, destinatario, mensagem) "
            sql2 = f"VALUES({escapar(criador)}, {escapar(destinatario)}, {escapar(mensagem)})"
            result = Conn.executa_insert(sql1 + sql2)
            if result:
                lista = Conn.executa_query(
                    "SELECT * FROM tb_oficios ORDER BY id_oficio DESC LIMIT 1"
                )
                return render(request, 'gerencias/lista_oficios.html', {'lista': lista})

        except Exception as e:
            mensagem = f"Erro ao inserir novo ofício: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao inserir novo ofício: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def novo_oficio(request):
    if request.method == 'POST':
        try:
            contexto = {
                'usuario': request.user,
                'id_usuario_cad': request.user.id,
                'username': request.user.username
            }
            return render(request, 'gerencias/novo_oficio.html', contexto)
        except Exception as e:
            mensagem = f"Erro ao acessar a página de cadastro de ofício: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao acessar a página de cadastro de ofício: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def lista_oficio(request):
    try:
        lista = TbOficios.objects.select_related('id_usuario').all().order_by('-data_criacao')
        primeiro_id = lista.first().id_oficio if lista.exists() else None
        contexto = {
            'id_oficio': primeiro_id,
            'lista': lista,
            'total': lista.count()
        }
        return render(request, 'gerencias/lista_oficios.html', contexto)
    except Exception as e:
        mensagem = f"Erro ao listar ofícios: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def exibe_oficio(request, id_oficio):
    try:
        oficio = get_object_or_404(TbOficios, id_oficio=id_oficio)
        contexto = {
            'oficio': oficio,
            'id_oficio': id_oficio,
            'mensagem': oficio.mensagem,
            'remetente': oficio.id_usuario.username
        }
        return render(request, 'gerencias/exibe_oficio.html', contexto)
    except Exception as e:
        mensagem = f"Erro ao exibir ofício com ID {id_oficio}.\n {e}"
        return render(request, 'gerencias/pagina_erro.html', {'mensagem': mensagem})


@login_required
def excluir_oficio(request, id_oficio):
    if request.method == 'POST':
        try:
            registro = TbOficios.objects.filter(id_oficio=id_oficio)
            registro.delete()
            return redirect('lista_oficio')
        except Exception as e:
            mensagem = f"Erro ao excluir ofício com ID {id_oficio}.\n {e}"
            return render(request, 'gerencias/pagina_erro.html', {'mensagem': mensagem})
    else:
        mensagem = f"Erro ao excluir ofício: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return render(request, 'gerencias/pagina_erro.html', {'mensagem': mensagem})


# ==========================================
# BLOCO MADRINHAS E PADRINHOS
# ==========================================

@login_required
def novo_madrinha_padrinho(request):
    if request.method == 'POST':
        try:
            contexto = {
                'usuario': request.user,
                'id_usuario_cad': request.POST.get('id_usuario_cad', request.user.id)
            }
            return render(request, 'gerencias/novo_madrinha_padrinho.html', contexto)
        except Exception as e:
            mensagem = f"Erro ao acessar a página de cadastro de madrinha/padrinho: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao acessar a página de cadastro de madrinha/padrinho: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def inserir_madrinha_padrinho(request):
    if request.method == 'POST':
        try:
            id_usuario_cad = request.POST.get('id_usuario_cad')
            cpf = (request.POST.get('cpf') or '').replace('.', '').replace('-', '')  # Remove máscara
            flag_anonimo = request.POST.get('flag_anonimo')
            pnome = request.POST.get('pnome')
            snome = request.POST.get('snome')
            endereco = request.POST.get('endereco')
            complemento = request.POST.get('complemento')
            bairro = request.POST.get('bairro')
            cidade = request.POST.get('cidade')
            estado = request.POST.get('estado')
            flag_ativo = request.POST.get('flag_ativo')

            sql1 = "INSERT INTO tb_madrinha_padrinho (id_usuario_cad, cpf, flag_anonimo, pnome, snome, endereco, complemento, bairro, cidade, estado, flag_ativo) "
            sql2 = f"VALUES({escapar(id_usuario_cad)}, {escapar(cpf)}, {escapar(flag_anonimo)}, {escapar(pnome)}, {escapar(snome)}, {escapar(endereco)}, {escapar(complemento)}, {escapar(bairro)}, {escapar(cidade)}, {escapar(estado)}, {escapar(flag_ativo)})"
            result = Conn.executa_insert(sql1 + sql2)

            if result:
                return redirect('lista_madrinha_padrinho')
            return redirect('lista_madrinha_padrinho')
        except Exception as e:
            mensagem = f"Erro ao inserir madrinha/padrinho: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao inserir madrinha/padrinho: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def lista_madrinha_padrinho(request):
    try:
        lista = Conn.executa_query(
            "SELECT * FROM tb_madrinha_padrinho WHERE flag_ativo = 'S' ORDER BY data_cadastro DESC"
        )
        return render(request, 'gerencias/listar_madrinhas_padrinhos.html', {'dados': lista})
    except Exception as e:
        mensagem = f"Erro ao listar madrinhas/padrinhos: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def lista_madrinha_padrinho_desativados(request):
    try:
        lista = Conn.executa_query(
            "SELECT * FROM tb_madrinha_padrinho WHERE flag_ativo = 'N' ORDER BY data_cadastro DESC"
        )
        return render(request, 'gerencias/listar_madrinhas_padrinhos_desativados.html', {'dados': lista})
    except Exception as e:
        mensagem = f"Erro ao listar madrinhas/padrinhos: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def editar_madrinha_padrinho(request, id_mad_pad):
    try:
        item = Conn.executa_query(
            f"SELECT * FROM tb_madrinha_padrinho WHERE id_mad_pad = {escapar(id_mad_pad)}"
        )

        if item and len(item) > 0:
            registro = item[0]
        else:
            registro = None

        return render(request, 'gerencias/editar_madrinha_padrinho.html', {'registro': registro})
    except Exception as e:
        mensagem = f"Erro ao acessar a página de edição de madrinha/padrinho: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def atualiza_madrinha_padrinho(request, id_mad_pad):
    if request.method == 'POST':
        try:
            registro = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)
            registro.cpf = request.POST.get('cpf', '').replace('.', '').replace('-', '')
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
            mensagem = f"Erro ao atualizar madrinha/padrinho: {e}"
            return pagina_erro(request, mensagem=mensagem)

    else:
        mensagem = f"Erro ao atualizar madrinha/padrinho: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def reativar_madrinha_padrinho(request, id_mad_pad):
    if request.method == 'POST':
        try:
            registro = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)
            registro.flag_ativo = 'S'
            registro.atualizacao_cad = timezone.now()
            registro.save()
            messages.success(request, 'Registro reativado com sucesso!')
            return redirect('lista_madrinha_padrinho')
        except Exception as e:
            mensagem = f"Erro ao reativar madrinha/padrinho: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao reativar madrinha/padrinho: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def api_salvar_madrinha_padrinho(request):
    if request.method == 'POST':
        try:
            # Recebe os dados no formato JSON
            dados = json.loads(request.body)

            cpf = dados.get('cpf', '').replace('.', '').replace('-', '')

            # Valida se o CPF já está cadastrado
            if TbMadrinhaPadrinho.objects.filter(cpf=cpf).exists():
                mensagem = f"Erro: CPF {cpf} já cadastrado!"
                return pagina_erro(request, mensagem=mensagem)

            novo = TbMadrinhaPadrinho.objects.create(
                id_usuario_cad=request.user,
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

            return JsonResponse({
                'success': True,
                'id': novo.id_mad_pad,
                'message': 'Cadastro realizado com sucesso'
            })

        except Exception as e:
            mensagem = f"Erro ao salvar madrinha/padrinho via API: {e}"
            return pagina_erro(request, mensagem=mensagem)

    else:
        mensagem = f"Erro ao salvar madrinha/padrinho via API: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def apadrinhar_crianca(request, id_mad_pad):
    if request.method == 'POST':
        try:
            registro = TbMadrinhaPadrinho.objects.filter(id_mad_pad=id_mad_pad).first()
            criancas = TbFilhosResponsavel.objects.filter(flag_ativo='S').order_by('pnome')
            contexto = {
                'registro': registro,
                'criancas': criancas,
                'titulo': 'Apadrinhar Criança'
            }
            return render(request, 'gerencias/apadrinhar_crianca.html', contexto)
        except Exception as e:
            mensagem = f"Erro ao acessar a página de apadrinhamento: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao acessar a página de apadrinhamento: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def vincular_mad_pad_crianca(request):
    if request.method == 'POST':
        try:
            id_mad_pad = request.POST.get('id_mad_pad')
            id_filho = request.POST.get('id_filho')
            sql1 = "INSERT INTO tb_apadrinhamento_crianca (id_mad_pad, id_filho) "
            sql2 = f"VALUES({escapar(id_mad_pad)}, {escapar(id_filho)})"
            Conn.executa_insert(sql1 + sql2)
            return redirect('lista_apadrinhamento')
        except Exception as e:
            mensagem = f"Erro ao vincular madrinha/padrinho à criança: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao vincular madrinha/padrinho à criança: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def lista_apadrinhamento(request):
    try:
        apadrinhamento = TbApadrinhamentoCrianca.objects.all().order_by('-data_cadastro')
        return render(request, 'gerencias/lista_apadrinhamentos.html', {'registros': apadrinhamento})
    except Exception as e:
        mensagem = f"Erro ao listar apadrinhamentos: {e}"
        return pagina_erro(request, mensagem=mensagem)


# ==========================================
# BLOCO EVENTOS E ENTREGAS
# ==========================================

@login_required
def listar_eventos(request):
    try:
        sql = "SELECT * FROM tb_evento ORDER BY data_evento DESC"
        lista = Conn.executa_query(sql)
        return render(request, 'gerencias/listar_eventos.html', {'lista': lista})
    except Exception as e:
        mensagem = f"Erro ao listar eventos: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def novo_evento(request):
    try:
        return render(request, 'gerencias/novo_evento.html')
    except Exception as e:
        mensagem = f"Erro ao acessar página de novo evento: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def atualiza_evento(request, id_evento):
    if request.method == 'POST':
        try:
            evento = TbEvento.objects.get(id_evento=id_evento)
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
            mensagem = f"Erro ao atualizar evento: {e}"
            return pagina_erro(request, mensagem=mensagem)

    else:
        mensagem = f"Erro ao atualizar evento: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def insere_novo_evento(request):
    if request.method == 'POST':
        try:
            nome = request.POST.get('nome')
            data_evento = request.POST.get('data_evento')
            endereco = request.POST.get('endereco')
            bairro = request.POST.get('bairro')
            cidade = request.POST.get('cidade')
            estado = request.POST.get('estado')
            flag_finalizado = request.POST.get('flag_finalizado', 'N')

            if not all([nome, data_evento, endereco, bairro, cidade, estado]):
                mensagem = "Todos os campos obrigatórios devem ser preenchidos."
                return pagina_erro(request, mensagem=mensagem)

            if not re.match(r'^\d{2}/\d{2}/\d{4}$', data_evento):
                messages.error(request, 'Formato de data inválido. Use dd/mm/aaaa.')
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
            mensagem = f"Erro ao inserir novo evento: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao inserir novo evento: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def editar_evento(request, id_evento):
    try:
        evento = TbEvento.objects.get(id_evento=id_evento)
        contexto = {
            'registro': evento
        }
        return render(request, 'gerencias/editar_evento.html', contexto)
    except Exception as e:
        mensagem = f"Erro ao editar evento: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def finalizar_evento(request, id_evento):
    if request.method == 'POST':
        try:
            evento = TbEvento.objects.get(id_evento=id_evento)
            evento.flag_finalizado = 'S'
            evento.save()

            return redirect('listar_eventos')
        except Exception as e:
            mensagem = f"Erro ao finalizar evento: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao finalizar evento: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def listar_entregas(request):
    try:
        entregas = TbEntrega.objects.all().order_by('-id_evento')
        return render(request, 'gerencias/listar_entregas.html', {'lista': entregas})
    except Exception as e:
        mensagem = f"Erro ao listar entregas do evento: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def nova_entrega(request):
    try:
        evento = TbEvento.objects.all().order_by('-id_evento')
        criancas = TbFilhosResponsavel.objects.filter(flag_ativo='S').order_by('pnome')
        madrinhas_padrinhos = TbMadrinhaPadrinho.objects.filter(flag_ativo='S').order_by('pnome')
        contexto = {
            'evento': evento,
            'criancas': criancas,
            'mad_pad': madrinhas_padrinhos
        }
        return render(request, 'gerencias/nova_entrega.html', contexto)
    except Exception as e:
        mensagem = f"Erro ao acessar a página de nova entrega: {e}"
        return pagina_erro(request, mensagem=mensagem)


@login_required
def insere_nova_entrega(request):
    if request.method == 'POST':
        try:
            id_evento = request.POST.get('id_evento')
            id_filho = request.POST.get('id_crianca')
            id_mad_pad = request.POST.get('id_mad_pad')

            evento = TbEvento.objects.filter(id_evento=id_evento).first()
            endereco = evento.endereco if evento else ''
            bairro = evento.bairro if evento else ''
            cidade = evento.cidade if evento else ''
            estado = evento.estado if evento else ''

            # Insere a nova entrega vinculada ao evento
            sql1 = "INSERT INTO tb_entrega (id_evento, id_mad_pad, id_crianca, endereco, cidade, bairro, estado) "
            sql2 = f"VALUES({escapar(id_evento)}, {escapar(id_mad_pad)}, {escapar(id_filho)}, {escapar(endereco)}, {escapar(cidade)}, {escapar(bairro)}, {escapar(estado)})"
            Conn.executa_insert(sql1 + sql2)
            return redirect('listar_entregas')

        except Exception as e:
            mensagem = f"Erro ao inserir nova entrega: {e}"
            return pagina_erro(request, mensagem=mensagem)
    else:
        mensagem = f"Erro ao inserir nova entrega: Método HTTP inválido. Esperado POST, recebido {request.method}."
        return pagina_erro(request, mensagem=mensagem)


@login_required
def editar_entrega(request, id_entrega):
    try:
        entrega = TbEntrega.objects.get(id_entrega=id_entrega)
        evento = entrega.id_evento
        criancas = TbFilhosResponsavel.objects.filter(flag_ativo='S').order_by('pnome')
        madrinhas_padrinhos = TbMadrinhaPadrinho.objects.filter(flag_ativo='S').order_by('pnome')
        contexto = {
            'entrega': entrega,
            'evento': evento,
            'criancas': criancas,
            'madrinhas_padrinhos': madrinhas_padrinhos
        }
        return render(request, 'gerencias/editar_entrega.html', contexto)
    except Exception as e:
        mensagem = f"Erro ao acessar a página de edição de entrega: {e}"
        return pagina_erro(request, mensagem=mensagem)