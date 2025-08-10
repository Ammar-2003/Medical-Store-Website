from django.views.generic import View, TemplateView , ListView, DetailView, TemplateView , CreateView
from django.shortcuts import render, redirect , get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from app.medicine.models import Medicine
from .models import Sale, SaleItem , Return , ReturnItem
import json
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum , Count
from django.db.models import Subquery, OuterRef
from django.db.models.functions import Coalesce
from django.db.models import Sum, F, ExpressionWrapper, DecimalField , Q , Prefetch
from .forms import ReturnForm, ReturnItemForm
from django.db import transaction
from django.urls import reverse
from datetime import time
from datetime import date, timedelta
from decimal import Decimal


@method_decorator(csrf_exempt, name='dispatch')
class CartView(View):
    def get(self, request):
        cart = request.session.get('cart', {})
        medicine_ids = cart.keys()
        medicines = Medicine.objects.filter(id__in=medicine_ids)
        
        cart_items = []
        subtotal = 0
        discount_amount = 0
        
        for medicine in medicines:
            quantity = cart[str(medicine.id)]
            item_total = medicine.price * quantity
            item_discount = medicine.calculated_discount * quantity
            
            subtotal += item_total
            discount_amount += item_discount
            
            cart_items.append({
                'medicine': medicine,
                'quantity': quantity,
                'price': medicine.price,
                'selling_price': medicine.selling_price,
                'discount': medicine.calculated_discount,
                'total': item_total - item_discount,
                'rack_number': medicine.rack_number
            })
        
        context = {
            'cart_items': cart_items,
            'subtotal': subtotal,
            'discount_amount': discount_amount,
            'total': subtotal - discount_amount
        }
        return render(request, 'sales/checkout.html', context)

    def post(self, request):
        try:
            data = json.loads(request.body.decode('utf-8'))
            medicine_id = str(data.get('medicine_id'))
            action = data.get('action')
            
            cart = request.session.get('cart', {})
            
            if action == 'add':
                quantity = int(data.get('quantity', 1))
                cart[medicine_id] = cart.get(medicine_id, 0) + quantity
            elif action == 'update':
                quantity = int(data.get('quantity', 1))
                if quantity > 0:
                    cart[medicine_id] = quantity
                else:
                    del cart[medicine_id]
            elif action == 'remove':
                if medicine_id in cart:
                    del cart[medicine_id]
            
            request.session['cart'] = cart
            request.session.modified = True
            
            # Calculate updated totals
            subtotal = 0
            discount_amount = 0
            medicine_ids = cart.keys()
            medicines = Medicine.objects.filter(id__in=medicine_ids)
            
            for medicine in medicines:
                quantity = cart[str(medicine.id)]
                item_total = medicine.price * quantity
                item_discount = medicine.calculated_discount * quantity
                subtotal += item_total
                discount_amount += item_discount
            
            return JsonResponse({
                'success': True,
                'cart_count': len(cart),
                'subtotal': subtotal,
                'discount_amount': discount_amount,
                'total': subtotal - discount_amount
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

class CheckoutView(View):
    def get(self, request):
        cart = request.session.get('cart', {})
        if not cart:
            messages.warning(request, "Your cart is empty")
            return redirect('home')

        try:
            items = []
            subtotal = 0
            discount_amount = 0

            for medicine_id, quantity in cart.items():
                try:
                    medicine = Medicine.objects.get(id=medicine_id)
                    item_total = medicine.price * quantity
                    item_discount = medicine.calculated_discount * quantity

                    items.append({
                        'medicine': medicine,
                        'quantity': quantity,
                        'price': medicine.price,
                        'discount': medicine.calculated_discount,
                        'total': item_total - item_discount
                    })

                    subtotal += item_total
                    discount_amount += item_discount

                except Medicine.DoesNotExist:
                    messages.warning(request, f"Medicine ID {medicine_id} no longer available")
                    continue

            if not items:
                messages.error(request, "No valid items in cart")
                return redirect('sales:cart')

            # Default adjustment fields
            price_deducted = 0
            extra = 0
            total = subtotal - discount_amount - price_deducted + extra

            context = {
                'items': items,
                'subtotal': subtotal,
                'discount_amount': discount_amount,
                'price_deducted': price_deducted,
                'extra': extra,
                'total': total,
            }
            return render(request, 'sales/checkout.html', context)

        except Exception as e:
            messages.error(request, f"Error loading checkout: {str(e)}")
            return redirect('sales:cart')

    @transaction.atomic
    def post(self, request):
        cart = request.session.get('cart', {})
        if not cart:
            messages.warning(request, "Your cart is empty")
            return redirect('home')

        try:
            # 1. First validate and convert all inputs
            subtotal = Decimal(request.POST.get('subtotal', '0'))
            discount = Decimal(request.POST.get('discount', '0'))
            price_deducted = Decimal(request.POST.get('price_deducted', '0'))
            extra = Decimal(request.POST.get('extra', '0'))

            # 2. Create the Sale WITHOUT specifying ID
            sale = Sale(
                subtotal=subtotal,
                discount_amount=discount,
                price_deducted=price_deducted,
                extra=extra,
                final_amount=subtotal - discount - price_deducted + extra
            )
            sale.save()  # Let Django handle the ID assignment

            # 3. Verify the sale has an ID
            if not sale.id:
                raise ValueError("Sale was not properly saved - no ID assigned")

            # 4. Process items
            for medicine_id, quantity in cart.items():
                try:
                    medicine = Medicine.objects.select_for_update().get(id=medicine_id)
                    quantity = int(quantity)

                    if quantity <= 0:
                        continue
                    if medicine.stock < quantity:
                        raise ValueError(f"Not enough stock for {medicine.name}")

                    SaleItem.objects.create(
                        sale=sale,
                        medicine=medicine,
                        quantity=quantity,
                        selling_price_per_unit=medicine.price,
                        discount_per_unit=medicine.calculated_discount,
                        total_price=(medicine.price - medicine.calculated_discount) * quantity
                    )

                    medicine.stock -= quantity
                    medicine.save()

                except Medicine.DoesNotExist:
                    continue

            request.session['cart'] = {}
            return redirect('sales:receipt', pk=sale.id)

        except Exception as e:
            messages.error(request, f"Checkout failed: {str(e)}")
            return redirect('sales:cart')

class ReceiptView(TemplateView):
    template_name = 'sales/receipt.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pk = self.kwargs.get('pk')  # ✅ Get 'pk' instead of 'sale_id'
        sale = Sale.objects.get(id=pk)
        items = sale.items.select_related('medicine').all()
        
        context.update({
            'sale': sale,
            'items': items,
            'print_immediately': True  # Flag for auto-printing
        })
        return context

class SalesDashboardView(TemplateView):
    template_name = 'sales/dashboard.html'
    
    def get_period_start_dates(self):
        today = timezone.now().date()
        return {
            'weekly': today - timedelta(days=today.weekday()),
            'monthly': today.replace(day=1),
            'six_monthly': date(today.year, 1 if today.month <= 6 else 7, 1),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        period_starts = self.get_period_start_dates()

        # Get all aggregated data with minimal queries
        today_data = Sale.get_aggregated_data('today')
        weekly_data = Sale.get_aggregated_data('weekly')
        monthly_data = Sale.get_aggregated_data('monthly')
        six_month_data = Sale.get_aggregated_data('six_months')
        all_time_data = Sale.get_aggregated_data()

        # Get recent sales for display (limited to 5 each)
        recent_sales = {
            'today': Sale.get_sales_data('today')[:5],
           # 'weekly': Sale.get_sales_data('weekly'),
           # 'monthly': Sale.get_sales_data('monthly')[:5],
          #  'six_monthly': Sale.get_sales_data('six_months')[:5],
        }

        context.update({
            # Today's data
            'today_sales': recent_sales['today'],
            'today_total': today_data['total_net'],
            'today_return_amount': today_data['total_returned'],
            'today_gross_sales': today_data['gross_sales'],
            'today_sales_count': today_data['total_sales'],
            'today_profit': today_data['total_profit'],

            # Weekly data
           # 'weekly_sales': recent_sales['weekly'],
            'weekly_total': weekly_data['total_net'],
            'weekly_return_amount': weekly_data['total_returned'],
            'weekly_gross_sales': weekly_data['gross_sales'],
            'weekly_sales_count': weekly_data['total_sales'],
            'weekly_profit': weekly_data['total_profit'],
            'weekly_start_date': period_starts['weekly'],

            # Monthly data
          #  'monthly_sales': recent_sales['monthly'],
            'monthly_total': monthly_data['total_net'],
            'monthly_return_amount': monthly_data['total_returned'],
            'monthly_gross_sales': monthly_data['gross_sales'],
            'monthly_sales_count': monthly_data['total_sales'],
            'monthly_profit': monthly_data['total_profit'],
            'monthly_start_date': period_starts['monthly'],
            
            # 6 Months data
           # 'six_months_sales': recent_sales['six_monthly'],
            'six_months_total': six_month_data['total_net'],
            'six_months_return_amount': six_month_data['total_returned'],
            'six_months_gross_sales': six_month_data['gross_sales'],
            'six_months_sales_count': six_month_data['total_sales'],
            'six_months_profit': six_month_data['total_profit'],
            'six_months_start_date': period_starts['six_monthly'],

            # All-time data
            'all_time_total': all_time_data['total_net'],
            'all_time_return_amount': all_time_data['total_returned'],
            'all_time_gross_sales': all_time_data['gross_sales'],
            'all_time_sales_count': all_time_data['total_sales'],
            'all_time_profit': all_time_data['total_profit'],
        })

        return context

class SaleDetailView(DetailView):
    model = Sale
    template_name = 'sales/detail.html'
    context_object_name = 'sale'

    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            'items__medicine',
            'items__return_items',
            'returns__items__sale_item'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sale = self.object
        context.update({
            'returns': sale.returns.all(),
            'total_returned_amount': sale.returned_amount,
            'net_amount': sale.net_amount,
            'total_profit': sale.total_profit,
            'is_fully_returned': sale.is_fully_returned,
            'has_returns': sale.returns.exists(),
        })
        return context

class SalesListView(ListView):
    model = Sale
    template_name = 'sales/list.html'
    context_object_name = 'sales'
    paginate_by = 50
    ordering = ['-sale_date']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Date range filtering
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if date_from:
            queryset = queryset.filter(sale_date__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(sale_date__date__lte=date_to)
        
        # Optimized prefetching with annotations
        return queryset.select_related().prefetch_related(
            Prefetch('items', 
                    queryset=SaleItem.objects.select_related('medicine')
                            .annotate(returned_qty=Coalesce(Sum('return_items__quantity'), 0))),
            Prefetch('returns__items',
                    queryset=ReturnItem.objects.select_related('sale_item'))
        ).annotate(
            item_count=Count('items', distinct=True),
            returned_item_count=Count('items__return_items', distinct=True),
            total_returned=Coalesce(
                Sum('returns__items__returned_price'),
                0,
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter parameters
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')
        context['date_from'] = date_from
        context['date_to'] = date_to
        
        # Get the already-evaluated queryset from the view
        sales = context['sales']
        
        # Calculate totals using annotated fields
        context['total_sales'] = sales.count()
        context['total_amount'] = sum(
            sale._net_amount for sale in sales 
            if not sale.is_fully_returned
        )
        context['total_profit'] = sum(
            sale._total_profit for sale in sales
        )
        
        # Optimize all-time totals calculation
        if date_from or date_to:
            context['all_time_total_amount'] = Sale.objects.aggregate(
                total=Sum('_net_amount')
            )['total'] or Decimal('0.00')
            context['all_time_total_profit'] = Sale.objects.aggregate(
                total=Sum('_total_profit')
            )['total'] or Decimal('0.00')
        
        return context

class ReportListView(ListView):
    model = Sale
    template_name = 'sales/report.html'
    context_object_name = 'sales'
    paginate_by = 50
    ordering = ['-sale_date']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Date range filtering
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if date_from:
            queryset = queryset.filter(sale_date__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(sale_date__date__lte=date_to)
        
        # Optimized prefetching with annotations
        return queryset.select_related().prefetch_related(
            Prefetch('items', 
                    queryset=SaleItem.objects.select_related('medicine')
                            .annotate(returned_qty=Coalesce(Sum('return_items__quantity'), 0))),
            Prefetch('returns__items',
                    queryset=ReturnItem.objects.select_related('sale_item'))
        ).annotate(
            item_count=Count('items', distinct=True),
            returned_item_count=Count('items__return_items', distinct=True),
            total_returned=Coalesce(
                Sum('returns__items__returned_price'),
                0,
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter parameters
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')
        context['date_from'] = date_from
        context['date_to'] = date_to
        
        # Get the already-evaluated queryset from the view
        sales = context['sales']
        
        # Calculate totals using annotated fields
        context['total_sales'] = sales.count()
        context['total_amount'] = sum(
            sale._net_amount for sale in sales 
            if not sale.is_fully_returned
        )
        context['total_profit'] = sum(
            sale._total_profit for sale in sales
        )
        
        # Optimize all-time totals calculation
        if date_from or date_to:
            context['all_time_total_amount'] = Sale.objects.aggregate(
                total=Sum('_net_amount')
            )['total'] or Decimal('0.00')
            context['all_time_total_profit'] = Sale.objects.aggregate(
                total=Sum('_total_profit')
            )['total'] or Decimal('0.00')
        
        return context

class CreateReturnView(CreateView):
    model = Return
    form_class = ReturnForm
    template_name = 'sales/create_return.html'

    def get_success_url(self):
        return reverse('sales:detail', kwargs={'pk': self.kwargs['sale_id']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sale = get_object_or_404(Sale, pk=self.kwargs['sale_id'])
        context['sale'] = sale
        
        # Initialize forms for each returnable item
        item_forms = []
        for item in sale.items.all():
            available_to_return = item.net_quantity
            if available_to_return > 0:
                form_prefix = f'item_{item.id}'
                form = ReturnItemForm(
                    prefix=form_prefix,
                    sale_item=item,
                    initial={
                        'quantity': 0,
                        'restock': True
                    }
                )
                item_forms.append({
                    'form': form,
                    'item': item,
                    'prefix': form_prefix,
                    'available_to_return': available_to_return,
                    'unit_price': item.unit_price,
                    'total_returnable': item.unit_price * available_to_return
                })
        
        context['item_forms'] = item_forms
        return context

    @transaction.atomic
    def form_valid(self, form):
        sale = get_object_or_404(Sale, pk=self.kwargs['sale_id'])
        form.instance.sale = sale
        form.instance.processed_by = self.request.user
        
        # First save the return to get an ID
        response = super().form_valid(form)
        
        total_refund = Decimal('0')
        any_items_returned = False
        
        # Process each item form
        for item in sale.items.all():
            form_prefix = f'item_{item.id}'
            item_form = ReturnItemForm(
                data=self.request.POST,
                prefix=form_prefix,
                sale_item=item
            )
            
            if item_form.is_valid():
                quantity = item_form.cleaned_data['quantity']
                restock = item_form.cleaned_data['restock']
                
                if quantity > 0:
                    any_items_returned = True
                    returned_price = item.unit_price * Decimal(str(quantity))
                    
                    # Create return item
                    ReturnItem.objects.create(
                        return_entry=self.object,
                        sale_item=item,
                        quantity=quantity,
                        returned_price=returned_price,
                        restocked=restock
                    )
                    
                    # Update medicine stock if restocked
                    if restock and item.medicine:
                        item.medicine.stock += quantity
                        item.medicine.save()
                    
                    total_refund += returned_price
        
        if not any_items_returned:
            # No items were actually returned, so delete the return entry
            self.object.delete()
            form.add_error(None, "You must return at least one item")
            return self.form_invalid(form)
        
        # Update return with total refund amount
        self.object.refund_amount = total_refund
        self.object.save()
        
        # Update sale cached values
        sale.refresh_from_db()
        sale._returned_amount = sale.calculate_returned_amount()
        sale._net_amount = max(sale.final_amount - sale._returned_amount, Decimal('0.00'))
        sale._total_profit = sale.calculate_total_profit()
        sale.save(update_fields=['_returned_amount', '_net_amount', '_total_profit'])
        
        return response
    
class ReturnView(ListView):
    model = Sale
    template_name = 'sales/return.html'
    context_object_name = 'sales'
    paginate_by = 50
    ordering = ['-sale_date']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Date range filtering
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        hour_filter = self.request.GET.get('hour_filter')
        
        if date_from:
            queryset = queryset.filter(sale_date__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(sale_date__date__lte=date_to)
        
        # Hour filter implementation
        if hour_filter:
            hour_filters = {
                'morning': Q(sale_date__time__gte=time(6, 0), sale_date__time__lt=time(12, 0)),
                'afternoon': Q(sale_date__time__gte=time(12, 0), sale_date__time__lt=time(17, 0)),
                'evening': Q(sale_date__time__gte=time(17, 0), sale_date__time__lt=time(22, 0)),
                'night': Q(sale_date__time__gte=time(22, 0)) | Q(sale_date__time__lt=time(6, 0))
            }
            queryset = queryset.filter(hour_filters[hour_filter])
        
        # Optimized prefetching with annotations
        return queryset.prefetch_related(
            Prefetch('items', 
                   queryset=SaleItem.objects.select_related('medicine')
                          .annotate(returned_qty=Coalesce(Sum('return_items__quantity'), 0))),
            Prefetch('returns__items',
                   queryset=ReturnItem.objects.select_related('sale_item'))
        ).annotate(
            item_count=Count('items', distinct=True),
            returned_item_count=Count('items__return_items', distinct=True),
            total_returned=Coalesce(
                Sum('returns__items__returned_price'),
                0,
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = context['sales']
        
        # Filter parameters
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        context['hour_filter'] = self.request.GET.get('hour_filter', '')
        
        # Calculate totals using prefetched data
        if queryset.exists():
            context['total_sales'] = queryset.count()
            context['total_amount'] = sum(
                sale._net_amount for sale in queryset 
                if not sale.is_fully_returned
            )
        
        return context

def delete_sale(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    
    # Restock only non-returned quantities
    for item in sale.items.all():
        if item.medicine:  # Check if medicine still exists
            restock_quantity = item.quantity - item.returned_quantity
            if restock_quantity > 0:
                item.medicine.stock += restock_quantity
                item.medicine.save()
    
    sale.delete()
    messages.success(request, f'Sale #{pk} deleted successfully. Medicines restocked.')
    return redirect('sales:list')