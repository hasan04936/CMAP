from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, authenticate, login, update_session_auth_hash
from django.contrib.auth.models import User
from django.db.models import Q
from django.conf import settings
from django.http import HttpResponse, Http404
from django.core.management import call_command
from django.contrib import messages
import io

from .models import Company, Category, SubCategory, Document, CustomField, CustomFieldValue, UserProfile, HistoryLog
from .utils import send_telegram_alert

# ====================================================================
# SMART EXTRACTOR: Finds the "Name" from dynamic custom fields
# ====================================================================
def get_doc_name(document):
    # Try to find a field that specifically has "name" in the title
    name_val = CustomFieldValue.objects.filter(
        document=document,
        custom_field__field_type__in=['text', 'email'],
        custom_field__field_name__icontains='name'
    ).exclude(value='').first()
    
    if name_val: return name_val.value
    
    # If no "name" field exists, just grab the very first text answer they typed
    first_val = CustomFieldValue.objects.filter(
        document=document,
        custom_field__field_type__in=['text', 'email', 'number']
    ).exclude(value='').first()
    
    if first_val: return first_val.value
    return "Unnamed Entry"
# ====================================================================

@login_required
def dashboard(request):
    company, _ = Company.objects.get_or_create(id=1)
    categories = Category.objects.all()

    today = timezone.now().date()
    today_str = today.strftime('%Y-%m-%d')
    
    # 1. RECENT UPDATES (Based on custom timer)
    recent_date = today - timedelta(days=company.recent_update_days)
    recent_updates_count = Document.objects.filter(uploaded_date__date__gte=recent_date).count()

    # 2. EXPIRE SOON (Based on custom timer)
    future_str = (today + timedelta(days=company.expire_alert_days)).strftime('%Y-%m-%d')
    expire_soon_count = Document.objects.filter(
        custom_values__custom_field__field_type='date',
        custom_values__value__lte=future_str,
        custom_values__value__gte=today_str,
        custom_values__custom_field__field_name__icontains='expire' # Only look at fields with 'expire' in the name!
    ).distinct().count()
    
    # 3. ALREADY EXPIRED
    expired_count = Document.objects.filter(
        custom_values__custom_field__field_type='date',
        custom_values__value__lt=today_str,
        custom_values__custom_field__field_name__icontains='expire'
    ).distinct().count()
    
    context = {
        'company': company,
        'categories': categories,
        'updated_today': recent_updates_count,
        'expire_soon': expire_soon_count,
        'expired': expired_count,
    }
    return render(request, 'management/dashboard.html', context)

@login_required
def category_detail(request, category_id):
    company = Company.objects.first()
    category = get_object_or_404(Category, id=category_id)
    subcategories = category.subcategories.all()
    
    context = {
        'company': company,
        'category': category,
        'subcategories': subcategories,
    }
    return render(request, 'management/category_detail.html', context)

@login_required
def subcategory_detail(request, subcategory_id):
    company = Company.objects.first()
    subcategory = get_object_or_404(SubCategory, id=subcategory_id)
    
    # 1. POST: Handle Form Submissions
    if request.method == 'POST':
        dynamic_title = f"{subcategory.name} Entry - {timezone.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Step A: Create the base Document
        doc = Document.objects.create(
            title=dynamic_title,
            category=subcategory.category,
            sub_category=subcategory,
        )
        
        # Step B: Loop through and save all Custom Fields dynamically
        for field in subcategory.custom_fields.all():
            input_name = f"custom_{field.id}" 
            
            if field.field_type == 'file':
                file_val = request.FILES.get(input_name)
                if file_val:
                    CustomFieldValue.objects.create(document=doc, custom_field=field, file_value=file_val)
            else:
                text_val = request.POST.get(input_name)
                if text_val:
                    CustomFieldValue.objects.create(document=doc, custom_field=field, value=text_val)
                    
        # Grab the human-readable name!
        display_name = get_doc_name(doc)
        
        # --- THE TRACKER: HUMAN READABLE UPLOAD ---
        HistoryLog.objects.create(
            user=request.user, 
            action="Created", 
            document_name=display_name, 
            folder_path=f"{subcategory.category.name} > {subcategory.name}"
        )
        
        # --- TELEGRAM TRIGGER: HUMAN READABLE UPLOAD ---
        alert_msg = (
            f"🟢 <b>NEW RECORD ADDED</b>\n\n"
            f"👤 <b>{request.user.username.upper()}</b> added a new <b>{subcategory.name}</b> "
            f"into the <b>{subcategory.category.name}</b> folder for <b>{display_name}</b>."
        )
        send_telegram_alert(alert_msg)
        # ------------------------------------

        messages.success(request, 'Entry Saved Successfully!')
        return redirect('subcategory_detail', subcategory_id=subcategory.id)

    # 2. GET: Display the Page
    documents = Document.objects.filter(sub_category=subcategory).order_by('-id')
    context = {
        'company': company,
        'subcategory': subcategory,
        'documents': documents,
        'custom_fields': subcategory.custom_fields.all(), 
    }
    return render(request, 'management/subcategory_detail.html', context)

