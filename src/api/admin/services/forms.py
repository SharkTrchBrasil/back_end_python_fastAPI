# src/utils/forms.py

from fastapi import Form
from pydantic import BaseModel
from typing import get_type_hints
from inspect import Parameter, Signature

def make_signature(fields):
    return Signature(
        parameters=[
            Parameter(
                name=name,
                kind=Parameter.POSITIONAL_OR_KEYWORD,
                default=default,
                annotation=field_type,
            )
            for name, default, field_type in fields
        ]
    )

def as_form(cls):
    hints = get_type_hints(cls)
    fields = []
    for field_name, field_type in hints.items():
        default = getattr(cls, field_name, ...)

        if default is ...:
            default = Form(...)  # obrigatório no form
        else:
            default = Form(default)  # opcional com valor default


        fields.append((field_name, default, field_type))
    cls.__signature__ = make_signature(fields)
    cls.__init__ = lambda self, **data: BaseModel.__init__(self, **data)
    return cls
