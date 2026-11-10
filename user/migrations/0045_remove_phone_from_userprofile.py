from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('user', '0044_notification_admin_access_removed'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicaluserprofile',
            name='phone',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='phone',
        ),
    ]
