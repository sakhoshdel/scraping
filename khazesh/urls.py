from django.urls import path
from .views import (search_mobiles,
                    ajax_search,
                    set_custom_mobile_id,
                    search_mobiles_without_custom_id,
                    set_auto_custom_id_page,
                    get_similar_mobiles)
from django.conf import settings
from django.conf.urls.static import static
# from .views import MyLoginView
# from django.contrib.auth.views import LoginView
from rest_framework import routers
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import MobileApiView
router = routers.DefaultRouter()

router.register('api/mobiles', MobileApiView, basename='mobile_api')




urlpatterns = [
    # path('', MyLoginView.as_view(), name="login"),
    # path('', LoginView.as_view(), name="login"),
    path('api/jwt_token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/jwt_token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', search_mobiles, name="serch_page"),
    path('ajax_search/', ajax_search, name="ajax_search"),
    path('set_custom_mobile_id/', set_custom_mobile_id, name="set_custom_mobile_id"),
    path('search_custom/', search_mobiles_without_custom_id, name="search_custom"),
    path('set_auto_custom_id/', set_auto_custom_id_page, name="set_auto_custom_id"),
    path('get_similar_mobiles/', get_similar_mobiles, name="get_similar_mobiles"),
    
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

urlpatterns += router.urls