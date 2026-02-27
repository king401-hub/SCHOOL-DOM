from django.contrib import admin
from .models import ThemeConfiguration, FeatureFlag

admin.site.register(ThemeConfiguration)
admin.site.register(FeatureFlag)
