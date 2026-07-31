from rest_framework.views import APIView
from rest_framework.response import Response
from adminpanel.permissions import IsAdminUser
from .engine import generate_insights


class InsightsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        insights = generate_insights()
        return Response({'insights': insights, 'count': len(insights)})
