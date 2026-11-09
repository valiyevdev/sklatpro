from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.db.models import Sum, Count, Q
from django.db import transaction as db_transaction
from django.http import FileResponse, Http404
from django.utils import timezone
from django.utils.text import slugify
from decimal import Decimal
import json

from users.models import Company
from reports.utils import get_company
from .models import (
    Document, DocumentItem, DocumentAttachment,
    DocumentVersion, DocumentTemplate, DocumentSignature,
    EDOConfig, EDOTransaction,
)
from .forms import (
    DocumentForm, DocumentFilterForm,
    DocumentTemplateForm, DocumentAttachmentUploadForm,
)

TYPE_PREFIX = {
    'sales_invoice': 'INV',
    'purchase_invoice': 'PUR',
    'proforma_invoice': 'PRO',
    'credit_note': 'CRN',
    'debit_note': 'DBN',
    'delivery_note': 'DEL',
    'goods_receipt': 'GRN',
    'goods_issue': 'GHI',
    'return_document': 'RET',
    'payment_receipt': 'PAY',
    'contract': 'CTR',
    'commercial_offer': 'CFO',
    'other': 'DOC',
}


def _get_company(request):
    company = getattr(request.user, 'company', None)
    if company:
        return company
    if request.user.is_superuser:
        from django.contrib import messages as _msgs
        _msgs.warning(request, 'Superuser: no company assigned. Showing first company data.')
        return Company.objects.first()
    return None


