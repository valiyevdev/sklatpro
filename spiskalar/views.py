import json
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count
from django.core.paginator import Paginator
from .models import SpiskalarList, SpiskalarItem, Task, ChecklistItem, TaskComment, TaskAttachment, TaskTemplate
from .forms import TaskForm, TaskCommentForm, TaskTemplateForm
from products.models import Product
from activity.models import Activity
from notifications.models import Notification
from core.translations import get_translation

User = get_user_model()


def _get_company(request):
    company = getattr(request.user, 'company', None)
    if company:
        return company
    if request.user.is_superuser:
        from django.contrib import messages as _msgs
        _msgs.warning(request, 'Superuser: no company assigned. Showing first company data.')
        from users.models import Company
        return Company.objects.first()
    return None


def _log_task_activity(task, activity_type, description, user):
    try:
        company = task.company
    except Exception:
        company = None
    Activity.log_activity(
        activity_type=activity_type,
        description=description,
        user=user,
        company=company,
        related_object_type='Task',
        related_object_id=task.pk,
    )


def _create_notification(user, company, title, message, ntype='system', obj_type=None, obj_id=None):
    if not user or not company:
        return
    Notification.objects.create(
        company=company,
        user=user,
        title=title,
        message=message,
        type=ntype,
        related_object_type=obj_type or '',
        related_object_id=obj_id,
    )


@login_required
@never_cache
def spiskalar_dashboard(request):
    company = _get_company(request)
    today = timezone.now().date()
    user = request.user

    tasks = Task.objects.filter(company=company) if company else Task.objects.none()
    my_tasks = tasks.filter(assigned_to=user)

    total_tasks = tasks.count()
    my_total = my_tasks.count()
    completed = my_tasks.filter(status='completed').count()
    in_progress = my_tasks.filter(status='in_progress').count()
    overdue = my_tasks.filter(due_date__lt=today).exclude(status__in=('completed', 'cancelled')).count()
    due_today = my_tasks.filter(due_date=today).exclude(status__in=('completed', 'cancelled')).count()
    high_priority = my_tasks.filter(priority__in=('high', 'urgent')).exclude(status__in=('completed', 'cancelled')).count()
    pending = my_tasks.filter(status__in=('pending', 'backlog')).count()

    completion_rate = round((completed / my_total * 100)) if my_total > 0 else 0

    recent_tasks = my_tasks.exclude(status__in=('completed', 'cancelled')).order_by('due_date', '-priority')[:10]
    overdue_tasks = my_tasks.filter(due_date__lt=today).exclude(status__in=('completed', 'cancelled')).order_by('due_date')[:5]

    lists = SpiskalarList.objects.filter(company=company) if company else SpiskalarList.objects.none()
    active_lists = lists.exclude(status='completed').count()

    return render(request, 'spiskalar/dashboard.html', {
        'total_tasks': total_tasks,
        'my_total': my_total,
        'completed': completed,
        'in_progress': in_progress,
        'overdue': overdue,
        'due_today': due_today,
        'high_priority': high_priority,
        'pending': pending,
        'completion_rate': completion_rate,
        'recent_tasks': recent_tasks,
        'overdue_tasks': overdue_tasks,
        'active_lists': active_lists,
    })


@login_required
@never_cache
def my_workspace(request):
    company = _get_company(request)
    today = timezone.now().date()
    user = request.user

    tasks = Task.objects.filter(company=company, assigned_to=user) if company else Task.objects.none()

    today_tasks = tasks.filter(due_date=today).exclude(status__in=('completed', 'cancelled'))
    overdue_tasks = tasks.filter(due_date__lt=today).exclude(status__in=('completed', 'cancelled')).order_by('due_date')
    upcoming = tasks.filter(due_date__gt=today, due_date__lte=today + timedelta(days=7)).exclude(status__in=('completed', 'cancelled')).order_by('due_date')
    high_priority = tasks.filter(priority__in=('high', 'urgent')).exclude(status__in=('completed', 'cancelled')).order_by('-priority')
    in_progress = tasks.filter(status='in_progress')
    recently_completed = tasks.filter(status='completed').order_by('-completed_at')[:10]
    no_due_date = tasks.filter(due_date__isnull=True).exclude(status__in=('completed', 'cancelled')).order_by('-created_at')

    my_lists = SpiskalarList.objects.filter(company=company, assigned_to=user).exclude(status='completed') if company else SpiskalarList.objects.none()

    return render(request, 'spiskalar/workspace.html', {
        'today_tasks': today_tasks,
        'overdue_tasks': overdue_tasks,
        'upcoming_tasks': upcoming,
        'high_priority': high_priority,
        'in_progress_tasks': in_progress,
        'recently_completed': recently_completed,
        'no_due_date': no_due_date,
        'my_lists': my_lists,
        'today': today,
    })


