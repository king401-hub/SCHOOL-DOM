from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0013_databaseimportjob"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameIndex(
                    model_name="databaseimportjob",
                    new_name="users_datab_tenant__784574_idx",
                    old_name="users_datab_tenant__d2d7de_idx",
                ),
                migrations.RenameIndex(
                    model_name="databaseimportjob",
                    new_name="users_datab_tenant__709a02_idx",
                    old_name="users_datab_tenant__705b75_idx",
                ),
            ],
            database_operations=[],
        ),
    ]
