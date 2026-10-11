import json
import os
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sapl.settings")
import django
django.setup()

from django.contrib.auth import get_user_model
from django.test import TestCase


class OpenAPIContractTests(TestCase):
    def test_custom_post_operations_document_their_actual_success_status(self):
        response = self.client.get(
            "/api/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json"
        )
        self.assertEqual(response.status_code, 200)
        schema = json.loads(response.content)
        paths = schema["paths"]

        for path in (
            "/api/auth/token",
            "/api/recriar-token/{id}",
            "/api/materia/tipomaterialegislativa/{id}/change_position/",
        ):
            responses = paths[path]["post"]["responses"]
            self.assertIn("200", responses, path)
            self.assertNotIn("201", responses, path)

        self.assertNotIn("requestBody", paths["/api/recriar-token/{id}"]["post"])
        self.assertIn("requestBody", paths["/api/auth/token"]["post"])
        self.assertIn(
            "requestBody",
            paths["/api/materia/tipomaterialegislativa/{id}/change_position/"]["post"],
        )
        self.assertIn("201", paths["/api/materia/tipomaterialegislativa/"]["post"]["responses"])

    def test_token_endpoint_keeps_its_http_200_contract(self):
        username = "openapi-probe-" + uuid.uuid4().hex
        user = get_user_model().objects.create_user(
            username=username, password="temporary-test-password"
        )
        response = self.client.post(
            "/api/auth/token",
            data=json.dumps({"username": user.get_username(), "password": "temporary-test-password"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content).get("token"))
