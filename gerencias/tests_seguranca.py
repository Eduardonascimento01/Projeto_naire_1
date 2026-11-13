"""
Testes das correções de segurança de 2026-11-13 (branch correcoes-seguranca).

Rodar:  python manage.py test --settings=setup.settings_test
"""
from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from gerencias.models import TbLogAuditoria, TbOficios
from gerencias.permissoes import GRUPO_LGPD


class CabecalhosTest(TestCase):
    def test_csp_e_permissions_policy_em_toda_resposta(self):
        r = self.client.get(reverse('login'))
        self.assertIn("default-src 'self'", r['Content-Security-Policy'])
        self.assertIn("frame-ancestors 'none'", r['Content-Security-Policy'])
        self.assertIn('camera=()', r['Permissions-Policy'])


class LogAuditoriaTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('func', password='x', is_staff=True)

    def test_visitante_anonimo_nao_grava_no_log(self):
        for i in range(20):
            self.client.get(f'/assets/css/arquivo{i}.css')
            self.client.get('/')
        self.assertEqual(TbLogAuditoria.objects.count(), 0)

    def test_funcionario_logado_e_registrado(self):
        self.client.force_login(self.user)
        self.client.get(reverse('lista_oficio'))
        self.assertTrue(TbLogAuditoria.objects.filter(usuario='func', rota='/gerencias/lista_oficio/').exists())

    def test_ip_falso_no_x_forwarded_for_e_ignorado(self):
        self.client.force_login(self.user)
        self.client.get(reverse('lista_oficio'), HTTP_X_FORWARDED_FOR='6.6.6.6', REMOTE_ADDR='10.1.2.3')
        log = TbLogAuditoria.objects.get()
        self.assertEqual(log.ip, '10.1.2.3')

    @override_settings(IP_HEADER='HTTP_X_REAL_IP')
    def test_ip_do_proxy_configurado(self):
        self.client.force_login(self.user)
        self.client.get(reverse('lista_oficio'), HTTP_X_REAL_IP='200.1.1.1', REMOTE_ADDR='10.0.0.1')
        self.assertEqual(TbLogAuditoria.objects.get().ip, '200.1.1.1')

    def test_arquivos_estaticos_nao_entram_no_log(self):
        self.client.force_login(self.user)
        self.client.get('/assets/css/naire.css')
        self.assertEqual(TbLogAuditoria.objects.count(), 0)


class RotasTest(TestCase):
    def test_esqueci_senha_por_email_desligado(self):
        self.assertEqual(self.client.get('/accounts/password_reset/').status_code, 404)

    def test_signup_manda_pro_login_e_nao_revela_o_admin(self):
        r = self.client.get('/signup/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], reverse('login'))

    def test_logout_por_get_nao_funciona(self):
        user = User.objects.create_user('func', password='x', is_staff=True)
        self.client.force_login(user)
        self.client.get(reverse('logout'))  # Django 5: só POST desloga
        self.assertEqual(self.client.get(reverse('lista_oficio')).status_code, 200)
        self.client.post(reverse('logout'))
        self.assertEqual(self.client.get(reverse('lista_oficio')).status_code, 302)


class OficiosTest(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', password='x', is_staff=True)
        self.bia = User.objects.create_user('bia', password='x', is_staff=True)
        self.caio = User.objects.create_user('caio', password='x', is_staff=True)
        lgpd = Group.objects.get_or_create(name=GRUPO_LGPD)[0]
        self.dpo = User.objects.create_user('dpo', password='x', is_staff=True)
        self.dpo.groups.add(lgpd)
        self.oficio = TbOficios.objects.create(id_usuario_id=self.ana.id, destinatario='bia',
                                               mensagem='assunto interno', data_criacao=timezone.now())
        self.url = reverse('exibe_oficio', args=[self.oficio.id_oficio])

    def test_remetente_destinatario_e_lgpd_veem(self):
        for user in (self.ana, self.bia, self.dpo):
            self.client.force_login(user)
            self.assertContains(self.client.get(self.url), 'assunto interno')
            self.assertContains(self.client.get(reverse('lista_oficio')), 'bia')

    def test_outro_funcionario_nao_ve(self):
        self.client.force_login(self.caio)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertNotContains(self.client.get(reverse('lista_oficio')), 'assunto interno')
