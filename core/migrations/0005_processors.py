"""Processors: IGDE is no longer tied to ACE.

The ACE settings (ACE_ROOT and memory limits) move from the settings
singleton to an "ACE" Processor, which becomes the default processor.
"""

import django.db.models.deletion
from django.db import migrations, models


def ace_settings_to_processor(apps, schema_editor):
    AppSettings = apps.get_model("core", "AppSettings")
    Processor = apps.get_model("core", "Processor")
    for cfg in AppSettings.objects.all():
        p = Processor.objects.create(
            name="ACE",
            backend="ace",
            location=cfg.ace_root,
            options={
                "maxChartMegabytes": cfg.max_chart_megabytes,
                "maxUnpackMegabytes": cfg.max_unpack_megabytes,
            },
        )
        cfg.default_processor = p
        cfg.save(update_fields=["default_processor"])


def processor_to_ace_settings(apps, schema_editor):
    AppSettings = apps.get_model("core", "AppSettings")
    for cfg in AppSettings.objects.all():
        p = cfg.default_processor
        if p is not None and p.backend == "ace":
            cfg.ace_root = p.location
            cfg.max_chart_megabytes = p.options.get("maxChartMegabytes", 1200)
            cfg.max_unpack_megabytes = p.options.get("maxUnpackMegabytes", 1500)
            cfg.save()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_test_suites"),
    ]

    operations = [
        migrations.CreateModel(
            name="Processor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("backend", models.CharField(max_length=32)),
                ("location", models.CharField(blank=True, default="", max_length=4096)),
                ("options", models.JSONField(blank=True, default=dict)),
                ("created", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.RenameModel(old_name="AceConfig", new_name="AppSettings"),
        migrations.AddField(
            model_name="appsettings",
            name="default_processor",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="core.processor"
            ),
        ),
        migrations.AddField(
            model_name="grammar",
            name="processor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="grammars",
                to="core.processor",
            ),
        ),
        migrations.RunPython(ace_settings_to_processor, processor_to_ace_settings),
        migrations.RemoveField(model_name="appsettings", name="ace_root"),
        migrations.RemoveField(model_name="appsettings", name="max_chart_megabytes"),
        migrations.RemoveField(model_name="appsettings", name="max_unpack_megabytes"),
    ]
