"""
Модуль для генерації PDF звітів та заявок підряднику
"""
import os
import platform
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
        # Реєструємо шрифт для української мови
        self._register_ukrainian_font()
    
    def _register_ukrainian_font(self):
        """Реєстрація шрифту з підтримкою кирилиці"""
        try:
            # Список можливих шляхів до шрифтів з підтримкою кирилиці
            font_paths = []
            
            if platform.system() == 'Windows':
                # Windows шрифти
                windows_fonts_dir = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
                font_paths.extend([
                    os.path.join(windows_fonts_dir, 'arial.ttf'),
                    os.path.join(windows_fonts_dir, 'arialbd.ttf'),
                    os.path.join(windows_fonts_dir, 'times.ttf'),
                    os.path.join(windows_fonts_dir, 'timesbd.ttf'),
                    os.path.join(windows_fonts_dir, 'calibri.ttf'),
                    os.path.join(windows_fonts_dir, 'calibrib.ttf'),
                ])
            elif platform.system() == 'Linux':
                # Linux шрифти
                font_paths.extend([
                    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
                    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
                ])
            
            # Спробуємо завантажити перший доступний шрифт
            font_registered = False
            regular_font_path = None
            bold_font_path = None
            
            # Спочатку знаходимо звичайний шрифт
            for font_path in font_paths:
                if os.path.exists(font_path) and 'bd' not in font_path.lower() and 'bold' not in font_path.lower():
                    regular_font_path = font_path
                    break
            
            # Знаходимо жирний шрифт
            if regular_font_path:
                # Для Windows
                if platform.system() == 'Windows':
                    base_name = os.path.basename(regular_font_path).lower()
                    if 'arial' in base_name:
                        bold_font_path = regular_font_path.replace('arial.ttf', 'arialbd.ttf')
                    elif 'times' in base_name:
                        bold_font_path = regular_font_path.replace('times.ttf', 'timesbd.ttf')
                    elif 'calibri' in base_name:
                        bold_font_path = regular_font_path.replace('calibri.ttf', 'calibrib.ttf')
                    else:
                        bold_font_path = regular_font_path
                # Для Linux
                elif platform.system() == 'Linux':
                    if 'DejaVuSans' in regular_font_path:
                        bold_font_path = regular_font_path.replace('DejaVuSans.ttf', 'DejaVuSans-Bold.ttf')
                    elif 'LiberationSans' in regular_font_path:
                        bold_font_path = regular_font_path.replace('LiberationSans-Regular.ttf', 'LiberationSans-Bold.ttf')
                    else:
                        bold_font_path = regular_font_path
                else:
                    bold_font_path = regular_font_path
                
                # Перевіряємо, чи існує жирний шрифт
                if not os.path.exists(bold_font_path):
                    bold_font_path = regular_font_path
                
                try:
                    # Реєструємо звичайний шрифт
                    pdfmetrics.registerFont(TTFont('UkrainianFont', regular_font_path))
                    # Реєструємо жирний шрифт
                    pdfmetrics.registerFont(TTFont('UkrainianFont-Bold', bold_font_path))
                    font_registered = True
                    logger.log_info(f"Зареєстровано український шрифт: {regular_font_path}")
                except Exception as e:
                    logger.log_warning(f"Не вдалося завантажити шрифт {regular_font_path}: {e}")
            
            if not font_registered:
                # Якщо не знайшли системний шрифт, використовуємо вбудований Helvetica
                # (він не підтримує кирилицю, але хоча б не буде помилки)
                logger.log_warning("Не знайдено шрифт з підтримкою кирилиці, використовується Helvetica")
                self._ukrainian_font = 'Helvetica'
                self._ukrainian_font_bold = 'Helvetica-Bold'
            else:
                self._ukrainian_font = 'UkrainianFont'
                self._ukrainian_font_bold = 'UkrainianFont-Bold'
                
        except Exception as e:
            logger.log_error(f"Помилка реєстрації українського шрифту: {e}")
            self._ukrainian_font = 'Helvetica'
            self._ukrainian_font_bold = 'Helvetica-Bold'
    
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
        
        # Заголовок з українським шрифтом
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=self._ukrainian_font_bold,
            fontSize=16,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=30,
            alignment=1  # Center
        )
        
        title_text = "Звіт по заявках"
        if start_date and end_date:
            title_text += f"<br/>Період: {start_date} - {end_date}"
        if company_filter:
            title_text += f"<br/>Компанія: {company_filter}"
        
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
                ('FONTNAME', (0, 0), (-1, 0), self._ukrainian_font_bold),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTNAME', (0, 1), (-1, -1), self._ukrainian_font),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(table)
        else:
            normal_style = ParagraphStyle(
                'NormalUA',
                parent=styles['Normal'],
                fontName=self._ukrainian_font,
                fontSize=10
            )
            story.append(Paragraph("Заявок не знайдено", normal_style))
        
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
        
        # Стилі для тексту з українським шрифтом
        normal_style = ParagraphStyle(
            'NormalUA',
            parent=styles['Normal'],
            fontName=self._ukrainian_font,
            fontSize=10,
            leading=12
        )
        
        header_style = ParagraphStyle(
            'HeaderUA',
            parent=styles['Heading2'],
            fontName=self._ukrainian_font_bold,
            fontSize=12,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=10,
            spaceBefore=10
        )
        
        # Заголовок з українським шрифтом (адаптовано під стиль сайту)
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=self._ukrainian_font_bold,
            fontSize=18,
            textColor=colors.HexColor('#0d6efd'),  # Bootstrap primary color
            spaceAfter=25,
            alignment=1
        )
        
        title_text = "Заявка на заправку картриджів"
        title_text += f"<br/>Дата: {datetime.now().strftime('%d.%m.%Y')}"
        
        story.append(Paragraph(title_text, title_style))
        story.append(Spacer(1, 20))
        
        # Структура: Компанія -> Принтер -> Картриджі
        # {company_name: {printer_model: {cartridge_name: quantity}}}
        structure = {}
        total_cartridges = 0
        
        with get_session() as session:
            for ticket in tickets:
                ticket_company = ticket.get('company_name', 'Не вказано')
                if company_name and ticket_company != company_name:
                    continue
                
                if ticket_company not in structure:
                    structure[ticket_company] = {}
                
                for item in ticket.get('items', []):
                    if item.get('item_type') == 'CARTRIDGE' and item.get('cartridge_type_id'):
                        cartridge = session.query(CartridgeType).filter(
                            CartridgeType.id == item['cartridge_type_id']
                        ).first()
                        
                        if cartridge:
                            cartridge_name = cartridge.name
                            quantity = item.get('quantity', 0)
                            total_cartridges += quantity
                            
                            # Отримуємо принтер, якщо вказано
                            printer_model = 'Без принтера'
                            if item.get('printer_model_id'):
                                printer = session.query(Printer).filter(
                                    Printer.id == item['printer_model_id']
                                ).first()
                                if printer:
                                    printer_model = printer.model
                            
                            if printer_model not in structure[ticket_company]:
                                structure[ticket_company][printer_model] = {}
                            
                            if cartridge_name in structure[ticket_company][printer_model]:
                                structure[ticket_company][printer_model][cartridge_name] += quantity
                            else:
                                structure[ticket_company][printer_model][cartridge_name] = quantity
        
        # Формуємо таблицю
        if structure:
            # Заголовок таблиці
            data = [['Компанія', 'Модель принтера', 'Картридж', 'Кількість']]
            
            # Заповнюємо дані
            for company_name_key, printers in sorted(structure.items()):
                for printer_model, cartridges in sorted(printers.items()):
                    for cartridge_name, quantity in sorted(cartridges.items()):
                        data.append([
                            company_name_key,
                            printer_model,
                            cartridge_name,
                            str(quantity)
                        ])
            
            # Підсумок
            data.append(['ВСЬОГО', '', '', str(total_cartridges)])
            
            table = Table(data, colWidths=[50*mm, 50*mm, 60*mm, 30*mm])
            table.setStyle(TableStyle([
                # Заголовок таблиці - синій колір як на сайті
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),  # Bootstrap primary
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  # Заголовки по центру
                ('ALIGN', (0, 1), (2, -2), 'LEFT'),  # Дані по лівому краю
                ('ALIGN', (3, 1), (3, -2), 'CENTER'),  # Кількість по центру
                ('ALIGN', (0, -1), (-1, -1), 'CENTER'),  # Підсумок по центру
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), self._ukrainian_font_bold),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('FONTNAME', (0, 1), (-1, -2), self._ukrainian_font),
                ('FONTSIZE', (0, 1), (-1, -2), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                # Тіло таблиці - світлий сірий фон
                ('BACKGROUND', (0, 1), (-1, -2), colors.HexColor('#f8f9fa')),  # Bootstrap light
                # Підсумок - трохи темніший
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e9ecef')),  # Bootstrap secondary-light
                ('FONTNAME', (0, -1), (-1, -1), self._ukrainian_font_bold),
                ('FONTSIZE', (0, -1), (-1, -1), 11),
                # Сітчаста рамка
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),  # Світла сіра рамка
                # Зовнішня рамка товстіша
                ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.HexColor('#0d6efd')),
                ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.HexColor('#0d6efd'))
            ]))
            
            story.append(table)
        else:
            story.append(Paragraph("Картриджів не знайдено", normal_style))
        
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
        
        # Заголовок з українським шрифтом (адаптовано під стиль сайту)
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=self._ukrainian_font_bold,
            fontSize=18,
            textColor=colors.HexColor('#0d6efd'),  # Bootstrap primary color
            spaceAfter=25,
            alignment=1
        )
        
        title_text = "Заявка на ремонт принтерів"
        title_text += f"<br/>Дата: {datetime.now().strftime('%d.%m.%Y')}"
        
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
                            # Беремо коментар адміністратора, якщо є, інакше коментар користувача
                            admin_comment = ticket.get('admin_comment') or ''
                            problem_description = admin_comment.strip() if admin_comment else ''
                            
                            if not problem_description:
                                user_comment = ticket.get('comment') or ''
                                problem_description = user_comment.strip() if user_comment else ''
                            
                            printers_list.append({
                                'model': printer.model,
                                'comment': problem_description
                            })
        
        # Таблиця принтерів
        if printers_list:
            # Стиль для тексту в комірках
            cell_style = ParagraphStyle(
                'CellStyle',
                parent=styles['Normal'],
                fontName=self._ukrainian_font,
                fontSize=10,
                leading=12,
                leftIndent=0,
                rightIndent=0,
                wordWrap='CJK'  # Автоматичний перенос слів
            )
            
            # Стиль для заголовків
            header_style = ParagraphStyle(
                'HeaderStyle',
                parent=styles['Normal'],
                fontName=self._ukrainian_font_bold,
                fontSize=11,
                textColor=colors.white,
                alignment=1  # По центру
            )
            
            data = [[Paragraph('Модель принтера', header_style), Paragraph('Опис проблеми', header_style)]]
            
            for printer_info in printers_list:
                model_text = printer_info['model'] or 'Не вказано'
                comment_text = printer_info['comment'] or 'Не вказано'
                
                # Використовуємо Paragraph для автоматичного переносу тексту
                data.append([
                    Paragraph(model_text, cell_style),
                    Paragraph(comment_text, cell_style)
                ])
            
            # Збільшуємо ширину колонки "Опис проблеми" та зменшуємо "Модель принтера"
            table = Table(data, colWidths=[60*mm, 120*mm])
            table.setStyle(TableStyle([
                # Заголовок таблиці - синій колір як на сайті
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),  # Bootstrap primary
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  # Заголовки по центру
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Модель принтера по центру
                ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # Опис проблеми по лівому краю
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Вирівнювання по верху для багаторядкового тексту
                ('FONTNAME', (0, 0), (-1, 0), self._ukrainian_font_bold),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('FONTNAME', (0, 1), (-1, -1), self._ukrainian_font),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                # Тіло таблиці - світлий сірий фон
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),  # Bootstrap light
                # Сітчаста рамка
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),  # Світла сіра рамка
                # Зовнішня рамка товстіша
                ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.HexColor('#0d6efd'))
            ]))
            
            story.append(table)
        else:
            normal_style = ParagraphStyle(
                'NormalUA',
                parent=styles['Normal'],
                fontName=self._ukrainian_font,
                fontSize=10
            )
            story.append(Paragraph("Принтерів не знайдено", normal_style))
        
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

