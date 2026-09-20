# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class EDIExchangeType(models.Model):
    _inherit = "edi.exchange.type"

    webservice_backend_id = fields.Many2one(
        related="backend_id.webservice_backend_id",
    )
    webservice_send_enabled = fields.Boolean(
        compute="_compute_webservice_send_enabled",
        help="Technical flag: whether `send_model_id` is the webservice "
        "send handler (`edi.webservice.send`). Used to show/hide "
        "webservice-specific settings on this type.",
    )
    webservice_endpoint_id = fields.Many2one(
        "webservice.endpoint",
        string="WebService Endpoint",
        help="Specific webservice endpoint to call when sending through this "
        "exchange type. If not set, the `webservice` key of the advanced "
        "YAML settings is used instead (see `edi.webservice.send`).",
    )
    webservice_send_as_bytes = fields.Boolean(
        string="Send As Bytes",
        help="By sending as bytes, `requests` won't try to guess and/or "
        "alter the encoding of the file being sent.",
    )

    # TODO: this should look for inheritance on edi.webservice.send
    # or a specific ir.model param because peopel can extend the model.
    @api.depends("send_model_id")
    def _compute_webservice_send_enabled(self):
        handler = self.env.ref(
            "edi_webservice_oca.model_edi_webservice_send", raise_if_not_found=False
        )
        for rec in self:
            rec.webservice_send_enabled = bool(handler) and rec.send_model_id == handler
