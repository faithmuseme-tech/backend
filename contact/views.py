from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from adminpanel.permissions import IsAdminUser
from .models import ContactInquiry
from .serializers import ContactInquirySerializer, ContactInquiryAdminSerializer


class ContactInquiryCreateView(APIView):
    """Public — anyone can submit an inquiry."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ContactInquirySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'detail': 'Inquiry submitted successfully.'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminInquiryListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = ContactInquiryAdminSerializer

    def get_queryset(self):
        qs = ContactInquiry.objects.all()
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class AdminInquiryDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = ContactInquiryAdminSerializer
    queryset = ContactInquiry.objects.all()
