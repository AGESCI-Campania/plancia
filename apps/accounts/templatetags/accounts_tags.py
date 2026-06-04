from django import template

register = template.Library()

_RUOLO_BADGE = {
    "admin": "bg-danger",
    "segreteria": "bg-primary",
    "incaricato_eg": "badge-iabr",
    "csq": "bg-success",
    "crp": "bg-warning text-dark",
    "pgv": "bg-info text-dark",
}

_RUOLO_AVATAR = {
    "admin": "avatar-admin",
    "segreteria": "avatar-segreteria",
    "incaricato_eg": "avatar-iabr",
    "csq": "avatar-csq",
    "crp": "avatar-crp",
    "pgv": "avatar-pgv",
}


@register.filter
def ruolo_badge_class(ruolo: str) -> str:
    return _RUOLO_BADGE.get(ruolo, "bg-secondary")


@register.filter
def ruolo_avatar_class(ruolo: str) -> str:
    return _RUOLO_AVATAR.get(ruolo, "")
