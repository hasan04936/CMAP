from django.db import models
from django.utils import timezone

class Company(models.Model):
    # Mandatory fields
    name = models.CharField(max_length=255)
    local_place = models.CharField(max_length=255)
    
    # Optional setup fields
    registration_number = models.CharField(max_length=100, blank=True, null=True)
    cr_number = models.CharField(max_length=100, blank=True, null=True)
    building_number = models.CharField(max_length=100, blank=True, null=True)
    street_name = models.CharField(max_length=255, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    contact_number = models.CharField(max_length=50, blank=True, null=True)
    email_address = models.EmailField(blank=True, null=True)
    logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)

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

    def __str__(self):
        return self.title