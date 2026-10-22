from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('',views.home,name='home'),
    path('logout/', auth_views.LogoutView.as_view(next_page=''), name='logout'),
    path('gerencias/signup/', views.userCreateView.as_view(),name='signup'),
    path('gerencias/pagina_erro/', views.pagina_erro, name='pagina_erro'),
    
    path('gerencias/novo_funcionario/',views.novo_funcionario, name='novo_funcionario'),
    path('gerencias/insere_funcionario/',views.insere_novo_funcionario, name='insere_novo_funcionario'),
    path('gerencias/lista_funcionarios/',views.lista_funcionarios, name='lista_funcionarios'),
    path('gerencias/editar_funcionario/<int:id_funcionario>/', views.editar_funcionario, name='editar_funcionario'),
    path('gerencias/atualizar_funcionario/', views.atualiza_funcionario, name='atualiza_funcionario'),
    path('gerencias/desativa_funcionario/<int:id_funcionario>',views.desativa_funcionario, name='desativa_funcionario'),
    path('gerencias/reativa_funcionario/<int:id_funcionario>',views.reativa_funcionario, name='reativa_funcionario'),
    path('gerencias/lista_funcionarios_desativados/',views.lista_funcionarios_desativos, name='lista_funcionarios_desativos'),


    path('gerencias/novo_responsavel/',views.novo_responsavel, name='novo_responsavel'),
    path('gerencias/insere_responsavel/', views.insere_novo_responsavel, name='insere_novo_responsavel'),
    path('gerencias/lista_responsavel/',views.lista_responsavel, name='lista_responsavel'),
    path('gerencias/lista_responsavel_des/',views.lista_responsavel_des, name='lista_responsavel_des'),
    path('gerencias/edit_responsavel/<int:id_responsavel>',views.edit_responsavel, name='edit_responsavel'),
    path('gerencias/lista_responsavel_nval/',views.lista_responsavel_nval, name='lista_responsavel_nval'),
    path('gerencias/atualiza_responsavel/',views.atualiza_responsavel, name='atualiza_responsavel'),
    path('gerencias/desativar_responsavel/<int:id_responsavel>',views.desativa_responsavel, name='desativar_responsavel'),
    path('gerencias/reativar_responsavel/<int:id_responsavel>',views.reativa_responsavel, name='reativar_responsavel'),
    path('gerencias/valida_responsavel/<int:id_responsavel>',views.valida_responsavel, name='valida_responsavel'),

    
    path('gerencias/lista_filhos/<int:id_responsavel>',views.lista_filhos, name='lista_filhos'),
    path('gerencias/lista_filhos_total/',views.lista_filhos_total, name='lista_filhos_total'),
    path('gerencias/insere_filho/',views.insere_novo_filho, name='insere_novo_filho'),
    path('gerencias/desativar_filho/<int:id_responsavel>/',views.desativar_filho, name='desativar_filho'),
    path('gerencias/reativar_filho/<int:id_filho>/',views.reativar_filho, name='reativar_filho'),
    path('gerencias/editar_filho/<int:id_filho>',views.editar_filho, name='editar_filho'),
    path('gerencias/buscar_filhos/', views.buscar_filhos, name='buscar_filhos'),
    path('gerencias/novo_filho/<int:id_responsavel>', views.novo_filho, name='novo_filho'),


    path('gerencias/novo_oficio/', views.novo_oficio, name='novo_oficio'),
    path('gerencias/lista_oficio/', views.lista_oficio, name='lista_oficio'),
    path('gerencias/insere_novo_oficio/', views.insere_novo_oficio, name='insere_novo_oficio'),
    path('gerencias/excluir_oficio/<int:id_oficio>', views.excluir_oficio, name='excluir_oficio'),
    path('gerencias/exibe_oficio/<int:id_oficio>', views.exibe_oficio, name='exibe_oficio'),


    path('gerencias/novo_madrinha_padrinho/', views.novo_madrinha_padrinho, name='novo_madrinha_padrinho'),
    path('gerencias/inserir_madrinha_padrinho/', views.inserir_madrinha_padrinho, name='inserir_madrinha_padrinho'),
    path('gerencias/lista_madrinha_padrinho/', views.lista_madrinha_padrinho, name='lista_madrinha_padrinho'),
    path('gerencias/lista_madrinha_padrinho_desativados/', views.lista_madrinha_padrinho_desativados, name='lista_madrinha_padrinho_desativados'),
    path('gerencias/editar_madrinha_padrinho/<int:id_mad_pad>/', views.editar_madrinha_padrinho, name='editar_madrinha_padrinho'),
    path('gerencias/atualiza_madrinha_padrinho/<int:id_mad_pad>/', views.atualiza_madrinha_padrinho, name='atualiza_madrinha_padrinho'),
    path('gerencias/apadrinhar_crianca/<int:id_mad_pad>/', views.apadrinhar_crianca, name='apadrinhar_crianca'),
    path('gerencias/vincular_mad_pad_crianca/', views.vincular_mad_pad_crianca, name='vincular_mad_pad_crianca'),
    path('gerencias/reativar_madrinha_padrinho/<int:id_mad_pad>/', views.reativar_madrinha_padrinho, name='reativar_madrinha_padrinho'),
    path('gerencias/lista_apadrinhamento/', views.lista_apadrinhamento, name='lista_apadrinhamento'),


    path('gerencias/novo_evento/', views.novo_evento, name='novo_evento'),
    path('gerencias/listar_eventos/', views.listar_eventos, name='listar_eventos'),
    path('gerencias/insere_novo_evento/', views.insere_novo_evento, name='insere_novo_evento'),
    path('gerencias/editar_evento/<int:id_evento>/', views.editar_evento, name='editar_evento'),
    path('gerencias/atualiza_evento/<int:id_evento>/', views.atualiza_evento, name='atualiza_evento'),
    path('gerencias/finalizar_evento/<int:id_evento>/', views.finalizar_evento, name='finalizar_evento'),


    path('gerencias/nova_entrega/', views.nova_entrega, name='nova_entrega'),
    path('gerencias/listar_entregas/', views.listar_entregas, name='listar_entregas'),
    path('gerencias/insere_nova_entrega/', views.insere_nova_entrega, name='insere_nova_entrega'),
    path('gerencias/atualiza_entrega/<int:id_entrega>/', views.atualiza_entrega, name='atualiza_entrega'),
    path('gerencias/editar_entrega/<int:id_entrega>/', views.editar_entrega, name='editar_entrega'),

]
