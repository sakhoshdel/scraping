from  khazesh.models import CodeExecutionStateAccessories, CategoryAccessories
from django.utils import timezone

def accessories_update_code_execution_state(name: str, category: str, success: bool, error_message: str = None):
    cat = CategoryAccessories.objects.filter(name_en=category).first()
    # Get or create the execution state for the code
    code_execution, created = CodeExecutionStateAccessories.objects.get_or_create(name=name, category=cat)

    # Update the status, error message, and last executed time
    code_execution.category = cat
    code_execution.status = success
    code_execution.last_executed = timezone.now()
    
    if not success and error_message:
        code_execution.error_message = error_message
    else:
        code_execution.error_message = None  # Clear previous error message if it succeeds
    
    code_execution.save()