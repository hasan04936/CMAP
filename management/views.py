from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from datetime import timedelta
from .models import Company, Category, SubCategory, Document, CustomField, CustomFieldValue
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.auth import authenticate

@login_required
def dashboard(request):
    company = Company.objects.first()
    categories = Category.objects.all()

    # 1. SMART BADGE: Count documents uploaded today
    today = timezone.now().date()
    updated_today_count = Document.objects.filter(uploaded_date__date=today).count()

    # 2. SMART BADGE: Count Dynamic Expiry Dates within 30 days!
    today_str = today.strftime('%Y-%m-%d')
    thirty_days_str = (today + timedelta(days=30)).strftime('%Y-%m-%d')
    
    expire_soon_count = Document.objects.filter(
        custom_values__custom_field__field_type='date',
        custom_values__value__lte=thirty_days_str,
        custom_values__value__gte=today_str
    ).distinct().count()
    
    context = {
        'company': company,
        'categories': categories,
        'updated_today': updated_today_count,
        'expire_soon': expire_soon_count,
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
        # Generate a dynamic title since we removed the input field
        dynamic_title = f"{subcategory.name} Entry - {timezone.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Step A: Create the base Document (No file required initially)
        doc = Document.objects.create(
            title=dynamic_title,
            category=subcategory.category,
            sub_category=subcategory,
        )
        
        # Step B: Loop through and save all Custom Fields dynamically!
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
        document.delete()
        
    return redirect('subcategory_detail', subcategory_id=subcategory_id)

@login_required
def edit_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    subcategory = document.sub_category
    
    if request.method == 'POST':
        # Loop through all dynamic fields and update their specific values
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
    return redirect('subcategory_detail', subcategory_id=subcategory.id)

@login_required
def history_log(request):
    company = Company.objects.first()
    # Grab all documents, ordered by the most recently updated first
    recent_updates = Document.objects.all().order_by('-updated_date')
    
    context = {
        'company': company,
        'recent_updates': recent_updates,
    }
    return render(request, 'management/history.html', context)

@login_required
def settings_page(request):

    # ADD THIS TO THE TOP OF settings_page AND company_profile
    if not (request.user.is_superuser or request.session.get('admin_unlocked', False)):
        return redirect('dashboard') # Kicks them out if they try to hack the URL!
    categories = Category.objects.all()
    # Grab all users registered in the system
    users = User.objects.all()
    
    context = {
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
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

@login_required
def add_subcategory(request):
    if request.method == 'POST':
        name = request.POST.get('subcategory_name')
        category_id = request.POST.get('category_id')
        if name and category_id:
            category = get_object_or_404(Category, id=category_id)
            SubCategory.objects.create(name=name, category=category)
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

@login_required
def edit_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        name = request.POST.get('category_name')
        if name:
            category.name = name
            category.save()
    return redirect('settings')

@login_required
def delete_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        category.delete()
    return redirect('settings')

@login_required
def edit_subcategory(request, subcategory_id):
    subcategory = get_object_or_404(SubCategory, id=subcategory_id)
    if request.method == 'POST':
        name = request.POST.get('subcategory_name')
        if name:
            subcategory.name = name
            subcategory.save()
    return redirect('settings')

@login_required
def delete_subcategory(request, subcategory_id):
    subcategory = get_object_or_404(SubCategory, id=subcategory_id)
    if request.method == 'POST':
        subcategory.delete()
    return redirect('settings')

@login_required
def manage_fields(request, subcategory_id):
    # Get the specific sub-folder we are building fields for
    subcategory = get_object_or_404(SubCategory, id=subcategory_id)
    
    if request.method == 'POST':
        # Check if we are ADDING a field
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
                
        # Check if we are DELETING a field
        elif 'delete_field' in request.POST:
            field_id = request.POST.get('field_id')
            CustomField.objects.filter(id=field_id).delete()
            
        return redirect('manage_fields', subcategory_id=subcategory.id)

    context = {
        'subcategory': subcategory,
        'fields': subcategory.custom_fields.all() 
    }
    return render(request, 'management/manage_fields.html', context)

# NEW SECURE LOGOUT FUNCTION
def custom_logout(request):
    logout(request)
    return redirect('login')

@login_required
def company_profile(request):
    # ADD THIS TO THE TOP OF settings_page AND company_profile
    if not (request.user.is_superuser or request.session.get('admin_unlocked', False)):
        return redirect('dashboard') # Kicks them out if they try to hack the URL!
    # Get or create the company profile so it never crashes
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
        return redirect('company_profile')

    return render(request, 'management/company_profile.html', {'company': company})

@login_required
def global_search(request):
    query = request.GET.get('q', '')
    results = []
    
    if query:
        # MAGIC SEARCH: Looks at the Title OR ANY custom field answer!
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
        role = request.POST.get('role') # 'admin' or 'staff'
        
        # Make sure the username doesn't already exist to prevent crashes
        if new_username and new_password and not User.objects.filter(username=new_username).exists():
            # Create the user securely
            user = User.objects.create_user(username=new_username, password=new_password)
            
            # If they selected Admin, give them superuser powers
            if role == 'admin':
                user.is_superuser = True
                user.is_staff = True
                user.save()
                
    return redirect('settings')
@login_required
def delete_user(request, user_id):
    user_to_delete = get_object_or_404(User, id=user_id)
    
    # SECURITY: Make sure they aren't trying to delete themselves!
    if request.method == 'POST' and user_to_delete != request.user:
        user_to_delete.delete()
        
    return redirect('settings')

@login_required
def admin_unlock(request):
    if request.method == 'POST':
        admin_user = request.POST.get('admin_username')
        admin_pass = request.POST.get('admin_password')
        next_url = request.POST.get('next_url', 'dashboard') # Where they wanted to go
        
        # Check if the credentials match a real admin
        user = authenticate(request, username=admin_user, password=admin_pass)
        if user is not None and user.is_superuser:
            # UNLOCK THE SYSTEM!
            request.session['admin_unlocked'] = True
            return redirect(next_url)
            
    # If they type the wrong password, just send them back to the dashboard
    return redirect('dashboard')