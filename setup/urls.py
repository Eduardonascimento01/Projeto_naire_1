from django.contrib import admin
from django.urls import path, include

from gerencias import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('gerencias.urls')),
    # A tela de login é a nossa (views.entrar), no lugar da padrão do Django.
    # Precisa vir ANTES do include abaixo para ter prioridade.
    path('accounts/login/', views.entrar, name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    
]
