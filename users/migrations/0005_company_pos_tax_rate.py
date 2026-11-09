from django.db import migrations, models
from decimal import Decimal


class Migration(migrations.Migration):
    dependencies = [('users', '0004_delete_notification')]
    operations = [migrations.AddField(
        model_name='company', name='pos_tax_rate',
        field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=5, verbose_name='POS Tax Rate (%)'),
    )]
