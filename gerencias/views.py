from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Q  # Necessário para buscas avançadas com ORM

# Esta função substitui o login_required padrão e exige que o usuário seja Administrador (is_staff)
def login_required(function=None):
    return user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser))(function)

from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.contrib.auth import get_user_model

User = get_user_model()

from gerencias.forms import AccountSignupForm
from gerencias.models import (
    Conn, TbFuncionario, TbTipoFuncionario, TbCadastroResponsavel,
    TbFilhosResponsavel, TbOficios, TbMadrinhaPadrinho,
    TbApadrinhamentoCrianca, TbEvento, TbEntrega,
)
import json
import re
from datetime import datetime, date

# Função auxiliar de Privacidade (LGPD) para mascarar dados sensíveis na tela
def mascarar_cpf(cpf):
    if not cpf: 
        return ""
    cpf_limpo = ''.join(filter(str.isdigit, str(cpf)))
    if len(cpf_limpo) == 11:
        return f"***.***.***-{cpf_limpo[-2:]}"
    return "***.***.***-**"

# Classe para criação de novos usuários com senha criptografada (Bcrypt/PBKDF2)
class userCreateView(CreateView):
    model = User
    template_name = 'registration/signup_form.html'
    form_class = AccountSignupForm
    success_url = reverse_lazy('login')
    success_message = 'Usuário criado com sucesso!'

    def form_valid(self, form):
        form.instance.password = make_password(form.instance.password)
        messages.success(self.request, self.success_message)
        return super(userCreateView, self).form_valid(form)

class Apad:
    def __init__(self, id_apad="", madrinha="", crianca="", data_cadastro="", flag_ativo=""):
        self.id_apad = id_apad
        self.madrinha = madrinha
        self.crianca = crianca
        self.data_cadastro = data_cadastro
        self.flag_ativo = flag_ativo

def home(request):
    return render(request, 'gerencias/index.html')

def pagina_erro(request, mensagem="Ocorreu um erro inesperado no processamento."):
    contexto = {'mensagem': mensagem}
    return render(request, 'gerencias/pagina_erro.html', contexto)


# ==========================================
# BLOCO FUNCIONÁRIOS
# ==========================================

@login_required
def lista_funcionarios(request):
    try:
        lista = TbFuncionario.objects.filter(flag_ativo='S')
        for func in lista:
            func.cpf = mascarar_cpf(func.cpf)
        return render(request, 'gerencias/lista_funcionarios.html', {'lista': lista})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro ao listar funcionários: {e}")


@login_required
def novo_funcionario(request):
    try:
        return render(request, 'gerencias/novo_funcionario.html')
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro ao acessar a página: {e}")


@login_required
def insere_novo_funcionario(request):
    try:
        if request.method == 'POST':
            tp_m = request.POST.get('tp_funcionario')
            pnome = request.POST.get('pnome')
            snome = request.POST.get('snome')
            cpf = (request.POST.get('cpf') or '').replace('.', '').replace('-', '')
            telefone = (request.POST.get('telefone') or '').replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
            rua = request.POST.get('rua') or ''
            numero = request.POST.get('numero') or ''
            rua_n = f"{rua}, {numero}"
            comp = request.POST.get('comp')
            bairro = request.POST.get('bairro')
            cidade = request.POST.get('cidade')
            estado = request.POST.get('estado')
            flag = request.POST.get('flag')

            sql = "INSERT INTO tb_funcionario (id_tipo, pnome, snome, cpf, telefone, endereco, complemento, bairro, cidade, estado, flag_ativo) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            result = Conn.executa_insert(sql, (tp_m, pnome, snome, cpf, telefone, rua_n, comp, bairro, cidade, estado, flag))

            # Atualizado para ORM para mascaramento correto no retorno
            func = TbFuncionario.objects.filter(id_funcionario=result)
            for f in func:
                f.cpf = mascarar_cpf(f.cpf)
            return render(request, 'gerencias/lista_funcionarios.html', {'lista': func})
        else:
            return pagina_erro(request, mensagem=f"Método HTTP inválido.")
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro ao inserir funcionário: {e}")


