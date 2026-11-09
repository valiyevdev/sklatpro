from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import never_cache
from .models import Contact
from core.translations import get_translation


@login_required
@never_cache
def contact_list(request):
    company = request.user.company
    contacts = Contact.objects.filter(company=company) if company else (Contact.objects.all() if request.user.is_superuser else Contact.objects.none())
    contact_type = request.GET.get('type', '')
    if contact_type:
        contacts = contacts.filter(type=contact_type)
    return render(request, 'contacts/contact_list.html', {'contacts': contacts, 'current_type': contact_type})


@login_required
@never_cache
def contact_create(request):
    company = request.user.company
    lang = request.session.get('language', 'uz')
    if request.method == 'POST':
        Contact.objects.create(
            company=company,
            name=request.POST.get('name', ''),
            type=request.POST.get('type', 'customer'),
            company_name=request.POST.get('company_name', ''),
            phone=request.POST.get('phone', ''),
            email=request.POST.get('email', ''),
            telegram=request.POST.get('telegram', ''),
            address=request.POST.get('address', ''),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, get_translation('contact_created', lang))
        return redirect('contacts:contact_list')
    return render(request, 'contacts/contact_form.html')


@login_required
@never_cache
def contact_detail(request, pk):
    company = request.user.company
    contact = get_object_or_404(Contact, pk=pk) if request.user.is_superuser else get_object_or_404(Contact, pk=pk, company=company)
    return render(request, 'contacts/contact_detail.html', {'contact': contact})


@login_required
@never_cache
def contact_update(request, pk):
    company = request.user.company
    lang = request.session.get('language', 'uz')
    contact = get_object_or_404(Contact, pk=pk) if request.user.is_superuser else get_object_or_404(Contact, pk=pk, company=company)
    if request.method == 'POST':
        contact.name = request.POST.get('name', contact.name)
        contact.type = request.POST.get('type', contact.type)
        contact.company_name = request.POST.get('company_name', contact.company_name)
        contact.phone = request.POST.get('phone', contact.phone)
        contact.email = request.POST.get('email', contact.email)
        contact.telegram = request.POST.get('telegram', contact.telegram)
        contact.address = request.POST.get('address', contact.address)
        contact.notes = request.POST.get('notes', contact.notes)
        contact.save()
        messages.success(request, get_translation('contact_updated', lang))
        return redirect('contacts:contact_detail', pk=pk)
    return render(request, 'contacts/contact_form.html', {'contact': contact})


@login_required
@never_cache
def contact_delete(request, pk):
    company = request.user.company
    lang = request.session.get('language', 'uz')
    contact = get_object_or_404(Contact, pk=pk) if request.user.is_superuser else get_object_or_404(Contact, pk=pk, company=company)
    if request.method == 'POST':
        contact.delete()
        messages.success(request, get_translation('contact_deleted', lang))
        return redirect('contacts:contact_list')
    return render(request, 'contacts/contact_confirm_delete.html', {'contact': contact})
