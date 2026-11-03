import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0036_feewaiver'),
        ('academic', '0027_studenttraitrecord'),
    ]

    operations = [
        migrations.AddField(
            model_name='classfee',
            name='term',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='class_fees', to='academic.term'),
        ),
        migrations.AddField(
            model_name='schoolfee',
            name='term',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='school_fees', to='academic.term'),
        ),
        migrations.AddField(
            model_name='schoolfee',
            name='closed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