@login_required
def desativa_funcionario(request, id_funcionario):
    try:
        if request.method == 'POST':
            Conn.executa_insert("UPDATE tb_funcionario SET flag_ativo = 'N' WHERE id_funcionario = %s", (id_funcionario,))
            return redirect('lista_funcionarios')
        else:
            return pagina_erro(request, mensagem="Método HTTP inválido.")
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro ao desativar: {e}")


@login_required
def reativa_funcionario(request, id_funcionario):
    try:
        if request.method == 'POST':
            Conn.executa_insert("UPDATE tb_funcionario SET flag_ativo = 'S' WHERE id_funcionario = %s", (id_funcionario,))
            return redirect('lista_funcionarios')
        else:
            return pagina_erro(request, mensagem="Método HTTP inválido.")
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro ao reativar: {e}")


@login_required
def lista_funcionarios_desativos(request):
    try:
        lista = TbFuncionario.objects.filter(flag_ativo='N')
        for func in lista:
            func.cpf = mascarar_cpf(func.cpf)
        return render(request, 'gerencias/lista_funcionarios_desativados.html', {'lista': lista})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro ao listar: {e}")

@login_required
def atualiza_funcionario(request):
    if request.method == 'POST':
        try:
            funcionario = get_object_or_404(TbFuncionario, id_funcionario=request.POST.get('id_funcionario'))
            funcionario.id_tipo = get_object_or_404(TbTipoFuncionario, id_tipo=request.POST.get('id_tipo'))
            funcionario.pnome = request.POST.get('pnome')
            funcionario.snome = request.POST.get('snome')
            
            # BLINDAGEM LGPD: Só atualiza o CPF se ele NÃO contiver os asteriscos da máscara
            cpf_form = request.POST.get('cpf', '')
            if '*' not in cpf_form:
                funcionario.cpf = cpf_form.replace('.', '').replace('-', '')
                
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
            return pagina_erro(request, mensagem=f"Erro ao atualizar: {e}")
    else:
        return pagina_erro(request, mensagem="Método HTTP inválido.")

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
            id_fun_cad = request.user.id
            nome = request.POST.get('pnome')
            sobrenome = request.POST.get('snome')
            cpf = (request.POST.get('cpf') or '').replace('.', '').replace('-', '')
            dt_nasc = (request.POST.get('dt_nasc') or '').replace('-', '')
            if len(dt_nasc) == 8:
                dt_nasc = f"{dt_nasc[6:8]}/{dt_nasc[4:6]}/{dt_nasc[0:4]}" 
            
            resp_trabalha = request.POST.get('resp_trabalha')
            flag_conjuge = request.POST.get('flag_conjuge')
            conjuge_trabalha = request.POST.get('conjuge_trabalha')
            endereco = request.POST.get('endereco')
            comp = request.POST.get('complemento')
            bairro = request.POST.get('bairro')
            cidade = request.POST.get('cidade')
            estado = request.POST.get('estado')
            obs = request.POST.get('obs')

            sql = "INSERT INTO tb_cadastro_responsavel (id_usuario_cad, pnome, snome, cpf, data_nascimento, flag_responsavel_trabalha, flag_conjuge, flag_conjuge_trabalha, endereco, complemento, bairro, cidade, estado, observacoes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            Conn.executa_insert(sql, (id_fun_cad, nome, sobrenome, cpf, dt_nasc, resp_trabalha, flag_conjuge, conjuge_trabalha, endereco, comp, bairro, cidade, estado, obs))
            return redirect('lista_responsavel')
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro ao inserir responsável: {e}")
    else:
        return render(request, 'gerencias/novo_responsavel.html')


@login_required
def lista_responsavel(request):
    try:
        responsavel = TbCadastroResponsavel.objects.filter(flag_ativo='S', flag_validado='S')
        for resp in responsavel:
            resp.cpf = mascarar_cpf(resp.cpf)
        return render(request, 'gerencias/lista_responsavel.html', {'dados': responsavel, 'titulo': 'Responsáveis Validados'})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro ao listar: {e}")


@login_required
def lista_responsavel_nval(request):
    try:
        responsavel = TbCadastroResponsavel.objects.filter(flag_ativo='S', flag_validado='N')
        for resp in responsavel:
            resp.cpf = mascarar_cpf(resp.cpf)
        return render(request, 'gerencias/lista_responsavel_nval.html', {'dados': responsavel, 'titulo': 'Responsáveis não Validados'})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro: {e}")


