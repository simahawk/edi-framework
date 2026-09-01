# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.tools import mute_logger

from ..utils import migrate_exchange_types
from .common import TestEDIWebserviceBase


class TestMigrateExchangeTypes(TestEDIWebserviceBase):
    @classmethod
    def _setup_records(cls):
        result = super()._setup_records()
        cls.component_model = cls.env.ref(
            "edi_component_oca.model_edi_oca_component_handler"
        )
        cls.handler_model = cls.env.ref("edi_webservice_oca.model_edi_webservice_send")
        return result

    def _make_type(self, code, settings_yaml):
        return self.env["edi.exchange.type"].create(
            {
                "name": f"Migrate {code}",
                "code": code,
                "backend_id": self.backend.id,
                "backend_type_id": self.backend.backend_type_id.id,
                "direction": "output",
                "send_model_id": self.component_model.id,
                "advanced_settings_edit": settings_yaml,
            }
        )

    def test_migrate_simple_settings_creates_endpoint(self):
        etype = self._make_type(
            "migrate_simple",
            """
            components:
              send:
                work_ctx:
                  webservice:
                    method: post
            """,
        )
        migrated = migrate_exchange_types(self.env, etype)
        self.assertEqual(migrated, etype)
        self.assertEqual(etype.send_model_id, self.handler_model)
        self.assertTrue(etype.webservice_endpoint_id)
        self.assertEqual(etype.webservice_endpoint_id.http_method, "post")
        self.assertEqual(
            etype.webservice_endpoint_id.backend_id,
            self.backend.webservice_backend_id,
        )

    @mute_logger("odoo.addons.edi_webservice_oca.utils")
    def test_migrate_complex_settings_falls_back_to_yaml(self):
        etype = self._make_type(
            "migrate_complex",
            """
            components:
              send:
                work_ctx:
                  webservice:
                    method: post
                    kwargs:
                      url_params:
                        endpoint: push/here
            """,
        )
        migrate_exchange_types(self.env, etype)
        self.assertEqual(etype.send_model_id, self.handler_model)
        self.assertFalse(etype.webservice_endpoint_id)
        settings = etype.get_settings()
        self.assertEqual(
            settings["execution_model"]["send"]["webservice"]["kwargs"]["url_params"],
            {"endpoint": "push/here"},
        )

    def test_migrate_send_as_bytes_extracted_to_field_when_simple(self):
        etype = self._make_type(
            "migrate_simple_bytes",
            """
            components:
              send:
                work_ctx:
                  webservice:
                    method: post
                    send_as_bytes: true
            """,
        )
        migrate_exchange_types(self.env, etype)
        self.assertTrue(etype.webservice_endpoint_id)
        self.assertTrue(etype.webservice_send_as_bytes)
        # `send_as_bytes` must not linger in the YAML fallback.
        settings = etype.get_settings()
        self.assertNotIn("send_as_bytes", settings.get("execution_model", {}))

    @mute_logger("odoo.addons.edi_webservice_oca.utils")
    def test_migrate_send_as_bytes_extracted_to_field_when_complex(self):
        etype = self._make_type(
            "migrate_complex_bytes",
            """
            components:
              send:
                work_ctx:
                  webservice:
                    method: post
                    send_as_bytes: true
                    kwargs:
                      url_params:
                        endpoint: push/here
            """,
        )
        migrate_exchange_types(self.env, etype)
        self.assertFalse(etype.webservice_endpoint_id)
        self.assertTrue(etype.webservice_send_as_bytes)
        settings = etype.get_settings()
        self.assertNotIn(
            "send_as_bytes", settings["execution_model"]["send"]["webservice"]
        )

    def test_migrate_is_idempotent(self):
        etype = self._make_type(
            "migrate_idempotent",
            """
            components:
              send:
                work_ctx:
                  webservice:
                    method: get
            """,
        )
        migrate_exchange_types(self.env, etype)
        endpoint = etype.webservice_endpoint_id
        # Simulate a re-run (e.g. against a fresh default search): must
        # reuse the same endpoint, not create a duplicate.
        etype.send_model_id = self.component_model
        migrate_exchange_types(self.env, etype)
        self.assertEqual(etype.webservice_endpoint_id, endpoint)
        self.assertEqual(
            self.env["webservice.endpoint"].search_count(
                [("tech_name", "=", f"migrated_{etype.id}")]
            ),
            1,
        )

    def test_migrate_restricted_to_given_exchange_types(self):
        settings_yaml = (
            "components:\n  send:\n    work_ctx:\n      webservice:\n        "
            "method: get\n"
        )
        etype1 = self._make_type("migrate_only_one_a", settings_yaml)
        etype2 = self._make_type("migrate_only_one_b", settings_yaml)
        migrate_exchange_types(self.env, etype1)
        self.assertEqual(etype1.send_model_id, self.handler_model)
        self.assertEqual(etype2.send_model_id, self.component_model)

    def test_migrate_default_search_finds_eligible_types(self):
        settings_yaml = (
            "components:\n  send:\n    work_ctx:\n      webservice:\n        "
            "method: get\n"
        )
        etype = self._make_type("migrate_default_search", settings_yaml)
        migrated = migrate_exchange_types(self.env)
        self.assertIn(etype, migrated)
