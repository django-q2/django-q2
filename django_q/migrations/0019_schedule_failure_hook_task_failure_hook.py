# Generated by Django 5.0.7 on 2024-07-31 05:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('django_q', '0018_schedule_timeout_hook_task_timeout_hook'),
    ]

    operations = [
        migrations.AddField(
            model_name='schedule',
            name='failure_hook',
            field=models.CharField(blank=True, help_text='e.g. module.tasks.failure_function', max_length=256, null=True),
        ),
        migrations.AddField(
            model_name='task',
            name='failure_hook',
            field=models.CharField(max_length=256, null=True),
        ),
    ]