from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from management import views
from django.urls import path, include
 

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard, name='dashboard'),
    path('search/', views.global_search, name='global_search'),
    path('company/', views.company_profile, name='company_profile'),
    path('category/<int:category_id>/', views.category_detail, name='category_detail'),
    path('subcategory/<int:subcategory_id>/', views.subcategory_detail, name='subcategory_detail'),
    path('document/<int:document_id>/delete/', views.delete_document, name='delete_document'),
    path('document/<int:document_id>/edit/', views.edit_document, name='edit_document'),
    path('history/', views.history_log, name='history_log'),
    path('settings/', views.settings_page, name='settings'),
    path('add_user/', views.add_user, name='add_user'),
    path('delete_user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('settings/category/add/', views.add_category, name='add_category'),
    path('settings/subcategory/add/', views.add_subcategory, name='add_subcategory'),
    path('settings/category/<int:category_id>/edit/', views.edit_category, name='edit_category'),
    path('settings/category/<int:category_id>/delete/', views.delete_category, name='delete_category'),
    path('settings/subcategory/<int:subcategory_id>/edit/', views.edit_subcategory, name='edit_subcategory'),
    path('settings/subcategory/<int:subcategory_id>/delete/', views.delete_subcategory, name='delete_subcategory'),
    path('settings/subcategory/<int:subcategory_id>/fields/', views.manage_fields, name='manage_fields'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('logout/', views.custom_logout, name='custom_logout'),
    path('admin_unlock/', views.admin_unlock, name='admin_unlock'),
    path('change_avatar/', views.change_avatar, name='change_avatar'),
    path('reset_password/', views.reset_password, name='reset_password'),
    path('change_avatar/', views.change_avatar, name='change_avatar'),
    path('reset_password/', views.reset_password, name='reset_password'),
    path('save_theme/', views.save_theme, name='save_theme'),
    path('update_alerts/', views.update_alerts, name='update_alerts'),
    path('filtered/<str:filter_type>/', views.filtered_documents, name='filtered_documents'),
    path('setup/admin/', views.setup_admin, name='setup_admin'),
    path('setup/company/', views.setup_company, name='setup_company'),
    path('settings/backup/', views.download_backup, name='download_backup'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)