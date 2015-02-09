from django.db import models
from django.contrib.auth.models import User
    
class Comments(models.Model):
    user = models.ForeignKey(User)
    text = models.CharField(max_length=255)
    parse = models.CharField(max_length=8192)
    mrs = models.CharField(max_length=8192)