@login_required
@never_cache
def task_list(request):
    company = _get_company(request)
    tasks = Task.objects.filter(company=company).select_related('assigned_to', 'created_by') if company else Task.objects.none()

    status = request.GET.get('status', '')
    priority = request.GET.get('priority', '')
    task_type = request.GET.get('type', '')
    assigned = request.GET.get('assigned', '')
    search = request.GET.get('q', '')
    overdue_filter = request.GET.get('overdue', '')

    if status:
        tasks = tasks.filter(status=status)
    if priority:
        tasks = tasks.filter(priority=priority)
    if task_type:
        tasks = tasks.filter(task_type=task_type)
    if assigned:
        tasks = tasks.filter(assigned_to_id=assigned)
    if search:
        tasks = tasks.filter(Q(title__icontains=search) | Q(description__icontains=search))
    if overdue_filter:
        today = timezone.now().date()
        tasks = tasks.filter(due_date__lt=today).exclude(status__in=('completed', 'cancelled'))

    tasks = tasks.order_by('-created_at')
    paginator = Paginator(tasks, 25)
    page = request.GET.get('page', 1)
    tasks_page = paginator.get_page(page)

    employees = User.objects.filter(company=company, is_active=True) if company else User.objects.none()

    return render(request, 'spiskalar/task_list.html', {
        'tasks': tasks_page,
        'employees': employees,
        'filters': {
            'status': status,
            'priority': priority,
            'type': task_type,
            'assigned': assigned,
            'q': search,
            'overdue': overdue_filter,
        },
    })


@login_required
@never_cache
def task_create(request):
    company = _get_company(request)
    lang = request.session.get('language', 'uz')
    employees = User.objects.filter(company=company, is_active=True) if company else User.objects.none()
    templates = TaskTemplate.objects.filter(company=company) if company else TaskTemplate.objects.none()

    if request.method == 'POST':
        template_id = request.POST.get('template_id')
        if template_id:
            tpl = get_object_or_404(TaskTemplate, pk=template_id, company=company)
            due_date = request.POST.get('due_date') or None
            assigned_to_id = request.POST.get('assigned_to') or None
            assigned_to = User.objects.filter(pk=assigned_to_id).first() if assigned_to_id else None
            task = tpl.create_task(
                company=company,
                created_by=request.user,
                assigned_to=assigned_to,
                due_date=due_date,
            )
            _log_task_activity(task, 'task_created', f"Task created from template: {task.title}", request.user)
            if task.assigned_to and task.assigned_to != request.user:
                _create_notification(task.assigned_to, company, 'Task Assigned',
                    f'You have been assigned task: {task.title}', 'system', 'Task', task.pk)
            messages.success(request, get_translation('task_created', lang))
            return redirect('spiskalar:task_detail', pk=task.pk)

        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.company = company
            task.created_by = request.user
            task.assigned_by = request.user
            if not task.status:
                task.status = 'pending'
            task.save()

            items_text = request.POST.get('checklist_items_text', '')
            if items_text:
                for idx, line in enumerate(items_text.strip().split('\n')):
                    line = line.strip()
                    if line:
                        ChecklistItem.objects.create(task=task, title=line, order=idx)

            _log_task_activity(task, 'task_created', f"Task created: {task.title}", request.user)
            if task.assigned_to and task.assigned_to != request.user:
                _create_notification(task.assigned_to, company, 'Task Assigned',
                    f'You have been assigned task: {task.title}', 'system', 'Task', task.pk)
            messages.success(request, get_translation('task_created', lang))
            return redirect('spiskalar:task_detail', pk=task.pk)
    else:
        form = TaskForm()

    return render(request, 'spiskalar/task_form.html', {
        'form': form,
        'employees': employees,
        'templates': templates,
    })


