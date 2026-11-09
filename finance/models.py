from django.conf import settings
from django.db import models
from django.utils import timezone
from users.models import Company

class CustomerDebt(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'To\'lanmagan'),
        ('partial', 'Qisman to\'langan'),
        ('paid', 'To\'liq to\'langan'),
        ('overdue', 'Muddati o\'tgan'),
    ]
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='company_customer_debts', null=True, blank=True, verbose_name="Company")
    customer_name = models.CharField(max_length=200, verbose_name="Mijoz nomi")
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefon raqami")
    debt_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Qarz miqdori")
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="To'langan miqdor")
    due_date = models.DateField(verbose_name="To'lov muddati")
    notes = models.TextField(blank=True, null=True, verbose_name="Izohlar")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid', verbose_name="To'lov holati")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='customer_debts_created')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Mijoz qarzi"
        verbose_name_plural = "Mijoz qarzlari"
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['customer_name']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['due_date']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.customer_name} - ${self.remaining_balance}"
    
    @property
    def remaining_balance(self):
        return self.debt_amount - self.paid_amount
    
    @property
    def is_overdue(self):
        return self.due_date < timezone.now().date() and self.payment_status != 'paid'
    
    def update_payment_status(self):
        if self.paid_amount >= self.debt_amount:
            self.payment_status = 'paid'
        elif self.paid_amount > 0:
            self.payment_status = 'partial'
        elif self.is_overdue:
            self.payment_status = 'overdue'
        else:
            self.payment_status = 'unpaid'
        self.save()

class SupplierDebt(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'To\'lanmagan'),
        ('partial', 'Qisman to\'langan'),
        ('paid', 'To\'liq to\'langan'),
        ('overdue', 'Muddati o\'tgan'),
    ]
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='company_supplier_debts', null=True, blank=True, verbose_name="Company")
    supplier_name = models.CharField(max_length=200, verbose_name="Taminotchi nomi")
    amount_owed = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Qarz miqdori")
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="To'langan miqdor")
    due_date = models.DateField(verbose_name="To'lov muddati")
    notes = models.TextField(blank=True, null=True, verbose_name="Izohlar")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid', verbose_name="To'lov holati")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='supplier_debts_created')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Taminotchi qarzi"
        verbose_name_plural = "Taminotchi qarzlari"
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['supplier_name']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['due_date']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.supplier_name} - ${self.remaining_balance}"
    
    @property
    def remaining_balance(self):
        return self.amount_owed - self.paid_amount
    
    @property
    def is_overdue(self):
        return self.due_date < timezone.now().date() and self.payment_status != 'paid'
    
    def update_payment_status(self):
        if self.paid_amount >= self.amount_owed:
            self.payment_status = 'paid'
        elif self.paid_amount > 0:
            self.payment_status = 'partial'
        elif self.is_overdue:
            self.payment_status = 'overdue'
        else:
            self.payment_status = 'unpaid'
        self.save()

class Payment(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('customer', 'Mijoz to\'lovi'),
        ('supplier', 'Taminotchi to\'lovi'),
    ]
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='company_payments', null=True, blank=True, verbose_name="Company")
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, verbose_name="To'lov turi")
    customer_debt = models.ForeignKey(CustomerDebt, on_delete=models.CASCADE, null=True, blank=True, related_name='payments')
    supplier_debt = models.ForeignKey(SupplierDebt, on_delete=models.CASCADE, null=True, blank=True, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="To'lov miqdori")
    payment_date = models.DateTimeField(default=timezone.now, verbose_name="To'lov sanasi")
    notes = models.TextField(blank=True, null=True, verbose_name="Izohlar")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='payments_created')
    
    class Meta:
        ordering = ['-payment_date']
        verbose_name = "To'lov"
        verbose_name_plural = "To'lovlar"
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['payment_type']),
            models.Index(fields=['payment_date']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        if self.customer_debt:
            return f"{self.customer_debt.customer_name} - ${self.amount}"
        elif self.supplier_debt:
            return f"{self.supplier_debt.supplier_name} - ${self.amount}"
        return f"To'lov - ${self.amount}"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            from django.db.models import F
            if self.customer_debt:
                CustomerDebt.objects.filter(pk=self.customer_debt_id).update(paid_amount=F('paid_amount') + self.amount)
                debt = CustomerDebt.objects.get(pk=self.customer_debt_id)
                debt.update_payment_status()
            elif self.supplier_debt:
                SupplierDebt.objects.filter(pk=self.supplier_debt_id).update(paid_amount=F('paid_amount') + self.amount)
                debt = SupplierDebt.objects.get(pk=self.supplier_debt_id)
                debt.update_payment_status()


# ============================================================
# NEW FINANCE MODELS — Phase 12
# ============================================================

class FinancialAccount(models.Model):
    ACCOUNT_TYPE_CHOICES = [
        ('cash', 'Cash'), ('bank', 'Bank'), ('mobile', 'Mobile Wallet'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='financial_accounts')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, blank=True)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, default='cash')
    currency = models.CharField(max_length=3, default='UZS')
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = ['company', 'code']

    def __str__(self):
        return f"{self.name} ({self.get_account_type_display()})"

    @property
    def current_balance(self):
        from django.db.models import Sum, Q
        income = FinancialTransaction.objects.filter(
            account=self, status='completed'
        ).aggregate(s=Sum('amount', filter=Q(direction='income')))['s'] or 0
        expense = FinancialTransaction.objects.filter(
            account=self, status='completed'
        ).aggregate(s=Sum('amount', filter=Q(direction='expense')))['s'] or 0
        return self.opening_balance + income - expense


