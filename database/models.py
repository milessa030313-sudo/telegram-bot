from django.db import models

class User(models.Model):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username


class Listing(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.title


class SentListing(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    sent_at = models.DateTimeField(auto_now_add=True)


class Stats(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    views = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Stats for {self.listing.title}"