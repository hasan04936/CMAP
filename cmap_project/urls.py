from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from management import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard, name='dashboard'),
    path('category/<int:category_id>/', views.category_detail, name='category_detail'),
    path('subcategory/<int:subcategory_id>/', views.subcategory_detail, name='subcategory_detail'),
    path('document/<int:document_id>/delete/', views.delete_document, name='delete_document'),
    path('document/<int:document_id>/edit/', views.edit_document, name='edit_document'),
    path('history/', views.history_log, name='history_log'),
    path('settings/', views.settings_page, name='settings'),
    path('settings/category/add/', views.add_category, name='add_category'),
    path('settings/subcategory/add/', views.add_subcategory, name='add_subcategory'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)