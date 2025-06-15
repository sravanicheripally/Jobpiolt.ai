from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import StudentProfile

class SignUpForm(UserCreationForm):
    email = forms.EmailField()
    class Meta:
        model = User
        fields = ('username', 'email', 'password1')
        def __init__(self, *args, **kwargs):
            super(SignUpForm, self).__init__(*args, **kwargs)
            if 'password2' in self.fields:
                del self.fields['password2']

class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = '__all__'
        exclude = ['user', 'plan']