@login_required
@never_cache
def task_detail(request, pk):
    company = _get_company(request)
    task = get_object_or_404(Task.objects.select_related('assigned_to', 'created_by', 'assigned_by', 'completed_by'), pk=pk, company=company)
    checklist = task.checklist_items.all()
    comments = task.comments.select_related('user').all()
    attachments = task.attachments.select_related('uploaded_by').all()
    activities = Activity.objects.filter(
        related_object_type='Task', related_object_id=task.pk
    ).select_related('user').order_by('-created_at')[:20]
    employees = User.objects.filter(company=company, is_active=True) if company else User.objects.none()
    comment_form = TaskCommentForm()

    return render(request, 'spiskalar/task_detail.html', {
        'task': task,
        'checklist': checklist,
        'comments': comments,
        'attachments': attachments,
        'activities': activities,
        'employees': employees,
        'comment_form': comment_form,
    })


@login_required
@never_cache
def task_update(request, pk):
    company = _get_company(request)
    lang = request.session.get('language', 'uz')
    task = get_object_or_404(Task, pk=pk, company=company)
    employees = User.objects.filter(company=company, is_active=True) if company else User.objects.none()

    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            old_assignee = task.assigned_to
            old_priority = task.priority
            old_status = task.status
            old_due = task.due_date

            task = form.save()

            if old_assignee != task.assigned_to and task.assigned_to:
                _log_task_activity(task, 'task_assigned', f"Assigned to {task.assigned_to.get_full_name()}", request.user)
                if task.assigned_to != request.user:
                    _create_notification(task.assigned_to, company, 'Task Reassigned',
                        f'Task "{task.title}" has been assigned to you', 'system', 'Task', task.pk)
            if old_priority != task.priority:
                _log_task_activity(task, 'task_priority_changed', f"Priority changed to {task.get_priority_display()}", request.user)
            if old_status != task.status:
                _log_task_activity(task, 'task_status_changed', f"Status changed to {task.get_status_display()}", request.user)
                if task.status == 'completed':
                    task.completed_at = timezone.now()
                    task.completed_by = request.user
                    task.save(update_fields=['completed_at', 'completed_by'])
            if old_due != task.due_date:
                _log_task_activity(task, 'task_due_date_changed', f"Due date changed to {task.due_date}", request.user)

            messages.success(request, get_translation('task_updated', lang))
            return redirect('spiskalar:task_detail', pk=pk)
    else:
        form = TaskForm(instance=task)

    return render(request, 'spiskalar/task_form.html', {
        'form': form,
        'task': task,
        'employees': employees,
    })


@login_required
@require_POST
def task_update_status(request, pk):
    company = _get_company(request)
    lang = request.session.get('language', 'uz')
    task = get_object_or_404(Task, pk=pk, company=company)
    new_status = request.POST.get('status', task.status)
    old_status = task.status

    VALID_TRANSITIONS = {
        'backlog': ['pending', 'cancelled'],
        'pending': ['in_progress', 'waiting', 'cancelled'],
        'in_progress': ['completed', 'waiting', 'blocked', 'cancelled'],
        'waiting': ['in_progress', 'cancelled'],
        'blocked': ['in_progress', 'cancelled'],
        'completed': ['pending'],
        'cancelled': ['pending'],
    }

    allowed = VALID_TRANSITIONS.get(old_status, [])
    if new_status not in allowed and new_status != old_status:
        messages.error(request, f'Cannot transition from {old_status} to {new_status}')
        return redirect('spiskalar:task_detail', pk=pk)

    task.status = new_status
    if new_status == 'completed':
        task.completed_at = timezone.now()
        task.completed_by = request.user
    elif old_status == 'completed':
        task.completed_at = None
        task.completed_by = None
    task.save()

    _log_task_activity(task, 'task_status_changed', f"Status: {old_status} → {new_status}", request.user)
    messages.success(request, get_translation('task_updated', lang))
    return redirect('spiskalar:task_detail', pk=pk)


