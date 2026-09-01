# Copyright 2022 Camptocamp SA
# @author Simone Orsi <simahawk@gmail.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from urllib.parse import urlparse

import responses
from requests import PreparedRequest, Session

from odoo import exceptions

from .common import TestEDIWebserviceBase


class TestSend(TestEDIWebserviceBase):
    @classmethod
    def setUpClass(cls):
        cls._super_send = Session.send
        super().setUpClass()

    @classmethod
    def _setup_records(cls):
        result = super()._setup_records()
        cls.ws_backend = cls.backend.webservice_backend_id
        cls.handler = cls.env["edi.webservice.send"]
        cls.settings1 = """
        execution_model:
          send:
            webservice:
              _no_method: post
              pargs:
                - foo
                - bar
              kwargs:
                random: 1
                url_params:
                  endpoint: push/here
        """
        cls.settings2 = """
        execution_model:
          send:
            webservice:
              method: post
              kwargs:
                url_params:
                  endpoint: push/here
        """
        cls.record.type_id.set_settings(cls.settings1)
        return result

    @classmethod
    def _request_handler(cls, s: Session, r: PreparedRequest, /, **kw):
        # Allow request to test custom URL
        if urlparse(r.url).netloc == "foo.test":
            return cls._super_send(s, r)
        return super()._request_handler(s, r, **kw)

    def test_handler_selected(self):
        self.assertEqual(self.record.type_id.send_model_id.model, "edi.webservice.send")

    def test_webservice_send_enabled(self):
        self.assertTrue(self.record.type_id.webservice_send_enabled)
        component_model = self.env.ref(
            "edi_component_oca.model_edi_oca_component_handler"
        )
        self.record.type_id.send_model_id = component_model
        self.assertFalse(self.record.type_id.webservice_send_enabled)

    def test_get_data_default_str(self):
        result = self.handler._get_data(self.record)
        self.assertIsInstance(result, str)

    def test_get_data_as_bytes(self):
        self.record.type_id.webservice_send_as_bytes = True
        result = self.handler._get_data(self.record)
        self.assertIsInstance(result, bytes)

    def test_get_ws_settings(self):
        self.assertEqual(
            self.handler._get_ws_settings(self.record),
            {
                "_no_method": "post",
                "pargs": ["foo", "bar"],
                "kwargs": {
                    "random": 1,
                    "url_params": {
                        "endpoint": "push/here",
                    },
                },
            },
        )

    def test_get_call_params_no_method(self):
        ws_settings = self.handler._get_ws_settings(self.record)
        msg = "`method` is required in `webservice` type settings"
        with self.assertRaisesRegex(exceptions.UserError, msg):
            self.handler._get_call_params(self.record, ws_settings)

    def test_get_call_params(self):
        self.record.type_id.set_settings(self.settings2)
        ws_settings = self.handler._get_ws_settings(self.record)
        method, pargs, kwargs = self.handler._get_call_params(self.record, ws_settings)
        self.assertEqual(method, "post")
        self.assertEqual(len(kwargs), 2)
        self.assertEqual(kwargs["data"], "This is a simple file")
        self.assertEqual(kwargs["url_params"], {"endpoint": "push/here"})

    @responses.activate
    def test_send(self):
        self.record.type_id.set_settings(self.settings2)
        url = "https://foo.test/push/here"
        responses.add(responses.POST, url, body="{}")
        result = self.handler.send(self.record)
        self.assertEqual(result, b"{}")
        self.assertEqual(
            responses.calls[0].request.headers["Content-Type"], "application/xml"
        )
        self.assertEqual(responses.calls[0].request.body, "This is a simple file")

    @responses.activate
    def test_send_with_endpoint(self):
        # A `webservice.endpoint` set on the exchange type takes precedence
        # over the `webservice` advanced settings key.
        # NOTE: uses its own backend since the demo one's URL is a
        # `{endpoint}` template meant for the `url_params` mechanism, not
        # for a `webservice.endpoint`'s relative `path`.
        backend = self.env["webservice.backend"].create(
            {
                "name": "Endpoint demo backend",
                "tech_name": "edi_demo_ws_endpoint",
                "protocol": "http",
                "url": "https://foo.test/",
                "content_type": "application/xml",
                "auth_type": "none",
            }
        )
        endpoint = self.env["webservice.endpoint"].create(
            {
                "name": "Push here",
                "tech_name": "push_here",
                "description": "Push the exchange file",
                "backend_id": backend.id,
                "http_method": "post",
                "path": "push/here",
            }
        )
        self.record.type_id.webservice_endpoint_id = endpoint.id
        url = "https://foo.test/push/here"
        responses.add(responses.POST, url, body="{}")
        result = self.handler.send(self.record)
        self.assertEqual(result, b"{}")
        self.assertEqual(responses.calls[0].request.body, "This is a simple file")
