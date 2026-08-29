import logging
from urllib.parse import quote

from asgiref.sync import async_to_sync
from django import forms
from django.contrib import admin, messages
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html

from shop.models import Tariff
from user.models import Profile
from user.services.remnawave_admin import (
    change_subscription_days,
    ensure_whitelist_sync,
    get_all_subscription_statuses,
    get_subscription_sync_status,
)

logger = logging.getLogger(__name__)

__all__ = ()


def _get_cached_subscription_status(profile):
    cache_key = f"admin_rw_subscription:{profile.telegram_id}"
    data = cache.get(cache_key)
    if data is None:
        data = async_to_sync(get_subscription_sync_status)(profile)
        cache.set(cache_key, data, 15)

    return data


def _get_cached_all_subscription_statuses():
    cache_key = "admin_rw_all_subscription_statuses"
    data = cache.get(cache_key)
    if data is None:
        data = async_to_sync(get_all_subscription_statuses)()
        cache.set(cache_key, data, 15)

    return data


class SubscriptionStatusFilter(admin.SimpleListFilter):
    title = "статус подписки"
    parameter_name = "subscription_status"

    def lookups(self, request, model_admin):
        return (
            ("active", "ACTIVE"),
            ("expired", "EXPIRED"),
        )

    def queryset(self, request, queryset):
        if self.value() not in {"active", "expired"}:
            return queryset

        try:
            statuses = _get_cached_all_subscription_statuses()
        except Exception:
            return queryset.none()

        matching_ids = []
        for profile in queryset:
            status = statuses.get(str(profile.telegram_id))
            is_active = bool(status and status["active"])

            if (self.value() == "active") == is_active:
                matching_ids.append(profile.pk)

        return queryset.filter(pk__in=matching_ids)