@login_required
def delete_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    subcategory_id = document.sub_category.id
    
    if request.method == 'POST':
        # Grab the human-readable name before deleting
        display_name = get_doc_name(document)
        
        # --- THE TRACKER: HUMAN READABLE DELETION ---
        HistoryLog.objects.create(
            user=request.user, 
            action="Deleted", 
            document_name=display_name, 
            folder_path=f"{document.sub_category.category.name} > {document.sub_category.name}"
        )
        
        # --- TELEGRAM TRIGGER: HUMAN READABLE DELETION ---
        alert_msg = (
            f"🗑️ <b>RECORD DELETED</b>\n\n"
            f"👤 <b>{request.user.username.upper()}</b> deleted the <b>{document.sub_category.name}</b> "
            f"from the <b>{document.sub_category.category.name}</b> folder of <b>{display_name}</b>."
        )
        send_telegram_alert(alert_msg)
        # ----------------------------------
        
        document.delete()
        messages.success(request, 'Entry Deleted Successfully!')
        
    return redirect('subcategory_detail', subcategory_id=subcategory_id)

@login_required
def edit_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    subcategory = document.sub_category
    
    if request.method == 'POST':
        for field in subcategory.custom_fields.all():
            input_name = f"custom_{field.id}"
            custom_val, created = CustomFieldValue.objects.get_or_create(document=document, custom_field=field)
            
            if field.field_type == 'file':
                file_val = request.FILES.get(input_name)
                if file_val:
                    custom_val.file_value = file_val
                    custom_val.save()
            else:
                text_val = request.POST.get(input_name)
                if text_val is not None:
                    custom_val.value = text_val
                    custom_val.save()
                    
        document.save()
        
        # Grab the updated human-readable name!
        display_name = get_doc_name(document)
        
        # --- THE TRACKER: HUMAN READABLE EDIT ---
        HistoryLog.objects.create(
            user=request.user, 
            action="Edited", 
            document_name=display_name, 
            folder_path=f"{subcategory.category.name} > {subcategory.name}"
        )
        
        # --- TELEGRAM TRIGGER: HUMAN READABLE EDIT ---
        alert_msg = (
            f"✏️ <b>RECORD UPDATED</b>\n\n"
            f"👤 <b>{request.user.username.upper()}</b> updated the <b>{subcategory.name}</b> "
            f"in the <b>{subcategory.category.name}</b> folder for <b>{display_name}</b>."
        )
        send_telegram_alert(alert_msg)
        # ------------------------------
        
        messages.success(request, 'Entry Updated Successfully!')
        
    return redirect('subcategory_detail', subcategory_id=subcategory.id)

@login_required
def history_log(request):
    logs = HistoryLog.objects.all().order_by('-timestamp')
    context = {
        'logs': logs,
    }
    return render(request, 'management/history.html', context)

@login_required
def settings_page(request):
    if not (request.user.is_superuser or request.session.get('admin_unlocked', False)):
        return redirect('dashboard')
    
    company = Company.objects.first()
    categories = Category.objects.all()
    users = User.objects.all()
    
    context = {
        'company': company,
        'categories': categories,
        'users': users,
    }
    return render(request, 'management/settings.html', context)

@login_required
def add_category(request):
    if request.method == 'POST':
        name = request.POST.get('category_name')
        if name:
            Category.objects.create(name=name)
            messages.success(request, 'Main Folder Created!')
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

