from django.utils.deprecation import MiddlewareMixin
from gerencias.models import TbLogAuditoria

class LogAuditoriaMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Ignora arquivos de design (CSS, JS) e painel admin padrão para não poluir o log
        if request.path.startswith('/static/') or request.path.startswith('/admin/'):
            return None

        # Captura o IP real do usuário
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')

        # Identifica quem é o usuário (ou se não fez login)
        usuario = request.user.username if request.user.is_authenticated else 'Anonimo'

        # Grava a ação no banco de forma 100% invisível para o usuário
        TbLogAuditoria.objects.create(
            usuario=usuario,
            acao=request.method,
            rota=request.path,
            ip=ip
        )