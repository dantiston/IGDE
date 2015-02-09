# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='comments',
            name='mrs',
            field=models.CharField(max_length=8192, default=''),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='comments',
            name='parse',
            field=models.CharField(max_length=8192, default=''),
            preserve_default=True,
        ),
    ]
