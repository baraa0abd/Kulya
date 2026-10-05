"""DB-level guard: any UPDATE on clinical_note fails, even one that bypasses Note.save()."""

from django.db import migrations

SQL = {
    "postgresql": (
        """
        CREATE FUNCTION clinical_note_immutable() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'clinical_note is immutable'; END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER clinical_note_immutable BEFORE UPDATE ON clinical_note
        FOR EACH ROW EXECUTE FUNCTION clinical_note_immutable();
        """,
        "DROP TRIGGER clinical_note_immutable ON clinical_note; DROP FUNCTION clinical_note_immutable();",
    ),
    "sqlite": (
        """
        CREATE TRIGGER clinical_note_immutable BEFORE UPDATE ON clinical_note
        BEGIN SELECT RAISE(ABORT, 'clinical_note is immutable'); END;
        """,
        "DROP TRIGGER clinical_note_immutable;",
    ),
}


def _run(index: int):
    def run(apps, schema_editor) -> None:
        schema_editor.execute(SQL[schema_editor.connection.vendor][index])

    return run


class Migration(migrations.Migration):
    dependencies = [("clinical", "0001_initial")]
    operations = [migrations.RunPython(_run(0), _run(1))]
