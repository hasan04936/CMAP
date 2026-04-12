from django.db import models
from django.utils import timezone

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

    def __str__(self):
        return self.name

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