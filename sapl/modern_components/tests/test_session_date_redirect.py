import json
import os
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sapl.settings')
import django
django.setup()

from django.db.models.query import QuerySet
from django.test import SimpleTestCase
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import ValidationError
from rest_framework.mixins import ListModelMixin
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from sapl.api.deprecated import SessaoPlenariaViewSet


class SessionDateRedirectTests(SimpleTestCase):
    def view(self, **params):
        view = SessaoPlenariaViewSet()
        view.request = Request(APIRequestFactory().get(
            '/api/sessao-plenaria/', params))
        view.format_kwarg = None
        view.kwargs = {}
        return view

    def test_filter_accepts_brazilian_and_iso_dates(self):
        for value in ('20/10/2026', '2026-10-20'):
            with self.subTest(value=value):
                view = self.view(data_inicio=value)
                filterset = DjangoFilterBackend().get_filterset(
                    view.request, view.get_queryset(), view)
                self.assertTrue(filterset.is_valid())
                self.assertEqual(filterset.form.cleaned_data['data_inicio'],
                                 date(2026, 10, 20))
                self.assertEqual(tuple(map(str, filterset.qs.query.sql_with_params()[1])),
                                 ('2026-10-20',))

    def test_date_returns_session_json_without_redirect(self):
        for value in ('20/10/2026', '2026-10-20'):
            with self.subTest(value=value):
                view = self.view(data_inicio=value, get_all='true')
                session = SimpleNamespace(pk=867)
                data = {'codReuniao': 867, 'datReuniaoString': '20/10/2026 09:30:00'}
                with patch.object(QuerySet, 'first', return_value=session):
                    with patch.object(view, 'get_serializer',
                                      return_value=SimpleNamespace(data=data)) as serialize:
                        response = view.list(view.request)
                serialize.assert_called_once_with(session)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Content-Type'], 'application/json')
                self.assertEqual(json.loads(response.content), data)
                self.assertNotIn('Location', response)

    def test_json_uses_lookup_result_instead_of_fixed_id(self):
        view = self.view(data_inicio='06/10/2026', get_all='TRUE')
        session = SimpleNamespace(pk=866)
        with patch.object(QuerySet, 'first', return_value=session):
            with patch.object(view, 'get_serializer',
                              return_value=SimpleNamespace(data={'codReuniao': 866})):
                response = view.list(view.request)
        self.assertEqual(json.loads(response.content), {'codReuniao': 866})

    def test_missing_session_returns_empty_json_list(self):
        view = self.view(data_inicio='19/10/2026', get_all='true')
        with patch.object(view, 'get_queryset',
                          return_value=view.get_queryset().none()):
            response = view.list(view.request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_multiple_sessions_return_first_by_time_then_id(self):
        view = self.view(data_inicio='20/10/2026', get_all='true')
        session = SimpleNamespace(pk=867)
        with patch.object(QuerySet, 'first', autospec=True, return_value=session) as first:
            with patch.object(view, 'get_serializer',
                              return_value=SimpleNamespace(data={'codReuniao': 867})):
                response = view.list(view.request)
        queryset = first.call_args.args[0]
        self.assertEqual(queryset.query.order_by,
                         ('data_inicio', 'hora_inicio', 'pk'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {'codReuniao': 867})
        self.assertNotIn('Location', response)

    def test_invalid_date_is_rejected_before_session_lookup(self):
        view = self.view(data_inicio='31/02/2026', get_all='true')
        with patch.object(QuerySet, 'first') as lookup:
            with self.assertRaises(ValidationError):
                view.list(view.request)
        lookup.assert_not_called()

    def test_requests_without_all_results_keep_regular_list(self):
        for params in ({'data_inicio': '20/10/2026'}, {'get_all': 'true'}):
            with self.subTest(params=params):
                view = self.view(**params)
                with patch.object(ListModelMixin, 'list',
                                  return_value=Response([])) as listing:
                    view.list(view.request)
                listing.assert_called_once()

    def test_other_filters_are_preserved_in_session_lookup(self):
        view = self.view(data_inicio='20/10/2026', data_fim='20/10/2026',
                         interativa='false', get_all='true')
        queryset = view.filter_queryset(view.get_queryset())
        sql, params = queryset.query.sql_with_params()
        self.assertIn('data_fim', sql)
        self.assertEqual(tuple(map(str, params)), ('2026-10-20', '2026-10-20'))
        self.assertIn('NOT', sql)