@login_required
def add_subcategory(request):
    if request.method == 'POST':
        name = request.POST.get('subcategory_name')
        category_id = request.POST.get('category_id')
        if name and category_id:
            category = get_object_or_404(Category, id=category_id)
            SubCategory.objects.create(name=name, category=category)
            messages.success(request, 'Sub-Folder Created!')
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

@login_required
def edit_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        name = request.POST.get('category_name')
        if name:
            old_name = category.name
            category.name = name
            category.save()
            
            HistoryLog.objects.create(
                user=request.user, 
                action="Edited", 
                document_name=f"Folder: {old_name} -> {name}", 
                folder_path="Settings > Architecture"
            )
            messages.success(request, 'Folder Renamed!')
            
    return redirect('settings')

@login_required
def delete_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        cat_name = category.name
        
        HistoryLog.objects.create(
            user=request.user, 
            action="Deleted", 
            document_name=f"Main Folder: {cat_name}", 
            folder_path="Settings > Architecture"
        )
        category.delete()
        messages.success(request, 'Folder Deleted!')
    return redirect('settings')

@login_required
def edit_subcategory(request, subcategory_id):
    subcategory = get_object_or_404(SubCategory, id=subcategory_id)
    if request.method == 'POST':
        name = request.POST.get('subcategory_name')
        if name:
            old_name = subcategory.name
            subcategory.name = name
            subcategory.save()
            
            HistoryLog.objects.create(
                user=request.user, 
                action="Edited", 
                document_name=f"Sub-Folder: {old_name} -> {name}", 
                folder_path=f"Settings > Architecture > {subcategory.category.name}"
            )
            messages.success(request, 'Sub-Folder Renamed!')
            
    return redirect('settings')

@login_required
def delete_subcategory(request, subcategory_id):
    subcategory = get_object_or_404(SubCategory, id=subcategory_id)
    if request.method == 'POST':
        sub_name = subcategory.name
        cat_name = subcategory.category.name
        
        HistoryLog.objects.create(
            user=request.user, 
            action="Deleted", 
            document_name=f"Sub-Folder: {sub_name}", 
            folder_path=f"Settings > Architecture > {cat_name}"
        )
        subcategory.delete()
        messages.success(request, 'Sub-Folder Deleted!')
    return redirect('settings')

@login_required
def manage_fields(request, subcategory_id):
    subcategory = get_object_or_404(SubCategory, id=subcategory_id)
    
    if request.method == 'POST':
        if 'add_field' in request.POST:
            field_name = request.POST.get('field_name')
            field_type = request.POST.get('field_type')
            is_required = request.POST.get('is_required') == 'on' 
            show_on_card = request.POST.get('show_on_card') == 'on' 
            
            if field_name:
                CustomField.objects.create(
                    sub_category=subcategory,
                    field_name=field_name,
                    field_type=field_type,
                    is_required=is_required,
                    show_on_card=show_on_card 
                )
                
        elif 'delete_field' in request.POST:
            field_id = request.POST.get('field_id')
            field_to_delete = CustomField.objects.filter(id=field_id).first()
            if field_to_delete:
                field_name = field_to_delete.field_name
                
                HistoryLog.objects.create(
                    user=request.user, 
                    action="Deleted", 
                    document_name=f"Database Field: {field_name}", 
                    folder_path=f"Settings > Field Builder > {subcategory.name}"
                )
                field_to_delete.delete()
            
        return redirect('manage_fields', subcategory_id=subcategory.id)

    context = {
        'subcategory': subcategory,
        'fields': subcategory.custom_fields.all() 
    }
    return render(request, 'management/manage_fields.html', context)

def custom_logout(request):
    logout(request)
    return redirect('login')

