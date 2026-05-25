from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class Company(models.Model):
    name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)
    contact_number = models.CharField(max_length=50, blank=True, null=True)
    email_address = models.EmailField(blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    
    # NEW: Official Text Fields
    tax_number = models.CharField(max_length=100, blank=True, null=True)
    cr_number = models.CharField(max_length=100, blank=True, null=True)
    license_number = models.CharField(max_length=100, blank=True, null=True)
    
    # NEW: Automatically records exactly when the company profile was created
    created_date = models.DateTimeField(auto_now_add=True, null=True)

    auto_logout_minutes = models.IntegerField(default=30)

    staff_permission_level = models.CharField(max_length=20, default='full') 
    alert_on_upload = models.BooleanField(default=True)
    alert_on_edit = models.BooleanField(default=True)
    alert_on_delete = models.BooleanField(default=True)
    alert_on_system = models.BooleanField(default=True)
    

    expire_alert_days = models.IntegerField(default=30)
    recent_update_days = models.IntegerField(default=7)

    # API & Integrations
    telegram_bot_token = models.CharField(max_length=255, blank=True, null=True)
    telegram_chat_id = models.CharField(max_length=100, blank=True, null=True)
    custom_domain = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name
    
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    theme = models.CharField(max_length=20, default='default') # <-- NEW: Saves the theme!

    def __str__(self):
        return f"{self.user.username}'s Profile"
class Category(models.Model):
    name = models.CharField(max_length=100) # e.g., Employees, Co Documents, Vehicles
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class SubCategory(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100) # e.g., ID, Contract, Visa

    def __str__(self):
        return f"{self.category.name} -> {self.name}"

class Employee(models.Model):
    # Specific employee bio details based on your design
    full_name = models.CharField(max_length=255)
    photo = models.ImageField(upload_to='employee_photos/', blank=True, null=True)
    house = models.CharField(max_length=255, blank=True, null=True)
    place = models.CharField(max_length=255, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    studies = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    emergency_contact_1 = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_2 = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.full_name

class Document(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    
    # Where does this document belong?
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    sub_category = models.ForeignKey(SubCategory, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True) # Links doc to a specific employee if needed

    # Notification & Meta Details
    issue_date = models.DateField(blank=True, null=True)
    expire_date = models.DateField(blank=True, null=True)
    issuing_authority = models.CharField(max_length=255, blank=True, null=True)
    agent_name = models.CharField(max_length=255, blank=True, null=True)
    agent_contact = models.CharField(max_length=100, blank=True, null=True)
    uploaded_date = models.DateTimeField(default=timezone.now)
    updated_date = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return self.title

    @property
    def card_header_value(self):
        # 1. Search for a field containing "name" in the name first
        for val in self.custom_values.all():
            if 'name' in val.custom_field.field_name.lower() and val.value:
                return val
        
        # 2. Fallback to the first show_on_card field
        show_card_val = self.custom_values.filter(custom_field__show_on_card=True).first()
        if show_card_val:
            return show_card_val
            
        # 3. Fallback to the very first text field
        for val in self.custom_values.all():
            if val.custom_field.field_type == 'text' and val.value:
                return val
                
        # 4. Fallback to any first custom field with a value
        for val in self.custom_values.all():
            if val.value:
                return val
        return None

    @property
    def card_body_values(self):
        header = self.card_header_value
        if header:
            return self.custom_values.filter(custom_field__show_on_card=True).exclude(id=header.id).order_by('custom_field__id')
        return self.custom_values.filter(custom_field__show_on_card=True).order_by('custom_field__id')

    @property
    def card_image_value(self):
        for val in self.custom_values.all():
            if val.custom_field.field_type == 'file' and val.file_value:
                return val
        return None

    @property
    def card_expire_value(self):
        for val in self.custom_values.all():
            if 'expire' in val.custom_field.field_name.lower() and val.value:
                return val
        return None

    @property
    def card_issue_value(self):
        for val in self.custom_values.all():
            name_lower = val.custom_field.field_name.lower()
            if ('issue' in name_lower or 'valid' in name_lower or 'start' in name_lower) and val.value:
                return val
        return None
    
# NEW: Defines the custom questions for a Sub-Category
class CustomField(models.Model):
    FIELD_TYPES = (
        ('text', 'Short Text'),
        ('date', 'Date Picker'),
        ('number', 'Number Only'),
        ('file', 'File / Image Upload'), # NEW: Added the File option!
    )
    sub_category = models.ForeignKey(SubCategory, on_delete=models.CASCADE, related_name='custom_fields')
    field_name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, default='text')
    is_required = models.BooleanField(default=False)

    show_on_card = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.sub_category.name} -> {self.field_name}"

class CustomFieldValue(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='custom_values')
    custom_field = models.ForeignKey(CustomField, on_delete=models.CASCADE)
    value = models.CharField(max_length=255, blank=True, null=True)
    # NEW: A dedicated space to save uploaded images/files for custom fields
    file_value = models.FileField(upload_to='custom_uploads/', blank=True, null=True) 

    def __str__(self):
        return f"{self.document.title} - {self.custom_field.field_name}"
    
class HistoryLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=50) # Will store "Uploaded", "Edited", or "Deleted"
    document_name = models.CharField(max_length=255, default="Unnamed Entry")
    folder_path = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} {self.action} {self.document_name}"