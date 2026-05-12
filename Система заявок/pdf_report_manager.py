"""
Модуль для генерації PDF звітів та заявок підряднику
"""
import os
import platform
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from database import get_session
from models import (
    Ticket,
    TicketItem,
    Company,
    User,
    CartridgeType,
    Printer,
    Contractor,
    PurchaseList,
    PurchaseListItem,
    StockItem,
    PurchaseSupplier,
)
from logger import logger
from budget_report import format_uah_pdf


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
    
    def generate_quote_receipt_pdf(self, title: str, lines: List[str]) -> BytesIO:
        """
        Згенерувати PDF-чек з довільних рядків (під калькулятор/копіювання).

        Args:
            title: Заголовок документа.
            lines: Рядки тексту чеку (безпечний plain text).

        Returns:
            BytesIO з PDF.
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=15 * mm,
            leftMargin=15 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
            title=title,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            name="QuoteTitle",
            parent=styles["Title"],
            fontName=self._ukrainian_font_bold,
            fontSize=16,
            leading=20,
            spaceAfter=10,
        )
        body_style = ParagraphStyle(
            name="QuoteBody",
            parent=styles["BodyText"],
            fontName=self._ukrainian_font,
            fontSize=10.5,
            leading=14,
            spaceAfter=2,
        )
        meta_style = ParagraphStyle(
            name="QuoteMeta",
            parent=styles["BodyText"],
            fontName=self._ukrainian_font,
            fontSize=9.5,
            leading=12,
            textColor=colors.grey,
            spaceAfter=8,
        )

        story: List[Any] = []
        story.append(Paragraph(title, title_style))
        story.append(Paragraph(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M')}", meta_style))
        story.append(Spacer(1, 4 * mm))

        for raw in lines:
            text = (raw or "").strip()
            if not text:
                story.append(Spacer(1, 3 * mm))
                continue
            # Paragraph розуміє базовий markup — екрануємо мінімально
            safe = (
                text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            story.append(Paragraph(safe, body_style))

        doc.build(story)
        buffer.seek(0)
        return buffer

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
            
            # Ширини колонок: Компанія, Модель принтера, Картридж, Кількість
            # Збільшуємо ширину "Модель принтера" для довгих назв
            table = Table(data, colWidths=[45*mm, 75*mm, 55*mm, 25*mm])
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

    def _xml_esc(self, text: str) -> str:
        """Екранування для ReportLab Paragraph."""
        return (
            (text or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def generate_budget_cost_pdf(self, payload: Dict[str, Any]) -> BytesIO:
        """
        PDF «Кошторис витрат» за узгодженою специфікацією (ReportLab).

        Args:
            payload: Результат validate_budget_form — display_name, it_line, period_label,
                document_date_label, justification, rows (article, purpose, amount), total_amount.

        Returns:
            BytesIO з PDF.
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=15 * mm,
            leftMargin=15 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
            title="Кошторис витрат",
        )
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "BudgetTitle",
            parent=styles["Heading1"],
            fontName=self._ukrainian_font_bold,
            fontSize=16,
            textColor=colors.HexColor("#1a237e"),
            spaceAfter=14,
            alignment=1,
        )
        meta_label_style = ParagraphStyle(
            "BudgetMetaLabel",
            parent=styles["Normal"],
            fontName=self._ukrainian_font_bold,
            fontSize=10,
            leading=12,
        )
        meta_value_style = ParagraphStyle(
            "BudgetMetaValue",
            parent=styles["Normal"],
            fontName=self._ukrainian_font,
            fontSize=10,
            leading=12,
        )
        section_title_style = ParagraphStyle(
            "BudgetSection",
            parent=styles["Heading2"],
            fontName=self._ukrainian_font_bold,
            fontSize=12,
            textColor=colors.HexColor("#0d6efd"),
            spaceBefore=10,
            spaceAfter=8,
        )
        body_style = ParagraphStyle(
            "BudgetBody",
            parent=styles["Normal"],
            fontName=self._ukrainian_font,
            fontSize=10,
            leading=13,
        )
        cell_left = ParagraphStyle(
            "BudgetCellLeft",
            parent=styles["Normal"],
            fontName=self._ukrainian_font,
            fontSize=9,
            leading=11,
            wordWrap="CJK",
        )
        cell_right = ParagraphStyle(
            "BudgetCellRight",
            parent=styles["Normal"],
            fontName=self._ukrainian_font,
            fontSize=9,
            leading=11,
            alignment=2,
        )
        cell_center = ParagraphStyle(
            "BudgetCellCenter",
            parent=styles["Normal"],
            fontName=self._ukrainian_font,
            fontSize=9,
            leading=11,
            alignment=1,
        )
        header_cell = ParagraphStyle(
            "BudgetHeaderCell",
            parent=styles["Normal"],
            fontName=self._ukrainian_font_bold,
            fontSize=9,
            leading=11,
            textColor=colors.white,
            alignment=1,
        )

        story: List[Any] = []
        story.append(Paragraph(self._xml_esc("КОШТОРИС ВИТРАТ"), title_style))

        meta_data = [
            [
                Paragraph(self._xml_esc("Підприємство"), meta_label_style),
                Paragraph(self._xml_esc(str(payload.get("display_name", ""))), meta_value_style),
                Paragraph(self._xml_esc("Підрозділ"), meta_label_style),
                Paragraph(self._xml_esc("IT-відділ"), meta_value_style),
            ],
            [
                Paragraph(self._xml_esc("Період"), meta_label_style),
                Paragraph(self._xml_esc(str(payload.get("period_label", ""))), meta_value_style),
                Paragraph(self._xml_esc("Дата"), meta_label_style),
                Paragraph(self._xml_esc(str(payload.get("document_date_label", ""))), meta_value_style),
            ],
        ]
        meta_tbl = Table(meta_data, colWidths=[28 * mm, 62 * mm, 28 * mm, 62 * mm])
        meta_tbl.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(meta_tbl)
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(self._xml_esc(str(payload.get("it_line", ""))), body_style))
        story.append(Spacer(1, 8 * mm))

        story.append(Paragraph(self._xml_esc("1. Заплановані витрати"), section_title_style))

        rows_in: List[Dict[str, Any]] = payload.get("rows") or []
        table_data: List[List[Any]] = [
            [
                Paragraph(self._xml_esc("№"), header_cell),
                Paragraph(self._xml_esc("Стаття витрат"), header_cell),
                Paragraph(self._xml_esc("Призначення"), header_cell),
                Paragraph(self._xml_esc("Сума, грн"), header_cell),
            ]
        ]
        for idx, row in enumerate(rows_in, start=1):
            amt = row["amount"]
            amt_str = format_uah_pdf(amt) if isinstance(amt, Decimal) else format_uah_pdf(Decimal(str(amt)))
            table_data.append(
                [
                    Paragraph(self._xml_esc(str(idx)), cell_center),
                    Paragraph(self._xml_esc(str(row.get("article", ""))), cell_left),
                    Paragraph(self._xml_esc(str(row.get("purpose", ""))), cell_left),
                    Paragraph(self._xml_esc(amt_str), cell_right),
                ]
            )

        total_amt = payload.get("total_amount")
        if total_amt is not None and not hasattr(total_amt, "quantize"):
            total_amt = Decimal(str(total_amt))
        total_str = format_uah_pdf(total_amt) if total_amt is not None else "0,00 грн"
        table_data.append(
            [
                Paragraph(self._xml_esc("Загальна сума бюджету"), cell_left),
                "",
                "",
                Paragraph(self._xml_esc(total_str), cell_right),
            ]
        )

        expense_table = Table(
            table_data,
            colWidths=[12 * mm, 45 * mm, 88 * mm, 28 * mm],
            repeatRows=1,
        )
        last_row = len(table_data) - 1
        expense_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 1), (0, -2), "CENTER"),
                    ("ALIGN", (3, 1), (3, -2), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTNAME", (0, 1), (-1, -2), self._ukrainian_font),
                    ("FONTSIZE", (0, 1), (-1, -2), 9),
                    ("BACKGROUND", (0, 1), (-1, -2), colors.HexColor("#f8f9fa")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
                    ("SPAN", (0, last_row), (2, last_row)),
                    ("BACKGROUND", (0, last_row), (-1, last_row), colors.HexColor("#e9ecef")),
                    ("FONTNAME", (0, last_row), (-1, last_row), self._ukrainian_font_bold),
                    ("ALIGN", (0, last_row), (0, last_row), "LEFT"),
                    ("ALIGN", (3, last_row), (3, last_row), "RIGHT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(expense_table)
        story.append(Spacer(1, 10 * mm))

        story.append(Paragraph(self._xml_esc("2. Обґрунтування"), section_title_style))
        story.append(Paragraph(self._xml_esc(str(payload.get("justification", ""))), body_style))
        story.append(Spacer(1, 10 * mm))

        story.append(Paragraph(self._xml_esc("3. Погодження"), section_title_style))
        sign_label = ParagraphStyle(
            "SignLabel",
            parent=styles["Normal"],
            fontName=self._ukrainian_font,
            fontSize=10,
            leading=14,
        )
        sign_role = ParagraphStyle(
            "SignRole",
            parent=styles["Normal"],
            fontName=self._ukrainian_font,
            fontSize=10,
            leading=14,
            alignment=2,
        )
        sign_blank = ParagraphStyle(
            "SignBlank",
            parent=styles["Normal"],
            fontName=self._ukrainian_font,
            fontSize=10,
            leading=14,
            alignment=1,
        )
        sign_rows = [
            [
                Paragraph(self._xml_esc("Підготував:"), sign_label),
                Paragraph(self._xml_esc(" "), sign_blank),
                Paragraph(self._xml_esc("IT-відділ"), sign_role),
            ],
            [
                Paragraph(self._xml_esc("Погоджено:"), sign_label),
                Paragraph(self._xml_esc(" "), sign_blank),
                Paragraph(self._xml_esc("Керівник підрозділу"), sign_role),
            ],
            [
                Paragraph(self._xml_esc("Затверджено:"), sign_label),
                Paragraph(self._xml_esc(" "), sign_blank),
                Paragraph(self._xml_esc("Керівник підприємства"), sign_role),
            ],
        ]
        sign_tbl = Table(sign_rows, colWidths=[38 * mm, 95 * mm, 47 * mm])
        sign_tbl.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LINEBELOW", (1, 0), (1, 0), 0.5, colors.black),
                    ("LINEBELOW", (1, 1), (1, 1), 0.5, colors.black),
                    ("LINEBELOW", (1, 2), (1, 2), 0.5, colors.black),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(sign_tbl)

        doc.build(story)
        buffer.seek(0)
        return buffer

    def generate_purchase_list_pdf(self, list_id: int) -> Optional[BytesIO]:
        """
        PDF списку закупівлі для друку з максимальним набором полів (реквізити, постачальник, склад, дати).

        Args:
            list_id: Ідентифікатор PurchaseList.

        Returns:
            BytesIO з PDF або None, якщо список не знайдено.
        """
        status_labels = {
            "FORMING": "Формування",
            "APPROVAL": "Узгодження",
            "INVOICE_RECEIVED": "Рахунок отримано",
            "PAID": "Сплачено",
            "DONE": "Виконано",
        }

        def fmt_dt(value: Any) -> str:
            if value is None:
                return "—"
            if hasattr(value, "strftime"):
                return value.strftime("%d.%m.%Y %H:%M")
            return str(value)

        with get_session() as session:
            pl = session.query(PurchaseList).filter(PurchaseList.id == list_id).first()
            if not pl:
                return None

            company_name = None
            if pl.company_id:
                c = session.query(Company).filter(Company.id == pl.company_id).first()
                company_name = c.name if c else None

            list_meta = {
                "id": pl.id,
                "title": pl.title or "",
                "description_plain": (pl.description or "").strip(),
                "status_code": pl.status or "",
                "created_at_fmt": fmt_dt(pl.created_at),
                "updated_at_fmt": fmt_dt(pl.updated_at),
                "done_at_fmt": fmt_dt(pl.done_at),
                "company_id_display": str(pl.company_id) if pl.company_id else "—",
                "company_name": company_name or "—",
            }

            rows = (
                session.query(StockItem, PurchaseSupplier, PurchaseListItem)
                .join(PurchaseListItem, PurchaseListItem.stock_item_id == StockItem.id)
                .join(PurchaseSupplier, PurchaseSupplier.id == StockItem.supplier_id)
                .filter(PurchaseListItem.purchase_list_id == pl.id)
                .order_by(StockItem.name.asc())
                .all()
            )

            line_rows = []
            total_cents = 0
            for item, supplier, pli in rows:
                q = int(pli.quantity or 1)
                up = int(pli.unit_price_cents or 0)
                line_cents = q * up
                total_cents += line_cents
                sup_parts: List[str] = []
                if supplier:
                    sup_parts.append(supplier.name or "—")
                    if supplier.website_url:
                        sup_parts.append(f"Сайт: {supplier.website_url}")
                    if supplier.contact_info:
                        sup_parts.append(supplier.contact_info)
                supplier_html = "<br/>".join(self._xml_esc(p) for p in sup_parts if p)
                desc = (item.description or "").strip()
                desc_html = self._xml_esc(desc).replace("\n", "<br/>") if desc else "—"
                url = (item.purchase_url or "").strip()
                url_html = self._xml_esc(url) if url else "—"
                line_rows.append(
                    {
                        "stock_item_id": item.id,
                        "pli_id": pli.id,
                        "name": item.name or "",
                        "description_html": desc_html,
                        "supplier_html": supplier_html or "—",
                        "has_contract": "Так" if (supplier and supplier.has_contract) else "Ні",
                        "url_html": url_html,
                        "quantity": q,
                        "unit_price_uah": Decimal(up) / Decimal(100),
                        "line_uah": Decimal(line_cents) / Decimal(100),
                        "pli_updated": fmt_dt(pli.updated_at),
                    }
                )

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=12 * mm,
            leftMargin=12 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
            title=f"Список закупівлі #{list_meta['id']}",
        )
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "PlPdfTitle",
            parent=styles["Heading1"],
            fontName=self._ukrainian_font_bold,
            fontSize=14,
            textColor=colors.HexColor("#1a237e"),
            spaceAfter=8,
        )
        sub_style = ParagraphStyle(
            "PlPdfSub",
            parent=styles["Normal"],
            fontName=self._ukrainian_font,
            fontSize=9,
            leading=11,
            textColor=colors.grey,
            spaceAfter=10,
        )
        meta_key = ParagraphStyle(
            "PlMetaKey",
            parent=styles["Normal"],
            fontName=self._ukrainian_font_bold,
            fontSize=9,
            leading=11,
        )
        meta_val = ParagraphStyle(
            "PlMetaVal",
            parent=styles["Normal"],
            fontName=self._ukrainian_font,
            fontSize=9,
            leading=11,
        )
        sec_style = ParagraphStyle(
            "PlSec",
            parent=styles["Heading2"],
            fontName=self._ukrainian_font_bold,
            fontSize=11,
            textColor=colors.HexColor("#0d6efd"),
            spaceBefore=6,
            spaceAfter=6,
        )
        cell_tiny = ParagraphStyle(
            "PlCellTiny",
            parent=styles["Normal"],
            fontName=self._ukrainian_font,
            fontSize=7,
            leading=9,
            wordWrap="CJK",
        )
        cell_tiny_r = ParagraphStyle(
            "PlCellTinyR",
            parent=styles["Normal"],
            fontName=self._ukrainian_font,
            fontSize=7,
            leading=9,
            alignment=2,
        )
        cell_tiny_c = ParagraphStyle(
            "PlCellTinyC",
            parent=styles["Normal"],
            fontName=self._ukrainian_font,
            fontSize=7,
            leading=9,
            alignment=1,
        )
        head_pl = ParagraphStyle(
            "PlHead",
            parent=styles["Normal"],
            fontName=self._ukrainian_font_bold,
            fontSize=7,
            leading=9,
            textColor=colors.white,
            alignment=1,
        )

        story: List[Any] = []
        story.append(Paragraph(self._xml_esc(list_meta["title"] or "Список закупівлі"), title_style))
        story.append(
            Paragraph(
                self._xml_esc(
                    f"Документ сформовано: {datetime.now().strftime('%d.%m.%Y %H:%M')} · ID списку: {list_meta['id']}"
                ),
                sub_style,
            )
        )

        desc_plain = list_meta["description_plain"]
        desc_meta = self._xml_esc(desc_plain).replace("\n", "<br/>") if desc_plain else "—"
        meta_tbl_data = [
            [
                Paragraph(self._xml_esc("Компанія"), meta_key),
                Paragraph(self._xml_esc(list_meta["company_name"]), meta_val),
                Paragraph(self._xml_esc("Статус"), meta_key),
                Paragraph(self._xml_esc(status_labels.get(list_meta["status_code"], list_meta["status_code"])), meta_val),
            ],
            [
                Paragraph(self._xml_esc("Створено"), meta_key),
                Paragraph(self._xml_esc(list_meta["created_at_fmt"]), meta_val),
                Paragraph(self._xml_esc("Оновлено (список)"), meta_key),
                Paragraph(self._xml_esc(list_meta["updated_at_fmt"]), meta_val),
            ],
            [
                Paragraph(self._xml_esc("Завершено (done_at)"), meta_key),
                Paragraph(self._xml_esc(list_meta["done_at_fmt"]), meta_val),
                Paragraph(self._xml_esc("Компанія ID"), meta_key),
                Paragraph(self._xml_esc(list_meta["company_id_display"]), meta_val),
            ],
            [
                Paragraph(self._xml_esc("Опис списку"), meta_key),
                Paragraph(desc_meta, meta_val),
                Paragraph(self._xml_esc("Позицій"), meta_key),
                Paragraph(self._xml_esc(str(len(line_rows))), meta_val),
            ],
        ]
        meta_tbl = Table(meta_tbl_data, colWidths=[32 * mm, 95 * mm, 38 * mm, 95 * mm])
        meta_tbl.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dee2e6")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(meta_tbl)
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(self._xml_esc("Позиції для закупівлі"), sec_style))

        if not line_rows:
            story.append(Paragraph(self._xml_esc("Позицій у списку немає."), meta_val))
            doc.build(story)
            buffer.seek(0)
            return buffer

        hdr = [
            Paragraph(self._xml_esc("№"), head_pl),
            Paragraph(self._xml_esc("ID поз."), head_pl),
            Paragraph(self._xml_esc("ID товару"), head_pl),
            Paragraph(self._xml_esc("Найменування"), head_pl),
            Paragraph(self._xml_esc("Опис"), head_pl),
            Paragraph(self._xml_esc("Постачальник / контакти"), head_pl),
            Paragraph(self._xml_esc("Договір"), head_pl),
            Paragraph(self._xml_esc("Посилання закупівлі"), head_pl),
            Paragraph(self._xml_esc("К-сть"), head_pl),
            Paragraph(self._xml_esc("Ціна, грн"), head_pl),
            Paragraph(self._xml_esc("Сума, грн"), head_pl),
            Paragraph(self._xml_esc("Оновл. поз."), head_pl),
        ]
        data: List[List[Any]] = [hdr]
        for i, r in enumerate(line_rows, start=1):
            data.append(
                [
                    Paragraph(self._xml_esc(str(i)), cell_tiny_c),
                    Paragraph(self._xml_esc(str(r["pli_id"])), cell_tiny_c),
                    Paragraph(self._xml_esc(str(r["stock_item_id"])), cell_tiny_c),
                    Paragraph(self._xml_esc(r["name"]), cell_tiny),
                    Paragraph(r["description_html"], cell_tiny),
                    Paragraph(r["supplier_html"], cell_tiny),
                    Paragraph(self._xml_esc(r["has_contract"]), cell_tiny_c),
                    Paragraph(r["url_html"], cell_tiny),
                    Paragraph(self._xml_esc(str(r["quantity"])), cell_tiny_c),
                    Paragraph(self._xml_esc(format_uah_pdf(r["unit_price_uah"])), cell_tiny_r),
                    Paragraph(self._xml_esc(format_uah_pdf(r["line_uah"])), cell_tiny_r),
                    Paragraph(self._xml_esc(r["pli_updated"]), cell_tiny_c),
                ]
            )

        total_uah = Decimal(total_cents) / Decimal(100)
        data.append(
            [
                Paragraph(self._xml_esc("Разом"), cell_tiny),
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                Paragraph(self._xml_esc(format_uah_pdf(total_uah.quantize(Decimal("0.01")))), cell_tiny_r),
                "",
            ]
        )

        col_w = [
            6 * mm,
            10 * mm,
            10 * mm,
            35 * mm,
            45 * mm,
            45 * mm,
            10 * mm,
            40 * mm,
            9 * mm,
            14 * mm,
            14 * mm,
            17 * mm,
        ]
        items_tbl = Table(data, colWidths=col_w, repeatRows=1)
        last_i = len(data) - 1
        items_tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dee2e6")),
                    ("BACKGROUND", (0, 1), (-1, -2), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.HexColor("#ffffff"), colors.HexColor("#f8f9fa")]),
                    ("SPAN", (0, last_i), (9, last_i)),
                    ("BACKGROUND", (0, last_i), (-1, last_i), colors.HexColor("#e9ecef")),
                    ("FONTNAME", (0, last_i), (-1, last_i), self._ukrainian_font_bold),
                    ("ALIGN", (10, last_i), (10, last_i), "RIGHT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(items_tbl)

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