class TariffAssignmentForm(forms.ModelForm):
    tarif = forms.ModelChoiceField(
        queryset=Tariff.objects.all(),
        required=False,
        label="Тариф",
        help_text="Выберите тариф для назначения. "
        "Синхронизация с Remnawave произойдёт автоматически.",
    )
    subscription_days_delta = forms.IntegerField(
        required=False,
        label="Изменить срок, дней",
        help_text=(
            "Введите положительное число для добавления или отрицательное "
            "для уменьшения. Изменение применяется в Remnawave к обеим "
            "подпискам."
        ),
    )

    class Meta:
        model = Profile
        fields = "__all__"


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    form = TariffAssignmentForm
    list_display = (
        "telegram_avatar",
        "telegram_id",
        "telegram_username",
        "telegram_contact",
        "balance",
        "tarif",
        "remnawave_subscription",
        "created_at",
    )
    search_fields = ("telegram_id", "telegram_username")
    list_filter = (SubscriptionStatusFilter, "tarif", "created_at")
    ordering = ("-created_at",)
    readonly_fields = (
        "created_at",
        "updated_at",
        "whitelist_uuid",
        "remnawave_subscription_info",
        "whitelist_sync_check",
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
                    "remnawave_subscription_info",
                    "whitelist_sync_check",
                    "subscription_days_delta",
                ),
            },
        ),
        (
            "Настройки",
            {
                "fields": (
                    "payment_reminder_enabled",
                    "notifications_enabled",
                    "server_notifications_enabled",
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

    @admin.display(description="Telegram", ordering="telegram_username")
    def telegram_contact(self, obj):
        username = (obj.telegram_username or "").lstrip("@")
        link = (
            f"https://t.me/{quote(username)}"
            if username
            else f"tg://user?id={obj.telegram_id}"
        )
        return format_html(
            '<a href="{}" target="_blank" rel="noopener" '
            'title="Открыть Telegram" style="display:inline-flex;'
            'align-items:center;color:#229ED9;">'
            '<svg width="22" height="22" viewBox="0 0 24 24" '
            'aria-hidden="true"><path fill="currentColor" d="M21.5 3.5L18.3 '
            "20c-.2 1.2-.9 1.5-1.8.9l-5-3.7-2.4 2.3c-.3.3-.5.5-1.1.5l.4-"
            "5.1 9.3-8.4c.4-.4-.1-.6-.6-.2L6.6 13.5l-5-1.6c-1.1-.3-1.1-"
            '1.1.2-1.6L21.1 3c.9-.3 1.6.2 1.4.5z"/></svg></a>',
            link,
        )

    @admin.display(description="")
    def telegram_avatar(self, obj):
        avatar_url = obj.telegram_avatar_url
        if avatar_url:
            return format_html(
                '<img src="{}" width="34" height="34" '
                'style="border-radius:50%;object-fit:cover;" '
                'alt="Аватар Telegram">',
                avatar_url,
            )

        initials = (obj.telegram_username or "TG").lstrip("@")[:1].upper()
        return format_html(
            '<span style="display:inline-flex;width:34px;height:34px;'
            "align-items:center;justify-content:center;border-radius:50%;"
            'background:#229ED9;color:#fff;font-weight:700;">{}</span>',
            initials,
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

        days_delta = form.cleaned_data.get("subscription_days_delta")
        if days_delta:
            try:
                async_to_sync(change_subscription_days)(obj, days_delta)
                self.message_user(
                    request,
                    f"Срок изменён на {days_delta:+d} дн. в Remnawave "
                    "для основной и _wl подписки.",
                    messages.SUCCESS,
                )
            except Exception as e:
                logger.error(
                    "Failed to change subscription days for profile %s: %s",
                    obj.telegram_id,
                    e,
                )
                self.message_user(
                    request,
                    f"Ошибка изменения срока в Remnawave: {e}",
                    messages.ERROR,
                )

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

    def remnawave_subscription_info(self, obj):
        try:
            data = async_to_sync(get_subscription_sync_status)(obj)
            rows = []
            for title, key in (("Основная", "main"), ("_wl", "whitelist")):
                user = data[key]
                if user is None:
                    rows.append(f"{title}: не найден")
                    continue

                rows.append(
                    f"{title}: {user['remaining_days']} дн. "
                    f"({user['status']})",
                )

            return format_html("{}<br>{}", *rows)
        except Exception as e:
            return format_html("Ошибка проверки: {}", e)

    remnawave_subscription_info.short_description = "Срок в Remnawave"

    @admin.display(description="Подписка Remnawave")
    def remnawave_subscription(self, obj):
        try:
            statuses = _get_cached_all_subscription_statuses()
        except Exception:
            return format_html(
                '<span style="color:#ba1a1a;">Ошибка связи</span>',
            )

        status_data = statuses.get(str(obj.telegram_id))
        if status_data is None:
            return format_html(
                '<span style="color:#ba1a1a;">Не найден</span>',
            )

        active = status_data["active"]
        color = "#146c2e" if active else "#ba1a1a"
        background = "#d6f5dc" if active else "#ffdad6"
        return format_html(
            '<span style="display:inline-block;padding:4px 9px;'
            "border-radius:999px;background:{};color:{};font-weight:600;"
            'font-size:12px;">{} · {} дн.</span>',
            background,
            color,
            status_data["status"],
            status_data["remaining_days"],
        )

    def whitelist_sync_check(self, obj):
        url = reverse(
            "admin:profile_check_whitelist_sync",
            args=[obj.pk],
        )
        return format_html(
            '<a class="button" href="{}">Проверить / создать _wl</a>',
            url,
        )

    whitelist_sync_check.short_description = "Проверка синхронизации"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/check-whitelist-sync/",
                self.admin_site.admin_view(self.check_whitelist_sync),
                name="profile_check_whitelist_sync",
            ),
        ]
        return custom_urls + urls

    def check_whitelist_sync(self, request, object_id):
        obj = self.get_object(request, object_id)
        if obj is None:
            self.message_user(
                request,
                "Пользователь не найден.",
                messages.ERROR,
            )
            return HttpResponseRedirect("../")

        try:
            tariff = obj.tarif
            whitelist = async_to_sync(ensure_whitelist_sync)(obj, tariff)
            if obj.whitelist_uuid != whitelist["uuid"]:
                Profile.objects.filter(pk=obj.pk).update(
                    whitelist_uuid=whitelist["uuid"],
                )
                obj.whitelist_uuid = whitelist["uuid"]
                cache.delete(f"admin_rw_subscription:{obj.telegram_id}")
                self.message_user(
                    request,
                    "_wl найден/создан, UUID синхронизирован с БД Gamma.",
                    messages.SUCCESS,
                )
            else:
                self.message_user(
                    request,
                    "_wl уже синхронизирован с БД Gamma.",
                    messages.SUCCESS,
                )

            data = async_to_sync(get_subscription_sync_status)(obj)
            whitelist = data["whitelist"]
            self.message_user(
                request,
                f"_wl: {whitelist['remaining_days']} дн., "
                f"статус {whitelist['status']}.",
                messages.SUCCESS,
            )
        except Exception as e:
            self.message_user(
                request,
                f"Ошибка проверки _wl: {e}",
                messages.ERROR,
            )

        return HttpResponseRedirect(
            reverse("admin:user_profile_change", args=[obj.pk]),
        )
