from django.db import models

ROUTE_CHOICES = [
    ('thika', 'Thika Road'),
    ('mombasa', 'Mombasa Road'),
    ('waiyaki', 'Waiyaki Way'),
    ('ngong', 'Ngong Road'),
    ('langata', "Lang'ata Road"),
]

FREQUENCY_CHOICES = [
    ('morning', 'Morning Only'),
    ('evening', 'Evening Only'),
    ('both', 'Morning & Evening'),
]

NOTIFY_BEFORE_CHOICES = [
    ('30', '30 minutes before'),
    ('60', '1 hour before'),
    ('120', '2 hours before'),
]

class Subscriber(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    route = models.CharField(max_length=50, choices=ROUTE_CHOICES)
    morning_time = models.TimeField(null=True, blank=True)
    evening_time = models.TimeField(null=True, blank=True)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='morning')
    notify_before = models.IntegerField(default=60)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.phone} ({self.route})"