@login_required
@require_POST
def task_assign(request, pk):
    company = _get_company(request)
    lang = request.session.get('language', 'uz')
    task = get_object_or_404(Task, pk=pk, company=company)
    user_id = request.POST.get('assigned_to')
    new_assignee = User.objects.filter(pk=user_id, company=company).first() if user_id else None

    task.assigned_to = new_assignee
    task.assigned_by = request.user
    task.save(update_fields=['assigned_to', 'assigned_by', 'updated_at'])

    name = new_assignee.get_full_name() if new_assignee else 'Unassigned'
    _log_task_activity(task, 'task_assigned', f"Assigned to {name}", request.user)
    if new_assignee and new_assignee != request.user:
        _create_notification(new_assignee, company, 'Task Assigned',
            f'You have been assigned task: {task.title}', 'system', 'Task', task.pk)
    messages.success(request, get_translation('task_updated', lang))
    return redirect('spiskalar:task_detail', pk=pk)


@login_required
@require_POST
def task_quick_create(request):
    company = _get_company(request)
    lang = request.session.get('language', 'uz')
    title = request.POST.get('title', '').strip()
    if not title:
        return JsonResponse({'success': False, 'error': 'Title required'})

    task = Task.objects.create(
        company=company,
        title=title,
        priority=request.POST.get('priority', 'normal'),
        assigned_to_id=request.POST.get('assigned_to') or None,
        due_date=request.POST.get('due_date') or None,
        task_type=request.POST.get('task_type', 'custom'),
        created_by=request.user,
        assigned_by=request.user,
    )
    _log_task_activity(task, 'task_created', f"Quick task created: {task.title}", request.user)
    if task.assigned_to and task.assigned_to != request.user:
        _create_notification(task.assigned_to, company, 'Task Assigned',
            f'You have been assigned task: {task.title}', 'system', 'Task', task.pk)

    return JsonResponse({
        'success': True,
        'task_id': task.pk,
        'title': task.title,
        'redirect': f'/lists/tasks/{task.pk}/',
    })


@login_required
@require_POST
def checklist_add(request, pk):
    company = _get_company(request)
    task = get_object_or_404(Task, pk=pk, company=company)
    title = request.POST.get('title', '').strip()
    if title:
        last_order = task.checklist_items.count()
        ChecklistItem.objects.create(task=task, title=title, order=last_order)
        _log_task_activity(task, 'checklist_item_added', f"Checklist item added: {title}", request.user)
    return redirect('spiskalar:task_detail', pk=pk)


@login_required
@require_POST
def checklist_toggle(request, pk, item_pk):
    company = _get_company(request)
    task = get_object_or_404(Task, pk=pk, company=company)
    item = get_object_or_404(ChecklistItem, pk=item_pk, task=task)
    item.completed = not item.completed
    if item.completed:
        item.completed_by = request.user
        item.completed_at = timezone.now()
    else:
        item.completed_by = None
        item.completed_at = None
    item.save()
    _log_task_activity(task, 'checklist_item_completed' if item.completed else 'checklist_item_uncompleted',
        f"Checklist item {'completed' if item.completed else 'uncompleted'}: {item.title}", request.user)

    total = task.checklist_items.count()
    done = task.checklist_items.filter(completed=True).count()
    return JsonResponse({
        'success': True,
        'completed': item.completed,
        'progress': round((done / total * 100)) if total > 0 else 0,
        'progress_display': f'{done}/{total}',
    })


@login_required
@require_POST
def checklist_delete(request, pk, item_pk):
    company = _get_company(request)
    task = get_object_or_404(Task, pk=pk, company=company)
    item = get_object_or_404(ChecklistItem, pk=item_pk, task=task)
    item.delete()
    return redirect('spiskalar:task_detail', pk=pk)


