# Generated by Django 3.0.7 on 2020-08-11 15:17

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_q", "0012_auto_20200702_1608"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="attempt_count",
            field=models.IntegerField(default=0),
        ),
    ]
