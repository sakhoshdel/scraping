from khazesh.models import CodeExecutionStateAccessories, CategoryAccessories
from django.utils import timezone

def accessories_update_code_execution_state(name: str, category: str, success: bool, error_message: str = None):
    """
    بروزرسانی وضعیت اجرای کرول برای لوازم جانبی
    """
    cat = CategoryAccessories.objects.filter(name_en=category).first()
    if not cat:
        return  # اگر دسته‌بندی پیدا نشد، از تابع خارج شو (می‌تونی بعداً هندل خطا کنی)

    code_execution, created = CodeExecutionStateAccessories.objects.get_or_create(
        name=name, category=cat
    )

    # زمان فعلی
    now = timezone.now()

    # اگر کرول موفق بود
    if success:
        code_execution.status = True
        code_execution.fail_count = 0  # ریست شمارنده خطا
        code_execution.last_success_at = now
        code_execution.status_text = "SUCCESS"
        code_execution.error_message = None  # پاک کردن خطای قبلی (در صورت وجود)

    else:
        # کرول ناموفق بود
        code_execution.status = False
        code_execution.fail_count = (code_execution.fail_count or 0) + 1

        # وضعیت بر اساس تعداد شکست‌ها
        if code_execution.fail_count < 3:
            code_execution.status_text = "WARNING"
        else:
            code_execution.status_text = "FAILING"

        # ثبت خطا
        code_execution.error_message = error_message or "خطای نامشخص"

    # همیشه زمان آخرین اجرا رو بروزرسانی کن
    code_execution.last_executed = now
    code_execution.save()
