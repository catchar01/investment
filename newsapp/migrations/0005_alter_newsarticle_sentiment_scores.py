# Generated by Django 4.2.9 on 2024-04-05 11:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("newsapp", "0004_newsarticle_sentiment_scores"),
    ]

    operations = [
        migrations.AlterField(
            model_name="newsarticle",
            name="sentiment_scores",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