@login_required
def company_profile(request):
    if not (request.user.is_superuser or request.session.get('admin_unlocked', False)):
        return redirect('dashboard') 
        
    company, created = Company.objects.get_or_create(id=1)

    if request.method == 'POST':
        company.name = request.POST.get('company_name')
        company.contact_number = request.POST.get('contact_number')
        company.email_address = request.POST.get('email_address')
        company.country = request.POST.get('country')
        company.district = request.POST.get('district')
        company.tax_number = request.POST.get('tax_number')
        company.cr_number = request.POST.get('cr_number')
        company.license_number = request.POST.get('license_number')
        
        if request.FILES.get('company_logo'):
            company.logo = request.FILES.get('company_logo')
            
        company.save()
        
        HistoryLog.objects.create(
            user=request.user, 
            action="Edited", 
            document_name="Company Details", 
            folder_path="System > Company Profile"
        )
        
        # --- TELEGRAM TRIGGER: COMPANY UPDATE ---
        alert_msg = f"🏢 <b>COMPANY PROFILE UPDATED</b>\n\n👤 <b>{request.user.username.upper()}</b> updated the core company settings and licenses."
        send_telegram_alert(alert_msg)
        # ----------------------------------------
        
        messages.success(request, 'Company Profile Updated!')
        return redirect('company_profile')

    return render(request, 'management/company_profile.html', {'company': company})

@login_required
def global_search(request):
    query = request.GET.get('q', '')
    results = []
    
    if query:
        results = Document.objects.filter(
            Q(title__icontains=query) |
            Q(custom_values__value__icontains=query)
        ).distinct().order_by('-id')
        
    context = {
        'query': query,
        'results': results,
    }
    return render(request, 'management/search_results.html', context)

@login_required
def add_user(request):
    if request.method == 'POST':
        new_username = request.POST.get('username')
        new_password = request.POST.get('password')
        role = request.POST.get('role') 
        
        if new_username and new_password and not User.objects.filter(username=new_username).exists():
            user = User.objects.create_user(username=new_username, password=new_password)
            
            if role == 'admin':
                user.is_superuser = True
                user.is_staff = True
                user.save()
            
            HistoryLog.objects.create(
                user=request.user, 
                action="Created", 
                document_name=f"New User: {new_username}", 
                folder_path="Settings > Accounts"
            )
            
            # --- TELEGRAM TRIGGER: NEW USER ---
            alert_msg = (
                f"👤 <b>NEW SYSTEM USER CREATED</b>\n\n"
                f"👤 <b>{request.user.username.upper()}</b> granted system access to a new user.\n\n"
                f"<b>Username:</b> {new_username}\n"
                f"<b>Role Level:</b> {role.upper()}"
            )
            send_telegram_alert(alert_msg)
            # ----------------------------------
            
            messages.success(request, 'New User Added Successfully!')
                
    return redirect('settings')

@login_required
def delete_user(request, user_id):
    user_to_delete = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST' and user_to_delete != request.user:
        deleted_username = user_to_delete.username
        
        HistoryLog.objects.create(
            user=request.user, 
            action="Deleted", 
            document_name=f"User Account: {deleted_username}", 
            folder_path="Settings > System Users"
        )
        
        # --- TELEGRAM TRIGGER: USER DELETED ---
        alert_msg = f"🚫 <b>USER ACCOUNT DELETED</b>\n\n👤 <b>{request.user.username.upper()}</b> permanently revoked access and deleted the account for <b>{deleted_username}</b>."
        send_telegram_alert(alert_msg)
        # --------------------------------------
        
        user_to_delete.delete()
        messages.success(request, 'User Deleted Successfully!')
        
    return redirect('settings')

@login_required
def admin_unlock(request):
    if request.method == 'POST':
        admin_user = request.POST.get('admin_username')
        admin_pass = request.POST.get('admin_password')
        next_url = request.POST.get('next_url', 'dashboard') 
        
        user = authenticate(request, username=admin_user, password=admin_pass)
        if user is not None and user.is_superuser:
            request.session['admin_unlocked'] = True
            messages.success(request, 'Admin Override Engaged 🔓')
            return redirect(next_url)
            
    return redirect('dashboard')

@login_required
def change_avatar(request):
    if request.method == 'POST':
        avatar_file = request.FILES.get('avatar')
        if avatar_file:
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            profile.avatar = avatar_file
            profile.save()

            HistoryLog.objects.create(
                user=request.user, 
                action="Edited", 
                document_name="Profile Avatar", 
                folder_path="Settings > My User Profile"
            )
            messages.success(request, 'Avatar Updated Successfully!')

    return redirect('settings')

@login_required
def reset_password(request):
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if new_password and new_password == confirm_password:
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user) 
            
            HistoryLog.objects.create(
                user=request.user, 
                action="Edited", 
                document_name="Account Password", 
                folder_path="Settings > My User Profile"
            )
            messages.success(request, 'Password Reset Successfully!')
            
    return redirect('settings')

