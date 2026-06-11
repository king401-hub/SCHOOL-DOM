from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0019_studentactivitytitle_star_rating"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="admin_title",
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
