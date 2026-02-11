from django.shortcuts import render

# Create your views here.
from django.shortcuts import render

from django_filters import FilterSet
from django_filters import filters
from rest_framework import viewsets, permissions

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework.decorators import action
from rest_framework import serializers
from accounts.models import User
import os


class UserSetFilter(FilterSet):
    title = filters.CharFilter(field_name="title", lookup_expr="icontains")

    class Meta:
        model = User
        fields = "__all__"


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = "__all__"


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.filter()
    serializer_class = UserSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = UserSetFilter
    # permission_classes = [DjangoModelPermissionsOrAnonReadOnly]
