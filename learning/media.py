from pathlib import PurePosixPath
from django.http import FileResponse, Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from learning.models import QuestionImage, Topic, Task, AttemptQuestion
from learning.permissions import has_teacher_profile
from learning.services.material_access import can_read_attempt_material


class PrivateMediaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, path):
        if ".." in PurePosixPath(path).parts or "\\" in path or path.startswith("/"):
            raise Http404
        image = QuestionImage.objects.filter(image=path).first()
        file = None
        content_type = "application/octet-stream"
        attachment = True
        if image:
            teacher_access = request.user.is_superuser or (has_teacher_profile(request.user) and request.user.has_perm("learning.view_question"))
            student_access = any(
                any(item["id"] == image.pk for item in question.content_snapshot.get("images", []))
                and can_read_attempt_material(question.attempt)
                for question in AttemptQuestion.objects.filter(
                    question_id=image.question_id, attempt__student__user=request.user,
                ).select_related(
                    "attempt__schedule_entry__group", "attempt__schedule_entry__topic__subject",
                    "attempt__schedule_entry__task",
                )
            )
            if not (teacher_access or student_access):
                raise Http404
            file = image.image
            types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
            content_type = types.get(PurePosixPath(path).suffix.lower(), content_type)
            attachment = content_type == "application/octet-stream"
        elif request.user.is_superuser or has_teacher_profile(request.user):
            for model in (Task, Topic):
                if request.user.has_perm(f"learning.view_{model._meta.model_name}"):
                    obj = model.objects.filter(src=path).first()
                    if obj:
                        file = obj.src
                        break
        if file is None:
            raise Http404
        try:
            response = FileResponse(file.open("rb"), as_attachment=attachment, filename=PurePosixPath(path).name, content_type=content_type)
        except (FileNotFoundError, OSError):
            raise Http404
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Vary"] = "Cookie"
        return response
