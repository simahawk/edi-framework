# Copyright 2020 Dixmit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "EDI WebService",
    "summary": """
        Defines webservice integration from EDI Exchange records""",
    "version": "18.0.1.1.0",
    "license": "AGPL-3",
    "development_status": "Beta",
    "author": "Dixmit, Camptocamp, Odoo Community Association (OCA)",
    "maintainers": ["etobella", "simahawk"],
    "website": "https://github.com/OCA/edi-framework",
    "depends": ["edi_component_oca", "edi_core_oca", "webservice", "webservice_core"],
    "data": [
        "views/edi_backend.xml",
        "views/edi_exchange_type.xml",
        "security/ir.model.access.csv",
    ],
    "demo": ["demo/edi_backend.xml"],
}
