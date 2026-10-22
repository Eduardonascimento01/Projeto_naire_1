from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from gerencias.views import insere_novo_evento, novo_oficio, userCreateView


class EdicaoEntregaTests(SimpleTestCase):
	def test_rota_de_atualizacao_de_entrega_existe(self):
		self.assertEqual(
			reverse('atualiza_entrega', kwargs={'id_entrega': 1}),
			'/gerencias/atualiza_entrega/1/'
		)

	def test_template_de_edicao_de_entrega_carrega(self):
		template = get_template('gerencias/editar_entrega.html')
		self.assertIsNotNone(template)

	def test_pagina_de_novo_oficio_aceita_get(self):
		request = RequestFactory().get('/gerencias/novo_oficio/')
		request.user = SimpleNamespace(id=1, username='teste')

		response = novo_oficio.__wrapped__(request)

		self.assertEqual(response.status_code, 200)

	@patch('gerencias.views.messages.success')
	def test_criacao_de_usuario_salva_formulario_uma_vez(self, success_message):
		form = SimpleNamespace(
			instance=SimpleNamespace(password='senha-plana'),
			save=Mock()
		)
		view = userCreateView()
		view.request = SimpleNamespace()

		response = view.form_valid(form)

		self.assertEqual(response.status_code, 302)
		form.save.assert_called_once_with()
		self.assertNotEqual(form.instance.password, 'senha-plana')

	def test_evento_rejeita_data_inexistente(self):
		request = RequestFactory().post('/gerencias/insere_novo_evento/', {
			'nome': 'Evento teste',
			'data_evento': '31/02/2026',
			'endereco': 'Rua teste',
			'bairro': 'Centro',
			'cidade': 'São Paulo',
			'estado': 'SP',
		})

		with patch('gerencias.views.messages.error'), patch('gerencias.views.TbEvento.objects.create') as create_event:
			response = insere_novo_evento.__wrapped__(request)

		self.assertEqual(response.status_code, 302)
		create_event.assert_not_called()
