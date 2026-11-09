"""
Regra única de quem pode usar as funções de LGPD (exportar, anonimizar,
excluir ofício). Usada tanto pelas views (que bloqueiam o acesso) quanto
pelos templates (que mostram ou escondem os botões), para as duas
nunca ficarem diferentes.
"""
GRUPO_LGPD = 'LGPD'


def pode_usar_lgpd(user):
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=GRUPO_LGPD).exists()
