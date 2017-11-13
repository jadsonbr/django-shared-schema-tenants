from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.forms.fields import FileField

from shared_schema_tenants.utils import import_item
from shared_schema_tenants_custom_data.models import (
    TenantSpecificFieldDefinition, TenantSpecificTable, TenantSpecificTableRow)
from shared_schema_tenants_custom_data.utils import compose_list
from shared_schema_tenants_custom_data.helpers.custom_tables_helpers import get_custom_table_manager


class TenantSpecificModelForm(forms.ModelForm):

    form_tenant_specific_field_mapping = {
        'integer': forms.IntegerField,
        'char': forms.CharField,
        'text': forms.CharField,
        'float': forms.FloatField,
        'datetime': forms.DateTimeField,
        'date': forms.DateField,
    }

    def __init__(self, *args, **kwargs):
        ModelClass = self.Meta.model

        self.tenant_specific_fields_definitions = TenantSpecificFieldDefinition.objects.filter(
            table_content_type=ContentType.objects.get_for_model(ModelClass))

        for definition in self.tenant_specific_fields_definitions:
            if not hasattr(self, definition.name):
                field_kwargs = {}
                if definition.is_required:
                    field_kwargs.update({
                        'required': True,
                        'allow_null': True
                    })
                if definition.default_value is not None:
                    field_kwargs.update({'default': definition.default_value})

                setattr(self, definition.name,
                        self.form_tenant_specific_field_mapping[definition.data_type](**field_kwargs))

        super(TenantSpecificModelForm, self).__init__(*args, **kwargs)

    def full_clean(self):
        """
        Clean all of self.data and populate self._errors and self.cleaned_data.
        """
        from django.forms.utils import ErrorDict
        self._errors = ErrorDict()
        if not self.is_bound:  # Stop further processing.
            return
        self.cleaned_data = {}
        # If the form is permitted to be empty, and none of the form data has
        # changed from the initial data, short circuit any validation.
        if self.empty_permitted and not self.has_changed():
            return

        self._clean_fields()
        self._clean_tenant_specific_fields()
        self._clean_form()
        self._post_clean()

    def _clean_tenant_specific_fields(self):
        tenant_specific_fields_names = self.tenant_specific_fields_definitions.values_list('name', flat=True)
        for name, field in self.fields.items():
            if name in tenant_specific_fields_names:
                value = field.widget.value_from_datadict(self.data, self.files, self.add_prefix(name))
                try:
                    value = field.clean(value)
                    validators = []
                    for validator_instance in field.validators.all():
                        validator_function = import_item(validator_instance.module_path)
                        validators.append(validator_function)

                    validate_method = compose_list(validators)
                    self.cleaned_data[name] = validate_method(value)
                    if hasattr(self, 'clean_%s' % name):
                        value = getattr(self, 'clean_%s' % name)()
                        self.cleaned_data[name] = value
                except ValidationError as e:
                    self.add_error(name, e)

    def _clean_fields(self):
        tenant_specific_fields_names = self.tenant_specific_fields_definitions.values_list('name', flat=True)
        for name, field in self.fields.items():
            # value_from_datadict() gets the data from the data dictionaries.
            # Each widget type knows how to retrieve its own data, because some
            # widgets split data over several HTML fields.
            if name not in tenant_specific_fields_names:
                if field.disabled:
                    value = self.get_initial_for_field(field, name)
                else:
                    value = field.widget.value_from_datadict(self.data, self.files, self.add_prefix(name))
                try:
                    if isinstance(field, FileField):
                        initial = self.get_initial_for_field(field, name)
                        value = field.clean(value, initial)
                    else:
                        value = field.clean(value)
                    self.cleaned_data[name] = value
                    if hasattr(self, 'clean_%s' % name):
                        value = getattr(self, 'clean_%s' % name)()
                        self.cleaned_data[name] = value
                except ValidationError as e:
                    self.add_error(name, e)


