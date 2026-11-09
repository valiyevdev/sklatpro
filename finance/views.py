from django.shortcuts import render, redirect, get_object_or_404

from django.contrib.auth.decorators import login_required

from django.contrib import messages

from django.db.models import Sum, Q

from django.core.paginator import Paginator

from django.utils import timezone

from django.db.models.functions import TruncMonth

from datetime import timedelta, date

from django.views.decorators.cache import never_cache

from .models import (CustomerDebt, SupplierDebt, Payment,
    FinancialAccount, FinancialTransaction, AccountTransfer,
    ExpenseCategory, IncomeCategory, Budget, PurchasePayment)

from .forms import CustomerDebtForm, SupplierDebtForm, PaymentForm

from activity.models import Activity
from core.translations import get_translation



@login_required

@never_cache

def financial_dashboard(request):
    lang = request.session.get('language', 'uz')

    # Get company

    company = request.user.company

    if not company and not request.user.is_superuser:

        messages.error(request, get_translation('no_company_assigned', lang))

        return redirect('login')

    

    # Filter by company

    if company:

        customer_debts = CustomerDebt.objects.filter(company=company)

        supplier_debts = SupplierDebt.objects.filter(company=company)

        payments = Payment.objects.filter(company=company)

    else:

        # Superuser sees all

        customer_debts = CustomerDebt.objects.all()

        supplier_debts = SupplierDebt.objects.all()

        payments = Payment.objects.all()

    

    # Customer Debt Statistics

    total_customer_debts = customer_debts.aggregate(total=Sum('debt_amount'))['total'] or 0

    total_customer_paid = customer_debts.aggregate(total=Sum('paid_amount'))['total'] or 0

    total_customer_outstanding = total_customer_debts - total_customer_paid

    

    # Supplier Debt Statistics

    total_supplier_debts = supplier_debts.aggregate(total=Sum('amount_owed'))['total'] or 0

    total_supplier_paid = supplier_debts.aggregate(total=Sum('paid_amount'))['total'] or 0

    total_supplier_outstanding = total_supplier_debts - total_supplier_paid

    

    # Total Outstanding

    total_outstanding = total_customer_outstanding + total_supplier_outstanding

    

    # Overdue Debts

    overdue_customer_debts = customer_debts.filter(due_date__lt=timezone.now().date(), payment_status__in=['unpaid', 'partial'])

    overdue_supplier_debts = supplier_debts.filter(due_date__lt=timezone.now().date(), payment_status__in=['unpaid', 'partial'])

    total_overdue = overdue_customer_debts.count() + overdue_supplier_debts.count()

    

    # Today's Collections

    today = timezone.now().date()

    today_payments = payments.filter(payment_date__date=today).aggregate(total=Sum('amount'))['total'] or 0

    

    # Monthly Collections

    thirty_days_ago = timezone.now() - timedelta(days=30)

    monthly_payments = payments.filter(payment_date__gte=thirty_days_ago).aggregate(total=Sum('amount'))['total'] or 0

    

    # Recent Debts

    recent_customer_debts = customer_debts.select_related('created_by').order_by('-created_at')[:5]

    recent_supplier_debts = supplier_debts.select_related('created_by').order_by('-created_at')[:5]

    

    # Recent Payments

    recent_payments = payments.select_related('created_by').order_by('-payment_date')[:10]

    

    # Phase 12 Stats

    if company:
        total_income = FinancialTransaction.objects.filter(
            company=company, direction='income', status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0

        total_expense = FinancialTransaction.objects.filter(
            company=company, direction='expense', status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0

        accounts = FinancialAccount.objects.filter(company=company)

        recent_transactions = FinancialTransaction.objects.filter(
            company=company
        ).order_by('-date', '-created_at')[:10]

        from purchases.models import Purchase
        unpaid_purchases = Purchase.objects.filter(
            company=company
        ).exclude(payment_status='paid').count()

    else:
        total_income = FinancialTransaction.objects.filter(
            direction='income', status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0

        total_expense = FinancialTransaction.objects.filter(
            direction='expense', status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0

        accounts = FinancialAccount.objects.all()

        recent_transactions = FinancialTransaction.objects.all().order_by(
            '-date', '-created_at'
        )[:10]

        from purchases.models import Purchase
        unpaid_purchases = Purchase.objects.exclude(
            payment_status='paid'
        ).count()

    net_profit = total_income - total_expense

    

    context = {

        'company': company,

        'total_customer_debts': total_customer_debts,

        'total_customer_paid': total_customer_paid,

        'total_customer_outstanding': total_customer_outstanding,

        'total_supplier_debts': total_supplier_debts,

        'total_supplier_paid': total_supplier_paid,

        'total_supplier_outstanding': total_supplier_outstanding,

        'total_outstanding': total_outstanding,

        'total_overdue': total_overdue,

        'today_payments': today_payments,

        'monthly_payments': monthly_payments,

        'recent_customer_debts': recent_customer_debts,

        'recent_supplier_debts': recent_supplier_debts,

        'recent_payments': recent_payments,

        'total_income': total_income,

        'total_expense': total_expense,

        'net_profit': net_profit,

        'accounts': accounts,

        'recent_transactions': recent_transactions,

        'unpaid_purchases': unpaid_purchases,

    }

    return render(request, 'finance/financial_dashboard.html', context)



@login_required

@never_cache

def customer_debt_list(request):
    lang = request.session.get('language', 'uz')

    # Get company

    company = request.user.company

    if not company and not request.user.is_superuser:

        messages.error(request, get_translation('no_company_assigned', lang))

        return redirect('login')

    

    # Filter by company

    if company:

        debts = CustomerDebt.objects.filter(company=company)

    else:

        debts = CustomerDebt.objects.all()

    

    # Search

    search_query = request.GET.get('search', '')

    if search_query:

        debts = debts.filter(

            Q(customer_name__icontains=search_query) |

            Q(phone_number__icontains=search_query)

        )

    

    # Status filter

    status_filter = request.GET.get('status', '')

    if status_filter:

        debts = debts.filter(payment_status=status_filter)

    

    # Sorting

    sort_by = request.GET.get('sort', '-created_at')

    valid_sort_fields = ['customer_name', '-customer_name', 'debt_amount', '-debt_amount', 'due_date', '-due_date', 'created_at', '-created_at']

    if sort_by in valid_sort_fields:

        debts = debts.order_by(sort_by)

    

    paginator = Paginator(debts, 20)

    page_number = request.GET.get('page')

    page_obj = paginator.get_page(page_number)

    

    context = {

        'page_obj': page_obj,

        'search_query': search_query,

        'status_filter': status_filter,

        'sort_by': sort_by,

        'company': company,

    }

    return render(request, 'finance/customer_debt_list.html', context)



@login_required

@never_cache

def customer_debt_create(request):
    lang = request.session.get('language', 'uz')

    # Get company

    company = request.user.company

    if not company and not request.user.is_superuser:

        messages.error(request, get_translation('no_company_assigned', lang))

        return redirect('login')

    

    if request.method == 'POST':

        form = CustomerDebtForm(request.POST)

        if form.is_valid():

            debt = form.save(commit=False)

            debt.created_by = request.user

            debt.company = company

            debt.save()

            Activity.log_activity(

                activity_type='customer_debt_created',

                description=f'"{debt.customer_name}" mijoz qarzi yaratildi. Qarz miqdori: ${debt.debt_amount}',

                user=request.user,

                related_object_type='CustomerDebt',

                related_object_id=debt.id

            )

            messages.success(request, get_translation('customer_debt_created', lang))

            return redirect('finance:customer_debt_list')

    else:

        form = CustomerDebtForm()

    

    return render(request, 'finance/customer_debt_form.html', {

        'form': form,

        'title': 'Mijoz qarzi qo\'shish',

        'company': company,

    })



@login_required

@never_cache

def customer_debt_update(request, pk):
    lang = request.session.get('language', 'uz')

    debt = get_object_or_404(CustomerDebt, pk=pk)

    

    # Check if user has access to this debt

    if not request.user.is_superuser:

        if not request.user.company or debt.company != request.user.company:

            messages.error(request, get_translation('permission_debt_access', lang))

            return redirect('finance:customer_debt_list')

    

    if request.method == 'POST':

        form = CustomerDebtForm(request.POST, instance=debt)

        if form.is_valid():

            form.save()

            Activity.log_activity(

                activity_type='customer_debt_updated',

                description=f'"{debt.customer_name}" mijoz qarzi yangilandi. Qarz miqdori: ${debt.debt_amount}',

                user=request.user,

                related_object_type='CustomerDebt',

                related_object_id=debt.id

            )

            messages.success(request, get_translation('customer_debt_updated', lang))

            return redirect('finance:customer_debt_list')

    else:

        form = CustomerDebtForm(instance=debt)

    

    return render(request, 'finance/customer_debt_form.html', {

        'form': form,

        'debt': debt,

        'title': 'Mijoz qarzini tahrirlash',

        'company': request.user.company,

    })



@login_required

def customer_debt_detail(request, pk):
    lang = request.session.get('language', 'uz')

    debt = get_object_or_404(CustomerDebt, pk=pk)

    

    # Check if user has access to this debt

    if not request.user.is_superuser:

        if not request.user.company or debt.company != request.user.company:

            messages.error(request, get_translation('permission_debt_access', lang))

            return redirect('finance:customer_debt_list')

    

    payments = debt.payments.all()

    

    context = {

        'debt': debt,

        'payments': payments,

        'company': request.user.company,

    }

    return render(request, 'finance/customer_debt_detail.html', context)



@login_required

@never_cache

def customer_debt_delete(request, pk):
    lang = request.session.get('language', 'uz')

    debt = get_object_or_404(CustomerDebt, pk=pk)

    

    # Check if user has access to this debt

    if not request.user.is_superuser:

        if not request.user.company or debt.company != request.user.company:

            messages.error(request, get_translation('permission_debt_access', lang))

            return redirect('finance:customer_debt_list')

    

    if request.method == 'POST':

        customer_name = debt.customer_name

        debt_amount = debt.debt_amount

        debt.delete()

        Activity.log_activity(

            activity_type='customer_debt_updated',

            description=f'"{customer_name}" mijoz qarzi o\'chirildi. Qarz miqdori: ${debt_amount}',

            user=request.user,

            related_object_type='CustomerDebt',

            related_object_id=pk

        )

        messages.success(request, get_translation('customer_debt_deleted', lang))

        return redirect('finance:customer_debt_list')

    

    return render(request, 'finance/customer_debt_confirm_delete.html', {

        'debt': debt,

        'company': request.user.company,

    })



@login_required

@never_cache

def supplier_debt_list(request):
    lang = request.session.get('language', 'uz')

    # Get company

    company = request.user.company

    if not company and not request.user.is_superuser:

        messages.error(request, get_translation('no_company_assigned', lang))

        return redirect('login')

    

    # Filter by company

    if company:

        debts = SupplierDebt.objects.filter(company=company)

    else:

        debts = SupplierDebt.objects.all()

    

    # Search

    search_query = request.GET.get('search', '')

    if search_query:

        debts = debts.filter(supplier_name__icontains=search_query)

    

    # Status filter

    status_filter = request.GET.get('status', '')

    if status_filter:

        debts = debts.filter(payment_status=status_filter)

    

    # Sorting

    sort_by = request.GET.get('sort', '-created_at')

    valid_sort_fields = ['supplier_name', '-supplier_name', 'amount_owed', '-amount_owed', 'due_date', '-due_date', 'created_at', '-created_at']

    if sort_by in valid_sort_fields:

        debts = debts.order_by(sort_by)

    

    paginator = Paginator(debts, 20)

    page_number = request.GET.get('page')

    page_obj = paginator.get_page(page_number)

    

    context = {

        'page_obj': page_obj,

        'search_query': search_query,

        'status_filter': status_filter,

        'sort_by': sort_by,

        'company': company,

    }

    return render(request, 'finance/supplier_debt_list.html', context)



@login_required

@never_cache

def supplier_debt_create(request):
    lang = request.session.get('language', 'uz')

    # Get company

    company = request.user.company

    if not company and not request.user.is_superuser:

        messages.error(request, get_translation('no_company_assigned', lang))

        return redirect('login')

    

    if request.method == 'POST':

        form = SupplierDebtForm(request.POST)

        if form.is_valid():

            debt = form.save(commit=False)

            debt.created_by = request.user

            debt.company = company

            debt.save()

            Activity.log_activity(

                activity_type='supplier_debt_created',

                description=f'"{debt.supplier_name}" taminotchi qarzi yaratildi. Qarz miqdori: ${debt.amount_owed}',

                user=request.user,

                related_object_type='SupplierDebt',

                related_object_id=debt.id

            )

            messages.success(request, get_translation('supplier_debt_created', lang))

            return redirect('finance:supplier_debt_list')

    else:

        form = SupplierDebtForm()

    

    return render(request, 'finance/supplier_debt_form.html', {

        'form': form,

        'title': 'Taminotchi qarzi qo\'shish',

        'company': company,

    })



@login_required

@never_cache

def supplier_debt_update(request, pk):
    lang = request.session.get('language', 'uz')

    debt = get_object_or_404(SupplierDebt, pk=pk)

    

    # Check if user has access to this debt

    if not request.user.is_superuser:

        if not request.user.company or debt.company != request.user.company:

            messages.error(request, get_translation('permission_debt_access', lang))

            return redirect('finance:supplier_debt_list')

    

    if request.method == 'POST':

        form = SupplierDebtForm(request.POST, instance=debt)

        if form.is_valid():

            form.save()

            Activity.log_activity(

                activity_type='supplier_debt_updated',

                description=f'"{debt.supplier_name}" taminotchi qarzi yangilandi. Qarz miqdori: ${debt.amount_owed}',

                user=request.user,

                related_object_type='SupplierDebt',

                related_object_id=debt.id

            )

            messages.success(request, get_translation('supplier_debt_updated', lang))

            return redirect('finance:supplier_debt_list')

    else:

        form = SupplierDebtForm(instance=debt)

    

    return render(request, 'finance/supplier_debt_form.html', {

        'form': form,

        'debt': debt,

        'title': 'Taminotchi qarzini tahrirlash',

        'company': request.user.company,

    })



@login_required

def supplier_debt_detail(request, pk):
    lang = request.session.get('language', 'uz')

    debt = get_object_or_404(SupplierDebt, pk=pk)

    

    # Check if user has access to this debt

    if not request.user.is_superuser:

        if not request.user.company or debt.company != request.user.company:

            messages.error(request, get_translation('permission_debt_access', lang))

            return redirect('finance:supplier_debt_list')

    

    payments = debt.payments.all()

    

    context = {

        'debt': debt,

        'payments': payments,

        'company': request.user.company,

    }

    return render(request, 'finance/supplier_debt_detail.html', context)



@login_required

@never_cache

def supplier_debt_delete(request, pk):
    lang = request.session.get('language', 'uz')

    debt = get_object_or_404(SupplierDebt, pk=pk)

    

    # Check if user has access to this debt

    if not request.user.is_superuser:

        if not request.user.company or debt.company != request.user.company:

            messages.error(request, get_translation('permission_debt_access', lang))

            return redirect('finance:supplier_debt_list')

    

    if request.method == 'POST':

        supplier_name = debt.supplier_name

        amount_owed = debt.amount_owed

        debt.delete()

        Activity.log_activity(

            activity_type='supplier_debt_updated',

            description=f'"{supplier_name}" taminotchi qarzi o\'chirildi. Qarz miqdori: ${amount_owed}',

            user=request.user,

            related_object_type='SupplierDebt',

            related_object_id=pk

        )

        messages.success(request, get_translation('supplier_debt_deleted', lang))

        return redirect('finance:supplier_debt_list')

    

    return render(request, 'finance/supplier_debt_confirm_delete.html', {

        'debt': debt,

        'company': request.user.company,

    })



@login_required

@never_cache

def payment_create(request, debt_type, debt_id):
    lang = request.session.get('language', 'uz')

    # Get company

    company = request.user.company

    if not company and not request.user.is_superuser:

        messages.error(request, get_translation('no_company_assigned', lang))

        return redirect('login')

    

    if debt_type == 'customer':

        debt = get_object_or_404(CustomerDebt, pk=debt_id)

    elif debt_type == 'supplier':

        debt = get_object_or_404(SupplierDebt, pk=debt_id)

    else:

        messages.error(request, get_translation('invalid_debt_type', lang))

        return redirect('finance:financial_dashboard')

    

    # Check if user has access to this debt

    if not request.user.is_superuser:

        if not request.user.company or debt.company != request.user.company:

            messages.error(request, get_translation('permission_debt_access', lang))

            return redirect('finance:financial_dashboard')

    

    if request.method == 'POST':

        form = PaymentForm(request.POST)

        if form.is_valid():

            payment = form.save(commit=False)

            payment.created_by = request.user

            payment.company = company

            payment.payment_type = debt_type

            if debt_type == 'customer':

                payment.customer_debt = debt

                activity_type = 'customer_debt_paid'

                description = f'"{debt.customer_name}" mijoz qarziga to\'lov qo\'shildi. Miqdor: ${payment.amount}'

            else:

                payment.supplier_debt = debt

                activity_type = 'supplier_debt_paid'

                description = f'"{debt.supplier_name}" taminotchi qarziga to\'lov qo\'shildi. Miqdor: ${payment.amount}'

            payment.save()

            Activity.log_activity(

                activity_type=activity_type,

                description=description,

                user=request.user,

                related_object_type='Payment',

                related_object_id=payment.id

            )

            messages.success(request, get_translation('payment_added', lang))

            if debt_type == 'customer':

                return redirect('finance:customer_debt_detail', pk=debt_id)

            else:

                return redirect('finance:supplier_debt_detail', pk=debt_id)

    else:

        form = PaymentForm()

    

    return render(request, 'finance/payment_form.html', {

        'form': form,

        'debt': debt,

        'debt_type': debt_type,

        'title': 'To\'lov qo\'shish',

        'company': company,

    })



@login_required

@never_cache

def customer_profile(request, customer_name):
    lang = request.session.get('language', 'uz')

    # Get company

    company = request.user.company

    if not company and not request.user.is_superuser:

        messages.error(request, get_translation('no_company_assigned', lang))

        return redirect('login')

    

    # Filter by company

    if company:

        debts = CustomerDebt.objects.filter(company=company, customer_name=customer_name).order_by('-created_at')

    else:

        debts = CustomerDebt.objects.filter(customer_name=customer_name).order_by('-created_at')

    

    if not debts:

        messages.error(request, get_translation('customer_not_found', lang))

        return redirect('finance:customer_debt_list')

    

    # Calculate totals

    total_debt = debts.aggregate(total=Sum('debt_amount'))['total'] or 0

    total_paid = debts.aggregate(total=Sum('paid_amount'))['total'] or 0

    total_remaining = total_debt - total_paid

    

    # Get all payments for this customer

    if company:

        payments = Payment.objects.filter(company=company, customer_debt__customer_name=customer_name).order_by('-payment_date')

    else:

        payments = Payment.objects.filter(customer_debt__customer_name=customer_name).order_by('-payment_date')

    

    context = {

        'customer_name': customer_name,

        'debts': debts,

        'payments': payments,

        'total_debt': total_debt,

        'total_paid': total_paid,

        'total_remaining': total_remaining,

        'company': company,

    }

    return render(request, 'finance/customer_profile.html', context)



@login_required

@never_cache

def supplier_profile(request, supplier_name):
    lang = request.session.get('language', 'uz')

    # Get company

    company = request.user.company

    if not company and not request.user.is_superuser:

        messages.error(request, get_translation('no_company_assigned', lang))

        return redirect('login')

    

    # Filter by company

    if company:

        debts = SupplierDebt.objects.filter(company=company, supplier_name=supplier_name).order_by('-created_at')

    else:

        debts = SupplierDebt.objects.filter(supplier_name=supplier_name).order_by('-created_at')

    

    if not debts:

        messages.error(request, get_translation('supplier_not_found', lang))

        return redirect('finance:supplier_debt_list')

    

    # Calculate totals

    total_debt = debts.aggregate(total=Sum('amount_owed'))['total'] or 0

    total_paid = debts.aggregate(total=Sum('paid_amount'))['total'] or 0

    total_remaining = total_debt - total_paid

    

    # Get all payments for this supplier

    if company:

        payments = Payment.objects.filter(company=company, supplier_debt__supplier_name=supplier_name).order_by('-payment_date')

    else:

        payments = Payment.objects.filter(supplier_debt__supplier_name=supplier_name).order_by('-payment_date')

    

    context = {

        'supplier_name': supplier_name,

        'debts': debts,

        'payments': payments,

        'total_debt': total_debt,

        'total_paid': total_paid,

        'total_remaining': total_remaining,

        'company': company,

    }

    return render(request, 'finance/supplier_profile.html', context)



# ============================================================
# Finance Phase 12
# ============================================================



def _get_company(user):
    return getattr(user, 'company', None)



def _require_company(request, lang):
    company = _get_company(request.user)
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return None, redirect('login')
    return company, None



@login_required
@never_cache
def transaction_list(request):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    if company:
        txns = FinancialTransaction.objects.filter(company=company)
    else:
        txns = FinancialTransaction.objects.all()

    search_query = request.GET.get('search', '')
    if search_query:
        txns = txns.filter(
            Q(description__icontains=search_query) |
            Q(reference_number__icontains=search_query)
        )

    type_filter = request.GET.get('type', '')
    if type_filter:
        txns = txns.filter(txn_type=type_filter)

    direction_filter = request.GET.get('direction', '')
    if direction_filter:
        txns = txns.filter(direction=direction_filter)

    date_from = request.GET.get('date_from', '')
    if date_from:
        txns = txns.filter(date__gte=date_from)

    date_to = request.GET.get('date_to', '')
    if date_to:
        txns = txns.filter(date__lte=date_to)

    txns = txns.order_by('-date', '-created_at')

    paginator = Paginator(txns, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'type_filter': type_filter,
        'direction_filter': direction_filter,
        'date_from': date_from,
        'date_to': date_to,
        'company': company,
    }
    return render(request, 'finance/transaction_list.html', context)



@login_required
@never_cache
def transaction_create(request):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    if request.method == 'POST':
        txn = FinancialTransaction(
            company=company,
            created_by=request.user,
            date=request.POST.get('date', timezone.now().date()),
            txn_type=request.POST.get('txn_type', ''),
            direction=request.POST.get('direction', ''),
            amount=request.POST.get('amount', 0),
            category=request.POST.get('category', ''),
            description=request.POST.get('description', ''),
            payment_method=request.POST.get('payment_method', ''),
            reference_number=request.POST.get('reference_number', ''),
        )
        account_id = request.POST.get('account')
        if account_id:
            txn.account = FinancialAccount.objects.filter(pk=account_id, company=company).first()
        txn.save()

        Activity.log_activity(
            activity_type='transaction_created',
            description=f'Financial transaction created: {txn.get_txn_type_display()} {txn.amount}',
            user=request.user,
            related_object_type='FinancialTransaction',
            related_object_id=txn.id
        )
        messages.success(request, get_translation('transaction_created', lang))
        return redirect('finance:transaction_list')

    if company:
        accounts = FinancialAccount.objects.filter(company=company, is_active=True)
    else:
        accounts = FinancialAccount.objects.filter(is_active=True)

    context = {
        'accounts': accounts,
        'company': company,
    }
    return render(request, 'finance/transaction_form.html', context)



@login_required
@never_cache
def account_list(request):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    if company:
        accounts = FinancialAccount.objects.filter(company=company)
    else:
        accounts = FinancialAccount.objects.all()

    context = {
        'accounts': accounts,
        'company': company,
    }
    return render(request, 'finance/account_list.html', context)



@login_required
@never_cache
def account_create(request):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    if request.method == 'POST':
        account = FinancialAccount(
            company=company,
            name=request.POST.get('name', ''),
            code=request.POST.get('code', ''),
            account_type=request.POST.get('account_type', 'cash'),
            currency=request.POST.get('currency', 'UZS'),
            opening_balance=request.POST.get('opening_balance', 0),
            notes=request.POST.get('notes', ''),
        )
        is_active = request.POST.get('is_active')
        account.is_active = is_active is not None
        account.save()

        Activity.log_activity(
            activity_type='account_created',
            description=f'Financial account "{account.name}" created.',
            user=request.user,
            related_object_type='FinancialAccount',
            related_object_id=account.id
        )
        messages.success(request, get_translation('account_created', lang))
        return redirect('finance:account_list')

    context = {
        'company': company,
    }
    return render(request, 'finance/account_form.html', context)



@login_required
@never_cache
def account_detail(request, pk):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    account = get_object_or_404(FinancialAccount, pk=pk)
    if not request.user.is_superuser:
        if not company or account.company != company:
            messages.error(request, get_translation('permission_denied', lang))
            return redirect('finance:account_list')

    recent_txns = FinancialTransaction.objects.filter(account=account).order_by('-date', '-created_at')[:20]

    context = {
        'account': account,
        'recent_transactions': recent_txns,
        'company': company,
    }
    return render(request, 'finance/account_detail.html', context)



@login_required
@never_cache
def account_edit(request, pk):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    account = get_object_or_404(FinancialAccount, pk=pk)
    if not request.user.is_superuser:
        if not company or account.company != company:
            messages.error(request, get_translation('permission_denied', lang))
            return redirect('finance:account_list')

    if request.method == 'POST':
        account.name = request.POST.get('name', account.name)
        account.code = request.POST.get('code', account.code)
        account.account_type = request.POST.get('account_type', account.account_type)
        account.currency = request.POST.get('currency', account.currency)
        account.opening_balance = request.POST.get('opening_balance', account.opening_balance)
        account.notes = request.POST.get('notes', account.notes)
        is_active = request.POST.get('is_active')
        account.is_active = is_active is not None
        account.save()

        Activity.log_activity(
            activity_type='account_updated',
            description=f'Financial account "{account.name}" updated.',
            user=request.user,
            related_object_type='FinancialAccount',
            related_object_id=account.id
        )
        messages.success(request, get_translation('account_updated', lang))
        return redirect('finance:account_list')

    context = {
        'account': account,
        'company': company,
    }
    return render(request, 'finance/account_form.html', context)



@login_required
@never_cache
def transfer_create(request):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    if request.method == 'POST':
        from_account = get_object_or_404(FinancialAccount, pk=request.POST.get('from_account'))
        to_account = get_object_or_404(FinancialAccount, pk=request.POST.get('to_account'))
        amount = request.POST.get('amount', 0)
        transfer_date = request.POST.get('date', timezone.now().date())
        notes = request.POST.get('notes', '')

        transfer = AccountTransfer(
            company=company,
            date=transfer_date,
            from_account=from_account,
            to_account=to_account,
            amount=amount,
            currency=from_account.currency,
            notes=notes,
            created_by=request.user,
        )
        transfer.save()

        FinancialTransaction.objects.create(
            company=company,
            date=transfer_date,
            txn_type='transfer_out',
            direction='expense',
            amount=amount,
            currency=from_account.currency,
            account=from_account,
            description=f'Transfer to {to_account.name}. {notes}',
            reference_number=f'TRF-{transfer.pk}',
            status='completed',
            created_by=request.user,
        )

        FinancialTransaction.objects.create(
            company=company,
            date=transfer_date,
            txn_type='transfer_in',
            direction='income',
            amount=amount,
            currency=to_account.currency,
            account=to_account,
            description=f'Transfer from {from_account.name}. {notes}',
            reference_number=f'TRF-{transfer.pk}',
            status='completed',
            created_by=request.user,
        )

        Activity.log_activity(
            activity_type='transfer_created',
            description=f'Transfer of {amount} from "{from_account.name}" to "{to_account.name}".',
            user=request.user,
            related_object_type='AccountTransfer',
            related_object_id=transfer.id
        )
        messages.success(request, get_translation('transfer_created', lang))
        return redirect('finance:account_list')

    if company:
        accounts = FinancialAccount.objects.filter(company=company, is_active=True)
    else:
        accounts = FinancialAccount.objects.filter(is_active=True)

    context = {
        'accounts': accounts,
        'company': company,
    }
    return render(request, 'finance/transfer_form.html', context)



@login_required
@never_cache
def expense_list(request):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    if company:
        expenses = FinancialTransaction.objects.filter(company=company, direction='expense')
    else:
        expenses = FinancialTransaction.objects.filter(direction='expense')

    expenses = expenses.order_by('-date', '-created_at')

    paginator = Paginator(expenses, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'company': company,
    }
    return render(request, 'finance/expense_list.html', context)



@login_required
@never_cache
def expense_create(request):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    if request.method == 'POST':
        txn = FinancialTransaction(
            company=company,
            created_by=request.user,
            date=request.POST.get('date', timezone.now().date()),
            txn_type='expense',
            direction='expense',
            amount=request.POST.get('amount', 0),
            description=request.POST.get('description', ''),
            payment_method=request.POST.get('payment_method', ''),
            status='completed',
        )
        account_id = request.POST.get('account')
        if account_id:
            txn.account = FinancialAccount.objects.filter(pk=account_id, company=company).first()
        category_id = request.POST.get('category')
        if category_id:
            cat = ExpenseCategory.objects.filter(pk=category_id, company=company).first()
            if cat:
                txn.category = cat.name
        txn.save()

        Activity.log_activity(
            activity_type='expense_created',
            description=f'Expense of {txn.amount} created.',
            user=request.user,
            related_object_type='FinancialTransaction',
            related_object_id=txn.id
        )
        messages.success(request, get_translation('expense_created', lang))
        return redirect('finance:expense_list')

    if company:
        accounts = FinancialAccount.objects.filter(company=company, is_active=True)
        categories = ExpenseCategory.objects.filter(company=company, is_active=True)
    else:
        accounts = FinancialAccount.objects.filter(is_active=True)
        categories = ExpenseCategory.objects.filter(is_active=True)

    context = {
        'accounts': accounts,
        'categories': categories,
        'company': company,
    }
    return render(request, 'finance/expense_form.html', context)



@login_required
@never_cache
def expense_category_list(request):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    if company:
        categories = ExpenseCategory.objects.filter(company=company)
    else:
        categories = ExpenseCategory.objects.all()

    context = {
        'categories': categories,
        'company': company,
    }
    return render(request, 'finance/expense_category_list.html', context)



@login_required
@never_cache
def income_list(request):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    if company:
        incomes = FinancialTransaction.objects.filter(company=company, direction='income')
    else:
        incomes = FinancialTransaction.objects.filter(direction='income')

    incomes = incomes.order_by('-date', '-created_at')

    paginator = Paginator(incomes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'company': company,
    }
    return render(request, 'finance/income_list.html', context)



@login_required
@never_cache
def income_create(request):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    if request.method == 'POST':
        txn = FinancialTransaction(
            company=company,
            created_by=request.user,
            date=request.POST.get('date', timezone.now().date()),
            txn_type='income',
            direction='income',
            amount=request.POST.get('amount', 0),
            description=request.POST.get('description', ''),
            payment_method=request.POST.get('payment_method', ''),
            status='completed',
        )
        account_id = request.POST.get('account')
        if account_id:
            txn.account = FinancialAccount.objects.filter(pk=account_id, company=company).first()
        category_id = request.POST.get('category')
        if category_id:
            cat = IncomeCategory.objects.filter(pk=category_id, company=company).first()
            if cat:
                txn.category = cat.name
        txn.save()

        Activity.log_activity(
            activity_type='income_created',
            description=f'Income of {txn.amount} created.',
            user=request.user,
            related_object_type='FinancialTransaction',
            related_object_id=txn.id
        )
        messages.success(request, get_translation('income_created', lang))
        return redirect('finance:income_list')

    if company:
        accounts = FinancialAccount.objects.filter(company=company, is_active=True)
        categories = IncomeCategory.objects.filter(company=company, is_active=True)
    else:
        accounts = FinancialAccount.objects.filter(is_active=True)
        categories = IncomeCategory.objects.filter(is_active=True)

    context = {
        'accounts': accounts,
        'categories': categories,
        'company': company,
    }
    return render(request, 'finance/income_form.html', context)



@login_required
@never_cache
def income_category_list(request):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    if company:
        categories = IncomeCategory.objects.filter(company=company)
    else:
        categories = IncomeCategory.objects.all()

    context = {
        'categories': categories,
        'company': company,
    }
    return render(request, 'finance/income_category_list.html', context)



@login_required
@never_cache
def budget_list(request):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    if company:
        budgets = Budget.objects.filter(company=company).select_related('category')
    else:
        budgets = Budget.objects.all().select_related('category')

    paginator = Paginator(budgets, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'company': company,
    }
    return render(request, 'finance/budget_list.html', context)



@login_required
@never_cache
def budget_create(request):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    if request.method == 'POST':
        budget = Budget(
            company=company,
            name=request.POST.get('name', ''),
            period_type=request.POST.get('period_type', 'monthly'),
            year=request.POST.get('year', timezone.now().year),
            month=request.POST.get('month') or None,
            planned_amount=request.POST.get('planned_amount', 0),
            notes=request.POST.get('notes', ''),
            status=request.POST.get('status', 'active'),
        )
        category_id = request.POST.get('category')
        if category_id:
            budget.category = ExpenseCategory.objects.filter(pk=category_id, company=company).first()
        budget.save()

        Activity.log_activity(
            activity_type='budget_created',
            description=f'Budget "{budget.name}" created.',
            user=request.user,
            related_object_type='Budget',
            related_object_id=budget.id
        )
        messages.success(request, get_translation('budget_created', lang))
        return redirect('finance:budget_list')

    if company:
        categories = ExpenseCategory.objects.filter(company=company, is_active=True)
    else:
        categories = ExpenseCategory.objects.filter(is_active=True)

    context = {
        'categories': categories,
        'company': company,
    }
    return render(request, 'finance/budget_form.html', context)



@login_required
@never_cache
def reports_hub(request):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    context = {
        'company': company,
    }
    return render(request, 'finance/reports_hub.html', context)



@login_required
@never_cache
def profit_loss_report(request):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if company:
        txns = FinancialTransaction.objects.filter(company=company, status='completed')
    else:
        txns = FinancialTransaction.objects.filter(status='completed')

    if date_from:
        txns = txns.filter(date__gte=date_from)
    if date_to:
        txns = txns.filter(date__lte=date_to)

    total_income = txns.filter(direction='income').aggregate(total=Sum('amount'))['total'] or 0
    total_expense = txns.filter(direction='expense').aggregate(total=Sum('amount'))['total'] or 0
    net_profit = total_income - total_expense

    context = {
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit,
        'date_from': date_from,
        'date_to': date_to,
        'company': company,
    }
    return render(request, 'finance/profit_loss.html', context)



@login_required
@never_cache
def cash_flow_report(request):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if company:
        txns = FinancialTransaction.objects.filter(company=company, status='completed')
    else:
        txns = FinancialTransaction.objects.filter(status='completed')

    if date_from:
        txns = txns.filter(date__gte=date_from)
    if date_to:
        txns = txns.filter(date__lte=date_to)

    monthly_income = (
        txns.filter(direction='income')
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )
    monthly_expense = (
        txns.filter(direction='expense')
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )
    monthly_transfers = (
        txns.filter(txn_type__in=['transfer_in', 'transfer_out'])
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )

    context = {
        'monthly_income': monthly_income,
        'monthly_expense': monthly_expense,
        'monthly_transfers': monthly_transfers,
        'date_from': date_from,
        'date_to': date_to,
        'company': company,
    }
    return render(request, 'finance/cash_flow.html', context)



@login_required
@never_cache
def receivables_aging(request):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    today = timezone.now().date()

    if company:
        debts = CustomerDebt.objects.filter(company=company).exclude(payment_status='paid')
    else:
        debts = CustomerDebt.objects.all().exclude(payment_status='paid')

    bucket_current = debts.filter(due_date__gte=today)
    bucket_31_60 = debts.filter(due_date__lt=today, due_date__gte=today - timedelta(days=60))
    bucket_61_90 = debts.filter(due_date__lt=today - timedelta(days=60), due_date__gte=today - timedelta(days=90))
    bucket_90_plus = debts.filter(due_date__lt=today - timedelta(days=90))

    def debt_total(qs):
        return qs.aggregate(total=Sum('debt_amount'))['total'] or 0

    context = {
        'bucket_current': bucket_current,
        'bucket_31_60': bucket_31_60,
        'bucket_61_90': bucket_61_90,
        'bucket_90_plus': bucket_90_plus,
        'total_current': debt_total(bucket_current),
        'total_31_60': debt_total(bucket_31_60),
        'total_61_90': debt_total(bucket_61_90),
        'total_90_plus': debt_total(bucket_90_plus),
        'company': company,
    }
    return render(request, 'finance/receivables_aging.html', context)



@login_required
@never_cache
def payables_aging(request):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    today = timezone.now().date()

    if company:
        debts = SupplierDebt.objects.filter(company=company).exclude(payment_status='paid')
    else:
        debts = SupplierDebt.objects.all().exclude(payment_status='paid')

    bucket_current = debts.filter(due_date__gte=today)
    bucket_31_60 = debts.filter(due_date__lt=today, due_date__gte=today - timedelta(days=60))
    bucket_61_90 = debts.filter(due_date__lt=today - timedelta(days=60), due_date__gte=today - timedelta(days=90))
    bucket_90_plus = debts.filter(due_date__lt=today - timedelta(days=90))

    def debt_total(qs):
        return qs.aggregate(total=Sum('amount_owed'))['total'] or 0

    context = {
        'bucket_current': bucket_current,
        'bucket_31_60': bucket_31_60,
        'bucket_61_90': bucket_61_90,
        'bucket_90_plus': bucket_90_plus,
        'total_current': debt_total(bucket_current),
        'total_31_60': debt_total(bucket_31_60),
        'total_61_90': debt_total(bucket_61_90),
        'total_90_plus': debt_total(bucket_90_plus),
        'company': company,
    }
    return render(request, 'finance/payables_aging.html', context)



@login_required
@never_cache
def customer_statement(request, pk):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    from sales.models import Customer
    customer = get_object_or_404(Customer, pk=pk)

    if company and customer.company != company:
        messages.error(request, get_translation('permission_denied', lang))
        return redirect('finance:financial_dashboard')

    if company:
        debts = CustomerDebt.objects.filter(company=company, customer_name=customer.name)
        payments = Payment.objects.filter(company=company, customer_debt__customer_name=customer.name)
        transactions = FinancialTransaction.objects.filter(company=company, customer=customer)
    else:
        debts = CustomerDebt.objects.filter(customer_name=customer.name)
        payments = Payment.objects.filter(customer_debt__customer_name=customer.name)
        transactions = FinancialTransaction.objects.filter(customer=customer)

    debts = debts.order_by('-created_at')
    payments = payments.order_by('-payment_date')
    transactions = transactions.order_by('-date', '-created_at')

    total_debt = debts.aggregate(total=Sum('debt_amount'))['total'] or 0
    total_paid = debts.aggregate(total=Sum('paid_amount'))['total'] or 0

    context = {
        'customer': customer,
        'debts': debts,
        'payments': payments,
        'transactions': transactions,
        'total_debt': total_debt,
        'total_paid': total_paid,
        'company': company,
    }
    return render(request, 'finance/customer_statement.html', context)



@login_required
@never_cache
def supplier_statement(request, pk):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    from purchases.models import Supplier
    supplier = get_object_or_404(Supplier, pk=pk)

    if company and supplier.company != company:
        messages.error(request, get_translation('permission_denied', lang))
        return redirect('finance:financial_dashboard')

    if company:
        debts = SupplierDebt.objects.filter(company=company, supplier_name=supplier.name)
        payments = PurchasePayment.objects.filter(company=company, purchase__supplier=supplier)
        transactions = FinancialTransaction.objects.filter(company=company, supplier=supplier)
    else:
        debts = SupplierDebt.objects.filter(supplier_name=supplier.name)
        payments = PurchasePayment.objects.filter(purchase__supplier=supplier)
        transactions = FinancialTransaction.objects.filter(supplier=supplier)

    debts = debts.order_by('-created_at')
    payments = payments.order_by('-payment_date')
    transactions = transactions.order_by('-date', '-created_at')

    total_debt = debts.aggregate(total=Sum('amount_owed'))['total'] or 0
    total_paid = debts.aggregate(total=Sum('paid_amount'))['total'] or 0

    context = {
        'supplier': supplier,
        'debts': debts,
        'payments': payments,
        'transactions': transactions,
        'total_debt': total_debt,
        'total_paid': total_paid,
        'company': company,
    }
    return render(request, 'finance/supplier_statement.html', context)



@login_required
@never_cache
def account_statement(request, pk):
    lang = request.session.get('language', 'uz')
    company, resp = _require_company(request, lang)
    if resp:
        return resp

    account = get_object_or_404(FinancialAccount, pk=pk)

    if not request.user.is_superuser:
        if not company or account.company != company:
            messages.error(request, get_translation('permission_denied', lang))
            return redirect('finance:account_list')

    transactions = FinancialTransaction.objects.filter(account=account).order_by('date', 'created_at')

    running_balance = account.opening_balance
    statement_lines = []
    for txn in transactions:
        if txn.direction == 'income':
            running_balance += txn.amount
        else:
            running_balance -= txn.amount
        statement_lines.append({
            'transaction': txn,
            'running_balance': running_balance,
        })

    paginator = Paginator(statement_lines, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'account': account,
        'page_obj': page_obj,
        'current_balance': running_balance,
        'company': company,
    }
    return render(request, 'finance/account_statement.html', context)