@login_required
def lista_responsavel_des(request):
    try:
        responsavel = TbCadastroResponsavel.objects.filter(flag_ativo='N')
        for resp in responsavel:
            resp.cpf = mascarar_cpf(resp.cpf)
        return render(request, 'gerencias/lista_responsavel_des.html', {'dados': responsavel, 'titulo': 'Responsáveis Desativados'})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro: {e}")


@login_required
def edit_responsavel(request, id_responsavel):
    if request.method == 'POST':
        try:
            responsavel = TbCadastroResponsavel.objects.filter(pk=id_responsavel)
            return render(request, 'gerencias/editar_responsavel.html', {'dados': responsavel, 'titulo': 'Responsável'})
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro: {e}")
    else:
        return pagina_erro(request, mensagem="Método inválido.")


@login_required
def atualiza_responsavel(request):
    if request.method == 'POST':
        try:
            responsavel = get_object_or_404(TbCadastroResponsavel, pk=request.POST.get('id_responsavel'))
            responsavel.pnome = request.POST.get('pnome')
            responsavel.snome = request.POST.get('snome')
            
            # BLINDAGEM LGPD: Só atualiza o CPF se ele NÃO contiver asteriscos
            cpf_form = request.POST.get('cpf', '')
            if '*' not in cpf_form:
                responsavel.cpf = cpf_form.replace(".", "").replace("-", "")
                
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
            return pagina_erro(request, mensagem=f"Erro: {e}")
    else:
        return pagina_erro(request, mensagem="Método HTTP inválido.")

@login_required
def valida_responsavel(request, id_responsavel):
    if request.method == 'POST':
        try:
            responsavel = get_object_or_404(TbCadastroResponsavel, pk=id_responsavel)
            responsavel.flag_validado = 'S'
            responsavel.save()
            return redirect('lista_responsavel')
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método HTTP inválido.")


@login_required
def desativa_responsavel(request, id_responsavel):
    if request.method == 'POST':
        try:
            responsavel = get_object_or_404(TbCadastroResponsavel, pk=id_responsavel)
            responsavel.flag_ativo = 'N'
            responsavel.save()
            return redirect('lista_responsavel')
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método HTTP inválido.")


@login_required
def reativa_responsavel(request, id_responsavel):
    if request.method == 'POST':
        try:
            responsavel = get_object_or_404(TbCadastroResponsavel, pk=id_responsavel)
            responsavel.flag_ativo = 'S'
            responsavel.save()
            return redirect('lista_responsavel')
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método HTTP inválido.")


# ==========================================
# BLOCO FILHOS (CRIANÇAS)
# ==========================================

@login_required
def lista_filhos(request, id_responsavel):
    try:
        registros = TbFilhosResponsavel.objects.filter(id_responsavel=id_responsavel, flag_ativo='S').order_by('-data_cadastro')
        for f in registros:
            f.cpf = mascarar_cpf(f.cpf)
            
        responsavel = TbCadastroResponsavel.objects.filter(id_responsavel=id_responsavel).first()
        responsavel_nome = f"{responsavel.pnome} {responsavel.snome}" if responsavel else ""
        
        contexto = {'lista': registros, 'id_responsavel': id_responsavel, 'responsavel_nome': responsavel_nome, 'titulo': 'Crianças Cadastradas'}
        return render(request, 'gerencias/lista_filhos.html', contexto)
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro: {e}")


@login_required
def lista_filhos_total(request):
    try:
        # Trocado Conn por ORM para decriptografia automática
        lista = TbFilhosResponsavel.objects.all().order_by('id_responsavel')
        for filho in lista:
            filho.cpf = mascarar_cpf(filho.cpf)
        return render(request, 'gerencias/lista_filhos_total.html', {'lista': lista})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro: {e}")


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
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")


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
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")


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
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")


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
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")


@login_required
def lista_filhos_responsavel(request):
    try:
        registros = TbFilhosResponsavel.objects.filter(id_responsavel=request.POST.get('id_responsavel'), flag_ativo='S').order_by('-data_cadastro')
        for r in registros:
            r.cpf = mascarar_cpf(r.cpf)
        return render(request, 'gerencias/lista_responsavel.html', {'dados': registros, 'titulo': 'Responsáveis Ativos'})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro: {e}")


