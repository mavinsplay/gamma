import logging

from asgiref.sync import async_to_sync
from django import forms
from django.contrib import admin, messages

from shop.models import Tariff
from user.models import Profile

logger = logging.getLogger(__name__)

__all__ = ()


class TariffAssignmentForm(forms.ModelForm):
    tarif = forms.ModelChoiceField(
        queryset=Tariff.objects.all(),
        required=False,
        label="Тариф",
        help_text="Выберите тариф для назначения. "
        "Синхронизация с Remnawave произойдёт автоматически.",
    )

    class Meta:
        model = Profile
        fields = "__all__"


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    form = TariffAssignmentForm
    list_display = (
        "telegram_id",
        "telegram_username",
        "balance",
        "tarif",
        "created_at",
    )
    search_fields = ("telegram_id", "telegram_username")
    list_filter = ("tarif", "created_at")
    ordering = ("-created_at",)
    readonly_fields = (
        "created_at",
        "updated_at",
        "whitelist_uuid",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "telegram_id",
                    "telegram_username",
                    "balance",
                ),
            },
        ),
        (
            "Тариф",
            {
                "fields": (
                    "tarif",
                    "whitelist_uuid",
                ),
            },
        ),
        (
            "Настройки",
            {
                "fields": (
                    "payment_reminder_enabled",
                    "notifications_enabled",
                    "subscription_expired_notification_sent",
                ),
            },
        ),
        (
            "Метки",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        old_tarif = None
        if change:
            try:
                old_obj = Profile.objects.get(pk=obj.pk)
                old_tarif = old_obj.tarif
            except Profile.DoesNotExist:
                pass

        new_tarif = form.cleaned_data.get("tarif")
        tariff_changed = old_tarif != new_tarif

        super().save_model(request, obj, form, change)

        if tariff_changed:
            try:
                from shop.services.remnawave_sync import (
                    sync_tariff_to_remnawave,
                )

                rw_data, wl_uuid = async_to_sync(
                    sync_tariff_to_remnawave,
                )(obj, new_tarif)

                # Persist whitelist_uuid
                if wl_uuid:
                    Profile.objects.filter(pk=obj.pk).update(
                        whitelist_uuid=wl_uuid,
                    )
                    obj.whitelist_uuid = wl_uuid
                else:
                    Profile.objects.filter(pk=obj.pk).update(
                        whitelist_uuid=None,
                    )
                    obj.whitelist_uuid = None

                if new_tarif:
                    self.message_user(
                        request,
                        f"Тариф «{new_tarif.name}» назначен. "
                        f"Remnawave синхронизирован.",
                        messages.SUCCESS,
                    )
                else:
                    self.message_user(
                        request,
                        "Тариф снят. " "Remnawave синхронизирован.",
                        messages.SUCCESS,
                    )
            except Exception as e:
                logger.error(
                    "Failed to sync tariff to Remnawave " "for profile %s: %s",
                    obj.telegram_id,
                    e,
                )
                self.message_user(
                    request,
                    f"Ошибка синхронизации с Remnawave: {e}",
                    messages.ERROR,
                )
