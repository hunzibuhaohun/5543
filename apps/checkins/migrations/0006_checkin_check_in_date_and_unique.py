# Generated manually for check-in day uniqueness support

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('checkins', '0005_alter_checkin_unique_together_alter_checkin_accuracy_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='checkin',
            name='check_in_date',
            field=models.DateField(db_index=True, default=django.utils.timezone.localdate, verbose_name='打卡日期'),
        ),
        migrations.AlterUniqueTogether(
            name='checkin',
            unique_together={('user', 'activity', 'check_in_date')},
        ),
    ]
