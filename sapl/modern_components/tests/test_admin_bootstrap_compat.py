from pathlib import Path
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.template.loader import get_template
from django.utils import timezone


class AdminBootstrapCompatibilityTests(TestCase):
    def test_login_uses_licensed_bootstrap_overlay(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("form-signin", body)
        self.assertIn("bootstrap/css/bootstrap.min.css", body)

    def test_core_admin_templates_compile(self):
        root = Path(__file__).resolve().parents[2] / "templates" / "admin"
        templates = sorted(p.relative_to(root).with_suffix("").as_posix()
                           for p in root.rglob("*.html")
                           if "/filer/" not in p.as_posix())
        self.assertGreaterEqual(len(templates), 25)
        for name in templates:
            get_template("admin/" + name + ".html")

    def test_admin_body_exposes_current_utc_offset(self):
        for zone in ("UTC", "America/Sao_Paulo"):
            with self.subTest(zone=zone), timezone.override(zone):
                expected = str(int(
                    timezone.localtime(timezone.now()).utcoffset().total_seconds()
                ))
                response = self.client.get("/admin/login/")
                self.assertEqual(response.status_code, 200)
                match = re.search(
                    r'data-admin-utc-offset="(-?\d+)"', response.content.decode()
                )
                self.assertIsNotNone(match)
                self.assertEqual(match.group(1), expected)

    def test_logout_requires_post(self):
        user = get_user_model().objects.create_user(
            username="admin-overlay-test", password="temporary-test-password", is_staff=True
        )
        self.client.force_login(user)
        self.assertEqual(self.client.get("/admin/logout/").status_code, 405)
        response = self.client.post("/admin/logout/")
        self.assertIn(response.status_code, (200, 302))
        self.assertNotIn("_auth_user_id", self.client.session)
