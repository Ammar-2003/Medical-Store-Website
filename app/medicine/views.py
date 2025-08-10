from django.views.generic import UpdateView, DeleteView, ListView , DetailView , TemplateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse
from .models import Medicine , PurchaseRecord
from .forms import MedicineAddForm , MedicineUpdateForm
from django.views.generic.edit import FormMixin
from django.utils import timezone
from datetime import datetime
from django.db.models import Sum, ExpressionWrapper, DecimalField , Value , Sum , Q , DateField
from django.db.models.functions import Coalesce , TruncDate
from decimal import Decimal
import pytz
from datetime import timedelta
from datetime import time


class MedicineInventoryView(FormMixin, ListView):
    model = Medicine
    form_class = MedicineAddForm  # Changed to MedicineAddForm
    template_name = 'medicines/medicine.html'
    context_object_name = 'medicines'
    ordering = ['-created_at']
    success_url = reverse_lazy('medicine')

    def get_queryset(self):
        queryset = super().get_queryset()
        self.search_query = self.request.GET.get('search', '')
        
        if self.search_query:
            try:
                medicine_id = int(self.search_query)
                queryset = queryset.filter(id=medicine_id)
            except ValueError:
                queryset = queryset.filter(name__icontains=self.search_query)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'form' not in context:
            context['form'] = self.get_form()
        context['search_query'] = self.request.GET.get('search', '')
        return context

    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        form = self.get_form()

        if form.is_valid():
            form.save()
            messages.success(self.request, "Medicine added successfully with initial stock.")
            return self.form_valid(form)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(self.request, f"{field.capitalize()}: {error}")
            return self.form_invalid(form)

class MedicineUpdateView(UpdateView):
    model = Medicine
    form_class = MedicineUpdateForm  # Changed to MedicineUpdateForm
    template_name = 'medicines/medicine_update.html'
    success_url = reverse_lazy('medicine')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.get_object()
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        additional_stock = form.cleaned_data.get('additional_stock', 0)
        
        if additional_stock > 0:
            messages.success(self.request, f'Added {additional_stock} units to stock')
        messages.success(self.request, 'Medicine details updated successfully')
        return response


class MedicineDeleteView(DeleteView):
    model = Medicine
    template_name = 'medicines/confirm_delete.html'
    success_url = reverse_lazy('medicine')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Medicine deleted successfully!')
        return super().delete(request, *args, **kwargs)

def medicine_suggestions(request):
    query = request.GET.get('q', '')
    medicines = Medicine.objects.filter(name__icontains=query).order_by('name')[:10]
    
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

class MedicineDetailView(DetailView):
    model = Medicine
    template_name = 'medicines/medicine_detail.html'
    context_object_name = 'medicine'  # This name will be used in your template
    
    # Optional: Add extra context
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"{self.object.name} Details"
        return context


class MedicineDashboardView(TemplateView):
    template_name = 'medicines/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Pakistan timezone setup
        pk_tz = pytz.timezone('Asia/Karachi')
        now_pk = timezone.now().astimezone(pk_tz)
        today_pk = now_pk.date()
        today_start = pk_tz.localize(datetime.combine(today_pk, time.min))
        today_end = pk_tz.localize(datetime.combine(today_pk, time.max))
        
        # Date range handling from request
        start_date_str = self.request.GET.get('start_date')
        end_date_str = self.request.GET.get('end_date')
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
        except (ValueError, TypeError):
            start_date = end_date = None

        if start_date and end_date and end_date < start_date:
            end_date = start_date

        # Base querysets
        medicines = Medicine.objects.all()
        
        # Get purchases with timezone awareness
        purchases = PurchaseRecord.objects.all().annotate(
            local_purchase_date=ExpressionWrapper(
                TruncDate('purchase_date', tzinfo=pk_tz),
                output_field=DateField()
            )
        )

        # Today's purchases - using time range to ensure proper reset at midnight PK time
        today_purchases = purchases.filter(
            purchase_date__gte=today_start,
            purchase_date__lte=today_end
        )
        
        # Debug output (remove in production)
        print(f"Today's date in PK: {today_pk}")
        print(f"Today's time range: {today_start} to {today_end}")
        print(f"Today's purchases count: {today_purchases.count()}")
        for purchase in today_purchases:
            print(f"Purchase: {purchase.id}, Date: {purchase.purchase_date}, Local: {purchase.local_purchase_date}")
        
        today_total = today_purchases.aggregate(
            total=Coalesce(
                Sum('total_amount'),
                Value(Decimal('0.00'), output_field=DecimalField())
            )
        )['total'] or Decimal('0.00')

        # All-time total
        all_time_total = purchases.aggregate(
            total=Coalesce(
                Sum('total_amount'),
                Value(Decimal('0.00'), output_field=DecimalField())
            )
        )['total'] or Decimal('0.00')

        # Date range total - using the local_purchase_date annotation for proper filtering
        date_range_total = Decimal('0.00')
        date_filtered_purchases = PurchaseRecord.objects.none()
        
        if start_date and end_date:
            date_filtered_purchases = purchases.filter(
                local_purchase_date__gte=start_date,
                local_purchase_date__lte=end_date
            )
            
            date_range_total = date_filtered_purchases.aggregate(
                total=Coalesce(
                    Sum('total_amount'),
                    Value(Decimal('0.00'), output_field=DecimalField())
                )
            )['total'] or Decimal('0.00')

        # Current inventory value
        current_inventory_value = Decimal('0.00')
        for medicine in medicines:
            # Calculate based on current stock and current purchase price
            stock = Decimal(medicine.stock or 0)
            price = Decimal(medicine.purchase_per_unit_price or 0)
            current_inventory_value += stock * price

        context.update({
            'medicines': medicines,
            'today_purchases': today_purchases,
            'filtered_purchases': date_filtered_purchases,
            'today_total': today_total,
            'all_time_total': all_time_total,
            'date_range_total': date_range_total,
            'current_inventory_value': current_inventory_value,
            'start_date': start_date.strftime('%Y-%m-%d') if start_date else '',
            'end_date': end_date.strftime('%Y-%m-%d') if end_date else '',
            'today_date': today_pk.strftime('%Y-%m-%d'),
            'has_date_range': bool(start_date and end_date)
        })

        return context


def search_purchases(request):
    query = request.GET.get('query', '').strip()
    
    if not query:
        medicines = Medicine.objects.all()
    else:
        medicines = Medicine.objects.filter(
            Q(name__icontains=query) | Q(company__icontains=query) | Q(formula__icontains=query)
        )
    
    data = []
    for med in medicines:
        retailers_price = float(med.retailers_price or 0)

        data.append({
            'id': med.id,
            'name': med.name,
            'company': med.company,
            'formula': med.formula,
            'stock': med.stock,
            'units_per_box': med.units_per_box,
            'retailers_price': retailers_price,
            'total_purchased': med.total_purchased,
            'total_purchase_amount': float(med.total_purchase_amount or 0),
            'last_purchased': med.updated_at.strftime('%Y-%m-%d'),
            'batch_number': "N/A",  # You can replace this if you have real batch data
        })

    return JsonResponse({'data': data})