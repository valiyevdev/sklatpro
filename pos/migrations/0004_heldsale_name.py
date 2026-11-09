from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pos', '0003_heldsale_terminal_nullable')]
    operations = [migrations.AddField(
        model_name='heldsale', name='name', field=models.CharField(blank=True, default='', max_length=120),
    )]
