from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="avatar_color",
            field=models.CharField(default="#46552F", max_length=7),
        ),
    ]
