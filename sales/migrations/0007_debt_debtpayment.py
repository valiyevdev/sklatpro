from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('sales', '0006_sale_idempotency_key'), ('users', '0005_company_pos_tax_rate')]
    operations = [
        migrations.CreateModel(
            name='Debt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total', models.DecimalField(decimal_places=2, max_digits=12)),
                ('paid', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('due_date', models.DateField()),
                ('status', models.CharField(choices=[('open', 'Open'), ('partial', 'Partial'), ('paid', 'Paid'), ('overdue', 'Overdue')], default='open', max_length=20)),
                ('note', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pos_debts', to='users.company')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pos_debts_created', to=settings.AUTH_USER_MODEL)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pos_debts', to='sales.customer')),
                ('sale', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='debt', to='sales.sale')),
            ],
            options={'ordering': ['due_date', '-created_at'], 'indexes': [models.Index(fields=['company', 'status'], name='sales_debt_compan_5e6f3a_idx'), models.Index(fields=['customer', 'due_date'], name='sales_debt_custom_32a880_idx')]},
        ),
        migrations.CreateModel(
            name='DebtPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('method', models.CharField(choices=[('cash', 'Cash'), ('card', 'Card'), ('transfer', 'Bank Transfer'), ('online', 'Online'), ('other', 'Other')], default='cash', max_length=20)),
                ('date', models.DateField(default=django.utils.timezone.localdate)),
                ('note', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pos_debt_payments', to='users.company')),
                ('debt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='sales.debt')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pos_debt_payments', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-date', '-created_at']},
        ),
    ]
