from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('sales', '0005_make_customer_nullable')]
    operations = [migrations.AddField(
        model_name='sale', name='idempotency_key',
        field=models.CharField(blank=True, max_length=80, null=True, unique=True),
    )]
