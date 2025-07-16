from django.shortcuts import render
# from django.http import HttpResponse
from .models import Brand, Mobile, ProductAccessories, CodeExecutionState, CodeExecutionStateAccessories, BrandAccessories, CategoryAccessories
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
# from django.urls import reverse_lazy
from django.contrib import messages
# from django.core.serializers import serialize
# from urllib.parse import unquote
from django.utils import timezone
from rest_framework.viewsets import  ModelViewSet
from rest_framework.viewsets import ViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
# from django.db.models import Q
from khazesh.serializers import MobileSerilizer
from fuzzywuzzy import fuzz
from datetime import timedelta
import re
from rest_framework.response import Response
from django.db.models import Min, Max



class DalgaStatusViewSet(ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        sites_param = request.query_params.get('sites', '')

        # توکن login_token دیگه نیاز نیست چون احراز هویت با Bearer انجام میشه
        site_names = [s.strip() for s in sites_param.split(',') if s.strip()]
        if not site_names:
            return Response({'error': 'لیست سایت‌ها ارسال نشده'}, status=400)

        one_hour_ago = timezone.now() - timedelta(hours=1)

        recent_updates = CodeExecutionState.objects.filter(
            name__in=site_names,
            last_executed__gte=one_hour_ago
        ).count()

        if recent_updates == 0:
            return Response({'dalga_active': False, 'message': 'دالگا غیرفعال است.'})
        return Response({'dalga_active': True})

class MobileApiView(ModelViewSet):
    queryset = Mobile.objects.all()
    http_method_names = ['get']
    serializer_class = MobileSerilizer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        queryset = super().get_queryset()
        two_days_ago = timezone.now() - timezone.timedelta(minutes=59)

        custom_id = self.request.query_params.get('id', None)
        if not custom_id:
            return queryset.none()

        return queryset.filter(custom_id=custom_id, updated_at__gt=two_days_ago, status=True)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # دریافت لیست سایت‌ها از کوئری
        buy_sites_param = request.query_params.get('buy_sites', '')
        sell_sites_param = request.query_params.get('sell_sites', '')

        # تبدیل به set
        buy_sites = set(s.strip() for s in buy_sites_param.split(',') if s.strip())
        sell_sites = set(s.strip() for s in sell_sites_param.split(',') if s.strip())

        buy_queryset = queryset.filter(site__in=buy_sites)
        sell_queryset = queryset.filter(site__in=sell_sites)

        buy_data = self.serializer_class(buy_queryset, many=True).data
        sell_data = self.serializer_class(sell_queryset, many=True).data

        buy_min = buy_queryset.aggregate(min_price=Min('min_price'))['min_price']
        sell_min = sell_queryset.aggregate(min_price=Min('min_price'))['min_price']

        # پیدا کردن source (سایت) مربوط به min_price
        buy_min_source = None
        sell_min_source = None

        if buy_min is not None:
            buy_min_item = buy_queryset.filter(min_price=buy_min).first()
            if buy_min_item:
                buy_min_source = buy_min_item.site  # یا .source اگر در مدل شما این فیلد باشه

        if sell_min is not None:
            sell_min_item = sell_queryset.filter(min_price=sell_min).first()
            if sell_min_item:
                sell_min_source = sell_min_item.site  # یا .source

        return Response({
            "buy_sites": {
                "items": buy_data,
                "min_price": int(buy_min / 10) if buy_min else None,
                "source": buy_min_source
            },
            "sell_sites": {
                "items": sell_data,
                "min_price": int(sell_min / 10) if sell_min else None,
                "source": sell_min_source
            }
        })
        
        
        
# from django.contrib.admin.views
class MyLoginView(LoginView):
    redirect_authenticated_user = True
    
    # def get_success_url(self):
    #     return reverse_lazy('tasks') 
    
    def form_invalid(self, form):
        messages.error(self.request,'Invalid username or password')
        return self.render_to_response(self.get_context_data(form=form))


def find_not_empty(filed_tuple):
    field_name, field_value = filed_tuple
    if field_value:
        return {field_name: field_value}


@login_required(login_url='/admin/login/')
def search_accessories(request, category):
    brand = BrandAccessories.objects.all()
    categories = CategoryAccessories.objects.all()
    return render(request, 'accessories.html', {'brands': brand, 'categories': categories, 'category_name' : category})


@login_required(login_url='/admin/login/')
def search_mobiles(request):
    all_site_status = CodeExecutionState.objects.all().order_by('-last_executed')
    return render(request, 'index.html', {'site_crashes':all_site_status})


@login_required(login_url='/admin/login/')
def search_tablet(request):
    all_site_status = CodeExecutionState.objects.all().order_by('-last_executed')
    return render(request, 'tablet.html', {'site_crashes':all_site_status})

def site_status(request):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        mobile = CodeExecutionState.objects.order_by('-last_executed').values()
        accessories = CodeExecutionStateAccessories.objects.order_by('-last_executed').values('name', 'last_executed','category__name_fa', 'status')
        return JsonResponse({'mobile': list(mobile), 'accessories': list(accessories)}, safe=False)

    # Handle other HTTP methods or errors
    return JsonResponse({'error': 'Invalid request method'}, status=400)

def ajax_search(request):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        two_days_ago = timezone.now() - timezone.timedelta(days=2, minutes=15)
        typeMobile = True if request.GET.get('type', '') == 'mobile' else False
        # Get query parameters from the AJAX request
        model:str = request.GET.get('model', '').strip()
        # print(model)
        brand = request.GET.get('brand', '')
        # print(brand)
        ram = request.GET.get('ram', '')
        # print(ram)
        memory = request.GET.get('memory', '')
        # print(memory)
        # print(not_active)
        vietnam = request.GET.get('vietnam', '')
        # print(vietnam)
        site = request.GET.get('site', '')
        # print(site)
        not_active = request.GET.get('not_active', '')
        if not_active == 'null':
            not_active = ''

       
        if model.isdigit():
            mobiles = Mobile.objects.filter(
            custom_id__icontains = model,
            updated_at__gt=two_days_ago,  
            mobile=typeMobile,

            ).select_related(brand).values('id', 'model', 'old_min_price', 'not_active', 'color_name',
                                        'seller', 'guarantee', 'ram', 'memory',
                                        'vietnam', 'dual_sim', 'max_price',
                                        'min_price', 'site', 'updated_at', 
                                        'url', 'brand__name',  'color_hex',
                                        'price_change_time', 'title',
                                        "custom_id", "status").order_by('min_price')
            return JsonResponse(list(mobiles), safe=False)
        
        
        else:
            fields = [('brand__name', brand), ('ram', ram),
                    ('memory__icontains', memory), ('not_active', not_active), ('vietnam', vietnam), ('site', site)]

            # crate dynamic fields
            filter_fildes_list = list(filter(None, list(map(find_not_empty, fields))))
            filter_fildes_dict = {k: v for d in filter_fildes_list for k, v in d.items()}
            
            if model:
                filter_fildes_dict['model__iregex'] = rf'\b{model}\b'              
            # filter_filds_dict.update({'model__icontains': model})
            # print(filter_fildes_dict)

            mobiles = Mobile.objects.filter(
                **filter_fildes_dict,
                updated_at__gt=two_days_ago,  
                mobile=typeMobile,     
            ).select_related(brand).values('id', 'model', 'old_min_price', 'not_active', 'color_name',
                                        'seller', 'guarantee', 'ram', 'memory',
                                        'vietnam', 'dual_sim', 'max_price',
                                        'min_price', 'site', 'updated_at', 
                                        'url', 'brand__name',  'color_hex',
                                        'price_change_time', 'title',
                                        "custom_id", "status").order_by('min_price')
            # print(mobiles)

            # Return the JSON response with the filtered mobile data
            return JsonResponse(list(mobiles), safe=False)

    # Handle other HTTP methods or errors
    return JsonResponse({'error': 'Invalid request method'}, status=400)



def accessories_ajax_search(request):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        two_days_ago = timezone.now() - timezone.timedelta(days=2, minutes=15)

        # Get query parameters from the AJAX request
        model:str = request.GET.get('model', '').strip()
        brand = request.GET.get('brand', '')
        category = request.GET.get('category', '')
        site = request.GET.get('site', '')
        


        if model.isdigit():
            accessories = ProductAccessories.objects.filter(
            custom_id__icontains = model,
            updated_at__gt=two_days_ago,

            ).select_related(brand).values('id', 'model', 'old_min_price', 'color_name',
                                        'seller', 'guarantee' 'max_price',
                                        'min_price', 'site', 'updated_at', 
                                        'url', 'brand__name_fa', 'brand__name_en',
                                        'category__name_fa', 'category__name_en',
                                        'color_hex', 'price_change_time', 'title','description', 'fake', 'stock',
                                        "custom_id", "status").order_by('min_price')
            return JsonResponse(list(accessories), safe=False)
        
        
        else:
            fields = [('brand__name_en', brand),('category__name_en', category),('site', site)]

            # crate dynamic fields
            filter_fildes_list = list(filter(None, list(map(find_not_empty, fields))))
            filter_fildes_dict = {k: v for d in filter_fildes_list for k, v in d.items()}
            
            if model:
                filter_fildes_dict['model__iregex'] = rf'\b{model}\b'              
            # filter_filds_dict.update({'model__icontains': model})
            # print(filter_fildes_dict)

            accessories = ProductAccessories.objects.filter(
                **filter_fildes_dict,
                updated_at__gt=two_days_ago,       
            ).select_related(brand).values('id', 'model', 'old_min_price', 'color_name',
                                        'seller', 'guarantee', 'max_price',
                                        'min_price', 'site', 'updated_at', 
                                        'url', 'brand__name_fa', 'brand__name_en',
                                        'category__name_fa', 'category__name_en',  'color_hex',
                                        'price_change_time', 'title','description', 'fake', 'stock',
                                        "custom_id", "status").order_by('min_price')


            # Return the JSON response with the filtered mobile data
            return JsonResponse(list(accessories), safe=False)

    # Handle other HTTP methods or errors
    return JsonResponse({'error': 'Invalid request method'}, status=400)


def set_custom_accessories_id(request):


    if request.method== 'GET':

        custom_id = request.GET.get('custom_id', '')
        model_id = request.GET.get('id', '')
        accessories = ProductAccessories.objects.filter(id=model_id)
        len_accessories = len(accessories)

        if len_accessories > 1 or len_accessories == 0:
            return JsonResponse({"Response": "Faild", "reason": "مشکل در سرور"})
        
        try:
            accessories = accessories.first()
            accessories.custom_id = custom_id
            accessories.save()
            return JsonResponse({"Response": 'success'}, status=203)
        except Exception as e:
            return JsonResponse({"Response": "Faild", "reason": "مشکل در ذخیره ابجکت"})
            

    
    return JsonResponse({'Response': 'Faild', "reason": f"{request.method}"})

def set_custom_mobile_id(request):

    # print('###', request.headers.get('x-requested-with'))
    # print(request.method)
    if request.method== 'GET':
        # title = unquote(request.GET.get('title', ''), encoding='utf-8')
        # memory = request.GET.get('memory', '')
        # ram = request.GET.get('ram', '')
        # color_name = unquote(request.GET.get('color_name', ''))
        # site = unquote(request.GET.get('site', ''))
        # seller = unquote(request.GET.get('seller', ''))
        # guarantee = unquote(request.GET.get('guarantee', ''))
        custom_id = request.GET.get('custom_id', '')
        model_id = request.GET.get('id', '')
        
        # filters = {'title__icontains': title,
        #           'color_name': color_name,
        #           'site': site,
        #           'seller__icontains': seller,
       
        #         }
        
        # if ram:
        #     filters['ram'] = ram
        # if memory:
        #     filters['memory'] = memory
            
        # print(request.GET)
        # print('color_name', color_name)
        # print(filters)
        
        # mobile = Mobile.objects.filter(**filters)
        mobile = Mobile.objects.filter(id=model_id)
        len_mobile = len(mobile)
        # print('len_mobile', len_mobile)
        # print(mobile)
        if len_mobile > 1 or len_mobile == 0:
            return JsonResponse({"Response": "Faild", "reason": "مشکل در سرور"})
        
        try:
            mobile = mobile.first()
            mobile.custom_id = custom_id
            mobile.save()
            return JsonResponse({"Response": 'success'}, status=203)
        except Exception as e:
            return JsonResponse({"Response": "Faild", "reason": "مشکل در ذخیره ابجکت"})
            
        # serialized_mobile = serialize('json', mobile)
        
        # print(serialized_mobile)
        
        # return JsonResponse({"Response": "success"}, safe=False)
    
    return JsonResponse({'Response': 'Faild', "reason": f"{request.method}"})


def search_mobiles_without_custom_id(request):

    return render(request, 'set_auto_custom_id.html')


def set_auto_custom_id_page(request):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        two_days_ago = timezone.now() - timezone.timedelta(days=2, minutes=15)

        # Get query parameters from the AJAX request
        model:str = request.GET.get('model', '').strip()
        brand = request.GET.get('brand', '')
        ram = request.GET.get('ram', '')
        memory = request.GET.get('memory', '')
        vietnam = request.GET.get('vietnam', '')
        site = request.GET.get('site', '')
        not_active = request.GET.get('not_active', '')
        if not_active == 'null':
            not_active = ''

    
        fields = [('brand__name', brand), ('ram', ram),
                ('memory__icontains', memory), ('not_active', not_active), ('vietnam', vietnam), ('site', site)]

        # crate dynamic fields
        filter_fildes_list = list(filter(None, list(map(find_not_empty, fields))))
        filter_fildes_dict = {k: v for d in filter_fildes_list for k, v in d.items()}
        # filter_fildes_dict.update({'model__icontains': model})
        # print(filter_fildes_dict)

        if model:
            filter_fildes_dict['model__iregex'] = rf"\b{model}\b"
        mobiles = Mobile.objects.filter(
            **filter_fildes_dict,
            # updated_at__gt=two_days_ago,   
            custom_id__isnull=True,   
  
        ).select_related(brand).values('id', 'model', 'old_min_price', 'not_active', 'color_name',
                                    'seller', 'guarantee', 'ram', 'memory',
                                    'vietnam', 'dual_sim', 'max_price',
                                    'min_price', 'site', 'updated_at', 
                                    'url', 'brand__name',  'color_hex',
                                    'price_change_time', 'title',
                                    "custom_id").order_by('min_price')
        # print(mobiles)

        # Return the JSON response with the filtered mobile data
        return JsonResponse(list(mobiles), safe=False)

    # Handle other HTTP methods or errors
    return JsonResponse({'error': 'Invalid request method'}, status=400)


MOBOMIN_CROWLED_BRANDS = ['samsung', 'xiaomi', 'nokia','honor', 'poco']


def remove_brand_from_start(model: str, brands: list) -> str:
    # Create a regex pattern to match any of the brands at the start, ignoring case
    
    pattern = r'^(' + '|'.join(map(re.escape, brands)) + r')\s*'
    # Replace the matched brand with an empty string
    return re.sub(pattern, '', model, flags=re.IGNORECASE)

def get_similar_mobiles(request):
    if request.method == 'GET':
        two_days_ago = timezone.now() - timezone.timedelta(days=2, minutes=15)
        # Get query parameters from the AJAX request
        model:str = request.GET.get('model', '').strip()
        model = remove_brand_from_start(model, MOBOMIN_CROWLED_BRANDS)
        brand = request.GET.get('brand', '')
        ram = request.GET.get('ram', '')
        memory = request.GET.get('memory', '')
        vietnam = request.GET.get('vietnam', '')
        print('vietnam', vietnam)
        mobile_id = request.GET.get('id', '')
        not_active = request.GET.get('not_active', '')
        if not_active == 'null':
            not_active = ''

        
    
        fields = [('brand__name', brand), ('ram', ram),
                ('memory__icontains', memory), ('vietnam', vietnam), ('not_active', not_active)]

        # crate dynamic fields
        filter_fildes_list = list(filter(None, list(map(find_not_empty, fields))))
        filter_fildes_dict = {k: v for d in filter_fildes_list for k, v in d.items()}
        # filter_fildes_dict.update({'model__icontains': model})
        # print(filter_fildes_dict)

        # print('filter_fildes_dict', filter_fildes_dict)
        mobiles = Mobile.objects.filter(
            **filter_fildes_dict,
            # updated_at__gt=two_days_ago,   
            custom_id__isnull=False,   
        )\
        .exclude(id=int(mobile_id))\
        .exclude(custom_id='')\
        .select_related(brand).values('id', 'model', 'old_min_price', 'not_active', 'color_name',
                                    'seller', 'guarantee', 'ram', 'memory',
                                    'vietnam', 'dual_sim', 'max_price',
                                    'min_price', 'site', 'updated_at', 
                                    'url', 'brand__name', 'color_hex',
                                    'price_change_time', 'title',
                                    "custom_id").order_by('min_price')
        
        similar_mobiles= []
        # mobiles = filter(lambda mobile: mobile.get('id', '') != int(mobile_id), mobiles)
        for mobile in mobiles:
            cleaned_model = remove_brand_from_start(mobile.get('model', ''), MOBOMIN_CROWLED_BRANDS)
            # print(mobile.get('model', ''))
            # print(cleaned_model)
            # print(model)
            ratio = fuzz.WRatio(model, cleaned_model)
            # print(ratio)
            if ratio >= 50:
                similar_mobiles.append(mobile)
        
        # print(similar_mobiles)
        # print(len(similar_mobiles))
        # print(list(mobiles))
        # print(len(list(mobiles)))

        # print(list(mobiles))           
        return JsonResponse(similar_mobiles, safe=False)

    # Handle other HTTP methods or errors
    return JsonResponse({'error': 'Invalid request method'}, status=400)

        