def get_tenant_specific_table_row_form_class(table_name):

    table_id = TenantSpecificTable.objects.get(name=table_name).id
    tenant_specific_fields_definitions = TenantSpecificFieldDefinition.objects.filter(
        table_content_type=ContentType.objects.get_for_model(TenantSpecificTable),
        table_id=table_id
    )
    tenant_specific_fields_names = list(tenant_specific_fields_definitions.values_list('name', flat=True))

    form_tenant_specific_field_mapping = {
        'integer': forms.IntegerField,
        'char': forms.CharField,
        'text': forms.CharField,
        'float': forms.FloatField,
        'datetime': forms.DateTimeField,
        'date': forms.DateField,
    }

    class TenantSpecificTableRowFormMetaclass(forms.models.ModelFormMetaclass):

        def __new__(mcs, name, bases, attrs):
            for definition in tenant_specific_fields_definitions:
                if not attrs.get(definition.name, False):
                    field_kwargs = {}
                    if definition.is_required:
                        field_kwargs.update({
                            'required': True,
                            'allow_null': True
                        })
                    if definition.default_value is not None:
                        field_kwargs.update({'initial': definition.default_value})

                    attrs[definition.name] = form_tenant_specific_field_mapping[definition.data_type](
                        **field_kwargs)
            return super(TenantSpecificTableRowFormMetaclass, mcs).__new__(mcs, name, bases, attrs)

    class TenantSpecificTableRowForm(forms.ModelForm, metaclass=TenantSpecificTableRowFormMetaclass):

        class Meta:
            model = TenantSpecificTableRow
            fields = ['id'] + tenant_specific_fields_names

        form_tenant_specific_field_mapping = {
            'integer': forms.IntegerField,
            'char': forms.CharField,
            'text': forms.CharField,
            'float': forms.FloatField,
            'datetime': forms.DateTimeField,
            'date': forms.DateField,
        }

        def __init__(self, *args, **kwargs):
            super(TenantSpecificTableRowForm, self).__init__(*args, **kwargs)

        def full_clean(self):
            """
            Clean all of self.data and populate self._errors and self.cleaned_data.
            """
            from django.forms.utils import ErrorDict
            self._errors = ErrorDict()
            if not self.is_bound:  # Stop further processing.
                return
            self.cleaned_data = {'table_id': table_id}
            # If the form is permitted to be empty, and none of the form data has
            # changed from the initial data, short circuit any validation.
            if self.empty_permitted and not self.has_changed():
                return

            self._clean_fields()
            self._clean_tenant_specific_fields()
            self._clean_form()
            self._post_clean()

        def _clean_tenant_specific_fields(self):
            for name, field in self.fields.items():
                if name in tenant_specific_fields_names:
                    definition = tenant_specific_fields_definitions.get(name=name)
                    value = field.widget.value_from_datadict(self.data, self.files, self.add_prefix(name))
                    try:
                        value = field.clean(value)
                        validators = []
                        for validator_instance in definition.validators.all():
                            validator_function = import_item(validator_instance.module_path)
                            validators.append(validator_function)

                        validate_method = compose_list(validators)
                        self.cleaned_data[name] = validate_method(value)
                        if hasattr(self, 'clean_%s' % name):
                            value = getattr(self, 'clean_%s' % name)()
                            self.cleaned_data[name] = value
                    except ValidationError as e:
                        self.add_error(name, e)

        def save(self, *args, **kwargs):
            self.instance.table_id = table_id
            new_instance = super(TenantSpecificTableRowForm, self).save(*args, **kwargs)
            return get_custom_table_manager(table_name).get(id=new_instance.id)

        def _post_clean(self):
            super()._post_clean()
            for name, value in [(k, v) for k, v in self.cleaned_data.items() if k in tenant_specific_fields_names]:
                setattr(self.instance, name, value)

        def _clean_fields(self):
            tenant_specific_fields_names = tenant_specific_fields_definitions.values_list('name', flat=True)
            for name, field in self.fields.items():
                # value_from_datadict() gets the data from the data dictionaries.
                # Each widget type knows how to retrieve its own data, because some
                # widgets split data over several HTML fields.
                if name not in tenant_specific_fields_names:
                    if field.disabled:
                        value = self.get_initial_for_field(field, name)
                    else:
                        value = field.widget.value_from_datadict(self.data, self.files, self.add_prefix(name))
                    try:
                        if isinstance(field, FileField):
                            initial = self.get_initial_for_field(field, name)
                            value = field.clean(value, initial)
                        else:
                            value = field.clean(value)
                        self.cleaned_data[name] = value
                        if hasattr(self, 'clean_%s' % name):
                            value = getattr(self, 'clean_%s' % name)()
                            self.cleaned_data[name] = value
                    except ValidationError as e:
                        self.add_error(name, e)

    return TenantSpecificTableRowForm