@login_required
def novo_filho(request, id_responsavel):
    if request.method == 'POST':
        try:
            registro = TbFilhosResponsavel.objects.filter(id_responsavel=id_responsavel).first()
            return render(request, 'gerencias/novo_filho.html', {'dados': registro, 'id_responsavel': id_responsavel, 'titulo': 'Crianças Cadastradas'})
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")


@login_required
def editar_filho(request, id_filho):
    if request.method == 'POST':
        try:
            registro = TbFilhosResponsavel.objects.filter(id_filho=id_filho).first()
            return render(request, 'gerencias/editar_filho.html', {'dados': registro, 'id_responsavel': registro.id_responsavel, 'titulo': 'Editar Criança'})
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")


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
                dt_nasc = f"{dt_nasc[6:8]}/{dt_nasc[4:6]}/{dt_nasc[0:4]}"
            cpf = (request.POST.get('cpf') or '').replace('.', '').replace('-', '')
            sexo = request.POST.get('sexo')
            roupa = request.POST.get('roupa')
            sapato = request.POST.get('sapato')
            outra_ong = request.POST.get('outra_ong')

            sql = "INSERT INTO tb_filhos_responsavel (id_responsavel, id_usuario_cad, pnome, snome, data_nascimento, cpf, sexo, numero_roupa, numero_sapato, cadastro_outra_ong) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            Conn.executa_insert(sql, (id_responsavel, id_usuario_cad, pnome, snome, dt_nasc, cpf, sexo, roupa, sapato, outra_ong))
            return redirect('lista_filhos', id_responsavel)
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")


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
                # ORM resolve a criptografia que o SQL puro não conseguia
                qs = TbFilhosResponsavel.objects.filter(
                    Q(pnome__icontains=termo_busca) | Q(snome__icontains=termo_busca),
                    flag_ativo='S'
                )
                resultados = list(qs)
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
                    termo_busca = 'Por favor, digite um número válido'

    # Adiciona idade calculada e mascara o CPF para exibição
    for filho in resultados:
        filho.idade = calcular_idade(filho.data_nascimento)
        filho.cpf = mascarar_cpf(filho.cpf)

    contexto = {'resultados': resultados, 'termo_busca': termo_busca, 'tipo_busca': tipo_busca, 'total_resultados': len(resultados)}
    return render(request, 'gerencias/buscar_filhos.html', contexto)

def calcular_idade(data_nascimento_str):
    if not data_nascimento_str: return None
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
            criador = request.user.id
            remetente = request.user.username
            destinatario = request.POST.get('destinatario')
            mensagem = request.POST.get('mensagem')
            mensagem = f"Mensagem de {remetente} para {destinatario}: {mensagem}"
            sql = "INSERT INTO tb_oficios (id_usuario, destinatario, mensagem) VALUES (%s, %s, %s)"
            Conn.executa_insert(sql, (criador, destinatario, mensagem))
            return redirect('lista_oficio')
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")


@login_required
def novo_oficio(request):
    try:
        return render(request, 'gerencias/novo_oficio.html', {'usuario': request.user, 'id_usuario_cad': request.user.id, 'username': request.user.username})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro: {e}")


@login_required
def lista_oficio(request):
    try:
        lista = TbOficios.objects.select_related('id_usuario').all().order_by('-data_criacao')
        primeiro_id = lista.first().id_oficio if lista.exists() else None
        return render(request, 'gerencias/lista_oficios.html', {'id_oficio': primeiro_id, 'lista': lista, 'total': lista.count()})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro: {e}")


@login_required
def exibe_oficio(request, id_oficio):
    try:
        oficio = get_object_or_404(TbOficios, id_oficio=id_oficio)
        return render(request, 'gerencias/exibe_oficio.html', {'oficio': oficio, 'id_oficio': id_oficio, 'mensagem': oficio.mensagem, 'remetente': oficio.id_usuario.username})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro: {e}")


@login_required
def excluir_oficio(request, id_oficio):
    if request.method == 'POST':
        try:
            TbOficios.objects.filter(id_oficio=id_oficio).delete()
            return redirect('lista_oficio')
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")

# ==========================================
# BLOCO MADRINHAS E PADRINHOS
# ==========================================

