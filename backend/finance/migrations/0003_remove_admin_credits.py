from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0002_admincredit_credittransaction_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="CreditTransaction",
        ),
        migrations.DeleteModel(
            name="AdminCredit",
        ),
    ]
