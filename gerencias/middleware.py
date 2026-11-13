from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

from gerencias.models import TbLogAuditoria


def ip_do_cliente(request):
    """
    IP verdadeiro de quem acessa, lido do cabeçalho definido em
    settings.IP_HEADER (padrão REMOTE_ADDR).

    Antes, o log lia o X-Forwarded-For, que o próprio visitante pode
    escrever: dava pra gravar qualquer IP falso na auditoria.
    Usado pelo log de auditoria e pela trava de força bruta (axes).
    """
    valor = request.META.get(getattr(settings, 'IP_HEADER', 'REMOTE_ADDR'), '') or request.META.get('REMOTE_ADDR', '')
    # Se o cabeçalho tiver uma lista (proxy), o último IP é o que o proxy de
    # confiança acrescentou; os anteriores podem ter vindo do visitante.
    return valor.split(',')[-1].strip() or None


class CabecalhosSegurancaMiddleware:
    """Acrescenta Content-Security-Policy e Permissions-Policy a toda resposta."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resposta = self.get_response(request)
        politica = getattr(settings, 'CSP_POLITICA', '')
        if politica and 'Content-Security-Policy' not in resposta:
            resposta['Content-Security-Policy'] = politica
        permissoes = getattr(settings, 'PERMISSIONS_POLICY', '')
        if permissoes and 'Permissions-Policy' not in resposta:
            resposta['Permissions-Policy'] = permissoes
        return resposta


class LogAuditoriaMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Só registra funcionário logado. Visitante anônimo não grava nada:
        # antes, cada pedido de qualquer pessoa virava uma linha no banco
        # (um robô conseguia encher o banco). Tentativas de login erradas
        # continuam registradas pela trava de força bruta (axes).
        if not request.user.is_authenticated:
            return None

        # Ignora arquivos de design (CSS, JS, imagens) e o painel admin.
        caminho = request.path
        if caminho.startswith(settings.STATIC_URL) or caminho.startswith('/static/'):
            return None
        if caminho.startswith('/' + getattr(settings, 'ADMIN_URL', 'admin/')):
            return None

        TbLogAuditoria.objects.create(
            usuario=request.user.username,
            acao=request.method,
            rota=caminho,
            ip=ip_do_cliente(request),
        )
