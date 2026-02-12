from django.urls import path
from .views import ConsumeEnergyView

urlpatterns = [
    path("consume/", ConsumeEnergyView.as_view(), name="consume-energy"),
]