from django.apps import AppConfig


class MailInboxConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mail_inbox"
    verbose_name = "SchoolDom Mail Receiver"
