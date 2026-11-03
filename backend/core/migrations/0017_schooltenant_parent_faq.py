from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_schooltenant_branch_label'),
    ]

    operations = [
        migrations.AddField(
            model_name='schooltenant',
            name='parent_faq',
            field=models.TextField(blank=True, default=''),
        ),
    ]
