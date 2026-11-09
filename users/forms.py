from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from core.translations import t as translate
from .models import Company

User = get_user_model()

PASSWORD_ERROR_KEYS = {
    'password_too_similar': 'pw_err_similar',
    'password_too_similar_username': 'pw_err_similar_username',
    'password_too_short': 'pw_err_short',
    'password_too_common': 'pw_err_common',
    'password_entirely_numeric': 'pw_err_numeric',
}

COMPANY_PLACEHOLDER_KEYS = {
    'company_name': 'company_name_placeholder',
    'email': 'company_email_placeholder',
    'phone': 'phone_placeholder',
    'address': 'address_placeholder',
    'city': 'city_placeholder',
    'country': 'country_placeholder',
    'tax_number': 'tax_number_placeholder',
}

USER_PLACEHOLDER_KEYS = {
    'email': 'email_placeholder',
    'first_name': 'first_name_placeholder',
    'last_name': 'last_name_placeholder',
    'phone': 'phone_placeholder',
}


def _post_clean_registration(form):
    ModelForm._post_clean(form)
    password = form.cleaned_data.get('password1')
    if password:
        language = getattr(form, 'language', 'uz')
        try:
            validate_password(password, user=form.instance)
        except ValidationError as error:
            messages = [translate(PASSWORD_ERROR_KEYS.get(e.code, ''), language) if e.code in PASSWORD_ERROR_KEYS else str(e) for e in error.error_list]
            form.add_error('password2', messages)


def _clean_confirm_password(form):
    password1 = form.cleaned_data.get('password1')
    password2 = form.cleaned_data.get('password2')
    if password1 and password2 and password1 != password2:
        language = getattr(form, 'language', 'uz')
        raise ValidationError(translate('pw_err_mismatch', language), code='password_mismatch')
    return password2


from core.lang import ph

class CompanyRegistrationForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['company_name', 'email', 'phone', 'address', 'city', 'country', 'tax_number']
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ph('ph_company_name')}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': ph('ph_email')}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ph('ph_phone_num')}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'placeholder': ph('ph_address'), 'rows': 3}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ph('ph_city')}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ph('ph_country')}),
            'tax_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ph('ph_tax_number')}),
        }

    def __init__(self, *args, language='uz', **kwargs):
        super().__init__(*args, **kwargs)
        self.language = language
        for name, key in COMPANY_PLACEHOLDER_KEYS.items():
            if name in self.fields:
                self.fields[name].widget.attrs['placeholder'] = translate(key, self.language)


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': ph('ph_email')})
    )
    first_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': ph('ph_first_name')})
    )
    last_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': ph('ph_last_name')})
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': ph('ph_phone_num')})
    )

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone', 'password1', 'password2']

    def __init__(self, *args, language='uz', **kwargs):
        super().__init__(*args, **kwargs)
        self.language = language
        self.fields['password1'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': translate('password_placeholder', self.language)})
        self.fields['password2'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': translate('confirm_password_placeholder', self.language)})
        for name, key in USER_PLACEHOLDER_KEYS.items():
            if name in self.fields:
                self.fields[name].widget.attrs['placeholder'] = translate(key, self.language)

    def _post_clean(self):
        _post_clean_registration(self)

    def clean_password2(self):
        return _clean_confirm_password(self)


class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': ph('ph_old_password')})
    )
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': ph('ph_new_password')})
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': ph('ph_confirm_new_password')})
    )


class CustomPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': ph('ph_email')})
    )


class CustomSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': ph('ph_new_password')})
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': ph('ph_confirm_new_password')})
    )


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'profile_picture', 'date_of_birth', 'address', 'city', 'country']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
        }


class EmployeeCreateForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': ph('ph_email')})
    )
    first_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': ph('ph_first_name')})
    )
    last_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': ph('ph_last_name')})
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': ph('ph_phone_num')})
    )
    role = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone', 'role', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': ph('ph_password')})
        self.fields['password2'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': ph('ph_confirm_password')})
        # Filter out SUPER_ADMIN role
        self.fields['role'].choices = [choice for choice in User.ROLE_CHOICES if choice[0] != 'SUPER_ADMIN']

    def _post_clean(self):
        _post_clean_registration(self)

    def clean_password2(self):
        return _clean_confirm_password(self)


class EmployeeUpdateForm(forms.ModelForm):
    role = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'role', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter out SUPER_ADMIN role
        self.fields['role'].choices = [choice for choice in User.ROLE_CHOICES if choice[0] != 'SUPER_ADMIN']
