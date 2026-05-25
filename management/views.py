from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, authenticate, login, update_session_auth_hash
from django.contrib.auth.models import User
from django.db.models import Q
from django.conf import settings
from django.http import HttpResponse, Http404
from django.core.management import call_command
from django.contrib import messages
import io
import threading
import os
import time
import re
from .models import Company, Category, SubCategory, Document, CustomField, CustomFieldValue, UserProfile, HistoryLog
from .utils import send_telegram_alert
import subprocess

# ====================================================================
# SMART EXTRACTOR: Finds the "Name" from dynamic custom fields
# ====================================================================
def get_doc_name(document):
    # Try to find a field that specifically has "name" in the title
    name_val = CustomFieldValue.objects.filter(
        document=document,
        custom_field__field_type__in=['text', 'email'],
        custom_field__field_name__icontains='name'
    ).exclude(value='').first()
    
    if name_val: return name_val.value
    
    # If no "name" field exists, just grab the very first text answer they typed
    first_val = CustomFieldValue.objects.filter(
        document=document,
        custom_field__field_type__in=['text', 'email', 'number']
    ).exclude(value='').first()
    
    if first_val: return first_val.value
    return "Unnamed Entry"
# ====================================================================

@login_required
def dashboard(request):
    company, _ = Company.objects.get_or_create(id=1)
    categories = Category.objects.all()

    today = timezone.now().date()
    today_str = today.strftime('%Y-%m-%d')
    
    # 1. RECENT UPDATES (Based on custom timer)
    recent_date = today - timedelta(days=company.recent_update_days)
    recent_updates_count = Document.objects.filter(uploaded_date__date__gte=recent_date).count()

    # 2. EXPIRE SOON (Based on custom timer)
    future_str = (today + timedelta(days=company.expire_alert_days)).strftime('%Y-%m-%d')
    expire_soon_count = Document.objects.filter(
        custom_values__custom_field__field_type='date',
        custom_values__value__lte=future_str,
        custom_values__value__gte=today_str,
        custom_values__custom_field__field_name__icontains='expire' # Only look at fields with 'expire' in the name!
    ).distinct().count()
    
    # 3. ALREADY EXPIRED
    expired_count = Document.objects.filter(
        custom_values__custom_field__field_type='date',
        custom_values__value__lt=today_str,
        custom_values__custom_field__field_name__icontains='expire'
    ).distinct().count()
    
    # 4. MOCKUP METRICS
    total_folders = categories.count()
    total_documents = Document.objects.count()
    active_documents = max(0, total_documents - expired_count)
    
    # Live storage utilization percentage
    storage_percentage = 24
    if total_documents > 0:
        storage_percentage = max(10, min(95, int((active_documents / total_documents) * 100)))

    # Conic percentages for Donut chart breakdown
    total_pie = expired_count + expire_soon_count + active_documents
    expired_pct = int((expired_count / total_pie) * 100) if total_pie > 0 else 0
    soon_pct = int((expire_soon_count / total_pie) * 100) if total_pie > 0 else 0
    active_pct = 100 - expired_pct - soon_pct if total_pie > 0 else 100

    # 5. RECENT ACTIVITIES DIRECTORY DATA
    recent_activities = []
    for cat in categories[:5]:
        latest_doc = Document.objects.filter(category=cat).order_by('-uploaded_date').first()
        last_modified = latest_doc.uploaded_date if latest_doc else None
        
        has_expired = Document.objects.filter(
            category=cat,
            custom_values__custom_field__field_type='date',
            custom_values__value__lt=today_str,
            custom_values__custom_field__field_name__icontains='expire'
        ).distinct().exists()
        
        recent_activities.append({
            'category': cat,
            'name': cat.name,
            'description': cat.description or f"{cat.name} related documents",
            'doc_count': Document.objects.filter(category=cat).count(),
            'last_modified': last_modified,
            'status': 'Attention' if has_expired else 'Active'
        })
    
    context = {
        'company': company,
        'categories': categories,
        'updated_today': recent_updates_count,
        'expire_soon': expire_soon_count,
        'expired': expired_count,
        'total_folders': total_folders,
        'total_documents': total_documents,
        'active_documents': active_documents,
        'storage_percentage': storage_percentage,
        'expired_pct': expired_pct,
        'soon_pct': soon_pct,
        'active_pct': active_pct,
        'recent_activities': recent_activities,
        'recent_sessions': HistoryLog.objects.select_related('user').order_by('-timestamp')[:4],
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
        # --- NEW SECURITY: BLOCK READ-ONLY STAFF FROM UPLOADING ---
        if not request.user.is_superuser and getattr(company, 'staff_permission_level', 'full') == 'read':
            messages.error(request, "Security: Staff accounts are currently set to Read-Only.")
            return redirect('subcategory_detail', subcategory_id=subcategory.id)
        # ----------------------------------------------------------

        dynamic_title = f"{subcategory.name} Entry - {timezone.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Step A: Create the base Document
        doc = Document.objects.create(
            title=dynamic_title,
            category=subcategory.category,
            sub_category=subcategory,
        )
        
        # Step B: Loop through and save all Custom Fields dynamically
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
                    
        # Grab the human-readable name!
        display_name = get_doc_name(doc)
        
        # --- THE TRACKER: HUMAN READABLE UPLOAD ---
        HistoryLog.objects.create(
            user=request.user, 
            action="Created", 
            document_name=display_name, 
            folder_path=f"{subcategory.category.name} > {subcategory.name}"
        )
        
        # --- TELEGRAM TRIGGER: CONTROLLED BY SETTINGS ---
        if getattr(company, 'alert_on_upload', True):
            alert_msg = (
                f"🟢 <b>NEW RECORD ADDED</b>\n\n"
                f"👤 <b>{request.user.username.upper()}</b> added a new <b>{subcategory.name}</b> "
                f"into the <b>{subcategory.category.name}</b> folder for <b>{display_name}</b>."
            )
            send_telegram_alert(alert_msg)
        # ------------------------------------------------

        messages.success(request, 'Entry Saved Successfully!')
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
    company = Company.objects.first()
    
    if request.method == 'POST':
        # --- NEW SECURITY: BLOCK READ & UPLOAD STAFF FROM DELETING ---
        if not request.user.is_superuser and getattr(company, 'staff_permission_level', 'full') in ['read', 'upload']:
            messages.error(request, "Security: You do not have permission to delete documents.")
            return redirect('subcategory_detail', subcategory_id=subcategory_id)
        # -------------------------------------------------------------

        # Grab the human-readable name before deleting
        display_name = get_doc_name(document)
        
        # --- THE TRACKER: HUMAN READABLE DELETION ---
        HistoryLog.objects.create(
            user=request.user, 
            action="Deleted", 
            document_name=display_name, 
            folder_path=f"{document.sub_category.category.name} > {document.sub_category.name}"
        )
        
        # --- TELEGRAM TRIGGER: CONTROLLED BY SETTINGS ---
        if getattr(company, 'alert_on_delete', True):
            alert_msg = (
                f"🗑️ <b>RECORD DELETED</b>\n\n"
                f"👤 <b>{request.user.username.upper()}</b> deleted the <b>{document.sub_category.name}</b> "
                f"from the <b>{document.sub_category.category.name}</b> folder of <b>{display_name}</b>."
            )
            send_telegram_alert(alert_msg)
        # ------------------------------------------------
        
        document.delete()
        messages.success(request, 'Entry Deleted Successfully!')
        
    return redirect('subcategory_detail', subcategory_id=subcategory_id)

@login_required
def edit_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    subcategory = document.sub_category
    company = Company.objects.first()
    
    if request.method == 'POST':
        # --- NEW SECURITY: BLOCK READ & UPLOAD STAFF FROM EDITING ---
        if not request.user.is_superuser and getattr(company, 'staff_permission_level', 'full') in ['read', 'upload']:
            messages.error(request, "Security: You do not have permission to edit documents.")
            return redirect('subcategory_detail', subcategory_id=subcategory.id)
        # ------------------------------------------------------------

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
        
        # Grab the updated human-readable name!
        display_name = get_doc_name(document)
        
        # --- THE TRACKER: HUMAN READABLE EDIT ---
        HistoryLog.objects.create(
            user=request.user, 
            action="Edited", 
            document_name=display_name, 
            folder_path=f"{subcategory.category.name} > {subcategory.name}"
        )
        
        # --- TELEGRAM TRIGGER: CONTROLLED BY SETTINGS ---
        if getattr(company, 'alert_on_edit', True):
            alert_msg = (
                f"✏️ <b>RECORD UPDATED</b>\n\n"
                f"👤 <b>{request.user.username.upper()}</b> updated the <b>{subcategory.name}</b> "
                f"in the <b>{subcategory.category.name}</b> folder for <b>{display_name}</b>."
            )
            send_telegram_alert(alert_msg)
        # ------------------------------------------------
        
        messages.success(request, 'Entry Updated Successfully!')
        
    return redirect('subcategory_detail', subcategory_id=subcategory.id)

@login_required
def history_log(request):
    logs = HistoryLog.objects.all().order_by('-timestamp')
    context = {
        'logs': logs,
    }
    return render(request, 'management/history.html', context)

@login_required
def settings_page(request):
    if not (request.user.is_superuser or request.session.get('admin_unlocked', False)):
        return redirect('dashboard')
    
    company = Company.objects.first()
    categories = Category.objects.all()
    users = User.objects.all()
    
    # --- MAGIC: READ THE HIDDEN CLOUDFLARE URL ---
    tunnel_url = None
    log_file = os.path.join(settings.BASE_DIR, 'tunnel.log')
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # --- UPDATED TO SEARCH FOR NGROK INSTEAD OF CLOUDFLARE ---
                match = re.search(r'(https://slouchy-womanless-vagueness\.ngrok-free\.dev)', content)
                if match:
                    tunnel_url = match.group(1)
        except Exception:
            pass
    # ---------------------------------------------
    
    context = {
        'company': company,
        'categories': categories,
        'users': users,
        'tunnel_url': tunnel_url, # Pass the URL to the web page
    }
    return render(request, 'management/settings.html', context)

@login_required
def toggle_tunnel(request):
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    if request.method == 'POST':
        action = request.POST.get('action')
        log_file = os.path.join(settings.BASE_DIR, 'tunnel.log')
        # Pointing to the new Ngrok file
        ngrok_exe = os.path.join(settings.BASE_DIR, 'ngrok.exe') 
        company = Company.objects.first()
        
        if action == 'start':
            # 1. INVISIBLE KILL COMMAND
            subprocess.run(["taskkill", "/F", "/IM", "ngrok.exe", "/T"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            time.sleep(0.5) # Give Windows half a second to release the file lock!
            
            # Delete old logs gracefully
            if os.path.exists(log_file):
                try:
                    os.remove(log_file)
                except Exception:
                    pass # If Windows blocks it, just ignore and overwrite it
            
            # 2. INVISIBLE START COMMAND
            cmd = [ngrok_exe, "http", "--url=slouchy-womanless-vagueness.ngrok-free.dev", "8000", "--log", log_file]
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            
            # 3. SMART WAIT: Check the log every 1 second (up to 12 seconds maximum)
            tunnel_url = None
            for _ in range(12):
                time.sleep(1) # wait 1 second
                if os.path.exists(log_file):
                    try:
                        with open(log_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Search specifically for your static Ngrok domain
                            match = re.search(r'(https://slouchy-womanless-vagueness\.ngrok-free\.dev)', content)
                            if match:
                                tunnel_url = match.group(1)
                                break  # Found the URL! Exit the waiting loop immediately.
                    except Exception:
                        pass
            
            if tunnel_url:
                # --- TELEGRAM TRIGGER: CONTROLLED BY SETTINGS ---
                if company and getattr(company, 'alert_on_system', True):
                    alert_msg = (
                        f"🌍 <b>REMOTE ACCESS ONLINE</b>\n\n"
                        f"👤 <b>{request.user.username.upper()}</b> opened the server for mobile access.\n\n"
                        f"🔗 <b>Click to Access C-MAP:</b>\n{tunnel_url}\n\n"
                        f"<i>Note: The system is running on a secure static domain.</i>"
                    )
                    send_telegram_alert(alert_msg)
                messages.success(request, "Remote Access Activated! 🌍🚀")
            else:
                messages.warning(request, "Tunnel started, but couldn't extract URL for Telegram. Please check logs.")
            
        elif action == 'stop':
            # 1. Kill the invisible Ngrok tunnel 
            os.system("taskkill /F /IM ngrok.exe /T > NUL 2>&1")
            time.sleep(0.5) # Give Windows half a second to release the file lock!
            
            # Delete the log gracefully
            if os.path.exists(log_file):
                try:
                    os.remove(log_file)
                except Exception:
                    pass # If Windows blocks it, just ignore it so it doesn't crash the page
            
            # --- TELEGRAM TRIGGER: CONTROLLED BY SETTINGS ---
            if company and getattr(company, 'alert_on_system', True):
                alert_msg = f"🔒 <b>REMOTE ACCESS OFFLINE</b>\n\n👤 <b>{request.user.username.upper()}</b> disabled mobile access. The system is now restricted to the local office network."
                send_telegram_alert(alert_msg)
            
            messages.success(request, "Remote Access Disabled. System is now Local Only. 🔒")
            
    return redirect('settings')

@login_required
def add_category(request):
    if request.method == 'POST':
        name = request.POST.get('category_name')
        if name:
            Category.objects.create(name=name)
            messages.success(request, 'Main Folder Created!')
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

@login_required
def add_subcategory(request):
    if request.method == 'POST':
        name = request.POST.get('subcategory_name')
        category_id = request.POST.get('category_id')
        if name and category_id:
            category = get_object_or_404(Category, id=category_id)
            SubCategory.objects.create(name=name, category=category)
            messages.success(request, 'Sub-Folder Created!')
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

@login_required
def edit_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        name = request.POST.get('category_name')
        if name:
            old_name = category.name
            category.name = name
            category.save()
            
            HistoryLog.objects.create(
                user=request.user, 
                action="Edited", 
                document_name=f"Folder: {old_name} -> {name}", 
                folder_path="Settings > Architecture"
            )
            messages.success(request, 'Folder Renamed!')
            
    return redirect('settings')

@login_required
def delete_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        cat_name = category.name
        
        HistoryLog.objects.create(
            user=request.user, 
            action="Deleted", 
            document_name=f"Main Folder: {cat_name}", 
            folder_path="Settings > Architecture"
        )
        category.delete()
        messages.success(request, 'Folder Deleted!')
    return redirect('settings')

@login_required
def edit_subcategory(request, subcategory_id):
    subcategory = get_object_or_404(SubCategory, id=subcategory_id)
    if request.method == 'POST':
        name = request.POST.get('subcategory_name')
        if name:
            old_name = subcategory.name
            subcategory.name = name
            subcategory.save()
            
            HistoryLog.objects.create(
                user=request.user, 
                action="Edited", 
                document_name=f"Sub-Folder: {old_name} -> {name}", 
                folder_path=f"Settings > Architecture > {subcategory.category.name}"
            )
            messages.success(request, 'Sub-Folder Renamed!')
            
    return redirect('settings')

@login_required
def delete_subcategory(request, subcategory_id):
    subcategory = get_object_or_404(SubCategory, id=subcategory_id)
    if request.method == 'POST':
        sub_name = subcategory.name
        cat_name = subcategory.category.name
        
        HistoryLog.objects.create(
            user=request.user, 
            action="Deleted", 
            document_name=f"Sub-Folder: {sub_name}", 
            folder_path=f"Settings > Architecture > {cat_name}"
        )
        subcategory.delete()
        messages.success(request, 'Sub-Folder Deleted!')
    return redirect('settings')

@login_required
def manage_fields(request, subcategory_id):
    subcategory = get_object_or_404(SubCategory, id=subcategory_id)
    
    if request.method == 'POST':
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
                
        elif 'delete_field' in request.POST:
            field_id = request.POST.get('field_id')
            field_to_delete = CustomField.objects.filter(id=field_id).first()
            if field_to_delete:
                field_name = field_to_delete.field_name
                
                HistoryLog.objects.create(
                    user=request.user, 
                    action="Deleted", 
                    document_name=f"Database Field: {field_name}", 
                    folder_path=f"Settings > Field Builder > {subcategory.name}"
                )
                field_to_delete.delete()
            
        return redirect('manage_fields', subcategory_id=subcategory.id)

    context = {
        'subcategory': subcategory,
        'fields': subcategory.custom_fields.all() 
    }
    return render(request, 'management/manage_fields.html', context)

def execute_shutdown():
    # Wait 2 seconds to allow the offline screen to load on the browser
    time.sleep(2)
    
    # 1. Kill the Cloudflare Tunnel
    os.system("taskkill /F /IM cloudflared.exe /T > NUL 2>&1")
    
    # 2. Kill the Python server (This is the EXACT command that worked for you before!)
    os.system("taskkill /F /IM python.exe /T > NUL 2>&1")

# 1. THE SCREEN LOCK (Safe: Keeps server running for mobile users)
def lock_screen(request):
    logout(request)
    messages.success(request, 'Screen Locked Successfully. Server is still running.')
    return redirect('login')

# 2. THE POWER BUTTON (Kills the whole system)
def shutdown_server(request):
    logout(request)
    threading.Thread(target=execute_shutdown).start()
    
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>C-MAP Server Offline</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@600;700;800;900&display=swap" rel="stylesheet">
        <style>
            :root {
                --font-sans: "Nunito", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                --app-bg: #030d28;
                --card-bg: rgba(255, 255, 255, 0.03);
                --border-color: rgba(255, 255, 255, 0.08);
                --text-main: #ffffff;
                --text-muted: rgba(255, 255, 255, 0.7);
                --danger: #ff4d4d;
                --danger-glow: rgba(255, 77, 77, 0.25);
            }
            
            * { box-sizing: border-box; }
            
            body {
                margin: 0;
                padding: 0;
                font-family: var(--font-sans);
                background: radial-gradient(circle at 50% 50%, #0d1b3e 0%, #030d28 100%);
                color: var(--text-main);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                overflow: hidden;
            }

            .container {
                width: min(520px, calc(100vw - 32px));
                padding: 40px 30px;
                background: var(--card-bg);
                border: 1px solid var(--border-color);
                border-radius: 28px;
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                box-shadow: 0 24px 64px rgba(0, 0, 0, 0.4);
                text-align: center;
                animation: fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1);
            }

            .icon-wrapper {
                width: 84px;
                height: 84px;
                background: rgba(255, 77, 77, 0.1);
                border: 1px solid var(--danger);
                color: var(--danger);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 32px;
                margin: 0 auto 24px;
                box-shadow: 0 0 30px var(--danger-glow);
                animation: pulse 2s infinite ease-in-out;
            }

            h1 {
                font-size: 26px;
                font-weight: 900;
                margin: 0 0 12px;
                letter-spacing: -0.5px;
            }

            p {
                font-size: 15px;
                color: var(--text-muted);
                line-height: 1.6;
                margin: 0 0 28px;
                font-weight: 700;
            }

            .info-box {
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 18px;
                padding: 18px;
                margin-bottom: 28px;
                font-size: 13.5px;
                line-height: 1.5;
                color: rgba(255, 255, 255, 0.8);
                font-weight: 800;
                text-align: left;
            }

            .btn-close {
                min-height: 48px;
                width: 100%;
                background: linear-gradient(135deg, #ff4d4d, #d63030);
                color: #ffffff;
                border: none;
                border-radius: 16px;
                font-weight: 900;
                font-size: 15px;
                cursor: pointer;
                box-shadow: 0 10px 25px var(--danger-glow);
                transition: all 0.2s ease;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
            }

            .btn-close:hover {
                transform: translateY(-2px);
                box-shadow: 0 14px 30px rgba(255, 77, 77, 0.35);
            }

            .btn-close:active {
                transform: translateY(0);
            }

            .countdown {
                font-size: 12px;
                color: rgba(255, 255, 255, 0.4);
                margin-top: 16px;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 1px;
            }

            @keyframes fadeInUp {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }

            @keyframes pulse {
                0%, 100% { transform: scale(1); box-shadow: 0 0 20px var(--danger-glow); }
                50% { transform: scale(1.05); box-shadow: 0 0 35px rgba(255, 77, 77, 0.4); }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon-wrapper">🔌</div>
            <h1>C-MAP Server Offline</h1>
            <p>The enterprise server has been shut down successfully.<br>You may now safely close this browser window.</p>
            
            <div class="info-box">
                👉 <strong>To restart C-MAP:</strong> Double-click the <strong>C-MAP Enterprise</strong> desktop icon on your PC to launch the server again.
            </div>

            <button class="btn-close" onclick="closeWindow()">
                Close Tab Now
            </button>

            <div class="countdown" id="countdown">Closing automatically in 3s...</div>
        </div>

        <script>
            var secondsLeft = 3;
            var countdownEl = document.getElementById('countdown');

            function closeWindow() {
                // Standard close
                window.close();
                // Forceful workaround trick
                window.open('', '_self');
                window.close();
                // Navigational fallback
                window.location.href = "about:blank";
            }

            var interval = setInterval(function() {
                secondsLeft--;
                if (secondsLeft <= 0) {
                    clearInterval(interval);
                    closeWindow();
                } else {
                    countdownEl.innerText = "Closing automatically in " + secondsLeft + "s...";
                }
            }, 1000);

            setTimeout(closeWindow, 3000);
        </script>
    </body>
    </html>
    """
    return HttpResponse(html)

@login_required
def company_profile(request):
    if not (request.user.is_superuser or request.session.get('admin_unlocked', False)):
        return redirect('dashboard') 
        
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
        
        HistoryLog.objects.create(
            user=request.user, 
            action="Edited", 
            document_name="Company Details", 
            folder_path="System > Company Profile"
        )
        
        # --- TELEGRAM TRIGGER: CONTROLLED BY SETTINGS ---
        if getattr(company, 'alert_on_system', True):
            alert_msg = f"🏢 <b>COMPANY PROFILE UPDATED</b>\n\n👤 <b>{request.user.username.upper()}</b> updated the core company settings and licenses."
            send_telegram_alert(alert_msg)
        # ------------------------------------------------
        
        messages.success(request, 'Company Profile Updated!')
        return redirect('company_profile')

    return render(request, 'management/company_profile.html', {'company': company})

@login_required
def global_search(request):
    query = request.GET.get('q', '')
    results = []
    
    if query:
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
        role = request.POST.get('role') 
        
        if new_username and new_password and not User.objects.filter(username=new_username).exists():
            user = User.objects.create_user(username=new_username, password=new_password)
            
            if role == 'admin':
                user.is_superuser = True
                user.is_staff = True
                user.save()
            
            HistoryLog.objects.create(
                user=request.user, 
                action="Created", 
                document_name=f"New User: {new_username}", 
                folder_path="Settings > Accounts"
            )
            
            company = Company.objects.first()
            # --- TELEGRAM TRIGGER: CONTROLLED BY SETTINGS ---
            if company and getattr(company, 'alert_on_system', True):
                alert_msg = (
                    f"👤 <b>NEW SYSTEM USER CREATED</b>\n\n"
                    f"👤 <b>{request.user.username.upper()}</b> granted system access to a new user.\n\n"
                    f"<b>Username:</b> {new_username}\n"
                    f"<b>Role Level:</b> {role.upper()}"
                )
                send_telegram_alert(alert_msg)
            # ------------------------------------------------
            
            messages.success(request, 'New User Added Successfully!')
                
    return redirect('user_settings')

@login_required
def delete_user(request, user_id):
    user_to_delete = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST' and user_to_delete != request.user:
        deleted_username = user_to_delete.username
        
        HistoryLog.objects.create(
            user=request.user, 
            action="Deleted", 
            document_name=f"User Account: {deleted_username}", 
            folder_path="Settings > System Users"
        )
        
        company = Company.objects.first()
        # --- TELEGRAM TRIGGER: CONTROLLED BY SETTINGS ---
        if company and getattr(company, 'alert_on_system', True):
            alert_msg = f"🚫 <b>USER ACCOUNT DELETED</b>\n\n👤 <b>{request.user.username.upper()}</b> permanently revoked access and deleted the account for <b>{deleted_username}</b>."
            send_telegram_alert(alert_msg)
        # ------------------------------------------------
        
        user_to_delete.delete()
        messages.success(request, 'User Deleted Successfully!')
        
    return redirect('user_settings')

@login_required
def admin_unlock(request):
    if request.method == 'POST':
        admin_user = request.POST.get('admin_username')
        admin_pass = request.POST.get('admin_password')
        next_url = request.POST.get('next_url', 'dashboard') 
        
        user = authenticate(request, username=admin_user, password=admin_pass)
        if user is not None and user.is_superuser:
            request.session['admin_unlocked'] = True
            messages.success(request, 'Admin Override Engaged 🔓')
            return redirect(next_url)
            
    return redirect('dashboard')

@login_required
def change_avatar(request):
    if request.method == 'POST':
        avatar_file = request.FILES.get('avatar')
        if avatar_file:
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            profile.avatar = avatar_file
            profile.save()

            HistoryLog.objects.create(
                user=request.user, 
                action="Edited", 
                document_name="Profile Avatar", 
                folder_path="Settings > My User Profile"
            )
            messages.success(request, 'Avatar Updated Successfully!')

    return redirect('user_settings')

@login_required
def reset_password(request):
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if new_password and new_password == confirm_password:
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user) 
            
            HistoryLog.objects.create(
                user=request.user, 
                action="Edited", 
                document_name="Account Password", 
                folder_path="Settings > My User Profile"
            )
            messages.success(request, 'Password Reset Successfully!')
            
    return redirect('user_settings')

@login_required
def save_theme(request):
    if request.method == 'POST':
        theme = request.POST.get('theme', 'default')
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.theme = theme
        profile.save()
    return redirect(request.META.get('HTTP_REFERER', 'settings'))

@login_required
def update_alerts(request):
    if request.method == 'POST':
        company, _ = Company.objects.get_or_create(id=1)
        
        # Save standard timers
        company.expire_alert_days = request.POST.get('expire_days', 30)
        company.recent_update_days = request.POST.get('recent_days', 7)
        company.auto_logout_minutes = request.POST.get('logout_minutes', 30)
        
        # --- NEW SECURITY & TELEGRAM TOGGLES ---
        company.staff_permission_level = request.POST.get('staff_permission', 'full')
        company.alert_on_upload = request.POST.get('alert_upload') == 'on'
        company.alert_on_edit = request.POST.get('alert_edit') == 'on'
        company.alert_on_delete = request.POST.get('alert_delete') == 'on'
        company.alert_on_system = request.POST.get('alert_system') == 'on'
        
        # 👇 THESE ARE THE CRITICAL LINES YOU ARE MISSING 👇
        company.telegram_bot_token = request.POST.get('telegram_bot_token', '')
        company.telegram_chat_id = request.POST.get('telegram_chat_id', '')
        company.custom_domain = request.POST.get('custom_domain', '')
        # 👆 --------------------------------------------- 👆
        
        company.save()

        HistoryLog.objects.create(user=request.user, action="Edited", document_name="Tracking Timers & APIs", folder_path="Settings")
        messages.success(request, "System Timers & Alerts saved successfully! 💾")
        
    return redirect('settings')

# --- NEW MAINTENANCE FUNCTION ---
@login_required
def prune_history_logs(request):
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    if request.method == 'POST':
        cutoff_date = timezone.now() - timedelta(days=90)
        deleted_count, _ = HistoryLog.objects.filter(timestamp__lt=cutoff_date).delete()
        
        HistoryLog.objects.create(
            user=request.user, 
            action="Deleted", 
            document_name=f"{deleted_count} Old Logs", 
            folder_path="System Maintenance"
        )
        messages.success(request, f"System Cleanup Complete! {deleted_count} old logs were removed. 🧹")
        
    return redirect('settings')
# --------------------------------

@login_required
def filtered_documents(request, filter_type):
    company, _ = Company.objects.get_or_create(id=1)
    today = timezone.now().date()
    today_str = today.strftime('%Y-%m-%d')
    
    results = []
    title = ""
    
    if filter_type == 'recent':
        recent_date = today - timedelta(days=company.recent_update_days)
        results = Document.objects.filter(uploaded_date__date__gte=recent_date).order_by('-uploaded_date')
        title = f"Recent Updates (Last {company.recent_update_days} Days)"
        
    elif filter_type == 'expire_soon':
        future_str = (today + timedelta(days=company.expire_alert_days)).strftime('%Y-%m-%d')
        results = Document.objects.filter(
            custom_values__custom_field__field_type='date',
            custom_values__value__lte=future_str,
            custom_values__value__gte=today_str,
            custom_values__custom_field__field_name__icontains='expire'
        ).distinct()
        title = f"Expiring Soon (Next {company.expire_alert_days} Days)"
        
    elif filter_type == 'expired':
        results = Document.objects.filter(
            custom_values__custom_field__field_type='date',
            custom_values__value__lt=today_str,
            custom_values__custom_field__field_name__icontains='expire'
        ).distinct()
        title = "Expired Documents"

    return render(request, 'management/filtered_documents.html', {'results': results, 'title': title})

def setup_admin(request):
    if User.objects.filter(is_superuser=True).exists():
        return redirect('login')

    if request.method == 'POST':
        admin_user = request.POST.get('username')
        admin_pass = request.POST.get('password')
        
        if admin_user and admin_pass:
            user = User.objects.create_user(username=admin_user, password=admin_pass)
            user.is_superuser = True
            user.is_staff = True
            user.save()
            
            login(request, user)
            return redirect('setup_company')
            
    return render(request, 'management/setup_admin.html')


@login_required
def setup_company(request):
    if Company.objects.exists():
        return redirect('dashboard')

    if request.method == 'POST':
        name = request.POST.get('company_name')
        if name:
            company = Company.objects.create(name=name)
            
            company.email_address = request.POST.get('email_address', '')
            company.contact_number = request.POST.get('contact_number', '')
            company.country = request.POST.get('country', '')
            
            if request.FILES.get('company_logo'):
                company.logo = request.FILES.get('company_logo')
                
            company.save()
            
            # Since the user created their account in the previous step, request.user now works perfectly!
            HistoryLog.objects.create(user=request.user, action="Created", document_name="System Initialization", folder_path="Core Server")
            return redirect('dashboard')
            
    return render(request, 'management/setup_company.html')

@login_required
def download_backup(request):
    if not request.user.is_superuser:
        raise Http404("Only administrators can download backups.")
        
    try:
        backup_data = io.StringIO()
        call_command('dumpdata', stdout=backup_data)
        
        response = HttpResponse(backup_data.getvalue(), content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename="cmap_database_backup.json"'
        
        try:
            from .models import HistoryLog
            HistoryLog.objects.create(
                user=request.user, 
                action="Created", 
                document_name="PostgreSQL Database Backup", 
                folder_path="Core Server"
            )
            company = Company.objects.first()
            # --- TELEGRAM TRIGGER: CONTROLLED BY SETTINGS ---
            if company and getattr(company, 'alert_on_system', True):
                send_telegram_alert(f"💾 <b>DATABASE BACKUP INITIATED</b>\n\n👤 <b>{request.user.username.upper()}</b> successfully downloaded a copy of the core database.")
        except Exception:
            pass 
            
        return response
        
    except Exception as e:
        raise Http404(f"Critical Error generating backup: {str(e)}")
    
@login_required
def download_logs(request):
    if not request.user.is_superuser:
        raise Http404("Only administrators can download logs.")
        
    log_file = os.path.join(settings.BASE_DIR, 'tunnel.log')
    
    if os.path.exists(log_file):
        with open(log_file, 'rb') as f:
            response = HttpResponse(f.read(), content_type='text/plain')
            response['Content-Disposition'] = 'attachment; filename="cmap_server_logs.txt"'
            return response
    else:
        messages.warning(request, "System logs are empty because remote access has not been activated yet.")
        return redirect('settings')

@login_required
def user_settings(request):
    if not (request.user.is_superuser or request.session.get('admin_unlocked', False)):
        return redirect('dashboard')
    company = Company.objects.first()
    users = User.objects.all().order_by('id')
    return render(request, 'management/user.html', {
        'company': company,
        'users': users,
    })

@login_required
def theme_settings(request):
    company = Company.objects.first()
    return render(request, 'management/theme.html', {
        'company': company,
    })

import subprocess
import time

@login_required
def toggle_tunnel(request):
    if not (request.user.is_superuser or request.session.get('admin_unlocked', False)):
        return redirect('dashboard')
        
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'start':
            # Stop any existing ngrok process first
            os.system("taskkill /F /IM ngrok.exe /T > NUL 2>&1")
            try:
                # Start ngrok in background
                ngrok_path = os.path.join(settings.BASE_DIR, 'ngrok.exe')
                subprocess.Popen([ngrok_path, 'http', '8000'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Wait for ngrok to allocate public URL
                time.sleep(2.5)
                
                import urllib.request
                import json
                req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels")
                with urllib.request.urlopen(req) as response:
                    res = json.loads(response.read().decode())
                    public_url = res['tunnels'][0]['public_url']
                    request.session['tunnel_url'] = public_url
                    messages.success(request, "Remote Access Tunnel Started Successfully! 🚀")
            except Exception as e:
                messages.error(request, f"Failed to start remote tunnel: {str(e)}")
                
        elif action == 'stop':
            os.system("taskkill /F /IM ngrok.exe /T > NUL 2>&1")
            if 'tunnel_url' in request.session:
                del request.session['tunnel_url']
            messages.success(request, "Remote Access Tunnel Stopped.")
            
    return redirect('settings')