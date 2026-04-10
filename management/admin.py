from django.contrib import admin
from .models import Company, Category, SubCategory, Employee, Document

# This registers your tables so they appear in the control panel
admin.site.register(Company)
admin.site.register(Category)
admin.site.register(SubCategory)
admin.site.register(Employee)
admin.site.register(Document)