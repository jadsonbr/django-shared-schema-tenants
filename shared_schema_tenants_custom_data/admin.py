from django.contrib import admin
from shared_schema_tenants_custom_data.forms import TenantSpecificModelForm
from shared_schema_tenants_custom_data.models import (
    TenantSpecificTable, TenantSpecificFieldDefinition, TenantSpecificTableRow, TenantSpecificFieldsValidator)


class TenantSpecificModelAdmin(admin.ModelAdmin):
    form = TenantSpecificModelForm


admin.site.register(TenantSpecificTable)
admin.site.register(TenantSpecificFieldDefinition)
admin.site.register(TenantSpecificTableRow)
admin.site.register(TenantSpecificFieldsValidator)
