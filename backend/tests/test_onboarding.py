"""Running without the demo seed: opening an organization, accounts, patients, passwords, AI off."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from ai.gateway import call_model
from clinical.models import Patient
from core.models import AuditEvent, Organization, Role, User

ACCOUNTS, PATIENTS, PASSWORD = "/api/admin/accounts/", "/api/admin/patients/", "/api/auth/password/"
GOOD = "a-long-unusual-passphrase-41"


@pytest.fixture
def admin(org, make_user) -> User:
    return make_user("admin", Role.ORG_ADMIN, org)


def test_create_org_admin_command(db, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_PASSWORD", "short")
    with pytest.raises(CommandError):
        call_command("create_org_admin", "Unit A", "unit_admin")
    monkeypatch.setenv("ADMIN_PASSWORD", GOOD)
    call_command("create_org_admin", "Unit A", "unit_admin")
    created = User.objects.get(username="unit_admin")
    assert created.role == Role.ORG_ADMIN and created.organization.name == "Unit A" and created.check_password(GOOD)
    with pytest.raises(CommandError):
        call_command("create_org_admin", "Unit A", "unit_admin")
    assert Organization.objects.filter(name="Unit A").count() == 1


def test_admin_opens_accounts_registers_a_patient_and_builds_the_care_team(api, admin, doctor, other_org) -> None:
    client = api(admin)
    weak = client.post(ACCOUNTS, {"username": "n1", "role": "nurse", "password": "12345"}, "json")
    assert weak.status_code == 400 and "password" in str(weak.content)
    for role in ("org_admin", "sys_admin", "auditor", "service"):  # no self-made administrators
        assert client.post(ACCOUNTS, {"username": "x", "role": role, "password": GOOD}, "json").status_code == 400
    nurse = client.post(ACCOUNTS, {"username": "n1", "display_name": "Nurse One", "role": "nurse", "password": GOOD})
    account = client.post(ACCOUNTS, {"username": "p1", "role": "patient", "password": GOOD}, "json")
    assert nurse.status_code == 201 and account.status_code == 201 and "password" not in nurse.json()
    assert User.objects.get(username="n1").organization_id == admin.organization_id

    body = {"mrn": "R-100", "full_name": "A Patient", "date_of_birth": "1970-02-03", "account": "p1"}
    registered = client.post(PATIENTS, body, "json")
    assert registered.status_code == 201, registered.content
    patient = Patient.objects.get(mrn="R-100")
    assert patient.user.username == "p1" and patient.organization_id == admin.organization_id
    assert client.post(PATIENTS, body, "json").status_code == 400  # same record number, same account
    assert client.post(PATIENTS, {**body, "mrn": "R-101"}, "json").status_code == 400  # account already linked

    assign = {"patient": str(patient.id), "professional": nurse.json()["id"]}
    assert client.post("/api/care-assignments/", assign, "json").status_code == 201
    assert [p["id"] for p in api(User.objects.get(username="n1")).get("/api/patients/").json()["results"]] == [
        str(patient.id)
    ]
    assert api(doctor).get("/api/patients/").json()["results"] == []  # not on the team: sees nothing
    assert api(User.objects.get(username="p1")).get("/api/patients/").json()["results"][0]["id"] == str(patient.id)
    assert {"account_created", "patient_registered"} <= set(AuditEvent.objects.values_list("action", flat=True))

    gone = client.post(f"{ACCOUNTS}{nurse.json()['id']}/deactivate/")
    assert gone.status_code == 200 and gone.json()["is_active"] is False


def test_only_the_organizations_own_admin_reaches_the_registry(
    api, admin, doctor, nurse, patient, make_user, other_org
):
    for user in (doctor, nurse, patient.user):
        assert api(user).get(ACCOUNTS).status_code == 403 and api(user).get(PATIENTS).status_code == 403
        assert (
            api(user).post(PATIENTS, {"mrn": "X", "full_name": "X", "date_of_birth": "1970-01-01"}).status_code == 403
        )
    assert api().get(ACCOUNTS).status_code == 401
    foreign = api(make_user("foreign_admin", Role.ORG_ADMIN, other_org))
    assert foreign.get(PATIENTS).json()["results"] == [] and foreign.get(ACCOUNTS).json()["results"] == []
    assert foreign.post(f"{ACCOUNTS}{doctor.id}/deactivate/").status_code == 404
    mine = api(admin).get(PATIENTS).json()["results"]
    assert [p["mrn"] for p in mine] == [patient.mrn] and set(mine[0]) == {
        "id", "mrn", "full_name", "date_of_birth", "account"
    }  # fmt: skip


def test_anyone_can_change_their_own_password(api, nurse) -> None:
    client = api(nurse)
    wrong = client.post(PASSWORD, {"current_password": "nope", "new_password": GOOD}, "json")
    assert wrong.status_code == 400 and "current_password" in str(wrong.content)
    old = "pw-for-tests-12345"
    assert client.post(PASSWORD, {"current_password": old, "new_password": "123"}, "json").status_code == 400
    assert client.post(PASSWORD, {"current_password": old, "new_password": GOOD}, "json").status_code == 204
    nurse.refresh_from_db()
    assert nurse.check_password(GOOD)
    assert api().post(PASSWORD, {"current_password": old, "new_password": GOOD}, "json").status_code == 401


def test_outside_demo_mode_nothing_is_seeded_and_no_template_passes_for_ai(db, settings) -> None:
    settings.DEMO_MODE = False
    with pytest.raises(CommandError):
        call_command("seed_demo")
    output, errors, _ = call_model("patient_chat_v1", {"question": "urea", "record": {}})
    assert output is None and errors[0]["code"] == "provider_error"
    settings.LLM_PROVIDER = "anthropic"  # no key configured: still no template answer
    assert call_model("patient_chat_v1", {"question": "urea", "record": {}})[0] is None
