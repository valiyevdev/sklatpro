from django.urls import path
from . import views

app_name = 'spiskalar'

urlpatterns = [
    # Dashboard & Workspace
    path('', views.spiskalar_dashboard, name='dashboard'),
    path('workspace/', views.my_workspace, name='workspace'),

    # Task CRUD
    path('tasks/', views.task_list, name='task_list'),
    path('tasks/create/', views.task_create, name='task_create'),
    path('tasks/<int:pk>/', views.task_detail, name='task_detail'),
    path('tasks/<int:pk>/edit/', views.task_update, name='task_update'),
    path('tasks/<int:pk>/delete/', views.task_delete, name='task_delete'),
    path('tasks/<int:pk>/complete/', views.task_complete, name='task_complete'),
    path('tasks/<int:pk>/status/', views.task_update_status, name='task_update_status'),
    path('tasks/<int:pk>/assign/', views.task_assign, name='task_assign'),

    # Task views
    path('tasks/kanban/', views.task_kanban, name='task_kanban'),
    path('tasks/kanban/<int:pk>/move/', views.task_kanban_move, name='task_kanban_move'),
    path('tasks/calendar/', views.task_calendar, name='task_calendar'),
    path('tasks/quick-create/', views.task_quick_create, name='task_quick_create'),
    path('tasks/bulk-action/', views.task_bulk_action, name='task_bulk_action'),
    path('tasks/search/', views.task_search_api, name='task_search_api'),

    # Checklist
    path('tasks/<int:pk>/checklist/add/', views.checklist_add, name='checklist_add'),
    path('tasks/<int:pk>/checklist/<int:item_pk>/toggle/', views.checklist_toggle, name='checklist_toggle'),
    path('tasks/<int:pk>/checklist/<int:item_pk>/delete/', views.checklist_delete, name='checklist_delete'),

    # Comments
    path('tasks/<int:pk>/comment/', views.task_comment_add, name='task_comment_add'),
    path('tasks/<int:pk>/comment/<int:comment_pk>/delete/', views.task_comment_delete, name='task_comment_delete'),

    # Templates
    path('templates/', views.template_list, name='template_list'),
    path('templates/create/', views.template_create, name='template_create'),
    path('templates/<int:pk>/use/', views.template_use, name='template_use'),

    # Legacy SpiskalarList CRUD (backward compatible)
    path('lists/', views.list_list, name='list_list'),
    path('lists/create/', views.list_create, name='list_create'),
    path('lists/<int:pk>/', views.list_detail, name='list_detail'),
    path('lists/<int:pk>/edit/', views.list_update, name='list_update'),
    path('lists/<int:pk>/delete/', views.list_delete, name='list_delete'),
    path('lists/<int:pk>/complete/<int:item_pk>/', views.list_item_complete, name='list_item_complete'),
]
