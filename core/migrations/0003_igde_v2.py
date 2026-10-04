import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Replace the v0.1 chat-style Comments model with ACE configuration
    and the grammar registry."""

    dependencies = [
        ("core", "0002_auto_20150208_2230"),
    ]

    operations = [
        migrations.DeleteModel(name="Comments"),
        migrations.CreateModel(
            name="Grammar",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("config_path", models.CharField(blank=True, default="", max_length=4096)),
                ("image_path", models.CharField(max_length=4096)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("compile_status", models.CharField(default="idle", max_length=16)),
                ("compile_log", models.TextField(blank=True, default="")),
                ("compiled_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.CreateModel(
            name="AceConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ace_root", models.CharField(blank=True, default="", max_length=4096)),
                ("max_results", models.PositiveIntegerField(default=5)),
                ("timeout_seconds", models.PositiveIntegerField(default=60)),
                ("max_chart_megabytes", models.PositiveIntegerField(default=1200)),
                ("max_unpack_megabytes", models.PositiveIntegerField(default=1500)),
                ("grammar_image_dir", models.CharField(blank=True, default="", max_length=4096)),
                (
                    "active_grammar",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="core.grammar",
                    ),
                ),
            ],
        ),
    ]