@login_required
def novo_madrinha_padrinho(request):
    if request.method == 'POST':
        try:
            return render(request, 'gerencias/novo_madrinha_padrinho.html', {'usuario': request.user, 'id_usuario_cad': request.POST.get('id_usuario_cad', request.user.id)})
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")


@login_required
def inserir_madrinha_padrinho(request):
    if request.method == 'POST':
        try:
            id_usuario_cad = request.user.id
            cpf = (request.POST.get('cpf') or '').replace('.', '').replace('-', '') 
            flag_anonimo = request.POST.get('flag_anonimo', 'N')
            
            if flag_anonimo == 'S':
                pnome = 'Anônimo'
                snome = ''
            else:
                pnome = request.POST.get('pnome')
                snome = request.POST.get('snome')
                
            endereco = request.POST.get('endereco')
            complemento = request.POST.get('complemento')
            bairro = request.POST.get('bairro')
            cidade = request.POST.get('cidade')
            estado = request.POST.get('estado')
            flag_ativo = request.POST.get('flag_ativo')

            sql = "INSERT INTO tb_madrinha_padrinho (id_usuario_cad, cpf, flag_anonimo, pnome, snome, endereco, complemento, bairro, cidade, estado, flag_ativo) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            Conn.executa_insert(sql, (id_usuario_cad, cpf, flag_anonimo, pnome, snome, endereco, complemento, bairro, cidade, estado, flag_ativo))
            return redirect('lista_madrinha_padrinho')
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")


@login_required
def lista_madrinha_padrinho(request):
    try:
        # Busca nativa do Django (Backend) para garantir precisão
        termo = request.GET.get('q', '').strip()
        if termo:
            lista = TbMadrinhaPadrinho.objects.filter(
                Q(pnome__icontains=termo) | Q(cpf__icontains=termo),
                flag_ativo='S'
            ).order_by('-data_cadastro')
        else:
            lista = TbMadrinhaPadrinho.objects.filter(flag_ativo='S').order_by('-data_cadastro')
            
        for mad_pad in lista:
            mad_pad.cpf = mascarar_cpf(mad_pad.cpf)
        return render(request, 'gerencias/listar_madrinhas_padrinhos.html', {'dados': lista, 'termo_busca': termo})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro: {e}")
    

@login_required
def lista_madrinha_padrinho_desativados(request):
    try:
        # Ajustado para ORM
        lista = TbMadrinhaPadrinho.objects.filter(flag_ativo='N').order_by('-data_cadastro')
        for mad_pad in lista:
            mad_pad.cpf = mascarar_cpf(mad_pad.cpf)
        return render(request, 'gerencias/listar_madrinhas_padrinhos_desativados.html', {'dados': lista})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro: {e}")


@login_required
def editar_madrinha_padrinho(request, id_mad_pad):
    try:
        registro = TbMadrinhaPadrinho.objects.filter(id_mad_pad=id_mad_pad).first()
        return render(request, 'gerencias/editar_madrinha_padrinho.html', {'registro': registro})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro: {e}")


@login_required
def atualiza_madrinha_padrinho(request, id_mad_pad):
    if request.method == 'POST':
        try:
            registro = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)
            
            # BLINDAGEM LGPD: Só atualiza o CPF se ele NÃO contiver asteriscos
            cpf_form = request.POST.get('cpf', '')
            if '*' not in cpf_form:
                registro.cpf = cpf_form.replace('.', '').replace('-', '')
                
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
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")

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
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")


@login_required
def api_salvar_madrinha_padrinho(request):
    if request.method == 'POST':
        try:
            dados = json.loads(request.body)
            cpf = dados.get('cpf', '').replace('.', '').replace('-', '')
            if TbMadrinhaPadrinho.objects.filter(cpf=cpf).exists():
                return pagina_erro(request, mensagem=f"Erro: CPF já cadastrado!")

            novo = TbMadrinhaPadrinho.objects.create(
                id_usuario_cad_id=request.user.id, cpf=cpf, flag_anonimo=dados.get('flag_anonimo', 'N'),
                pnome=dados.get('pnome'), snome=dados.get('snome'), endereco=dados.get('endereco'),
                complemento=dados.get('complemento'), bairro=dados.get('bairro'), cidade=dados.get('cidade'),
                estado=dados.get('estado'), data_cadastro=timezone.now(), flag_ativo='S'
            )
            return JsonResponse({'success': True, 'id': novo.id_mad_pad, 'message': 'Cadastro realizado'})
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro via API: {e}")
    return pagina_erro(request, mensagem="Método inválido.")


