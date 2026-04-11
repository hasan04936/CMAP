from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from datetime import timedelta
from .models import Company, Category, SubCategory, Document, CustomField, CustomFieldValue

def dashboard(request):
    company = Company.objects.first()
    categories = Category.objects.all()

    # 1. Calculate "Updated Today"
    today = timezone.now().date()
    updated_today_count = Document.objects.filter(updated_date__date=today).count()

    # 2. Calculate "Expire Soon" (Expiring within the next 30 days)
    thirty_days_from_now = today + timedelta(days=30)
    expire_soon_count = Document.objects.filter(
        expire_date__lte=thirty_days_from_now,
        expire_date__gte=today
    ).count()
    
    context = {
        'company': company,
        'categories': categories,
        'updated_today': updated_today_count,
        'expire_soon': expire_soon_count,
    }
    return render(request, 'management/dashboard.html', context)

# ---> THIS WAS THE MISSING FUNCTION! <---
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
    # ... rest of the function remains the same

    # 2. GET: Display the Page
    documents = Document.objects.filter(sub_category=subcategory).order_by('-id')
    context = {
        'company': company,
        'subcategory': subcategory,
        'documents': documents,
        # NEW: Send the custom fields to the HTML page!
        'custom_fields': subcategory.custom_fields.all(), 
    }
    return render(request, 'management/subcategory_detail.html', context)

    # 2. GET: Display the Page
    documents = Document.objects.filter(sub_category=subcategory).order_by('-id')
    context = {
        'company': company,
        'subcategory': subcategory,
        'documents': documents,
    }
    return render(request, 'management/subcategory_detail.html', context)

def delete_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    subcategory_id = document.sub_category.id
    
    if request.method == 'POST':
        document.delete()
        
    return redirect('subcategory_detail', subcategory_id=subcategory_id)

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

def history_log(request):
    company = Company.objects.first()
    # Grab all documents, ordered by the most recently updated first
    recent_updates = Document.objects.all().order_by('-updated_date')
    
    context = {
        'company': company,
        'recent_updates': recent_updates,
    }
    return render(request, 'management/history.html', context)

def settings_page(request):
    company = Company.objects.first()
    categories = Category.objects.all()

    # If the user clicks "Save Company Details"
    if request.method == 'POST' and 'update_company' in request.POST:
        company.name = request.POST.get('company_name')
        company.contact_number = request.POST.get('contact_number')
        company.email_address = request.POST.get('email_address')
        company.country = request.POST.get('country')
        company.district = request.POST.get('district')
        
        # Save the new official numbers
        company.tax_number = request.POST.get('tax_number')
        company.cr_number = request.POST.get('cr_number')
        company.license_number = request.POST.get('license_number')
        
        # Check for a new logo upload
        if request.FILES.get('company_logo'):
            company.logo = request.FILES.get('company_logo')
            
        company.save() # Lock in the changes
        return redirect('settings')

    context = {
        'company': company,
        'categories': categories,
    }
    return render(request, 'management/settings.html', context)

def add_category(request):
    if request.method == 'POST':
        name = request.POST.get('category_name')
        if name:
            Category.objects.create(name=name)
    # This magic line sends them back to the exact page they clicked the button from!
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

def add_subcategory(request):
    if request.method == 'POST':
        name = request.POST.get('subcategory_name')
        category_id = request.POST.get('category_id')
        if name and category_id:
            category = get_object_or_404(Category, id=category_id)
            SubCategory.objects.create(name=name, category=category)
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

def edit_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        name = request.POST.get('category_name')
        if name:
            category.name = name
            category.save()
    return redirect('settings')

def delete_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        category.delete()
    return redirect('settings')

def edit_subcategory(request, subcategory_id):
    subcategory = get_object_or_404(SubCategory, id=subcategory_id)
    if request.method == 'POST':
        name = request.POST.get('subcategory_name')
        if name:
            subcategory.name = name
            subcategory.save()
    return redirect('settings')

def delete_subcategory(request, subcategory_id):
    subcategory = get_object_or_404(SubCategory, id=subcategory_id)
    if request.method == 'POST':
        subcategory.delete()
    return redirect('settings')

def manage_fields(request, subcategory_id):
    # Get the specific sub-folder we are building fields for
    subcategory = get_object_or_404(SubCategory, id=subcategory_id)
    
    if request.method == 'POST':
        # Check if we are ADDING a field
        # Check if we are ADDING a field
        if 'add_field' in request.POST:
            field_name = request.POST.get('field_name')
            field_type = request.POST.get('field_type')
            is_required = request.POST.get('is_required') == 'on' 
            show_on_card = request.POST.get('show_on_card') == 'on' # NEW CHECKBOX
            
            if field_name:
                CustomField.objects.create(
                    sub_category=subcategory,
                    field_name=field_name,
                    field_type=field_type,
                    is_required=is_required,
                    show_on_card=show_on_card # SAVES IT!
                )
                
        # Check if we are DELETING a field
        elif 'delete_field' in request.POST:
            field_id = request.POST.get('field_id')
            CustomField.objects.filter(id=field_id).delete()
            
        return redirect('manage_fields', subcategory_id=subcategory.id)

    context = {
        'subcategory': subcategory,
        # Get all fields already created for this folder
        'fields': subcategory.custom_fields.all() 
    }
    return render(request, 'management/manage_fields.html', context)