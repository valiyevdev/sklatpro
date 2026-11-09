from django.db import migrations, models
from decimal import Decimal


class Migration(migrations.Migration):
    dependencies = [('products', '0014_product_measurement_unit_product_netto_brutto_and_more')]
    operations = [migrations.AddField(
        model_name='product', name='wholesale_price',
        field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=12, verbose_name='Wholesale Price'),
    )]
