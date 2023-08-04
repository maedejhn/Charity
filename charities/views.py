from rest_framework import status, generics
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsCharityOwner, IsBenefactor
from charities.models import Task
from charities.serializers import (
    TaskSerializer, CharitySerializer, BenefactorSerializer
)
from .models import *


class BenefactorRegistration(generics.CreateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = BenefactorSerializer

    def post(self, request, *args, **kwargs):
        benefactor_serializer = BenefactorSerializer(data=request.data)
        if benefactor_serializer.is_valid():
            benefactor_serializer.save(user=request.user)
            return Response(benefactor_serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(benefactor_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CharityRegistration(generics.CreateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = CharitySerializer

    def post(self, request, *args, **kwargs):
        charity_serializer = CharitySerializer(data=request.data)
        if charity_serializer.is_valid():
            charity_serializer.save(user=request.user)
            return Response(charity_serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(charity_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class Tasks(generics.ListCreateAPIView):
    serializer_class = TaskSerializer

    def get_queryset(self):
        return Task.objects.all_related_tasks_to_user(self.request.user)

    def post(self, request, *args, **kwargs):
        data = {
            **request.data,
            "charity_id": request.user.charity.id
        }
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            self.permission_classes = [IsAuthenticated, ]
        else:
            self.permission_classes = [IsCharityOwner, ]

        return [permission() for permission in self.permission_classes]

    def filter_queryset(self, queryset):
        filter_lookups = {}
        for name, value in Task.filtering_lookups:
            param = self.request.GET.get(value)
            if param:
                filter_lookups[name] = param
        exclude_lookups = {}
        for name, value in Task.excluding_lookups:
            param = self.request.GET.get(value)
            if param:
                exclude_lookups[name] = param

        return queryset.filter(**filter_lookups).exclude(**exclude_lookups)


class TaskRequest(generics.GenericAPIView):
    permission_classes = [IsBenefactor]

    def get(self, request, task_id):
        task = get_object_or_404(Task.objects, id=task_id)

        if task.state == 'P':
            task.assign_to_benefactor(benefactor=request.user.benefactor)
            task.save()
            return Response(data={'detail': 'Request sent.'}, status=status.HTTP_200_OK)

        else:
            return Response(data={'detail': 'This task is not pending.'}, status=status.HTTP_404_NOT_FOUND)


class TaskResponse(generics.GenericAPIView):
    permission_classes = (IsCharityOwner,)

    def post(self, request, task_id):
        task = Task.objects.get(id=task_id)
        response = request.data['response']
        if (response != "A") & (response != "R"):
            return Response(data={'detail': 'Required field ("A" for accepted / "R" for rejected)'},
                            status=status.HTTP_400_BAD_REQUEST)
        elif task.state != 'W':
            return Response(data={'detail': 'This task is not waiting.'}, status=status.HTTP_404_NOT_FOUND)
        elif response == 'A':
            task._accept_benefactor()
            return Response(data={'detail': 'Response sent.'}, status=status.HTTP_200_OK)
        else:
            task._reject_benefactor()
            return Response(data={'detail': 'Response sent.'}, status=status.HTTP_200_OK)


class DoneTask(APIView):
    permission_classes = (IsCharityOwner,)

    def post(self, request, task_id):
        task = Task.objects.get(id=task_id)
        if task is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        elif task.state != 'A':
            return Response(data={'detail': 'Task is not assigned yet.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            task.state = 'D'
            task.save()
            return Response(data={'detail': 'Task has been done successfully.'}, status=status.HTTP_200_OK)
