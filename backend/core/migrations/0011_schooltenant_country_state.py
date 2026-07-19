from django.db import migrations, models
import django_countries.fields


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_schooltenant_compliance_deadline_reference_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="schooltenant",
            name="country",
            field=django_countries.fields.CountryField(blank=True, default="NG", max_length=2),
        ),
        migrations.AddField(
            model_name="schooltenant",
            name="state",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
    ]
