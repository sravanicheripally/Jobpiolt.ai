from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate
from .forms import SignUpForm, StudentProfileForm
from .models import Plan
import razorpay

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

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

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

@login_required
def profile_form(request):
    if request.method == 'POST':
        form = StudentProfileForm(request.POST, request.FILES)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.plan = Plan.objects.last()  # You can update this logic
            profile.save()
            return redirect('home')
    else:
        form = StudentProfileForm()
    return render(request, 'profile_form.html', {'form': form})