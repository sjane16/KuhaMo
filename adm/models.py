from django.db import models


class Building(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10)
    has_floors = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Floor(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='floors')
    floor_number = models.IntegerField()
    label = models.CharField(max_length=100)

    class Meta:
        ordering = ['floor_number']
        unique_together = ['building', 'floor_number']

    def __str__(self):
        return f"{self.building.name} - Floor {self.floor_number}"


class Room(models.Model):
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name='rooms')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    order = models.PositiveIntegerField(default=0, help_text = "Controls the display order in dropdown.")

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name
    
