from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import never_cache
from .models import Notification


@login_required
@never_cache
def notification_list(request):
    company = request.user.company
    notifications = Notification.objects.filter(user=request.user, company=company) if company else Notification.objects.filter(user=request.user)
    unread_count = notifications.filter(read=False).count()
    return render(request, 'notifications/notification_list.html', {'notifications': notifications, 'unread_count': unread_count})


@login_required
@never_cache
def notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.read = True
    notification.save()
    return redirect('notifications:notification_list')


@login_required
@never_cache
def notification_mark_all_read(request):
    company = request.user.company
    if company:
        Notification.objects.filter(user=request.user, company=company, read=False).update(read=True)
    else:
        Notification.objects.filter(user=request.user, read=False).update(read=True)
    return redirect('notifications:notification_list')


@login_required
@never_cache
def notification_delete(request, pk):
    if request.method == 'POST':
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        notification.delete()
        messages.success(request, 'Notification deleted.')
    return redirect('notifications:notification_list')
