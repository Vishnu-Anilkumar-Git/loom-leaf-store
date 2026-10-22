from django.core.management.base import BaseCommand

from orders.notifications import send_abandoned_cart_reminders


class Command(BaseCommand):
    help = "Send one-time reminders for signed-in carts unchanged for 24 hours."

    def handle(self, *args, **options):
        count = send_abandoned_cart_reminders()
        self.stdout.write(self.style.SUCCESS(f"Sent {count} abandoned-cart reminder(s)."))
