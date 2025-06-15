from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate
from .forms import SignUpForm, StudentProfileForm
from .models import Plan,JobApplier
import razorpay
from django.views.decorators.csrf import csrf_protect
import pandas as pd
import os, re
from datetime import datetime
from django.db import connections
from django.shortcuts import render
from django.contrib import messages
from datetime import date, timedelta
import pdfplumber
import docx


# Razorpay credentials
RAZORPAY_KEY_ID='rzp_test_Anl5NixDMZZiL0'
RAZORPAY_KEY_SECRET='2fQLWgSjV9PVLJA6ewSSOT6g'
client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = SignUpForm()
    return render(request, 'signup.html', {'form': form})

@csrf_protect
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            # Check if user is a JobApplier
            if hasattr(user, 'jobapplier'):
                return redirect('job_applier_dashboard')
            else:
                return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def job_applier_dashboard(request):
    return render(request, 'job_applier_dashboard.html')


def home(request):
    return render(request, 'home.html')

@login_required
def plans(request):
    plans = Plan.objects.all()
    return render(request, 'plans.html', {'plans': plans})


@login_required
def subscribe(request, plan_id):
    plan = get_object_or_404(Plan, id=plan_id)

    if request.method == 'POST':
        amount = int(plan.price * 100)
        order = client.order.create({
            'amount': amount,
            'currency': 'INR',
            'payment_capture': 1
        })

        context = {
            'plan': plan,
            'order_id': order['id'],
            'razorpay_key': RAZORPAY_KEY_ID,
            'amount': amount,
            'user': request.user
        }
        return render(request, 'payment_success.html', context)

    return redirect('plans')

def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

def extract_text_from_docx(file):
    doc = docx.Document(file)
    return "\n".join([para.text for para in doc.paragraphs])

def parse_resume(text):
    data = {
        'firstname': '',
        'lastname': '',
        'skills': '',
        'email': '',
        'description': ''
    }

    # First name & Last name (basic assumption based on first line or email)
    lines = text.strip().split('\n')
    if lines:
        name_parts = lines[0].split()
        if len(name_parts) >= 2:
            data['firstname'] = name_parts[0]
            data['lastname'] = name_parts[1]

    # Email
    email_match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    if email_match:
        data['email'] = email_match.group(0)

    # Skills
    skill_keywords = ['Python', 'Django', 'React', 'SQL', 'Machine Learning', 'Java', 'C++', 'HTML', 'CSS']
    skills_found = [skill for skill in skill_keywords if skill.lower() in text.lower()]
    data['skills'] = ", ".join(skills_found)

    # Description (just taking first 5 lines as summary)
    data['description'] = "\n".join(lines[1:6])

    return data


@login_required
def profile_form(request):
    initial_data = {}

    if request.method == 'POST':
        form = StudentProfileForm(request.POST, request.FILES)

        if request.FILES.get('resume'):
            resume = request.FILES['resume']
            text = ""
            if resume.name.endswith('.pdf'):
                text = extract_text_from_pdf(resume)
            elif resume.name.endswith('.docx'):
                text = extract_text_from_docx(resume)

            parsed_data = parse_resume(text)
            form = StudentProfileForm(initial=parsed_data)

        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.plan = Plan.objects.last()  # Update as needed
            profile.save()
            return redirect('home')
    else:
        form = StudentProfileForm()

    return render(request, 'profile_form.html', {'form': form})


@login_required
def upload_excel_view(request):
    if request.method == 'POST':
        file = request.FILES.get('file')

        if not file:
            messages.error(request, "Please upload a file.")
            return render(request, 'upload_excel.html')

        # Auto-generate table name from file name
        filename = os.path.splitext(file.name)[0]
        table_name = re.sub(r'\W+', '_', filename).lower()

        # Read Excel file into DataFrame
        df = pd.read_excel(file)

        required_columns = {'username', 'email', 'company name', 'location', 'date'}
        if not required_columns.issubset(df.columns):
            messages.error(request, "Excel must contain: username, email, company name, location, date")
            return render(request, 'upload.html')

        # Insert data into MySQL
        with connections['mysql_db'].cursor() as cursor:
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS `{table_name}` (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(100),
                    email VARCHAR(100),
                    company_name VARCHAR(100),
                    location VARCHAR(100),
                    date DATE
                )
            """)

            for _, row in df.iterrows():
                try:
                    date_value = (
                        row['date'] if isinstance(row['date'], datetime)
                        else datetime.strptime(str(row['date']), '%Y-%m-%d')
                    )
                except:
                    continue  # skip invalid date

                cursor.execute(f"""
                    INSERT INTO `{table_name}` (username, email, company_name, location, date)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    row['username'],
                    row['email'],
                    row['company name'],
                    row['location'],
                    date_value
                ))

        messages.success(request, f"Data uploaded to table '{table_name}' successfully.")
        return render(request, 'upload.html')

    return render(request, 'upload.html')


@login_required
def filter_data_view(request):
    results = []
    selected_filter = request.GET.get('filter', 'day')
    table_name = request.GET.get('table_name', 'user_data_200_records')  # default fallback

    if not table_name:
        return render(request, 'filter_data.html', {'records': [], 'selected_filter': selected_filter})

    today = date.today()
    params = []

    if selected_filter == 'day':
        query = f"SELECT * FROM `{table_name}` WHERE DATE(date) = %s"
        params.append(today)

    elif selected_filter == 'week':
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = today
        query = f"SELECT * FROM `{table_name}` WHERE DATE(date) BETWEEN %s AND %s"
        params.extend([start_of_week, end_of_week])

    elif selected_filter == 'month':
        query = f"SELECT * FROM `{table_name}` WHERE MONTH(date) = %s AND YEAR(date) = %s"
        params.extend([today.month, today.year])
    else:
        query = f"SELECT * FROM `{table_name}`"  # fallback

    # 🛠 Use MySQL DB explicitly
    with connections['mysql_db'].cursor() as cursor:
        try:
            cursor.execute(query, params)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            results = [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print("Error:", e)

    return render(request, 'filter_data.html', {'records': results, 'selected_filter': selected_filter})