def _generate_number(company, doc_type):
    prefix = TYPE_PREFIX.get(doc_type, 'DOC')
    year = timezone.now().year
    last = (
        Document.objects.filter(company=company, doc_type=doc_type, number__startswith=f'{prefix}-{year}-')
        .order_by('-number')
        .values_list('number', flat=True)
        .first()
    )
    if last:
        try:
            seq = int(last.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f'{prefix}-{year}-{seq:06d}'


def _recalc_totals(document):
    items = document.items.all()
    subtotal = sum(i.line_total for i in items)
    document.subtotal = subtotal
    document.tax = sum(i.tax for i in items)
    document.discount = sum(i.discount for i in items)
    document.total = document.subtotal
    document.save(update_fields=['subtotal', 'tax', 'discount', 'total'])


def _make_snapshot(document):
    return {
        'number': document.number,
        'title': document.title,
        'status': document.status,
        'doc_type': document.doc_type,
        'date': str(document.date),
        'total': str(document.total),
        'subtotal': str(document.subtotal),
        'tax': str(document.tax),
        'discount': str(document.discount),
        'currency': document.currency,
        'items_count': document.items.count(),
    }


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@login_required
@never_cache
def documents_dashboard(request):
    company = _get_company(request)
    docs = Document.objects.filter(company=company)

    status_counts = dict(docs.values_list('status').annotate(c=Count('id')).values_list('status', 'c'))
    type_counts = dict(docs.values_list('doc_type').annotate(c=Count('id')).values_list('doc_type', 'c'))
    recent = docs.select_related('customer', 'supplier')[:10]
    total = docs.count()
    total_value = docs.aggregate(s=Sum('total'))['s'] or Decimal('0')

    return render(request, 'documents/documents_dashboard.html', {
        'status_counts': status_counts,
        'type_counts': type_counts,
        'recent_docs': recent,
        'total': total,
        'total_value': total_value,
        'type_choices': Document.TYPE_CHOICES,
        'status_choices': Document.STATUS_CHOICES,
    })


# ─── LIST ─────────────────────────────────────────────────────────────────────

@login_required
@never_cache
def document_list(request):
    company = _get_company(request)
    qs = Document.objects.filter(company=company).select_related('customer', 'supplier')

    form = DocumentFilterForm(request.GET)
    if form.is_valid():
        if form.cleaned_data['doc_type']:
            qs = qs.filter(doc_type=form.cleaned_data['doc_type'])
        if form.cleaned_data['status']:
            qs = qs.filter(status=form.cleaned_data['status'])
        if form.cleaned_data['date_from']:
            qs = qs.filter(date__gte=form.cleaned_data['date_from'])
        if form.cleaned_data['date_to']:
            qs = qs.filter(date__lte=form.cleaned_data['date_to'])
        q = form.cleaned_data.get('search', '').strip()
        if q:
            qs = qs.filter(
                Q(number__icontains=q) |
                Q(title__icontains=q) |
                Q(customer__name__icontains=q) |
                Q(supplier__name__icontains=q)
            )

    page_obj = None
    total_count = qs.count()

    return render(request, 'documents/document_list.html', {
        'documents': qs,
        'filter_form': form,
        'total_count': total_count,
        'type_choices': Document.TYPE_CHOICES,
        'status_choices': Document.STATUS_CHOICES,
    })


# ─── CREATE ───────────────────────────────────────────────────────────────────

@login_required
@never_cache
def document_create(request):
    company = _get_company(request)

    if request.method == 'POST':
        form = DocumentForm(request.POST)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.company = company
            doc.created_by = request.user
            doc.number = _generate_number(company, doc.doc_type)
            doc.save()

            # Save inline items
            items_data = request.POST.getlist('item_description')
            for i, desc in enumerate(items_data):
                if not desc.strip():
                    continue
                item = DocumentItem(
                    company=company,
                    document=doc,
                    description=desc,
                    quantity=Decimal(request.POST.getlist('item_quantity')[i] or '1'),
                    unit_price=Decimal(request.POST.getlist('item_unit_price')[i] or '0'),
                    discount=Decimal(request.POST.getlist('item_discount')[i] or '0'),
                    tax=Decimal(request.POST.getlist('item_tax')[i] or '0'),
                    sort_order=i,
                )
                item.save()

            _recalc_totals(doc)
            messages.success(request, f'Document {doc.number} created successfully.')
            return redirect('documents:document_detail', pk=doc.pk)
    else:
        form = DocumentForm(initial={'date': timezone.now().date()})

    return render(request, 'documents/document_form.html', {
        'form': form,
        'title': 'Create Document',
        'is_create': True,
    })


# ─── DETAIL ───────────────────────────────────────────────────────────────────

@login_required
@never_cache
def document_detail(request, pk):
    company = _get_company(request)
    doc = get_object_or_404(Document.objects.select_related('customer', 'supplier', 'created_by', 'signed_by', 'approved_by'), pk=pk, company=company)
    items = doc.items.select_related('product').all()
    attachments = doc.attachments.all()
    versions = doc.versions.all()
    signatures = doc.signatures.select_related('signer').all()

    return render(request, 'documents/document_detail.html', {
        'doc': doc,
        'items': items,
        'attachments': attachments,
        'versions': versions,
        'signatures': signatures,
    })


# ─── EDIT ─────────────────────────────────────────────────────────────────────

@login_required
@never_cache
def document_edit(request, pk):
    company = _get_company(request)
    doc = get_object_or_404(Document, pk=pk, company=company)

    if doc.status != 'draft':
        messages.error(request, 'Only draft documents can be edited.')
        return redirect('documents:document_detail', pk=doc.pk)

    if request.method == 'POST':
        form = DocumentForm(request.POST, instance=doc)
        if form.is_valid():
            doc = form.save()

            # Rebuild items from POST
            doc.items.all().delete()
            items_data = request.POST.getlist('item_description')
            for i, desc in enumerate(items_data):
                if not desc.strip():
                    continue
                item = DocumentItem(
                    company=company,
                    document=doc,
                    description=desc,
                    quantity=Decimal(request.POST.getlist('item_quantity')[i] or '1'),
                    unit_price=Decimal(request.POST.getlist('item_unit_price')[i] or '0'),
                    discount=Decimal(request.POST.getlist('item_discount')[i] or '0'),
                    tax=Decimal(request.POST.getlist('item_tax')[i] or '0'),
                    sort_order=i,
                )
                item.save()

            _recalc_totals(doc)
            messages.success(request, f'Document {doc.number} updated successfully.')
            return redirect('documents:document_detail', pk=doc.pk)
    else:
        form = DocumentForm(instance=doc)

    return render(request, 'documents/document_form.html', {
        'form': form,
        'doc': doc,
        'items': doc.items.all(),
        'title': f'Edit {doc.number}',
        'is_create': False,
    })


# ─── STATUS CHANGE ────────────────────────────────────────────────────────────

@login_required
@require_POST
def document_status_change(request, pk):
    company = _get_company(request)
    doc = get_object_or_404(Document, pk=pk, company=company)
    new_status = request.POST.get('status', '').strip()

    valid_statuses = [s[0] for s in Document.STATUS_CHOICES]
    if new_status not in valid_statuses:
        messages.error(request, 'Invalid status.')
        return redirect('documents:document_detail', pk=doc.pk)

    doc.status = new_status
    doc.save(update_fields=['status'])
    messages.success(request, f'Document {doc.number} status changed to {new_status}.')
    return redirect('documents:document_detail', pk=doc.pk)


# ─── APPROVE ──────────────────────────────────────────────────────────────────

@login_required
@require_POST
def document_approve(request, pk):
    company = _get_company(request)
    doc = get_object_or_404(Document, pk=pk, company=company)

    doc.status = 'approved'
    doc.approval_status = 'approved'
    doc.approved_by = request.user
    doc.approved_at = timezone.now()
    doc.save(update_fields=['status', 'approval_status', 'approved_by', 'approved_at'])

    messages.success(request, f'Document {doc.number} approved.')
    return redirect('documents:document_detail', pk=doc.pk)


# ─── CANCEL ───────────────────────────────────────────────────────────────────

@login_required
@require_POST
def document_cancel(request, pk):
    company = _get_company(request)
    doc = get_object_or_404(Document, pk=pk, company=company)

    doc.status = 'cancelled'
    doc.save(update_fields=['status'])

    messages.success(request, f'Document {doc.number} cancelled.')
    return redirect('documents:document_detail', pk=doc.pk)


# ─── ARCHIVE ──────────────────────────────────────────────────────────────────

@login_required
@require_POST
def document_archive(request, pk):
    company = _get_company(request)
    doc = get_object_or_404(Document, pk=pk, company=company)

    doc.status = 'archived'
    doc.save(update_fields=['status'])

    messages.success(request, f'Document {doc.number} archived.')
    return redirect('documents:document_list')


# ─── PREVIEW ──────────────────────────────────────────────────────────────────

@login_required
@never_cache
def document_preview(request, pk):
    company = _get_company(request)
    doc = get_object_or_404(Document.objects.select_related('customer', 'supplier'), pk=pk, company=company)
    items = doc.items.select_related('product').all()
    return render(request, 'documents/document_preview.html', {
        'doc': doc, 'items': items,
    })


# ─── PRINT ────────────────────────────────────────────────────────────────────

@login_required
@never_cache
def document_print(request, pk):
    company = _get_company(request)
    doc = get_object_or_404(Document.objects.select_related('customer', 'supplier'), pk=pk, company=company)
    items = doc.items.select_related('product').all()
    return render(request, 'documents/document_print.html', {
        'doc': doc, 'items': items,
    })


# ─── NEW VERSION ──────────────────────────────────────────────────────────────

@login_required
@require_POST
def document_new_version(request, pk):
    company = _get_company(request)
    doc = get_object_or_404(Document, pk=pk, company=company)

    # Save snapshot of current version
    DocumentVersion.objects.create(
        company=company,
        document=doc,
        version_number=doc.version,
        status=doc.status,
        total=doc.total,
        reason=doc.version_reason,
        snapshot=_make_snapshot(doc),
        created_by=request.user,
    )

    # Create new version document
    new_doc = Document.objects.create(
        company=company,
        doc_type=doc.doc_type,
        number=_generate_number(company, doc.doc_type),
        title=f"{doc.title or doc.number} (v{doc.version + 1})",
        status='draft',
        date=doc.date,
        due_date=doc.due_date,
        customer=doc.customer,
        supplier=doc.supplier,
        currency=doc.currency,
        subtotal=doc.subtotal,
        tax=doc.tax,
        discount=doc.discount,
        total=doc.total,
        notes=doc.notes,
        version=doc.version + 1,
        parent_version=doc,
        created_by=request.user,
    )

    # Copy items
    for item in doc.items.all():
        DocumentItem.objects.create(
            company=company,
            document=new_doc,
            product=item.product,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount=item.discount,
            tax=item.tax,
            line_total=item.line_total,
            gtin=item.gtin,
            serial_number=item.serial_number,
            batch_number=item.batch_number,
            marking_code=item.marking_code,
            sort_order=item.sort_order,
        )

    messages.success(request, f'New version {new_doc.number} created from {doc.number}.')
    return redirect('documents:document_detail', pk=new_doc.pk)


# ─── VERSIONS LIST ────────────────────────────────────────────────────────────

@login_required
@never_cache
def document_versions(request, pk):
    company = _get_company(request)
    doc = get_object_or_404(Document, pk=pk, company=company)
    versions = doc.versions.select_related('created_by').all()
    return render(request, 'documents/document_versions.html', {
        'doc': doc, 'versions': versions,
    })


# ─── ATTACHMENTS ──────────────────────────────────────────────────────────────

@login_required
@never_cache
def document_attachment_upload(request, pk):
    company = _get_company(request)
    doc = get_object_or_404(Document, pk=pk, company=company)

    if request.method == 'POST':
        form = DocumentAttachmentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data['file']
            DocumentAttachment.objects.create(
                company=company,
                document=doc,
                file=f,
                filename=f.name,
                file_size=f.size,
                content_type=f.content_type or '',
                uploaded_by=request.user,
            )
            messages.success(request, f'Attachment "{f.name}" uploaded.')
        else:
            messages.error(request, 'Failed to upload attachment.')
        return redirect('documents:document_detail', pk=doc.pk)

    form = DocumentAttachmentUploadForm()
    return render(request, 'documents/document_attachment_upload.html', {
        'doc': doc,
        'form': form,
    })


@login_required
@never_cache
def document_download(request, att_pk):
    company = _get_company(request)
    att = get_object_or_404(DocumentAttachment, pk=att_pk, company=company)

    if not att.file:
        raise Http404('File not found')

    return FileResponse(att.file.open('rb'), as_attachment=True, filename=att.filename)


@login_required
@require_POST
def document_attachment_delete(request, att_pk):
    company = _get_company(request)
    att = get_object_or_404(DocumentAttachment, pk=att_pk, company=company)
    doc_pk = att.document.pk
    att.file.delete(save=False)
    att.delete()
    messages.success(request, 'Attachment deleted.')
    return redirect('documents:document_detail', pk=doc_pk)


# ─── TEMPLATES ────────────────────────────────────────────────────────────────

@login_required
@never_cache
def document_template_list(request):
    company = _get_company(request)
    templates = DocumentTemplate.objects.filter(company=company)
    return render(request, 'documents/document_template_list.html', {
        'templates': templates,
    })


@login_required
@never_cache
def document_template_create(request):
    company = _get_company(request)

    if request.method == 'POST':
        form = DocumentTemplateForm(request.POST)
        if form.is_valid():
            tpl = form.save(commit=False)
            tpl.company = company
            tpl.save()
            messages.success(request, f'Template "{tpl.name}" created.')
            return redirect('documents:document_template_list')
    else:
        form = DocumentTemplateForm()

    return render(request, 'documents/document_template_form.html', {
        'form': form,
    })


# ─── EDO ──────────────────────────────────────────────────────────────────────

@login_required
@never_cache
def edo_dashboard(request):
    company = _get_company(request)
    configs = EDOConfig.objects.filter(company=company)
    recent_txns = EDOTransaction.objects.filter(company=company).select_related('document')[:20]
    return render(request, 'documents/edo_dashboard.html', {
        'configs': configs,
        'recent_txns': recent_txns,
    })


@login_required
@require_POST
def edo_send(request, pk):
    company = _get_company(request)
    doc = get_object_or_404(Document, pk=pk, company=company)

    config = EDOConfig.objects.filter(company=company, is_active=True).first()
    if not config:
        messages.error(request, 'No active EDO configuration found.')
        return redirect('documents:document_detail', pk=doc.pk)

    txn = EDOTransaction.objects.create(
        company=company,
        config=config,
        document=doc,
        direction='out',
        action='send',
        request_payload={
            'doc_number': doc.number,
            'doc_type': doc.doc_type,
            'total': str(doc.total),
            'customer': str(doc.customer) if doc.customer else None,
        },
        status='failed',
        error_code='INTEGRATION_NOT_CONFIGURED',
        error_message='EDO Integration Not Configured — this is a mock transaction. Connect a real EDO provider to enable document exchange.',
        completed_at=timezone.now(),
    )

    doc.is_electronic = True
    doc.external_status = 'error'
    doc.external_response = json.dumps({
        'status': 'error',
        'message': 'Integration Not Configured',
        'transaction_id': str(txn.id),
    })
    doc.save(update_fields=['is_electronic', 'external_status', 'external_response'])

    messages.warning(request, f'EDO send recorded (mock). Provider integration is not configured.')
    return redirect('documents:document_detail', pk=doc.pk)


@login_required
@never_cache
def edo_status(request, pk):
    company = _get_company(request)
    doc = get_object_or_404(Document, pk=pk, company=company)
    last_txn = doc.edo_transactions.order_by('-created_at').first()

    status_info = {
        'external_status': doc.external_status,
        'last_transaction': None,
    }
    if last_txn:
        status_info['last_transaction'] = {
            'action': last_txn.action,
            'status': last_txn.status,
            'error_message': last_txn.error_message,
            'created_at': last_txn.created_at.isoformat() if last_txn.created_at else None,
        }

    return render(request, 'documents/edo_status.html', {
        'doc': doc,
        'status_info': status_info,
    })


# ─── SIGNATURES ───────────────────────────────────────────────────────────────

@login_required
@require_POST
def document_signature_request(request, pk):
    company = _get_company(request)
    doc = get_object_or_404(Document, pk=pk, company=company)

    signer_email = request.POST.get('signer_email', '').strip()
    signer = request.user  # Default to requesting user
    if signer_email:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        signer = User.objects.filter(email=signer_email, company=company).first() or signer

    DocumentSignature.objects.create(
        company=company,
        document=doc,
        signer=signer,
        status='pending',
    )

    doc.signature_status = 'pending'
    doc.save(update_fields=['signature_status'])

    messages.success(request, f'Signature request sent to {signer.email}.')
    return redirect('documents:document_detail', pk=doc.pk)


@login_required
@require_POST
def document_sign(request, pk):
    company = _get_company(request)
    doc = get_object_or_404(Document, pk=pk, company=company)

    sig = doc.signatures.filter(signer=request.user, status='pending').first()
    if not sig:
        messages.error(request, 'No pending signature found for you.')
        return redirect('documents:document_detail', pk=doc.pk)

    sig.status = 'signed'
    sig.signed_at = timezone.now()
    sig.certificate_info = {'mock': True, 'message': 'Integration Not Configured — mock signature'}
    sig.save(update_fields=['status', 'signed_at', 'certificate_info'])

    doc.signature_status = 'signed'
    doc.signed_by = request.user
    doc.signed_at = timezone.now()
    doc.save(update_fields=['signature_status', 'signed_by', 'signed_at'])

    messages.success(request, f'Document {doc.number} signed successfully.')
    return redirect('documents:document_detail', pk=doc.pk)