class ExpenseCategory(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='expense_categories')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Expense categories'

    def __str__(self):
        return self.name


class IncomeCategory(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='income_categories')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Income categories'

    def __str__(self):
        return self.name


class FinancialTransaction(models.Model):
    TYPE_CHOICES = [
        ('sale', 'Sale'), ('purchase', 'Purchase'),
        ('customer_payment', 'Customer Payment'), ('supplier_payment', 'Supplier Payment'),
        ('customer_refund', 'Customer Refund'), ('supplier_refund', 'Supplier Refund'),
        ('income', 'Income'), ('expense', 'Expense'),
        ('transfer_in', 'Transfer In'), ('transfer_out', 'Transfer Out'),
        ('adjustment', 'Adjustment'),
    ]
    DIRECTION_CHOICES = [('income', 'Income'), ('expense', 'Expense')]
    STATUS_CHOICES = [('completed', 'Completed'), ('pending', 'Pending'), ('reversed', 'Reversed')]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='financial_transactions')
    date = models.DateField(default=timezone.now)
    txn_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default='UZS')
    account = models.ForeignKey(FinancialAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    category = models.CharField(max_length=100, blank=True)
    customer = models.ForeignKey('sales.Customer', on_delete=models.SET_NULL, null=True, blank=True)
    supplier = models.ForeignKey('purchases.Supplier', on_delete=models.SET_NULL, null=True, blank=True)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.PositiveIntegerField(null=True, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    payment_method = models.CharField(max_length=20, blank=True, choices=[
        ('cash', 'Cash'), ('card', 'Card'), ('transfer', 'Bank Transfer'),
        ('terminal', 'Terminal'), ('online', 'Online'), ('other', 'Other'),
    ])
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['company', 'date']),
            models.Index(fields=['txn_type']),
            models.Index(fields=['direction']),
            models.Index(fields=['status']),
            models.Index(fields=['reference_type', 'reference_id']),
        ]

    def __str__(self):
        return f"{self.get_txn_type_display()}: {self.amount} ({self.date})"


class AccountTransfer(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='account_transfers')
    date = models.DateField(default=timezone.now)
    from_account = models.ForeignKey(FinancialAccount, on_delete=models.CASCADE, related_name='transfers_out')
    to_account = models.ForeignKey(FinancialAccount, on_delete=models.CASCADE, related_name='transfers_in')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default='UZS')
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=[
        ('completed', 'Completed'), ('pending', 'Pending'), ('reversed', 'Reversed'),
    ], default='completed')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.from_account} → {self.to_account}: {self.amount}"


class Budget(models.Model):
    PERIOD_CHOICES = [('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('annual', 'Annual')]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='budgets')
    name = models.CharField(max_length=200)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, related_name='budgets')
    period_type = models.CharField(max_length=20, choices=PERIOD_CHOICES, default='monthly')
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField(null=True, blank=True)
    planned_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    actual_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=[
        ('active', 'Active'), ('closed', 'Closed'),
    ], default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['year', 'month', 'category__name']

    def __str__(self):
        return f"{self.name} ({self.year})"

    @property
    def variance(self):
        return self.actual_amount - self.planned_amount

    @property
    def variance_pct(self):
        if self.planned_amount:
            return round((self.actual_amount - self.planned_amount) / self.planned_amount * 100, 1)
        return 0


class ExchangeRate(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='exchange_rates')
    base_currency = models.CharField(max_length=3)
    quote_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=12, decimal_places=6)
    date = models.DateField(default=timezone.now)
    source = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        unique_together = ['company', 'base_currency', 'quote_currency', 'date']

    def __str__(self):
        return f"{self.base_currency}/{self.quote_currency}: {self.rate}"


class PurchasePayment(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='purchase_payments')
    purchase = models.ForeignKey('purchases.Purchase', on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=[
        ('cash', 'Cash'), ('card', 'Card'), ('transfer', 'Bank Transfer'),
        ('terminal', 'Terminal'), ('other', 'Other'),
    ], default='cash')
    payment_date = models.DateField(default=timezone.now)
    account = models.ForeignKey(FinancialAccount, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"Payment for {self.purchase}: {self.amount}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            from django.db.models import F
            purchase = self.purchase
            total_paid = purchase.payments.aggregate(s=models.Sum('amount'))['s'] or 0
            if total_paid >= purchase.total:
                purchase.payment_status = 'paid'
            elif total_paid > 0:
                purchase.payment_status = 'partial'
            else:
                purchase.payment_status = 'unpaid'
            purchase.save(update_fields=['payment_status'])

