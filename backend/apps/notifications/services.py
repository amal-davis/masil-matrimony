from .models import Notification


def notify(recipient, kind, title, body="", link=""):
    """Record an in-app notification. Call inside the transaction of the change it reports."""
    return Notification.objects.create(recipient=recipient, kind=kind, title=title, body=body, link=link)