@login_required
@require_POST
def task_comment_add(request, pk):
    company = _get_company(request)
    task = get_object_or_404(Task, pk=pk, company=company)
    form = TaskCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.task = task
        comment.user = request.user
        comment.save()
        _log_task_activity(task, 'task_comment_added', f"Comment added by {request.user.get_full_name()}", request.user)
    return redirect('spiskalar:task_detail', pk=pk)


@login_required
@never_cache
def task_kanban(request):
    company = _get_company(request)
    tasks = Task.objects.filter(company=company).select_related('assigned_to', 'created_by') if company else Task.objects.none()

    task_type = request.GET.get('type', '')
    assigned = request.GET.get('assigned', '')
    if task_type:
        tasks = tasks.filter(task_type=task_type)
    if assigned:
        tasks = tasks.filter(assigned_to_id=assigned)

    statuses = ['backlog', 'pending', 'in_progress', 'waiting', 'completed']
    columns = []
    for s in statuses:
        columns.append({'status': s, 'tasks': tasks.filter(status=s).order_by('-priority', 'due_date', '-created_at')})

    employees = User.objects.filter(company=company, is_active=True) if company else User.objects.none()

    return render(request, 'spiskalar/task_kanban.html', {
        'columns': columns,
        'employees': employees,
        'filters': {'type': task_type, 'assigned': assigned},
    })


@login_required
@require_POST
def task_kanban_move(request, pk):
    company = _get_company(request)
    task = get_object_or_404(Task, pk=pk, company=company)
    new_status = request.POST.get('status', '')
    valid_statuses = [s for s, _ in Task.STATUS_CHOICES]
    if new_status in valid_statuses:
        old_status = task.status
        task.status = new_status
        if new_status == 'completed':
            task.completed_at = timezone.now()
            task.completed_by = request.user
        elif old_status == 'completed':
            task.completed_at = None
            task.completed_by = None
        task.save()
        _log_task_activity(task, 'task_status_changed', f"Status: {old_status} → {new_status}", request.user)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid status'})


@login_required
@never_cache
def task_calendar(request):
    company = _get_company(request)
    tasks = Task.objects.filter(company=company).select_related('assigned_to') if company else Task.objects.none()
    tasks = tasks.exclude(status__in=('completed', 'cancelled')).exclude(due_date__isnull=True)

    assigned = request.GET.get('assigned', '')
    if assigned:
        tasks = tasks.filter(assigned_to_id=assigned)

    employees = User.objects.filter(company=company, is_active=True) if company else User.objects.none()

    return render(request, 'spiskalar/task_calendar.html', {
        'tasks': tasks,
        'employees': employees,
        'filters': {'assigned': assigned},
    })


@login_required
@require_POST
def task_complete(request, pk):
    company = _get_company(request)
    lang = request.session.get('language', 'uz')
    task = get_object_or_404(Task, pk=pk, company=company)
    task.status = 'completed'
    task.completed_at = timezone.now()
    task.completed_by = request.user
    task.save(update_fields=['status', 'completed_at', 'completed_by', 'updated_at'])
    _log_task_activity(task, 'task_completed', f"Task completed: {task.title}", request.user)
    messages.success(request, get_translation('task_completed_msg', lang))
    return redirect('spiskalar:task_detail', pk=pk)


@login_required
@require_POST
def task_delete(request, pk):
    company = _get_company(request)
    lang = request.session.get('language', 'uz')
    task = get_object_or_404(Task, pk=pk, company=company)
    task_title = task.title
    task.delete()
    _log_task_activity(task, 'task_deleted', f"Task deleted: {task_title}", request.user)
    messages.success(request, get_translation('task_deleted_msg', lang))
    return redirect('spiskalar:task_list')


