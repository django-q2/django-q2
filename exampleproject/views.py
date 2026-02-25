import time

from django.http import HttpResponse
from django.urls import reverse

from django_q import tasks


# internal function to be called with django_q
def new_task(run_for_minutes):
    print("Task started")
    time.sleep(run_for_minutes)
    print("Task done")
    return True


def add_task(request):
    task_id = tasks.async_task(new_task, 5)
    result_url = reverse("get_result", args=[task_id])
    return HttpResponse(
        f"Added async task with <a href='{result_url}'>Go to results</a>"
    )


def get_result(request, task_id):
    task = tasks.fetch(task_id)
    if not task:
        msg = "Task running... please refresh after some time"
    else:
        msg = f"Async task result: {task.result}"
    return HttpResponse(msg)
