from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
import uuid

class Company(models.Model):
    """
    Company model for multi-tenant SaaS architecture.
    Each company represents a separate tenant with completely isolated data.
    """
    SUBSCRIPTION_PLANS = [
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
    ]
    
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar ($)'),
        ('EUR', 'Euro (€)'),
        ('GBP', 'British Pound (£)'),
        ('UZS', 'Uzbek Som (so\'m)'),
        ('RUB', 'Russian Ruble (₽)'),
    ]
    
    THEME_CHOICES = [
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('auto', 'Auto'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_name = models.CharField(max_length=200, verbose_name="Company Name")
    slug = models.SlugField(max_length=200, unique=True, verbose_name="Slug")
    logo = models.ImageField(upload_to='company_logos/', blank=True, null=True, verbose_name="Company Logo")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Phone Number")
    email = models.EmailField(verbose_name="Company Email")
    address = models.TextField(blank=True, null=True, verbose_name="Address")
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name="City")
    country = models.CharField(max_length=100, blank=True, null=True, verbose_name="Country")
    tax_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Tax Number")
    
    # Subscription
    subscription_plan = models.CharField(max_length=20, choices=SUBSCRIPTION_PLANS, default='free', verbose_name="Subscription Plan")
    subscription_start_date = models.DateField(blank=True, null=True, verbose_name="Subscription Start Date")
    subscription_end_date = models.DateField(blank=True, null=True, verbose_name="Subscription End Date")
    
    # Settings
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD', verbose_name="Currency")
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='auto', verbose_name="Theme")
    pos_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="POS Tax Rate (%)")
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name="Is Active")
    is_verified = models.BooleanField(default=False, verbose_name="Is Verified")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    
    class Meta:
        db_table = 'companies'
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['email']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.company_name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.company_name)
        super().save(*args, **kwargs)
    
    @property
    def is_subscription_active(self):
        if self.subscription_plan == 'free':
            return True
        if self.subscription_end_date:
            return self.subscription_end_date >= timezone.now().date()
        return False

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'SUPER_ADMIN')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    ROLE_CHOICES = [
        ('SUPER_ADMIN', 'Super Admin'),
        ('COMPANY_ADMIN', 'Company Admin'),
        ('MANAGER', 'Manager'),
        ('STAFF', 'Staff'),
        ('VIEWER', 'Viewer'),
    ]
    
    username = None
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='STAFF')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name='employees', verbose_name="Company")
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_password_change = models.DateTimeField(blank=True, null=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['company']),
            models.Index(fields=['role']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    def get_full_name(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.email
    
    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save()
    
    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.is_active = True
        self.save()
    
    def is_super_admin(self):
        return self.role == 'SUPER_ADMIN'
    
    def is_company_admin(self):
        return self.role == 'COMPANY_ADMIN'
    
    def is_manager(self):
        return self.role == 'MANAGER'
    
    def is_staff_user(self):
        return self.role == 'STAFF'
    
    def is_viewer(self):
        return self.role == 'VIEWER'
    
    def has_company_access(self):
        """Check if user has access to a company"""
        return self.company is not None or self.is_super_admin()
