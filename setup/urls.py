from django.conf import settings
from django.contrib import admin
from django.urls import path, include

from gerencias import views

urlpatterns = [
    # Endereço do admin vem do .env (DJANGO_ADMIN_URL); padrão "admin/".
    path(settings.ADMIN_URL, admin.site.urls),
    path('', include('gerencias.urls')),
    # A tela de login é a nossa (views.entrar), no lugar da padrão do Django.
    path('accounts/login/', views.entrar, name='login'),
    # As rotas prontas do Django (django.contrib.auth.urls) foram tiradas:
    # elas ligavam "esqueci minha senha" por e-mail (/accounts/password_reset/)
    # sem e-mail configurado. Login e logout já têm rota própria; senha nova
    # é definida pelo administrador na edição do funcionário.
]
