from django_cryptography.fields import encrypt
from django.db import models
from django.conf import settings
import mysql.connector

# Classe de conexão otimizada e segura
class Conn:
    @staticmethod
    def _get_connection():
        db_conf = settings.DATABASES['default']
        return mysql.connector.connect(
            host=db_conf.get('HOST', 'localhost'),
            user=db_conf.get('USER', 'root'),
            password=db_conf.get('PASSWORD', '1234'),
            database=db_conf.get('NAME', 'bd_naire2'),
            port=db_conf.get('PORT', '3306')
        )

    @staticmethod
    def executa_query(consulta, params=None):
        mydb = Conn._get_connection()
        try:
            mycursor = mydb.cursor(dictionary=True)
            mycursor.execute(consulta, params or ())
            myresult = mycursor.fetchall()
            return myresult
        finally:
            mydb.close()

    @staticmethod
    def executa_insert(consulta, params=None):
        mydb = Conn._get_connection()
        try:
            mycursor = mydb.cursor()
            mycursor.execute(consulta, params or ())
            mydb.commit()
            return mycursor.lastrowid
        finally:
            mydb.close()


class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.IntegerField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.IntegerField()
    is_active = models.IntegerField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'

    def __str__(self):
        return self.username


class TbTipoFuncionario(models.Model):
    id_tipo = models.AutoField(primary_key=True)
    descricao = models.CharField(unique=True, max_length=45)

    class Meta:
        managed = False
        db_table = 'tb_tipo_funcionario'

    def __str__(self):
        return self.descricao


