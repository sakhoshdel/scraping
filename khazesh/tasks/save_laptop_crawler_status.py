from khazesh.models import CodeExecutionStateLaptop
from django.utils import timezone

def laptop_update_code_execution_state(name: str, success: bool, error_message: str = None):
    """
    بروزرسانی وضعیت اجرای کرول برای لپ‌تاپ
    """
    # دریافت یا ایجاد رکورد
    code_execution, created = CodeExecutionStateLaptop.objects.get_or_create(name=name)

    now = timezone.now()

    # اگر کرول موفق بود
    if success:
        code_execution.status = True
        code_execution.fail_count = 0                      # ریست تعداد خطاها
        code_execution.last_success_at = now               # ثبت آخرین موفقیت
        code_execution.status_text = "SUCCESS"             # وضعیت کلی: موفق
        code_execution.error_message = None                # پاک کردن خطای قبلی
    else:
        code_execution.status = False
        code_execution.fail_count = (code_execution.fail_count or 0) + 1

        # تعیین وضعیت بر اساس تعداد شکست‌های متوالی
        if code_execution.fail_count < 3:
            code_execution.status_text = "WARNING"         # هشدار
        else:
            code_execution.status_text = "FAILING"         # وضعیت بحرانی

        code_execution.error_message = error_message or "خطای نامشخص"

    # بروزرسانی زمان آخرین اجرا
    code_execution.last_executed = now

    # ذخیره در دیتابیس
    code_execution.save()