@login_required
@require_POST
def task_bulk_action(request):
    company = _get_company(request)
    lang = request.session.get('language', 'uz')
    action = request.POST.get('action', '')
    task_ids = request.POST.getlist('task_ids')

    if not task_ids:
        messages.error(request, 'No tasks selected')
        return redirect('spiskalar:task_list')

    tasks = Task.objects.filter(pk__in=task_ids, company=company)

    if action == 'complete':
        tasks.update(status='completed', completed_at=timezone.now(), completed_by=request.user)
        messages.success(request, f'{tasks.count()} tasks completed')
    elif action == 'cancel':
        tasks.update(status='cancelled')
        messages.success(request, f'{tasks.count()} tasks cancelled')
    elif action == 'assign':
        user_id = request.POST.get('bulk_assign_to')
        if user_id:
            tasks.update(assigned_to_id=user_id, assigned_by=request.user)
            messages.success(request, f'{tasks.count()} tasks assigned')
    elif action == 'priority':
        new_priority = request.POST.get('bulk_priority')
        if new_priority:
            tasks.update(priority=new_priority)
            messages.success(request, f'{tasks.count()} tasks priority updated')
    elif action == 'delete':
        count = tasks.count()
        tasks.delete()
        messages.success(request, f'{count} tasks deleted')

    return redirect('spiskalar:task_list')


@login_required
@never_cache
def template_list(request):
    company = _get_company(request)
    templates = TaskTemplate.objects.filter(company=company) if company else TaskTemplate.objects.none()
    return render(request, 'spiskalar/template_list.html', {'templates': templates})


@login_required
@never_cache
def template_create(request):
    company = _get_company(request)
    lang = request.session.get('language', 'uz')
    if request.method == 'POST':
        items_raw = request.POST.get('checklist_items_text', '')
        items_list = [line.strip() for line in items_raw.strip().split('\n') if line.strip()]
        tpl = TaskTemplate.objects.create(
            company=company,
            name=request.POST.get('name', ''),
            description=request.POST.get('description', ''),
            task_type=request.POST.get('task_type', 'custom'),
            priority=request.POST.get('priority', 'normal'),
            checklist_items=items_list,
            created_by=request.user,
        )
        messages.success(request, get_translation('template_created', lang))
        return redirect('spiskalar:template_list')
    return render(request, 'spiskalar/template_form.html')


@login_required
@require_POST
def template_use(request, pk):
    company = _get_company(request)
    lang = request.session.get('language', 'uz')
    tpl = get_object_or_404(TaskTemplate, pk=pk, company=company)
    due_date = request.POST.get('due_date') or None
    assigned_to_id = request.POST.get('assigned_to') or None
    assigned_to = User.objects.filter(pk=assigned_to_id, company=company).first() if assigned_to_id else None
    task = tpl.create_task(company=company, created_by=request.user, assigned_to=assigned_to, due_date=due_date)
    _log_task_activity(task, 'task_created', f"Task created from template: {task.title}", request.user)
    messages.success(request, get_translation('task_created', lang))
    return redirect('spiskalar:task_detail', pk=task.pk)


@login_required
def task_search_api(request):
    company = _get_company(request)
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})
    tasks = Task.objects.filter(company=company).filter(
        Q(title__icontains=q) | Q(description__icontains=q)
    ).select_related('assigned_to')[:20]
    results = [{
        'id': t.pk,
        'title': t.title,
        'status': t.status,
        'priority': t.priority,
        'assigned_to': t.assigned_to.get_full_name() if t.assigned_to else None,
    } for t in tasks]
    return JsonResponse({'results': results})


@login_required
@require_POST
def task_comment_delete(request, pk, comment_pk):
    company = _get_company(request)
    task = get_object_or_404(Task, pk=pk, company=company)
    comment = get_object_or_404(TaskComment, pk=comment_pk, task=task)
    if comment.user == request.user or request.user.role in ('COMPANY_ADMIN', 'MANAGER'):
        comment.delete()
    return redirect('spiskalar:task_detail', pk=pk)


# ====================================================================
# LEGACY SPISKALAR LIST VIEWS (backward compatible)
# ====================================================================

@login_required
@never_cache
def list_list(request):
    company = _get_company(request)
    spiskalar = SpiskalarList.objects.filter(company=company).select_related('assigned_to') if company else SpiskalarList.objects.all()
    return render(request, 'spiskalar/list_list.html', {'lists': spiskalar})


