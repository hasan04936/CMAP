from .models import Company

def company_context(request):
    try:
        company = Company.objects.first()
    except Exception:
        company = None
    return {
        'company': company
    }
