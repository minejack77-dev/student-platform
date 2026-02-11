from django.shortcuts import render

from django_filters import FilterSet
from django_filters import filters
from rest_framework import viewsets, permissions

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework.decorators import action
from rest_framework import serializers
from learning.models import Topic
import os

# Create your views here.


class TopicSetFilter(FilterSet):
    title = filters.CharFilter(field_name="title", lookup_expr="icontains")

    class Meta:
        model = Topic
        fields = "__all__"


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = "__all__"


class TopicViewSet(viewsets.ModelViewSet):
    queryset = Topic.objects.filter()
    serializer_class = TopicSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = TopicSetFilter
    # permission_classes = [DjangoModelPermissionsOrAnonReadOnly]
