from django.http import JsonResponse
from .tasks import myprint

## Example of running celery task
def run_celery_task(request):
    # 1st method
    myprint.delay() ## args can be passed as well but not objects
    ##Syntax: task_name.delay(arg1, arg2, ...)
    # 2nd method
    myprint.apply_async() ## args can be passed as well but not objects
    # Syntax: task_name.apply_async(args=[arg1, arg2], kwargs={'key': value}, options={})
    return JsonResponse({'status':'success'})
