from django.db import migrations, models

OLD_TO_NEW = {
    '#009C6B': '#1D4E9E',
    '#46552F': '#1D4E9E',
    '#232719': '#0B2545',
    '#B07A2A': '#7A5A00',
    '#4C6B7A': '#0E6E86',
}


def recolour(apps, schema_editor):
    UserProfile = apps.get_model('authentication', 'UserProfile')
    for old, new in OLD_TO_NEW.items():
        UserProfile.objects.filter(avatar_color__iexact=old).update(avatar_color=new)


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0004_userprofile_is_suspended_userprofile_suspended_at_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='avatar_color',
            field=models.CharField(default='#1D4E9E', max_length=7),
        ),
        migrations.RunPython(recolour, migrations.RunPython.noop),
    ]
