"""Persistence, validation, and access checks for administrator-created pins."""
from types import SimpleNamespace
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from .map_node_views import campus_map_nodes
from .models import CampusMapNode


class MapNodeTests(TestCase):
    def request(self, data=None, *, admin=False, student=False):
        factory = APIRequestFactory()
        request = factory.get('/api/navigation/nodes/') if data is None else factory.post(
            '/api/navigation/nodes/', data, format='json')
        if admin or student:
            force_authenticate(request, user=SimpleNamespace(is_authenticated=True, is_superuser=admin))
        return campus_map_nodes(request)

    def test_only_superusers_can_create_nodes(self):
        for student in (False, True):
            response = self.request({'name': 'New Office', 'x': 20, 'y': 25}, student=student)
            self.assertEqual(response.status_code, 403)
        self.assertFalse(CampusMapNode.objects.exists())

    def test_created_node_is_persistent_and_publicly_available(self):
        created = self.request({'name': '  New   Office  ', 'x': 20.25, 'y': 25.75}, admin=True)
        self.assertEqual(created.status_code, 201)
        self.assertTrue(created.data['id'].startswith('custom_'))
        node = CampusMapNode.objects.get()
        self.assertEqual(node.name, 'New Office')
        self.assertEqual((node.x, node.y), (20.25, 25.75))
        self.assertEqual(self.request().data['nodes'], [created.data])

    def test_invalid_names_and_positions_do_not_create_nodes(self):
        for fields in ({'name': ''}, {'name': '   '}, {'name': 'x' * 121},
                       {'name': 'Main Entrance'}, {'name': 'finance office'},
                       {'name': 'Office\x00'}, {'x': -1}, {'y': 101},
                       {'x': True}, {'y': None}, {'x': 'NaN'}, {'y': 'Infinity'}):
            with self.subTest(fields=fields):
                response = self.request({'name': 'New Office', 'x': 20, 'y': 25, **fields}, admin=True)
                self.assertEqual(response.status_code, 400)
        self.assertFalse(CampusMapNode.objects.exists())

    def test_duplicate_names_are_rejected_case_insensitively(self):
        self.assertEqual(self.request({'name': 'New Office', 'x': 0, 'y': 0}, admin=True).status_code, 201)
        response = self.request({'name': ' new OFFICE ', 'x': 25, 'y': 30}, admin=True)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(CampusMapNode.objects.count(), 1)

    def test_session_creation_requires_csrf(self):
        request = APIRequestFactory(enforce_csrf_checks=True).post(
            '/api/navigation/nodes/', {'name': 'New Office', 'x': 20, 'y': 25}, format='json')
        request.user = SimpleNamespace(is_authenticated=True, is_superuser=True, is_active=True)
        response = campus_map_nodes(request)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(CampusMapNode.objects.exists())