@login_required
def apadrinhar_crianca(request, id_mad_pad):
    if request.method == 'POST':
        try:
            registro = TbMadrinhaPadrinho.objects.filter(id_mad_pad=id_mad_pad).first()
            if registro: registro.cpf = mascarar_cpf(registro.cpf)
            
            criancas = TbFilhosResponsavel.objects.filter(flag_ativo='S').order_by('pnome')
            for c in criancas: c.cpf = mascarar_cpf(c.cpf)
            
            return render(request, 'gerencias/apadrinhar_crianca.html', {'registro': registro, 'criancas': criancas, 'titulo': 'Apadrinhar Criança'})
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")


@login_required
def vincular_mad_pad_crianca(request):
    if request.method == 'POST':
        try:
            id_mad_pad = request.POST.get('id_mad_pad')
            id_filho = request.POST.get('id_filho')
            sql = "INSERT INTO tb_apadrinhamento_crianca (id_mad_pad, id_filho) VALUES (%s, %s)"
            Conn.executa_insert(sql, (id_mad_pad, id_filho))
            return redirect('lista_apadrinhamento')
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")


@login_required
def lista_apadrinhamento(request):
    try:
        apadrinhamento = TbApadrinhamentoCrianca.objects.all().order_by('-data_cadastro')
        return render(request, 'gerencias/lista_apadrinhamentos.html', {'registros': apadrinhamento})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro: {e}")


# ==========================================
# BLOCO EVENTOS E ENTREGAS
# ==========================================

@login_required
def listar_eventos(request):
    try:
        lista = Conn.executa_query("SELECT * FROM tb_evento ORDER BY data_evento DESC")
        return render(request, 'gerencias/listar_eventos.html', {'lista': lista})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro: {e}")


@login_required
def novo_evento(request):
    try:
        return render(request, 'gerencias/novo_evento.html')
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro: {e}")


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
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")


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
                return pagina_erro(request, mensagem="Todos os campos obrigatórios devem ser preenchidos.")

            if not re.match(r'^\d{2}/\d{2}/\d{4}$', data_evento):
                messages.error(request, 'Formato de data inválido. Use dd/mm/aaaa.')
                return redirect('novo_evento')
            try:
                datetime.strptime(data_evento, '%d/%m/%Y')
            except ValueError:
                messages.error(request, 'Data inválida.')
                return redirect('novo_evento')

            TbEvento.objects.create(
                nome=nome, data_evento=data_evento, endereco=endereco, bairro=bairro,
                cidade=cidade, estado=estado, flag_finalizado=flag_finalizado, data_cadastro=timezone.now()
            )
            return redirect('listar_eventos')
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")


@login_required
def editar_evento(request, id_evento):
    try:
        evento = TbEvento.objects.get(id_evento=id_evento)
        return render(request, 'gerencias/editar_evento.html', {'registro': evento})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro: {e}")


@login_required
def finalizar_evento(request, id_evento):
    if request.method == 'POST':
        try:
            evento = TbEvento.objects.get(id_evento=id_evento)
            evento.flag_finalizado = 'S'
            evento.save()
            return redirect('listar_eventos')
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")


@login_required
def listar_entregas(request):
    try:
        entregas = TbEntrega.objects.all().order_by('-id_evento')
        return render(request, 'gerencias/listar_entregas.html', {'lista': entregas})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro: {e}")


@login_required
def nova_entrega(request):
    try:
        evento = TbEvento.objects.all().order_by('-id_evento')
        criancas = TbFilhosResponsavel.objects.filter(flag_ativo='S').order_by('pnome')
        madrinhas_padrinhos = TbMadrinhaPadrinho.objects.filter(flag_ativo='S').order_by('pnome')
        
        # Mascara na tela de vincular entrega também
        for c in criancas: c.cpf = mascarar_cpf(c.cpf)
        for m in madrinhas_padrinhos: m.cpf = mascarar_cpf(m.cpf)

        return render(request, 'gerencias/nova_entrega.html', {'evento': evento, 'criancas': criancas, 'mad_pad': madrinhas_padrinhos})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro: {e}")


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

            sql = "INSERT INTO tb_entrega (id_evento, id_mad_pad, id_crianca, endereco, cidade, bairro, estado) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            Conn.executa_insert(sql, (id_evento, id_mad_pad, id_filho, endereco, cidade, bairro, estado))
            return redirect('listar_entregas')
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro: {e}")
    return pagina_erro(request, mensagem="Método inválido.")


