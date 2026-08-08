"""Unit tests for require_auth — both decorator forms and role gating."""

import pytest
from werkzeug.exceptions import HTTPException

from app.utils.auth import require_auth


@require_auth
def bare_form():
    return "ok"


@require_auth()
def called_form():
    return "ok"


@require_auth(roles=["service_role"])
def role_gated():
    return "ok"


def test_both_forms_accept_valid_token(app, make_token):
    headers = {"Authorization": f"Bearer {make_token()}"}
    with app.test_request_context(headers=headers):
        assert bare_form() == "ok"
        assert called_form() == "ok"


def test_both_forms_reject_missing_token(app):
    with app.test_request_context():
        for fn in (bare_form, called_form):
            with pytest.raises(HTTPException) as exc:
                fn()
            assert exc.value.code == 401


def test_role_gate_rejects_wrong_role(app, make_token):
    headers = {"Authorization": f"Bearer {make_token()}"}  # role=authenticated
    with app.test_request_context(headers=headers):
        with pytest.raises(HTTPException) as exc:
            role_gated()
        assert exc.value.code == 403


def test_role_gate_accepts_matching_role(app, make_token):
    headers = {"Authorization": f"Bearer {make_token(role='service_role')}"}
    with app.test_request_context(headers=headers):
        assert role_gated() == "ok"


def test_g_user_is_populated(app, make_token):
    from flask import g

    headers = {"Authorization": f"Bearer {make_token(email='who@local.test')}"}
    with app.test_request_context(headers=headers):
        bare_form()
        assert g.user["email"] == "who@local.test"
        assert g.user["role"] == "authenticated"
