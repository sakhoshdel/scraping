from khazesh.models import CodeExecutionState
from django.utils import timezone

def update_code_execution_state(name: str, success: bool, error_message: str = None):
    """
    بروزرسانی وضعیت اجرای کرول برای موبایل و تبلت
    """
    code_execution, created = CodeExecutionState.objects.get_or_create(name=name)
    now = timezone.now()

    if success:
        code_execution.status = True
        code_execution.fail_count = 0
        code_execution.last_success_at = now
        code_execution.status_text = "SUCCESS"
        code_execution.error_message = None
    else:
        code_execution.status = False
        code_execution.fail_count = (code_execution.fail_count or 0) + 1

        if code_execution.fail_count < 3:
            code_execution.status_text = "WARNING"
        else:
            code_execution.status_text = "FAILING"

        code_execution.error_message = error_message or "خطای نامشخص"

    code_execution.last_executed = now
    code_execution.save()