@login_required
def editar_entrega(request, id_entrega):
    try:
        entrega = TbEntrega.objects.get(id_entrega=id_entrega)
        eventos = TbEvento.objects.all().order_by('-id_evento')
        criancas = TbFilhosResponsavel.objects.filter(flag_ativo='S').order_by('pnome')
        madrinhas_padrinhos = TbMadrinhaPadrinho.objects.filter(flag_ativo='S').order_by('pnome')
        
        for c in criancas: c.cpf = mascarar_cpf(c.cpf)
        for m in madrinhas_padrinhos: m.cpf = mascarar_cpf(m.cpf)

        return render(request, 'gerencias/editar_entrega.html', {'entrega': entrega, 'eventos': eventos, 'criancas': criancas, 'madrinhas_padrinhos': madrinhas_padrinhos})
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro: {e}")


@login_required
def atualiza_entrega(request, id_entrega):
    if request.method != 'POST':
        return pagina_erro(request, mensagem="Método inválido.")
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
        return pagina_erro(request, mensagem=f"Erro: {e}")

# ==========================================
# BLOCO DIREITOS DO TITULAR (LGPD)
# ==========================================
import json
from django.core.serializers.json import DjangoJSONEncoder

@login_required
def exportar_dados_titular(request, id_mad_pad):
    """
    LGPD Cap. III - Direito à Portabilidade
    Gera um arquivo JSON com todos os dados que a ONG possui sobre o Padrinho/Madrinha
    """
    try:
        titular = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)
        
        # Coleta os dados do titular
        dados = {
            "Nome": titular.pnome,
            "Sobrenome": titular.snome,
            "Endereco": f"{titular.endereco}, {titular.complemento} - {titular.bairro}, {titular.cidade}/{titular.estado}",
            "Data_Cadastro": titular.data_cadastro,
            "Status_Ativo": titular.flag_ativo,
            "Criancas_Apadrinhadas": []
        }

        # Coleta o histórico de crianças vinculadas a este padrinho
        vinculos = TbApadrinhamentoCrianca.objects.filter(id_mad_pad=id_mad_pad)
        for v in vinculos:
            dados["Criancas_Apadrinhadas"].append({
                "Nome_Crianca": v.id_filho.pnome,
                "Data_Vinculo": v.data_cadastro
            })

        # Retorna o arquivo para download
        response = JsonResponse(dados, encoder=DjangoJSONEncoder, json_dumps_params={'ensure_ascii': False, 'indent': 4})
        response['Content-Disposition'] = f'attachment; filename="dados_padrinho_{id_mad_pad}.json"'
        return response

    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro ao exportar dados: {e}")

@login_required
def anonimizar_titular(request, id_mad_pad):
    if request.method == 'POST':
        try:
            titular = get_object_or_404(TbMadrinhaPadrinho, id_mad_pad=id_mad_pad)
            titular.pnome, titular.snome = "Titular", "Anonimizado (LGPD)"
            titular.cpf = "00000000000" 
            titular.endereco, titular.complemento, titular.telefone = "Dado Removido", "", "Removido"
            titular.flag_anonimo, titular.flag_ativo = 'S', 'N'
            titular.save()
            
            # LGPD: Limpa endereços residuais no histórico de Entregas
            entregas = TbEntrega.objects.filter(id_mad_pad=id_mad_pad)
            for entrega in entregas:
                entrega.endereco = "Endereço Anonimizado (LGPD)"
                entrega.bairro = "Anonimizado"
                entrega.save()
                
            TbLogAuditoria.objects.create(usuario=request.user.username, acao='ANONIMIZACAO_LGPD', rota=f'/padrinhos/{id_mad_pad}', ip=request.META.get('REMOTE_ADDR'))
            messages.success(request, 'Dados do titular anonimizados com sucesso.')
            return redirect('lista_madrinha_padrinho')
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro ao anonimizar titular: {e}")
    return pagina_erro(request, mensagem="Método inválido.")

