from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Company

class SetupWizardMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Let CSS, Images, and the Setup URLs pass through without getting blocked!
        allowed_paths = [
            reverse('setup_admin'),
            reverse('setup_company'),
        ]
        
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return self.get_response(request)

        # 2. THE GATEKEEPER LOGIC
        if request.path not in allowed_paths:
            admin_exists = User.objects.filter(is_superuser=True).exists()
            company_exists = Company.objects.exists()

            # If no Admin exists, trap them in Step 1
            if not admin_exists:
                return redirect('setup_admin')
            
            # If Admin exists but no Company, trap them in Step 2
            elif not company_exists:
                return redirect('setup_company')

        response = self.get_response(request)
        return response