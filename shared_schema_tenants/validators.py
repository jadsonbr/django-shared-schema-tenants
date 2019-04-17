import json
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _


def validate_json(value):
    try:
        value = json.loads(value)
    except Exception:
        raise ValidationError(_("This field must be a valid json"))

    return value
