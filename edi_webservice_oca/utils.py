# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""Helpers to migrate exchange types off the deprecated `component`-based
webservice send integration (see `components/send.py`) onto the new
`edi.webservice.send` model handler.

This is deliberately NOT wired as an automatic module migration: from here
we cannot tell whether a given exchange type's effective send behavior
comes from the generic `edi_component_oca.model_edi_oca_component_handler`
bridge, or from a custom, hand-extended `edi.webservice.send` Component -
blindly repointing `send_model_id` for every such type could silently
change behavior for anyone who extended the component.

Treat this as a starting point / library to migrate your own data once
you've confirmed which exchange types are safe to move, e.g. from
``odoo shell``::

    from odoo.addons.edi_webservice_oca.utils import migrate_exchange_types
    migrated = migrate_exchange_types(env)
    env.cr.commit()

Or restrict it to specific types::

    migrate_exchange_types(env, env["edi.exchange.type"].browse([12, 34]))
"""

import logging

import yaml

_logger = logging.getLogger(__name__)


def migrate_exchange_types(env, exchange_types=None):
    """Move exchange types off the generic component handler onto the new
    `edi.webservice.send` model handler, converting "simple" webservice
    settings into an actual `webservice.endpoint` where possible.

    :param env: Odoo environment.
    :param exchange_types: optional `edi.exchange.type` recordset to
        restrict the migration to; defaults to every type whose
        `send_model_id` is still the generic component handler and whose
        backend has a `webservice_backend_id`.
    :return: the `edi.exchange.type` recordset that was migrated.
    """
    component_model = env.ref(
        "edi_component_oca.model_edi_oca_component_handler", raise_if_not_found=False
    )
    if not component_model:
        # `edi_component_oca` was never installed: nothing relied on it.
        return env["edi.exchange.type"].browse()
    handler_model = env.ref("edi_webservice_oca.model_edi_webservice_send")

    if exchange_types is None:
        exchange_types = env["edi.exchange.type"].search(
            [
                ("send_model_id", "=", component_model.id),
                ("backend_id.webservice_backend_id", "!=", False),
            ]
        )
    for etype in exchange_types:
        _migrate_type_settings(env, etype)
    exchange_types.send_model_id = handler_model
    return exchange_types


def _is_simple_ws_settings(ws_settings):
    if not ws_settings.get("method"):
        return False
    if ws_settings.get("pargs"):
        return False
    # Any `kwargs` (typically `url_params`, used to fill a `{placeholder}`
    # in the backend's URL) cannot be safely reproduced by an endpoint's
    # `url_param_ids`, which is a querystring mechanism, not a
    # path-placeholder one. Keep those as YAML instead of auto-converting.
    return not ws_settings.get("kwargs")


def _migrate_type_settings(env, etype):
    settings = yaml.safe_load(etype.advanced_settings_edit or "") or {}
    send_conf = settings.get("components", {}).get("send", {})
    work_ctx = send_conf.get("work_ctx", {})
    ws_settings = work_ctx.pop("webservice", None)
    if ws_settings is None:
        # Nothing to move: the type relied on the backend-level auto
        # selection without any explicit `webservice` YAML settings.
        return
    if not work_ctx:
        send_conf.pop("work_ctx", None)
    if not send_conf:
        settings.get("components", {}).pop("send", None)

    # `send_as_bytes` is now a proper field, independent of whether the
    # rest of the settings are simple enough to become an endpoint.
    if ws_settings.pop("send_as_bytes", None):
        etype.webservice_send_as_bytes = True

    if _is_simple_ws_settings(ws_settings) and not etype.webservice_endpoint_id:
        etype.webservice_endpoint_id = _create_endpoint_from_settings(env, etype, ws_settings)
    else:
        settings.setdefault("execution_model", {}).setdefault("send", {})[
            "webservice"
        ] = ws_settings

    etype.advanced_settings_edit = yaml.safe_dump(settings, sort_keys=False)
    return bool(etype.webservice_endpoint_id)


def _create_endpoint_from_settings(env, etype, ws_settings):
    ws_backend = etype.backend_id.webservice_backend_id
    tech_name = f"migrated_{etype.code}"
    endpoint = env["webservice.endpoint"].search(
        [("backend_id", "=", ws_backend.id), ("tech_name", "=", tech_name)], limit=1
    )
    if not endpoint:
        endpoint = env["webservice.endpoint"].create(
            {
                "name": etype.name,
                "tech_name": tech_name,
                "description": (
                    f"Auto-migrated from exchange type '{etype.code}' "
                    "advanced settings."
                ),
                "backend_id": ws_backend.id,
                "http_method": ws_settings["method"].lower(),
            }
        )
        _logger.info(
            "edi.exchange.type(%s): created webservice.endpoint(%s) from "
            "advanced settings.",
            etype.id,
            endpoint.id,
        )
    return endpoint
