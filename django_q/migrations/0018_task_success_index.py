# Generated by Django 4.2.7 on 2024-03-05 17:03

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_q", "0017_task_cluster_alter"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="task",
            index=models.Index(
                condition=models.Q(("success", True)),
                fields=["group", "name", "func"],
                name="success_index",
            ),
        ),
    ]
