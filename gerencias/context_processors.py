from gerencias.permissoes import pode_usar_lgpd


def permissoes(request):
    """Disponibiliza `pode_lgpd` em todos os templates."""
    return {'pode_lgpd': pode_usar_lgpd(request.user)}