class TbFuncionario(models.Model):
    id_funcionario = models.AutoField(primary_key=True)
    id_tipo = models.ForeignKey(TbTipoFuncionario, models.DO_NOTHING, db_column='id_tipo')
    pnome = models.CharField(max_length=255)
    snome = models.CharField(max_length=255)
    
    # CRIPTOGRAFIA ATIVADA AQUI
    cpf = encrypt(models.CharField(max_length=255, blank=True, null=True))
    
    endereco = models.CharField(max_length=255)
    telefone = models.CharField(max_length=45, blank=True, null=True)
    complemento = models.CharField(max_length=255, blank=True, null=True)
    bairro = models.CharField(max_length=255)
    cidade = models.CharField(max_length=255)
    estado = models.CharField(max_length=2)
    flag_ativo = models.CharField(max_length=1, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tb_funcionario'

    def __str__(self):
        return f"{self.pnome} {self.snome}"
        
    @property
    def cpf_mascarado(self):
        if not self.cpf: 
            return ""
        cpf_limpo = ''.join(filter(str.isdigit, str(self.cpf)))
        if len(cpf_limpo) == 11:
            return f"***.***.***-{cpf_limpo[-2:]}"
        return "***.***.***-**"


class TbCadastroResponsavel(models.Model):
    id_responsavel = models.AutoField(primary_key=True)
    id_usuario_cad = models.ForeignKey(AuthUser, models.DO_NOTHING, db_column='id_usuario_cad', blank=True, null=True)
    data_cadastro = models.DateTimeField(blank=True, null=True)
    ultima_atualizacao = models.DateTimeField(blank=True, null=True)
    pnome = models.CharField(max_length=100, blank=True, null=True)
    snome = models.CharField(max_length=255, blank=True, null=True)
    
    # CRIPTOGRAFIA ATIVADA AQUI
    cpf = encrypt(models.CharField(max_length=255, blank=True, null=True))
    
    titulo = models.CharField(max_length=45, blank=True, null=True)
    data_nascimento = models.CharField(max_length=10, blank=True, null=True)
    flag_responsavel_trabalha = models.CharField(max_length=1, blank=True, null=True)
    flag_conjuge = models.CharField(max_length=1, blank=True, null=True)
    flag_conjuge_trabalha = models.CharField(max_length=1, blank=True, null=True)
    endereco = models.CharField(max_length=255, blank=True, null=True)
    complemento = models.CharField(max_length=255, blank=True, null=True)
    bairro = models.CharField(max_length=255)
    cidade = models.CharField(max_length=255)
    estado = models.CharField(max_length=2)
    url_image_familia = models.CharField(max_length=255, blank=True, null=True)
    flag_validado = models.CharField(max_length=1, blank=True, null=True)
    flag_ativo = models.CharField(max_length=1, blank=True, null=True)
    observacoes = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tb_cadastro_responsavel'

    def __str__(self):
        return f"{self.pnome or ''} {self.snome or ''}".strip()
        
    @property
    def cpf_mascarado(self):
        if not self.cpf: 
            return ""
        cpf_limpo = ''.join(filter(str.isdigit, str(self.cpf)))
        if len(cpf_limpo) == 11:
            return f"***.***.***-{cpf_limpo[-2:]}"
        return "***.***.***-**"


class TbFilhosResponsavel(models.Model):
    id_filho = models.AutoField(primary_key=True)
    id_responsavel = models.ForeignKey(TbCadastroResponsavel, models.DO_NOTHING, db_column='id_responsavel')
    id_usuario_cad = models.ForeignKey(AuthUser, models.DO_NOTHING, db_column='id_usuario_cad', blank=True, null=True)
    pnome = models.CharField(max_length=100, blank=True, null=True)
    snome = models.CharField(max_length=255, blank=True, null=True)
    data_nascimento = models.CharField(max_length=10, blank=True, null=True)
    
    # CRIPTOGRAFIA ATIVADA AQUI
    cpf = encrypt(models.CharField(max_length=255, blank=True, null=True))
    
    sexo = models.CharField(max_length=2, blank=True, null=True)
    numero_roupa = models.CharField(max_length=15, blank=True, null=True)
    numero_sapato = models.IntegerField(blank=True, null=True)
    cadastro_outra_ong = models.CharField(max_length=1, blank=True, null=True)
    url_imagem = models.CharField(max_length=255, blank=True, null=True)
    data_cadastro = models.DateTimeField(blank=True, null=True)
    data_atualizacao = models.DateTimeField(blank=True, null=True)
    flag_ativo = models.CharField(max_length=1, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tb_filhos_responsavel'

    def __str__(self):
        return f"{self.pnome or ''} {self.snome or ''}".strip()
        
    @property
    def cpf_mascarado(self):
        if not self.cpf: 
            return ""
        cpf_limpo = ''.join(filter(str.isdigit, str(self.cpf)))
        if len(cpf_limpo) == 11:
            return f"***.***.***-{cpf_limpo[-2:]}"
        return "***.***.***-**"


class TbOficios(models.Model):
    id_oficio = models.AutoField(primary_key=True)
    data_criacao = models.DateTimeField(blank=True, null=True)
    id_usuario = models.ForeignKey(AuthUser, models.DO_NOTHING, db_column='id_usuario')
    destinatario = models.CharField(max_length=255, blank=True, null=True)
    mensagem = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tb_oficios'

    def __str__(self):
        return f"Ofício #{self.id_oficio} - {self.destinatario}"


class TbMadrinhaPadrinho(models.Model):
    id_mad_pad = models.AutoField(primary_key=True)
    id_usuario_cad = models.ForeignKey(AuthUser, models.DO_NOTHING, db_column='id_usuario_cad', blank=True, null=True)
    
    # CRIPTOGRAFIA ATIVADA AQUI
    cpf = encrypt(models.CharField(max_length=255, blank=True, null=True))
    
    flag_anonimo = models.CharField(max_length=1, blank=True, null=True)
    pnome = models.CharField(max_length=100, blank=True, null=True)
    snome = models.CharField(max_length=255, blank=True, null=True)
    endereco = models.CharField(max_length=255, blank=True, null=True)
    complemento = models.CharField(max_length=255, blank=True, null=True)
    bairro = models.CharField(max_length=255, blank=True, null=True)
    cidade = models.CharField(max_length=255, blank=True, null=True)
    estado = models.CharField(max_length=255, blank=True, null=True)
    data_cadastro = models.DateTimeField(blank=True, null=True)
    atualizacao_cad = models.DateTimeField(blank=True, null=True)
    flag_ativo = models.CharField(max_length=1, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tb_madrinha_padrinho'

    def __str__(self):
        return f"{self.pnome or ''} {self.snome or ''}".strip()
        
    @property
    def cpf_mascarado(self):
        if not self.cpf: 
            return ""
        cpf_limpo = ''.join(filter(str.isdigit, str(self.cpf)))
        if len(cpf_limpo) == 11:
            return f"***.***.***-{cpf_limpo[-2:]}"
        return "***.***.***-**"


class TbApadrinhamentoCrianca(models.Model):
    id_apadrinhamento = models.AutoField(primary_key=True)
    id_mad_pad = models.ForeignKey(TbMadrinhaPadrinho, models.DO_NOTHING, db_column='id_mad_pad')
    id_filho = models.ForeignKey(TbFilhosResponsavel, models.DO_NOTHING, db_column='id_filho')
    data_cadastro = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tb_apadrinhamento_crianca'


class TbEntrega(models.Model):
    id_entrega = models.AutoField(primary_key=True)
    id_evento = models.IntegerField()
    id_mad_pad = models.IntegerField(blank=True, null=True)
    id_crianca = models.IntegerField(blank=True, null=True)
    endereco = models.CharField(max_length=255, blank=True, null=True)
    bairro = models.CharField(max_length=255, blank=True, null=True)
    cidade = models.CharField(max_length=255, blank=True, null=True)
    estado = models.CharField(max_length=255, blank=True, null=True)
    data_cadastro = models.DateTimeField(blank=True, null=True)
    data_chegada = models.DateTimeField(blank=True, null=True)
    flag_finalizado = models.CharField(max_length=1, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tb_entrega'


class TbEvento(models.Model):
    id_evento = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=255)
    data_evento = models.CharField(max_length=10)
    data_cadastro = models.DateTimeField(blank=True, null=True)
    endereco = models.CharField(max_length=255, blank=True, null=True)
    bairro = models.CharField(max_length=255, blank=True, null=True)
    cidade = models.CharField(max_length=255, blank=True, null=True)
    estado = models.CharField(max_length=225, blank=True, null=True)
    flag_finalizado = models.CharField(max_length=1, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tb_evento'

    def __str__(self):
        return f"{self.nome} ({self.data_evento})"


class TbLogAuditoria(models.Model):
    id_log = models.AutoField(primary_key=True)
    usuario = models.CharField(max_length=150, blank=True, null=True)
    acao = models.CharField(max_length=50)
    rota = models.CharField(max_length=255)
    ip = models.CharField(max_length=50, blank=True, null=True)
    data_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = 'tb_log_auditoria'

    def __str__(self):
        return f"{self.data_hora} - {self.usuario} - {self.acao} - {self.rota}"