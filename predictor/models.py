from django.db import models

ROUTE_CHOICES = [
    ('thika', 'Thika Road'),
    ('mombasa', 'Mombasa Road'),
    ('waiyaki', 'Waiyaki Way'),
    ('ngong', 'Ngong Road'),
    ('langata', 'Lang\'ata Road'),
]

class Subscriber(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    route = models.CharField(max_length=50, choices=ROUTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.phone} ({self.route})"