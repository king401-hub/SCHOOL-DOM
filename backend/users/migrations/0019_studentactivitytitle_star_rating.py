from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0018_student_activity_title"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentactivitytitle",
            name="star_rating",
            field=models.DecimalField(
                decimal_places=1,
                default=1,
                max_digits=2,
                validators=[
                    django.core.validators.MinValueValidator(0.5),
                    django.core.validators.MaxValueValidator(5),
                ],
            ),
        ),
    ]
