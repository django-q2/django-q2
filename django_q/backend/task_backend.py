from django import VERSION as DJANGO_VERSION

if DJANGO_VERSION < (6, 0):
    raise NotImplementedError("Task backend support requires Django ≥ 6.0")


from django.tasks.backends.base import BaseTaskBackend
from django_q .tasks import async_task, result
from django_q.conf import Conf


class DjangoQ2Backend(BaseTaskBackend):
    supports_get_result = True

    def __init__(self, alias, params):
        super().__init__(alias, params)
    
    def get_result(self, result_id,  *args, **kwargs):
        wait = kwargs.pop("wait", 0)
        cached = kwargs.pop("cached", Conf.CACHED)

        if args or kwargs:
            raise TypeError("get_result() received unsupported arguments")

        return result(task_id=result_id, wait=wait, cached=cached)
    
    def enqueue(self, task, args, kwargs):
        self.validate_task(task)
        return async_task(task.module_path, *args, **kwargs)
        
