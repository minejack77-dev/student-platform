from django.shortcuts import render

from django_filters import FilterSet
from django_filters import filters
from rest_framework import viewsets, permissions

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework.decorators import action
from rest_framework import serializers
from learning.models import Topic, Group
from accounts.models import Student
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


class GroupSetFilter(FilterSet):
    title = filters.CharFilter(field_name="title", lookup_expr="icontains")

    class Meta:
        model = Group
        fields = "__all__"


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = "__all__"


class StudentBriefSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Student
        fields = ("id", "user", "username", "email")


class GroupDetailSerializer(serializers.ModelSerializer):
    students = StudentBriefSerializer(many=True, read_only=True)

    class Meta:
        model = Group
        fields = "__all__"


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.prefetch_related("students__user").filter()
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = GroupSetFilter

    def get_serializer_class(self):
        if self.action == "retrieve":
            return GroupDetailSerializer
        return GroupSerializer
