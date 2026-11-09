from django import forms
from .models import SpiskalarList, SpiskalarItem, Task, ChecklistItem, TaskComment, TaskTemplate


from core.lang import ph

class SpiskalarListForm(forms.ModelForm):
    class Meta:
        model = SpiskalarList
        fields = ['name', 'description', 'type', 'assigned_to', 'priority', 'start_date', 'due_date', 'status', 'notes']


class SpiskalarItemForm(forms.ModelForm):
    class Meta:
        model = SpiskalarItem
        fields = ['product', 'title', 'description', 'quantity', 'notes']


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'task_type', 'status', 'priority', 'assigned_to', 'start_date', 'due_date', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].required = False


class ChecklistItemForm(forms.ModelForm):
    class Meta:
        model = ChecklistItem
        fields = ['title', 'completed']


class TaskCommentForm(forms.ModelForm):
    class Meta:
        model = TaskComment
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3, 'placeholder': ph('ph_write_note')}),
        }


class TaskTemplateForm(forms.ModelForm):
    class Meta:
        model = TaskTemplate
        fields = ['name', 'description', 'task_type', 'priority', 'checklist_items']
        widgets = {
            'checklist_items': forms.HiddenInput(),
        }
