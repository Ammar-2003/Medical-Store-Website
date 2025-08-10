import csv
import io
import logging
import time
import threading
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import connection
from django.utils import timezone
from django.db.models import Sum

logger = logging.getLogger(__name__)

class BackupManager:
    def __init__(self):
        self.last_successful_backup_month = None
        self.backup_lock = threading.Lock()
        self.is_running = False

    def run_backup_loop(self):
        """Main backup loop that runs monthly"""
        while True:
            try:
                current_time = timezone.now()
                
                # Check if it's the first day of month and we haven't backed up yet
                if (current_time.day == 1 and 
                    (self.last_successful_backup_month is None or 
                     self.last_successful_backup_month != current_time.month)):
                    
                    with self.backup_lock:
                        self.is_running = True
                        try:
                            success = self.run_full_backup()
                            if success:
                                self.last_successful_backup_month = current_time.month
                                logger.info(f"✅ Backup completed for {current_time.strftime('%B %Y')}")
                            else:
                                logger.error("Backup failed to complete successfully")
                        except Exception as e:
                            logger.error(f"Backup failed: {str(e)}", exc_info=True)
                        finally:
                            self.is_running = False
                
                # Sleep until next day or next month
                self._smart_sleep(current_time)
                
            except Exception as e:
                logger.critical(f"Backup scheduler crashed: {e}", exc_info=True)
                time.sleep(3600)  # Wait 1 hour before restarting on error

    def _smart_sleep(self, current_time):
        """Calculate optimal sleep time based on current date"""
        if current_time.day == 1:
            # If today is 1st, check again tomorrow
            sleep_seconds = 86400  # 1 day
        else:
            # Calculate sleep until first of next month
            next_month = self._get_first_of_next_month(current_time)
            sleep_seconds = (next_month - current_time).total_seconds()
        
        logger.debug(f"Sleeping for {sleep_seconds/3600:.1f} hours")
        time.sleep(sleep_seconds)

    def _get_first_of_next_month(self, current_time):
        """Get datetime for first day of next month at 00:00:01"""
        if current_time.month == 12:
            return current_time.replace(
                year=current_time.year+1, 
                month=1, 
                day=1, 
                hour=0, 
                minute=0, 
                second=1,
                microsecond=0
            )
        return current_time.replace(
            month=current_time.month+1, 
            day=1, 
            hour=0, 
            minute=0, 
            second=1,
            microsecond=0
        )

    def run_full_backup(self):
        """Execute all backup tasks with proper resource cleanup"""
        logger.info("🚀 Starting backup process...")
        try:
            return self.send_backup_email()
        except Exception as e:
            logger.error(f"Backup failed: {str(e)}", exc_info=True)
            raise
        finally:
            connection.close()

    def _sleep_until_next_month(self, current_time):
        """Calculate sleep time until first day of next month"""
        # Get first day of next month at 00:00:01
        if current_time.month == 12:
            next_month = current_time.replace(year=current_time.year+1, month=1, day=1, hour=0, minute=0, second=1)
        else:
            next_month = current_time.replace(month=current_time.month+1, day=1, hour=0, minute=0, second=1)
        
        sleep_seconds = (next_month - current_time).total_seconds()
        logger.info(f"Sleeping until next month: {next_month} ({sleep_seconds/86400:.1f} days)")
        time.sleep(sleep_seconds)

    def run_full_backup(self):
        """Execute all backup tasks with proper resource cleanup"""
        logger.info("Starting backup process...")
        try:
            return self.send_backup_email()
        except Exception as e:
            logger.error(f"Backup failed: {str(e)}", exc_info=True)
            raise
        finally:
            connection.close()

    def _generate_csv_data(self, headers, data_rows, filename_prefix):
        """Generic CSV generation function"""
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_NONNUMERIC)
        writer.writerow(headers)
        writer.writerows(data_rows)
        output.seek(0)
        timestamp = timezone.now().strftime('%Y%m%d_%H%M')
        return output.getvalue(), f"{filename_prefix}_{timestamp}.csv"

    def _generate_sales_data(self):
        """Generate comprehensive sales data CSV"""
        from .models import Sale, SaleItem
        try:
            headers = [
                'Sale ID', 'Date', 'Subtotal', 'Discount Amount', 'Price Deducted',
                'Extra Amount', 'Final Amount', 'Net Amount', 'Total Profit',
                'Returned Amount', 'Is Fully Returned', 'Item Count',
                'Total Quantity Sold', 'Total Quantity Returned'
            ]
            
            sales = Sale.objects.all().prefetch_related('items', 'returns__items')
            data_rows = []
            
            for sale in sales:
                item_count = sale.items.count()
                total_quantity = sale.items.aggregate(total=Sum('quantity'))['total'] or 0
                returned_quantity = sum(
                    item.returned_quantity 
                    for item in sale.items.all()
                )
                
                data_rows.append([
                    sale.id,
                    timezone.localtime(sale.sale_date).strftime('%Y-%m-%d %H:%M:%S'),
                    float(sale.subtotal),
                    float(sale.discount_amount),
                    float(sale.price_deducted),
                    float(sale.extra),
                    float(sale.final_amount),
                    float(sale.net_amount),
                    float(sale.total_profit),
                    float(sale.returned_amount),
                    sale.is_fully_returned,
                    item_count,
                    total_quantity,
                    returned_quantity
                ])
            
            return self._generate_csv_data(headers, data_rows, "sales_records")
        finally:
            connection.close()

    def _generate_sale_items_data(self):
        """Generate detailed sale items data CSV"""
        from .models import SaleItem
        try:
            headers = [
                'Sale ID', 'Medicine ID', 'Medicine Name', 'Quantity', 
                'Unit Selling Price', 'Unit Purchase Price', 'Unit Profit',
                'Discount Per Unit', 'Total Price', 'Returned Quantity',
                'Net Quantity', 'Returned Amount', 'Net Amount', 'Is Fully Returned'
            ]
            
            items = SaleItem.objects.select_related('medicine', 'sale')
            data_rows = []
            
            for item in items:
                data_rows.append([
                    item.sale_id,
                    item.medicine_id if item.medicine else '',
                    item.medicine.name if item.medicine else 'Deleted Medicine',
                    item.quantity,
                    float(item.selling_price_per_unit),
                    float(item.purchase_price_per_unit),
                    float(item.selling_price_per_unit - item.purchase_price_per_unit),
                    float(item.discount_per_unit),
                    float(item.total_price),
                    float(item.returned_quantity),
                    float(item.net_quantity),
                    float(item.returned_price),
                    float(item.net_price),
                    item.is_fully_returned
                ])
            
            return self._generate_csv_data(headers, data_rows, "sale_items")
        finally:
            connection.close()

    def _generate_medicine_inventory(self):
        """Generate comprehensive medicine inventory CSV"""
        from app.medicine.models import Medicine, PurchaseRecord
        try:
            headers = [
                'Medicine ID', 'Name', 'Company', 'Formula', 'Batch No',
                'Current Stock', 'Units Per Box', 'Retail Price (Box)',
                'Selling Price (Box)', 'Unit Purchase Price', 'Unit Selling Price',
                'Expiry Date', 'Is Expired', 'Is Expiring Soon', 'Rack Number',
                'Total Purchased Quantity', 'Total Purchase Amount',
                'Last Purchase Date', 'Last Purchase Price'
            ]
            
            medicines = Medicine.objects.prefetch_related('purchases')
            data_rows = []
            
            for med in medicines:
                last_purchase = med.last_purchase
                
                data_rows.append([
                    med.id,
                    med.name,
                    med.company,
                    med.formula,
                    med.batch_no,
                    med.stock,
                    med.units_per_box,
                    float(med.retailers_price),
                    float(med.packet_price),
                    float(med.purchase_per_unit_price),
                    float(med.selling_per_unit_price),
                    med.expiry_date.strftime('%Y-%m-%d'),
                    med.is_expired,
                    med.is_expiring_soon,
                    med.rack_number,
                    med.total_purchased,
                    float(med.total_purchase_amount),
                    last_purchase.purchase_date.strftime('%Y-%m-%d') if last_purchase else '',
                    float(last_purchase.unit_price) if last_purchase else 0
                ])
            
            return self._generate_csv_data(headers, data_rows, "medicine_inventory")
        finally:
            connection.close()

    def _generate_purchase_records(self):
        """Generate all purchase records CSV"""
        from app.medicine.models import PurchaseRecord
        try:
            headers = [
                'Purchase ID', 'Medicine ID', 'Medicine Name', 'Quantity',
                'Unit Price', 'Total Amount', 'Purchase Date', 'Notes'
            ]
            
            purchases = PurchaseRecord.objects.select_related('medicine')
            data_rows = []
            
            for purchase in purchases:
                data_rows.append([
                    purchase.id,
                    purchase.medicine_id,
                    purchase.medicine.name if purchase.medicine else 'Deleted Medicine',
                    purchase.quantity,
                    float(purchase.unit_price),
                    float(purchase.total_amount),
                    purchase.purchase_date.strftime('%Y-%m-%d %H:%M:%S'),
                    purchase.notes
                ])
            
            return self._generate_csv_data(headers, data_rows, "purchase_records")
        finally:
            connection.close()

    def _generate_financial_summary(self):
        """Generate comprehensive financial summary CSV"""
        from .models import Sale
        from app.medicine.models import Medicine, PurchaseRecord
        try:
            headers = [
                'Metric', 'Value', 'Description'
            ]
            
            # Calculate all financial metrics
            sales_summary = Sale.get_aggregated_data()
            total_medicine_value = sum(
                med.stock * med.purchase_per_unit_price 
                for med in Medicine.objects.all()
            )
            total_purchase_amount = PurchaseRecord.objects.aggregate(
                total=Sum('total_amount')
            )['total'] or Decimal('0.00')
            
            data_rows = [
                ['Total Sales Count', sales_summary['total_sales'], 'Number of completed sales'],
                ['Gross Sales Amount', float(sales_summary['gross_sales']), 'Total sales before returns/discounts'],
                ['Net Sales Amount', float(sales_summary['total_net']), 'Sales after returns/discounts'],
                ['Total Profit', float(sales_summary['total_profit']), 'Net profit after all adjustments'],
                ['Total Returns Amount', float(sales_summary['total_returned']), 'Total value of returned items'],
                ['Total Inventory Value', float(total_medicine_value), 'Current stock purchase value'],
                ['Total Purchases Amount', float(total_purchase_amount), 'All-time purchase spending'],
                ['Profit Margin', 
                 float((sales_summary['total_profit'] / sales_summary['total_net'] * 100) if sales_summary['total_net'] else 0),
                 'Profit as percentage of net sales']
            ]

            
            return self._generate_csv_data(headers, data_rows, "financial_summary")
        finally:
            connection.close()

    def send_backup_email(self):
        """Send backup email with all generated attachments"""
        if not hasattr(settings, 'BACKUP_EMAIL'):
            logger.error("Backup email not configured in settings")
            raise ValueError("Backup email not configured")

        try:
            # Generate all data files
            sales_data, sales_filename = self._generate_sales_data()
            items_data, items_filename = self._generate_sale_items_data()
            inventory_data, inventory_filename = self._generate_medicine_inventory()
            purchases_data, purchases_filename = self._generate_purchase_records()
            financial_data, financial_filename = self._generate_financial_summary()

            timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
            subject = f"Complete Pharmacy Backup - {timestamp} (PKT)"
            body = f"""Automatic comprehensive backup report generated at {timestamp} Pakistan Time.
            
This backup contains all critical business data including:

1. {sales_filename} - Complete sales records with financial metrics
2. {items_filename} - Detailed line items for each sale
3. {inventory_filename} - Current medicine inventory with valuation
4. {purchases_filename} - All purchase records from suppliers
5. {financial_filename} - Financial summary with KPIs

Store this backup securely as it contains sensitive business information.
"""
            
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.BACKUP_EMAIL],
                cc=getattr(settings, 'BACKUP_EMAIL_CC', []),
            )
            
            # Attach all files
            attachments = [
                (sales_filename, sales_data),
                (items_filename, items_data),
                (inventory_filename, inventory_data),
                (purchases_filename, purchases_data),
                (financial_filename, financial_data)
            ]
            
            for filename, data in attachments:
                email.attach(filename, data, 'text/csv; charset=utf-8')
            
            email.send(fail_silently=False)
            logger.info("Comprehensive backup email sent successfully to %s", settings.BACKUP_EMAIL)
            return True
        except Exception as e:
            logger.error(f"Failed to send backup email: {str(e)}", exc_info=True)
            raise