from typing import get_type_hints, Optional, List, Union
from fastapi import Form
from pydantic import BaseModel
from inspect import signature, Parameter

def as_form(cls):
    new_params = []

    for field_name, model_field in cls.__annotations__.items():
        default = getattr(cls, field_name, ...)
        actual_type = model_field

        if hasattr(actual_type, '__origin__') and actual_type.__origin__ in [list, List]:
            item_type = actual_type.__args__[0]
            new_params.append(
                Parameter(
                    field_name,
                    Parameter.POSITIONAL_ONLY,
                    default=Form(default if default is not None else None),
                    annotation=List[item_type],
                )
            )
        else:
            new_params.append(
                Parameter(
                    field_name,
                    Parameter.POSITIONAL_ONLY,
                    default=Form(default),
                    annotation=actual_type,
                )
            )

    def as_form_func(*args, **kwargs):
        return cls(*args, **kwargs)

    sig = signature(as_form_func)
    as_form_func.__signature__ = sig.replace(parameters=new_params)
    setattr(cls, "as_form", classmethod(as_form_func))
    return cls
