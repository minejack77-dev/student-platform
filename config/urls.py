"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from django.conf.urls import include

from rest_framework.routers import DefaultRouter
from learning import views as learning_views
from accounts import views as accounts_views
from django.views.generic import TemplateView
from django.views.generic import RedirectView
from django.http import FileResponse, Http404
from django.conf import settings

def serve_sw(request):
    sw_path = settings.BASE_DIR / "student-platform-frontend" / "dist" / "static" / "sw.js"
    if not sw_path.exists():
        raise Http404("sw.js not found")
    response = FileResponse(open(sw_path, "rb"), content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    return response


def serve_manifest(request):
    path = settings.BASE_DIR / "student-platform-frontend" / "dist" / "manifest.webmanifest"
    if not path.exists():
        raise Http404("manifest.webmanifest not found")
    return FileResponse(open(path, "rb"), content_type="application/manifest+json")


router = DefaultRouter()
router.register(r"subject", learning_views.SubjectViewSet, basename="subject")
router.register(r"workbook", learning_views.WorkbookViewSet, basename="workbook")
router.register(r"unit", learning_views.UnitViewSet, basename="unit")
router.register(r"topic", learning_views.TopicViewSet, basename="topic")
router.register(r"task", learning_views.TaskViewSet, basename="task")
router.register(r"question", learning_views.QuestionViewSet, basename="question")
router.register(r"group", learning_views.GroupViewSet, basename="group")
router.register(r"user", accounts_views.UserViewSet, basename="user")
router.register(r"teacher", accounts_views.TeacherViewSet, basename="teacher")
router.register(r"student", accounts_views.StudentViewSet, basename="student")
router.register(r"attempt", learning_views.AttemptViewSet, basename="attempt")
router.register(
    r"attempt_question",
    learning_views.AttemptQuestionViewSet,
    basename="attempt_question",
)
router.register(r"answer", learning_views.AnswerViewSet, basename="answer")

urlpatterns = [path("admin/", admin.site.urls), path("api/", include(router.urls)), path("webpush/", include("webpush.urls"))]
urlpatterns += [
    path("sw.js", serve_sw, name="sw"),
    path("api/auth/csrf/", accounts_views.CsrfCookieView.as_view(), name="auth-csrf"),
    path("api/auth/login/", accounts_views.LoginView.as_view(), name="auth-login"),
    path("api/auth/logout/", accounts_views.LogoutView.as_view(), name="auth-logout"),
    path(
        "api/auth/me/", accounts_views.MeView.as_view(), name="auth-me"
    ),  # Возвращает текущего пользователя
    path("", TemplateView.as_view(template_name="index.html"), name="index"),
    path("manifest.webmanifest", serve_manifest, name="manifest"),
    path(
        "<path:route>", TemplateView.as_view(template_name="index.html"), name="index"
    ),
]
