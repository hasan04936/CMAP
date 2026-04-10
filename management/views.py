from django.shortcuts import render
from .models import Company, Category, Document

def dashboard(request):
    # Grab the first company in the database (Grow Green TRD)
    company = Company.objects.first()
    # Grab all the main categories you created
    categories = Category.objects.all()
    
    # Bundle the data to send to the HTML page
    context = {
        'company': company,
        'categories': categories,
    }
    return render(request, 'management/dashboard.html', context)