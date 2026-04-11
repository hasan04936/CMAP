from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from datetime import timedelta
from .models import Company, Category, SubCategory, Document

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
        title = request.POST.get('title')
        uploaded_file = request.FILES.get('document_file')
        issue_date = request.POST.get('issue_date') or None
        expire_date = request.POST.get('expire_date') or None
        agent_name = request.POST.get('agent_name')
        agent_contact = request.POST.get('agent_contact')
        
        if title and uploaded_file:
            Document.objects.create(
                title=title,
                file=uploaded_file,
                category=subcategory.category,
                sub_category=subcategory,
                issue_date=issue_date,
                expire_date=expire_date,
                agent_name=agent_name,
                agent_contact=agent_contact
            )
            return redirect('subcategory_detail', subcategory_id=subcategory.id)

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
    subcategory_id = document.sub_category.id
    
    if request.method == 'POST':
        document.title = request.POST.get('title')
        document.issue_date = request.POST.get('issue_date') or None
        document.expire_date = request.POST.get('expire_date') or None
        document.agent_name = request.POST.get('agent_name')
        document.agent_contact = request.POST.get('agent_contact')
        
        new_file = request.FILES.get('document_file')
        if new_file:
            document.file = new_file
            
        document.save()
        
    return redirect('subcategory_detail', subcategory_id=subcategory_id)

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