@login_required
@never_cache
def list_create(request):
    company = _get_company(request)
    lang = request.session.get('language', 'uz')
    products = Product.objects.filter(company=company) if company else Product.objects.none()
    employees = User.objects.filter(company=company, is_active=True) if company else User.objects.none()
    if request.method == 'POST':
        spiskalar = SpiskalarList.objects.create(
            company=company,
            name=request.POST.get('name', ''),
            type=request.POST.get('type', 'custom'),
            assigned_to_id=request.POST.get('assigned_to') or None,
            priority=request.POST.get('priority', 'medium'),
            due_date=request.POST.get('due_date') or None,
            notes=request.POST.get('notes', ''),
            created_by=request.user,
        )
        product_ids = request.POST.getlist('products')
        quantities = request.POST.getlist('quantities')
        for pid, qty in zip(product_ids, quantities):
            if pid and qty:
                SpiskalarItem.objects.create(list=spiskalar, product_id=int(pid), quantity=int(qty))
        messages.success(request, get_translation('spiskalar_created', lang))
        return redirect('spiskalar:list_detail', pk=spiskalar.pk)
    return render(request, 'spiskalar/list_form.html', {'products': products, 'employees': employees})


@login_required
@never_cache
def list_detail(request, pk):
    company = _get_company(request)
    spiskalar = get_object_or_404(SpiskalarList.objects.select_related('assigned_to'), pk=pk, company=company)
    items = spiskalar.items.select_related('product').all()
    return render(request, 'spiskalar/list_detail.html', {'list': spiskalar, 'items': items})


@login_required
@never_cache
def list_update(request, pk):
    company = _get_company(request)
    lang = request.session.get('language', 'uz')
    spiskalar = get_object_or_404(SpiskalarList, pk=pk, company=company)
    products = Product.objects.filter(company=company)
    employees = User.objects.filter(company=company, is_active=True)
    if request.method == 'POST':
        spiskalar.name = request.POST.get('name', spiskalar.name)
        spiskalar.type = request.POST.get('type', spiskalar.type)
        spiskalar.assigned_to_id = request.POST.get('assigned_to') or None
        spiskalar.priority = request.POST.get('priority', spiskalar.priority)
        spiskalar.due_date = request.POST.get('due_date') or None
        spiskalar.notes = request.POST.get('notes', spiskalar.notes)
        spiskalar.status = request.POST.get('status', spiskalar.status)
        spiskalar.save()
        messages.success(request, get_translation('spiskalar_updated', lang))
        return redirect('spiskalar:list_detail', pk=pk)
    items = spiskalar.items.all()
    return render(request, 'spiskalar/list_form.html', {'products': products, 'employees': employees, 'list': spiskalar, 'items': items})


@login_required
@never_cache
def list_delete(request, pk):
    company = _get_company(request)
    lang = request.session.get('language', 'uz')
    spiskalar = get_object_or_404(SpiskalarList, pk=pk, company=company)
    if request.method == 'POST':
        spiskalar.delete()
        messages.success(request, get_translation('spiskalar_deleted', lang))
        return redirect('spiskalar:list_list')
    return render(request, 'spiskalar/list_confirm_delete.html', {'list': spiskalar})


@login_required
@never_cache
def list_item_complete(request, pk, item_pk):
    company = _get_company(request)
    lang = request.session.get('language', 'uz')
    spiskalar = get_object_or_404(SpiskalarList, pk=pk, company=company)
    item = get_object_or_404(SpiskalarItem, pk=item_pk, list=spiskalar)
    if request.method == 'POST':
        complete_qty = int(request.POST.get('complete_quantity', item.quantity))
        item.completed_quantity = min(complete_qty, item.quantity)
        if item.completed_quantity >= item.quantity:
            item.completed = True
            item.completed_at = timezone.now()
            item.completed_by = request.user
        item.save()
        all_done = all(i.completed for i in spiskalar.items.all())
        if all_done:
            spiskalar.status = 'completed'
            spiskalar.save()
        elif any(i.completed_quantity > 0 for i in spiskalar.items.all()):
            spiskalar.status = 'in_progress'
            spiskalar.save()
        messages.success(request, get_translation('item_updated', lang))
    return redirect('spiskalar:list_detail', pk=pk)
