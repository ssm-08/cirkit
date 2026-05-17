# cirkit_app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("",         views.circuit_page,    name="cirkit-ui"),
    path("run/",     views.run_circuit,     name="cirkit-run"),
    path("validate/",views.validate_circuit,name="cirkit-validate"),
]

# In your project's main urls.py:
#   path("cirkit/", include("cirkit_app.urls")),
#
# Endpoints:
#   GET  /cirkit/          → serves ui/index.html
#   POST /cirkit/run/      → streaming circuit execution
#   POST /cirkit/validate/ → circuit validation
