# Generated by Django 4.1.5 on 2023-01-29 11:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("django_q", "0016_schedule_intended_date_kwarg"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="cluster",
            field=models.CharField(blank=True, default=None, max_length=100, null=True),
        ),
    ]