@login_required
def save_theme(request):
    if request.method == 'POST':
        theme = request.POST.get('theme', 'default')
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.theme = theme
        profile.save()
    return redirect(request.META.get('HTTP_REFERER', 'settings'))

@login_required
def update_alerts(request):
    if request.method == 'POST':
        company, _ = Company.objects.get_or_create(id=1)
        company.expire_alert_days = request.POST.get('expire_days', 30)
        company.recent_update_days = request.POST.get('recent_days', 7)
        company.auto_logout_minutes = request.POST.get('logout_minutes', 30)
        company.save()

        HistoryLog.objects.create(user=request.user, action="Edited", document_name="Tracking Timers", folder_path="Settings")
        messages.success(request, "System Timers & Alerts saved successfully! 💾")
        
    return redirect('settings')

@login_required
def filtered_documents(request, filter_type):
    company, _ = Company.objects.get_or_create(id=1)
    today = timezone.now().date()
    today_str = today.strftime('%Y-%m-%d')
    
    results = []
    title = ""
    
    if filter_type == 'recent':
        recent_date = today - timedelta(days=company.recent_update_days)
        results = Document.objects.filter(uploaded_date__date__gte=recent_date).order_by('-uploaded_date')
        title = f"Recent Updates (Last {company.recent_update_days} Days)"
        
    elif filter_type == 'expire_soon':
        future_str = (today + timedelta(days=company.expire_alert_days)).strftime('%Y-%m-%d')
        results = Document.objects.filter(
            custom_values__custom_field__field_type='date',
            custom_values__value__lte=future_str,
            custom_values__value__gte=today_str,
            custom_values__custom_field__field_name__icontains='expire'
        ).distinct()
        title = f"Expiring Soon (Next {company.expire_alert_days} Days)"
        
    elif filter_type == 'expired':
        results = Document.objects.filter(
            custom_values__custom_field__field_type='date',
            custom_values__value__lt=today_str,
            custom_values__custom_field__field_name__icontains='expire'
        ).distinct()
        title = "Expired Documents"

    return render(request, 'management/filtered_documents.html', {'results': results, 'title': title})

def setup_admin(request):
    if User.objects.filter(is_superuser=True).exists():
        return redirect('login')

    if request.method == 'POST':
        admin_user = request.POST.get('username')
        admin_pass = request.POST.get('password')
        
        if admin_user and admin_pass:
            user = User.objects.create_user(username=admin_user, password=admin_pass)
            user.is_superuser = True
            user.is_staff = True
            user.save()
            
            login(request, user)
            return redirect('setup_company')
            
    return render(request, 'management/setup_admin.html')

@login_required
def setup_company(request):
    if Company.objects.exists():
        return redirect('dashboard')

    if request.method == 'POST':
        name = request.POST.get('company_name')
        if name:
            company = Company.objects.create(name=name)
            
            company.email_address = request.POST.get('email_address', '')
            company.contact_number = request.POST.get('contact_number', '')
            company.country = request.POST.get('country', '')
            
            if request.FILES.get('company_logo'):
                company.logo = request.FILES.get('company_logo')
                
            company.save()
            
            HistoryLog.objects.create(user=request.user, action="Created", document_name="System Initialization", folder_path="Core Server")
            return redirect('dashboard')
            
    return render(request, 'management/setup_company.html')

@login_required
def download_backup(request):
    if not request.user.is_superuser:
        raise Http404("Only administrators can download backups.")
        
    try:
        backup_data = io.StringIO()
        call_command('dumpdata', stdout=backup_data)
        
        response = HttpResponse(backup_data.getvalue(), content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename="cmap_database_backup.json"'
        
        try:
            from .models import HistoryLog
            HistoryLog.objects.create(
                user=request.user, 
                action="Created", 
                document_name="PostgreSQL Database Backup", 
                folder_path="Core Server"
            )
            # --- TELEGRAM TRIGGER: BACKUP ---
            send_telegram_alert(f"💾 <b>DATABASE BACKUP INITIATED</b>\n\n👤 <b>{request.user.username.upper()}</b> successfully downloaded a copy of the core PostgreSQL database.")
        except Exception:
            pass 
            
        return response
        
    except Exception as e:
        raise Http404(f"Critical Error generating backup: {str(e)}")