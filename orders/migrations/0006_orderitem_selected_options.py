from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("orders", "0005_alter_order_status")]
    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="selected_options",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
