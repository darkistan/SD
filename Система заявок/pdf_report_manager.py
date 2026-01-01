"""
Модуль для генерації PDF звітів та заявок підряднику
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from database import get_session
from models import Ticket, TicketItem, Company, User, CartridgeType, Printer, Contractor
from logger import logger


class PDFReportManager:
    """Клас для генерації PDF звітів"""
    
    def __init__(self):
        """Ініціалізація менеджера PDF"""
        # Намагаємося завантажити шрифт для української мови
        try:
            # Спробуємо використати стандартний шрифт, який підтримує кирилицю
            # Якщо потрібно, можна додати власний TTF шрифт
            pass
        except Exception:
            pass
    
    def generate_tickets_report(
        self,
        tickets: List[Dict[str, Any]],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        company_filter: Optional[str] = None
    ) -> BytesIO:
        """
        Генерація звіту по заявках
        
        Args:
            tickets: Список заявок
            start_date: Початкова дата (опціонально)
            end_date: Кінцева дата (опціонально)
            company_filter: Фільтр по компанії (опціонально)
        
        Returns:
            BytesIO об'єкт з PDF
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        # Заголовок
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=30,
            alignment=1  # Center
        )
        
        title_text = "Звіт по заявках"
        if start_date and end_date:
            title_text += f"\nПеріод: {start_date} - {end_date}"
        if company_filter:
            title_text += f"\nКомпанія: {company_filter}"
        
        story.append(Paragraph(title_text, title_style))
        story.append(Spacer(1, 12))
        
        # Таблиця заявок
        if tickets:
            data = [['№', 'Тип', 'Статус', 'Компанія', 'Користувач', 'Дата створення']]
            
            for ticket in tickets:
                data.append([
                    str(ticket.get('id', '')),
                    ticket.get('ticket_type', ''),
                    ticket.get('status', ''),
                    ticket.get('company_name', ''),
                    ticket.get('user_name', ''),
                    ticket.get('created_at', '')[:10] if ticket.get('created_at') else ''
                ])
            
            table = Table(data, colWidths=[20*mm, 30*mm, 40*mm, 50*mm, 50*mm, 40*mm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(table)
        else:
            story.append(Paragraph("Заявок не знайдено", styles['Normal']))
        
        doc.build(story)
        buffer.seek(0)
        return buffer
    
    def generate_contractor_request_refill(
        self,
        tickets: List[Dict[str, Any]],
        contractor: Dict[str, Any],
        company_name: Optional[str] = None
    ) -> BytesIO:
        """
        Генерація заявки підряднику на заправку
        
        Args:
            tickets: Список заявок на заправку
            contractor: Дані підрядника
            company_name: Назва компанії (опціонально)
        
        Returns:
            BytesIO об'єкт з PDF
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        # Заголовок
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=30,
            alignment=1
        )
        
        title_text = "Заявка на заправку картриджей"
        if company_name:
            title_text += f"\nКомпанія: {company_name}"
        title_text += f"\nДата: {datetime.now().strftime('%d.%m.%Y')}"
        title_text += f"\nПідрядник: {contractor.get('name', '')}"
        
        story.append(Paragraph(title_text, title_style))
        story.append(Spacer(1, 20))
        
        # Збираємо картриджі по типах
        cartridges_summary = {}
        
        with get_session() as session:
            for ticket in tickets:
                for item in ticket.get('items', []):
                    if item.get('item_type') == 'CARTRIDGE' and item.get('cartridge_type_id'):
                        cartridge = session.query(CartridgeType).filter(
                            CartridgeType.id == item['cartridge_type_id']
                        ).first()
                        
                        if cartridge:
                            cartridge_name = cartridge.name
                            quantity = item.get('quantity', 0)
                            
                            if cartridge_name in cartridges_summary:
                                cartridges_summary[cartridge_name] += quantity
                            else:
                                cartridges_summary[cartridge_name] = quantity
        
        # Таблиця картриджів
        if cartridges_summary:
            data = [['Тип картриджа', 'Кількість']]
            
            for cartridge_name, quantity in sorted(cartridges_summary.items()):
                data.append([cartridge_name, str(quantity)])
            
            # Підсумок
            total = sum(cartridges_summary.values())
            data.append(['ВСЬОГО', str(total)])
            
            table = Table(data, colWidths=[120*mm, 60*mm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(table)
        else:
            story.append(Paragraph("Картриджів не знайдено", styles['Normal']))
        
        story.append(Spacer(1, 30))
        
        # Підпис
        story.append(Paragraph("Підпис адміністратора: _________________", styles['Normal']))
        
        doc.build(story)
        buffer.seek(0)
        return buffer
    
    def generate_contractor_request_repair(
        self,
        tickets: List[Dict[str, Any]],
        contractor: Dict[str, Any],
        company_name: Optional[str] = None
    ) -> BytesIO:
        """
        Генерація заявки підряднику на ремонт
        
        Args:
            tickets: Список заявок на ремонт
            contractor: Дані підрядника
            company_name: Назва компанії (опціонально)
        
        Returns:
            BytesIO об'єкт з PDF
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        # Заголовок
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=30,
            alignment=1
        )
        
        title_text = "Заявка на ремонт принтерів"
        if company_name:
            title_text += f"\nКомпанія: {company_name}"
        title_text += f"\nДата: {datetime.now().strftime('%d.%m.%Y')}"
        title_text += f"\nПідрядник: {contractor.get('name', '')}"
        
        story.append(Paragraph(title_text, title_style))
        story.append(Spacer(1, 20))
        
        # Збираємо принтери
        printers_list = []
        
        with get_session() as session:
            for ticket in tickets:
                for item in ticket.get('items', []):
                    if item.get('item_type') == 'PRINTER' and item.get('printer_model_id'):
                        printer = session.query(Printer).filter(
                            Printer.id == item['printer_model_id']
                        ).first()
                        
                        if printer:
                            printers_list.append({
                                'model': printer.model,
                                'comment': ticket.get('comment', '')
                            })
        
        # Таблиця принтерів
        if printers_list:
            data = [['Модель принтера', 'Опис проблеми']]
            
            for printer_info in printers_list:
                data.append([
                    printer_info['model'],
                    printer_info['comment'] or 'Не вказано'
                ])
            
            table = Table(data, colWidths=[80*mm, 100*mm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(table)
        else:
            story.append(Paragraph("Принтерів не знайдено", styles['Normal']))
        
        story.append(Spacer(1, 30))
        
        # Підпис
        story.append(Paragraph("Підпис адміністратора: _________________", styles['Normal']))
        
        doc.build(story)
        buffer.seek(0)
        return buffer


# Глобальний екземпляр менеджера PDF
_pdf_report_manager: Optional[PDFReportManager] = None


def get_pdf_report_manager() -> PDFReportManager:
    """Отримання глобального менеджера PDF"""
    global _pdf_report_manager
    if _pdf_report_manager is None:
        _pdf_report_manager = PDFReportManager()
    return _pdf_report_manager