# ==========================================
# LGPD - FUNCIONÁRIOS E RESPONSÁVEIS
# ==========================================

@login_required
def exportar_dados_funcionario(request, id_funcionario):
    try:
        func = get_object_or_404(TbFuncionario, id_funcionario=id_funcionario)
        dados = {
            "Nome": func.pnome, "Sobrenome": func.snome,
            "Telefone": func.telefone, "Endereco": func.endereco,
            "Bairro": func.bairro, "Cidade": func.cidade, "Estado": func.estado,
            "Status_Ativo": func.flag_ativo
        }
        response = JsonResponse(dados, encoder=DjangoJSONEncoder, json_dumps_params={'ensure_ascii': False, 'indent': 4})
        response['Content-Disposition'] = f'attachment; filename="dados_funcionario_{id_funcionario}.json"'
        return response
    except Exception as e:
        return pagina_erro(request, mensagem=f"Erro ao exportar dados: {e}")

@login_required
def anonimizar_funcionario(request, id_funcionario):
    if request.method == 'POST':
        try:
            func = get_object_or_404(TbFuncionario, id_funcionario=id_funcionario)
            func.pnome, func.snome = "Funcionário", "Anonimizado (LGPD)"
            func.cpf = "00000000000"
            func.telefone, func.endereco, func.complemento = "Removido", "Removido", ""
            func.flag_ativo = 'N'
            func.save()
            TbLogAuditoria.objects.create(usuario=request.user.username, acao='ANONIMIZACAO_FUNC', rota=f'/func/{id_funcionario}', ip=request.META.get('REMOTE_ADDR'))
            return redirect('lista_funcionarios')
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro ao anonimizar: {e}")
    return pagina_erro(request, mensagem="Método inválido.")

@login_required
def exportar_dados_responsavel(request, id_responsavel):
    try:
        resp = get_object_or_404(TbCadastroResponsavel, id_responsavel=id_responsavel)
        dados = {
            "Nome": resp.pnome, "Sobrenome": resp.snome,
            "Data_Nascimento": resp.data_nascimento,
            "Endereco": resp.endereco, "Bairro": resp.bairro, "Cidade": resp.cidade,
            "Status_Ativo": resp.flag_ativo,
            "Dependentes": []  # Nova lista para abrigar os filhos
        }
        
        # LGPD: Busca todas as crianças vinculadas ao responsável
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
        return pagina_erro(request, mensagem=f"Erro ao exportar dados: {e}")

@login_required
def anonimizar_responsavel(request, id_responsavel):
    if request.method == 'POST':
        try:
            resp = get_object_or_404(TbCadastroResponsavel, id_responsavel=id_responsavel)
            resp.pnome, resp.snome = "Responsável", "Anonimizado (LGPD)"
            resp.cpf, resp.data_nascimento = "00000000000", "01/01/1900"
            resp.endereco, resp.complemento = "Removido", ""
            resp.flag_ativo = 'N'
            resp.save()
            
            # LGPD EFEITO CASCATA: Anonimiza imediatamente todos os filhos dependentes
            filhos = TbFilhosResponsavel.objects.filter(id_responsavel=id_responsavel)
            for filho in filhos:
                filho.pnome, filho.snome = "Criança", "Anonimizada"
                filho.cpf, filho.data_nascimento = "00000000000", "01/01/1900"
                filho.flag_ativo = 'N'
                filho.save()
                
            # LGPD: Limpa endereços residuais dessas crianças no histórico de Entregas
            entregas = TbEntrega.objects.filter(id_crianca__in=filhos)
            for entrega in entregas:
                entrega.endereco = "Endereço Anonimizado (LGPD)"
                entrega.bairro = "Anonimizado"
                entrega.save()
                
            TbLogAuditoria.objects.create(usuario=request.user.username, acao='ANONIMIZACAO_CASCATA', rota=f'/resp/{id_responsavel}', ip=request.META.get('REMOTE_ADDR'))
            return redirect('lista_responsavel')
        except Exception as e:
            return pagina_erro(request, mensagem=f"Erro ao anonimizar: {e}")
    return pagina_erro(request, mensagem="Método inválido.")
