from  khazesh.models import CodeExecutionState
from django.utils import timezone

def update_code_execution_state(name: str, success: bool, error_message: str = None):
    # Get or create the execution state for the code
    code_execution, created = CodeExecutionState.objects.get_or_create(name=name)

    # Update the status, error message, and last executed time
    code_execution.status = success
    code_execution.last_executed = timezone.now()
    
    if not success and error_message:
        code_execution.error_message = error_message
    else:
        code_execution.error_message = None  # Clear previous error message if it succeeds
    
    code_execution.save()