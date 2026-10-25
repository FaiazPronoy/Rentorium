import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0005_blueprint_avatar_colours"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="two_step",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="EmailCode",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "purpose",
                    models.CharField(
                        choices=[
                            ("sign_in", "Sign in"),
                            ("turn_on", "Turn on two-step sign in"),
                        ],
                        max_length=10,
                    ),
                ),
                ("code_hash", models.CharField(max_length=128)),
                ("tries", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="email_codes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["user", "purpose", "-created_at"],
                        name="authenticat_user_id_7cb2ed_idx",
                    )
                ],
            },
        ),
    ]
