# views.py
from django.views.generic import ListView
from app.medicine.models import Medicine
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET

class HomeView(ListView):
    model = Medicine
    template_name = 'home/home.html'
    context_object_name = 'medicines'

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('search_query', '')
        
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
            )
        else:
            queryset = Medicine.objects.none()
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search_query', '')
        return context

@require_GET
def search_by_formula(request):
    query = request.GET.get('q', '').strip()
    
    if query:
        medicines = Medicine.objects.filter(formula__icontains=query).values(
            'name', 'formula', 'company', 'price', 'stock'
        )
        return JsonResponse(list(medicines), safe=False)
    
    return JsonResponse([], safe=False)

def medicine_search_results(request):
    query = request.GET.get('q', '')
    medicines = Medicine.objects.all()
    
    results = []
    for med in medicines:
        results.append({
            'id': med.id,
            'name': med.name,
            'company': med.company,
            'formula': med.formula,
            'batch_no': med.batch_no if med.batch_no else None,  # Added batch_no field
            'highlighted_name': med.name.replace(query, f'<span class="font-bold">{query}</span>'),
            'price': float(med.price),
            'selling_price': float(med.selling_price),
            'stock': med.stock,
            'rack_number': med.rack_number if med.rack_number else None,
            'discount_display': med.get_discount_display(),
            'calculated_discount': float(med.calculated_discount)
        })
    
    return JsonResponse({'results': results})

