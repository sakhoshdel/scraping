from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class DateModel(models.Model):
    price_change_time = models.DateTimeField(null=True, verbose_name=_('تاریخ و ساعت ایجاد'))
    updated_at = models.DateTimeField(null=True, verbose_name=_('تاریخ و ساعت آپدیت'))

    class Meta:
        abstract = True


class Brand(models.Model):
    name = models.CharField(max_length=50, verbose_name=_('برند'))

    def __str__(self) -> str:
        return self.name

class Mobile(DateModel):
    mobile_digi_id = models.CharField(max_length=200, null=True, blank=True, verbose_name=_("آیدی گوشی مناسب هر سایت"))
    model = models.CharField(max_length=100, verbose_name=_("مدل"))
    color_name = models.CharField(max_length=30, null=True, blank=True, verbose_name=_('رنگ'))
    color_hex = models.CharField(max_length=500 ,null=True, blank=True, verbose_name=_('کد هگز رنگ'))
    seller = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('فروشنده'))
    guarantee = models.CharField(max_length=150, null=True, blank=True, verbose_name=_('گارانتی'))
    ram = models.CharField(max_length=20, null=True, blank=True, verbose_name=_('حافظه رم'))
    memory = models.CharField(max_length=20, null=True, blank=True, verbose_name=_('حافظه داخلی'))
    vietnam = models.BooleanField(default=False, null=True, blank=True, verbose_name=_('ساخت ویتنام'))
    dual_sim = models.BooleanField(default=True, verbose_name=_('دو سیم کارت')) 
    title = models.CharField(max_length=200, verbose_name=_('توضیحات تایتل'))
    max_price = models.DecimalField(max_digits=10, decimal_places=0 , verbose_name=_('بیشترین قیمت'))
    min_price = models.DecimalField(max_digits=10, decimal_places=0 , verbose_name=_('کمترین قیمت'))
    old_min_price = models.DecimalField(max_digits=10, decimal_places=0,null=True, blank=True, verbose_name=_('کمترین قیمت قبلی'))
    active = models.BooleanField(default=True, verbose_name=_('موجود'))
    site = models.CharField(max_length=30 , verbose_name=_('سایت'))
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name='mobiles', verbose_name=_('برند'))
    url = models.URLField(max_length=1000)
    not_active = models.BooleanField(default=False)
    price_diff_time = models.CharField(max_length=200, null=True, blank=True)
    custom_id = models.CharField(max_length=20, null=True, blank=True)
    status = models.BooleanField(default=False, verbose_name=_('وضعیت'))
    mobile = models.BooleanField(default=True, verbose_name=_('موبایل یا تبلت'))
    price_changes_24h = models.JSONField(default=list, blank=True, verbose_name="تغییرات قیمت ۲۴ ساعته")

class ConnectionErrorLog(models.Model):
    url = models.URLField()
    error_message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.url} - {self.timestamp}"
    


class CodeExecutionState(models.Model):
    name = models.CharField(max_length=100, unique=True)  # Unique site name for each code
    status = models.BooleanField(default=False)  # True if success, False if failed
    last_executed = models.DateTimeField(default=timezone.now)  # When the code was last executed
    error_message = models.TextField(null=True, blank=True)  # Error logs

    def __str__(self):
        return f"{self.name} - {'Success' if self.status else 'Failure'}"




class CategoryAccessories(models.Model):
    name_fa = models.CharField(max_length=50, verbose_name=_('نام فارسی دسته بندی'))
    name_en = models.CharField(max_length=50, verbose_name=_('نام لاتین دسته بندی'))

    def __str__(self) -> str:
        return self.name_en



class BrandAccessories(models.Model):
    name_fa = models.CharField(max_length=50, verbose_name=_('نام فارسی برند '))
    name_en = models.CharField(max_length=50, verbose_name=_('نام لاتین برند'))

    def __str__(self) -> str:
        return self.name_en

class ProductAccessories(models.Model):
    model = models.CharField(max_length=100, verbose_name=_("مدل"))
    color_name = models.CharField(max_length=30, null=True, blank=True, verbose_name=_('رنگ'))
    color_hex = models.CharField(max_length=500 ,null=True, blank=True, verbose_name=_('کد هگز رنگ'))
    seller = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('فروشنده'))
    guarantee = models.CharField(max_length=150, null=True, blank=True, verbose_name=_('گارانتی'))
    title = models.CharField(max_length=200, verbose_name=_('توضیحات تایتل'))
    max_price = models.DecimalField(max_digits=10, decimal_places=0 , verbose_name=_('بیشترین قیمت'))
    min_price = models.DecimalField(max_digits=10, decimal_places=0 , verbose_name=_('کمترین قیمت'))
    old_min_price = models.DecimalField(max_digits=10, decimal_places=0,null=True, blank=True, verbose_name=_('کمترین قیمت قبلی'))
    stock = models.BooleanField(default=True, verbose_name=_('موجود'))
    fake = models.BooleanField(default=True, verbose_name=_('اصل یا غیراصل'))
    site = models.CharField(max_length=30 , verbose_name=_('سایت'))
    brand = models.ForeignKey(BrandAccessories, on_delete=models.PROTECT,  verbose_name=_('برند'))
    category = models.ForeignKey(CategoryAccessories, on_delete=models.PROTECT, verbose_name=_('دسته بندی'))
    url = models.URLField(max_length=1000)
    price_change_time = models.DateTimeField(null=True, verbose_name=_('تاریخ و ساعت ایجاد'))
    updated_at = models.DateTimeField(null=True, verbose_name=_('تاریخ و ساعت آپدیت'))  
    price_diff_time = models.CharField(max_length=200, null=True, blank=True)
    updated_bartardigital = models.DateTimeField(null=True, verbose_name=_('آخرین بروزرسانی در برتردیجیتال'))
    description = models.CharField(max_length=10000, null=True, blank=True, verbose_name=_('توضیحات تکمیلی'))
    custom_id = models.CharField(max_length=20, null=True, blank=True)
    status = models.BooleanField(default=False, verbose_name=_('وضعیت'))
    price_changes_24h = models.JSONField(default=list, blank=True, verbose_name="تغییرات قیمت ۲۴ ساعته")

    

class CodeExecutionStateAccessories(models.Model):
    name = models.CharField(max_length=100, unique=True)  # Unique site name for each code
    category = models.ForeignKey(CategoryAccessories, on_delete=models.PROTECT, verbose_name=_('دسته بندی'))
    status = models.BooleanField(default=False)  # True if success, False if failed
    last_executed = models.DateTimeField(default=timezone.now)  # When the code was last executed
    error_message = models.TextField(null=True, blank=True)  # Error logs

    def __str__(self):
        return f"{self.name} - {'Success' if self.status else 'Failure'}"
