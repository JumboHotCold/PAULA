"""
PauliBot Institutional Analytics & Reporting Engine
===================================================
Generates executive reports, print-ready HTML views, and exports to CSV / PDF.
Branded for Saint Paul University Surigao (SPUS).
"""

import io
import csv
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models
from django.db.models import Count, Q
from django.db.models.functions import ExtractWeekDay, ExtractHour

from .models import CustomUser, Conversation, ChatHistory, StudentNeed

# Institutional Color Palette
SPUS_GREEN = '#0A4D2E'
SPUS_GOLD = '#D4AF37'
SPUS_DARK = '#1F2937'
SPUS_GRAY = '#6B7280'
SPUS_LIGHT_BG = '#F9FAFB'
BORDER_GRAY = '#E5E7EB'


def get_analytics_summary_data(start_date=None, end_date=None):
    """
    Computes comprehensive analytics metrics for institutional reporting.
    Optional date filtering supported.
    """
    now = timezone.now()
    
    # Base querysets
    chat_qs = ChatHistory.objects.all()
    needs_qs = StudentNeed.objects.select_related('student').all()
    user_qs = CustomUser.objects.filter(is_superuser=False)

    if start_date:
        chat_qs = chat_qs.filter(timestamp__gte=start_date)
        needs_qs = needs_qs.filter(created_at__gte=start_date)
    if end_date:
        chat_qs = chat_qs.filter(timestamp__lte=end_date)
        needs_qs = needs_qs.filter(created_at__lte=end_date)

    # 1. User & Conversation Metrics
    total_enrolled = user_qs.filter(is_active=True).count()
    total_conversations = Conversation.objects.count()
    total_queries = chat_qs.count()
    
    # 2. Feedback & Satisfaction
    positive_feedback = chat_qs.filter(feedback='positive').count()
    negative_feedback = chat_qs.filter(feedback='negative').count()
    total_feedback = positive_feedback + negative_feedback
    satisfaction_rate = round((positive_feedback / total_feedback * 100), 1) if total_feedback > 0 else 100.0

    # 3. Student Needs Status & Urgency
    total_needs = needs_qs.count()
    open_needs = needs_qs.filter(status='Open').count()
    in_progress_needs = needs_qs.filter(status='In Progress').count()
    resolved_needs = needs_qs.filter(status='Resolved').count()
    at_risk_students = needs_qs.filter(
        urgency__in=['Critical', 'High'],
        status__in=['Open', 'In Progress']
    ).values('student').distinct().count()

    urgency_counts = {
        'Critical': needs_qs.filter(urgency='Critical').count(),
        'High': needs_qs.filter(urgency='High').count(),
        'Medium': needs_qs.filter(urgency='Medium').count(),
        'Low': needs_qs.filter(urgency='Low').count(),
    }

    type_counts = {
        'Financial': needs_qs.filter(need_type='Financial').count(),
        'Academic': needs_qs.filter(need_type='Academic').count(),
        'Enrollment': needs_qs.filter(need_type='Enrollment').count(),
        'Mental Health': needs_qs.filter(need_type='Mental Health').count(),
    }

    # 4. Keyword Categories / Trending Confusion
    categories = {
        'Enrollment & Admissions': ['enroll', 'registration', 'register', 'admission', 'admit'],
        'Scholarships & Grants': ['scholarship', 'financial aid', 'grant', 'stipend'],
        'Academic & Grades': ['grade', 'gwa', 'transcript', 'mark', 'score', 'passing'],
        'Tuition & Balances': ['tuition', 'fee', 'payment', 'pay', 'balance', 'cashier'],
        'Clearance & Forms': ['requirement', 'document', 'submit', 'form', 'clearance'],
        'Campus Locations': ['location', 'where', 'office', 'building', 'room', 'campus', 'nav'],
        'Schedules & Classes': ['schedule', 'class', 'time', 'calendar', 'subject'],
        'Faculty & Staff': ['staff', 'faculty', 'professor', 'teacher', 'instructor', 'dean'],
        'Leave / Withdrawal': ['leave', 'loa', 'absence', 'withdraw'],
        'General Inquiries': [],
    }

    messages = list(chat_qs.values_list('message', flat=True))
    cat_counts = {cat: 0 for cat in categories}
    for msg in messages:
        msg_l = (msg or '').lower()
        matched = False
        for cat, keywords in categories.items():
            if cat == 'General Inquiries':
                continue
            for kw in keywords:
                if kw in msg_l:
                    cat_counts[cat] += 1
                    matched = True
                    break
        if not matched:
            cat_counts['General Inquiries'] += 1

    trending_topics = [
        {'category': cat, 'count': cnt, 'percentage': round((cnt / total_queries * 100), 1) if total_queries > 0 else 0}
        for cat, cnt in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)
        if cnt > 0
    ]

    # 5. Recent Flagged High-Urgency Cases
    high_priority_cases = []
    recent_flagged = needs_qs.filter(urgency__in=['Critical', 'High']).order_by('-created_at')[:15]
    for n in recent_flagged:
        student_name = f"{n.student.first_name} {n.student.last_name}".strip() or n.student.username
        high_priority_cases.append({
            'id': n.id,
            'student_id': n.student.student_id or 'N/A',
            'name': student_name,
            'need_type': n.need_type,
            'urgency': n.urgency,
            'status': n.status,
            'advisor': n.assigned_advisor,
            'date': n.created_at.strftime('%Y-%m-%d %H:%M'),
            'description': n.description[:120] + ('...' if len(n.description) > 120 else ''),
        })

    return {
        'generated_at': now.strftime('%B %d, %Y - %I:%M %p'),
        'timestamp_iso': now.isoformat(),
        'date_range': f"{start_date.strftime('%Y-%m-%d') if start_date else 'All Time'} to {end_date.strftime('%Y-%m-%d') if end_date else 'Present'}",
        'kpis': {
            'total_enrolled': total_enrolled,
            'total_queries': total_queries,
            'total_conversations': total_conversations,
            'satisfaction_rate': satisfaction_rate,
            'positive_feedback': positive_feedback,
            'negative_feedback': negative_feedback,
            'at_risk_students': at_risk_students,
            'total_needs': total_needs,
            'open_needs': open_needs,
            'in_progress_needs': in_progress_needs,
            'resolved_needs': resolved_needs,
        },
        'urgency_distribution': urgency_counts,
        'type_distribution': type_counts,
        'trending_topics': trending_topics,
        'high_priority_cases': high_priority_cases,
    }


# ==============================================================================
# CSV EXPORT GENERATOR
# ==============================================================================

def generate_analytics_csv(report_type='summary'):
    """
    Generates CSV data for download.
    Includes UTF-8 BOM so Microsoft Excel correctly displays characters.
    """
    output = io.StringIO()
    # Write UTF-8 BOM
    output.write('\ufeff')
    writer = csv.writer(output)

    if report_type == 'student_needs':
        writer.writerow([
            'Saint Paul University Surigao - PauliBot Student Needs Case Log'
        ])
        writer.writerow([f'Exported At: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'])
        writer.writerow([])
        writer.writerow([
            'Case ID', 'Student ID', 'Student Name', 'Need Type', 
            'Urgency Level', 'Case Status', 'Assigned Advisor', 
            'Date Filed', 'Description'
        ])
        needs = StudentNeed.objects.select_related('student').order_by('-created_at')
        for n in needs:
            name = f"{n.student.first_name} {n.student.last_name}".strip() or n.student.username
            writer.writerow([
                n.id,
                n.student.student_id or 'N/A',
                name,
                n.need_type,
                n.urgency,
                n.status,
                n.assigned_advisor,
                n.created_at.strftime('%Y-%m-%d %H:%M'),
                n.description.replace('\n', ' '),
            ])

    elif report_type == 'queries':
        writer.writerow([
            'Saint Paul University Surigao - PauliBot Query & Interaction Log'
        ])
        writer.writerow([f'Exported At: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'])
        writer.writerow([])
        writer.writerow(['Chat ID', 'User ID', 'Username', 'Timestamp', 'Feedback', 'User Inquiry', 'Bot Response Preview'])
        chats = ChatHistory.objects.select_related('user').order_by('-timestamp')[:500]
        for c in chats:
            writer.writerow([
                c.id,
                c.user.student_id or 'N/A',
                c.user.username,
                c.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                c.feedback or 'None',
                c.message.replace('\n', ' '),
                (c.response[:150] + '...').replace('\n', ' ') if c.response else '',
            ])

    else: # 'summary' executive report
        data = get_analytics_summary_data()
        kpis = data['kpis']
        writer.writerow(['Saint Paul University Surigao - PauliBot Institutional Analytics Summary'])
        writer.writerow([f'Generated: {data["generated_at"]}'])
        writer.writerow([])
        writer.writerow(['KEY PERFORMANCE INDICATORS', 'VALUE'])
        writer.writerow(['Total Enrolled Students', kpis['total_enrolled']])
        writer.writerow(['Total Inquiries Handled', kpis['total_queries']])
        writer.writerow(['Total Chat Sessions', kpis['total_conversations']])
        writer.writerow(['Student Satisfaction Rate', f"{kpis['satisfaction_rate']}%"])
        writer.writerow(['Positive Feedback Count', kpis['positive_feedback']])
        writer.writerow(['Negative Feedback Count', kpis['negative_feedback']])
        writer.writerow(['At-Risk Flagged Students', kpis['at_risk_students']])
        writer.writerow(['Open Student Needs Cases', kpis['open_needs']])
        writer.writerow(['In Progress Cases', kpis['in_progress_needs']])
        writer.writerow(['Resolved Cases', kpis['resolved_needs']])
        writer.writerow([])
        writer.writerow(['STUDENT NEEDS BY CATEGORY', 'COUNT'])
        for cat, cnt in data['type_distribution'].items():
            writer.writerow([cat, cnt])
        writer.writerow([])
        writer.writerow(['STUDENT NEEDS BY URGENCY', 'COUNT'])
        for urg, cnt in data['urgency_distribution'].items():
            writer.writerow([urg, cnt])
        writer.writerow([])
        writer.writerow(['TOP QUERY TOPICS / CONFUSION', 'COUNT', 'PERCENTAGE'])
        for top in data['trending_topics']:
            writer.writerow([top['category'], top['count'], f"{top['percentage']}%"])

    return output.getvalue().encode('utf-8')


# ==============================================================================
# PDF EXPORT GENERATOR (ReportLab)
# ==============================================================================

def generate_analytics_pdf(report_type='summary'):
    """
    Generates a professional, print-ready institutional PDF report using ReportLab.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    primary_color = colors.HexColor(SPUS_GREEN)
    gold_color = colors.HexColor(SPUS_GOLD)
    dark_text = colors.HexColor(SPUS_DARK)
    gray_text = colors.HexColor(SPUS_GRAY)

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=primary_color,
        alignment=0,
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=gray_text,
        alignment=0,
    )
    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=primary_color,
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=dark_text,
    )
    header_cell_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    )
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=dark_text,
    )
    cell_bold_style = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=dark_text,
    )

    elements = []
    data = get_analytics_summary_data()
    kpis = data['kpis']

    # --- Header Banner ---
    header_data = [
        [
            Paragraph("<b>SAINT PAUL UNIVERSITY SURIGAO</b><br/><font size=8 color='#6B7280'>San Nicolas St., Surigao City, Philippines • Office of Student Affairs & Technology</font>", subtitle_style),
            Paragraph(f"<font color='#0A4D2E'><b>OFFICIAL REPORT</b></font><br/><font size=8>Generated: {data['generated_at']}</font>", ParagraphStyle('RightMeta', parent=subtitle_style, alignment=2))
        ]
    ]
    header_table = Table(header_data, colWidths=[360, 180])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(header_table)
    elements.append(HRFlowable(width="100%", thickness=2, color=gold_color, spaceAfter=8, spaceBefore=4))

    # Title
    elements.append(Paragraph("PauliBot AI Campus Pulse & Institutional Analytics Report", title_style))
    elements.append(Paragraph("Comprehensive evaluation of student inquiries, flagged institutional needs, and sentiment metrics.", subtitle_style))
    elements.append(Spacer(1, 10))

    # --- Key Performance Indicators Table ---
    elements.append(Paragraph("Key Performance Indicators (Executive Summary)", h2_style))

    kpi_table_data = [
        [
            Paragraph("Metric", header_cell_style),
            Paragraph("Value", header_cell_style),
            Paragraph("Institutional Context", header_cell_style)
        ],
        [
            Paragraph("Total Inquiries Handled", cell_bold_style),
            Paragraph(str(kpis['total_queries']), cell_style),
            Paragraph("Total user questions processed through PauliBot AI", cell_style)
        ],
        [
            Paragraph("Active / Enrolled Students", cell_bold_style),
            Paragraph(str(kpis['total_enrolled']), cell_style),
            Paragraph("Registered student accounts in the campus system", cell_style)
        ],
        [
            Paragraph("Satisfaction Rating", cell_bold_style),
            Paragraph(f"{kpis['satisfaction_rate']}%", cell_style),
            Paragraph(f"Based on {kpis['positive_feedback']} thumbs up vs {kpis['negative_feedback']} thumbs down", cell_style)
        ],
        [
            Paragraph("At-Risk Student Cases", cell_bold_style),
            Paragraph(str(kpis['at_risk_students']), cell_style),
            Paragraph("Students flagged with Critical/High urgency in active queue", cell_style)
        ],
        [
            Paragraph("Open / Pending Requests", cell_bold_style),
            Paragraph(f"{kpis['open_needs'] + kpis['in_progress_needs']}", cell_style),
            Paragraph(f"Open: {kpis['open_needs']} | In Progress: {kpis['in_progress_needs']} | Resolved: {kpis['resolved_needs']}", cell_style)
        ],
    ]

    kpi_table = Table(kpi_table_data, colWidths=[150, 70, 320])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_GRAY)),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor(SPUS_LIGHT_BG)]),
    ]))
    elements.append(kpi_table)
    elements.append(Spacer(1, 12))

    # --- Distributions Side-by-Side Table ---
    elements.append(Paragraph("Student Needs & Query Breakdown", h2_style))

    # Needs by Urgency
    urgency_rows = [
        [Paragraph("Urgency Level", header_cell_style), Paragraph("Cases", header_cell_style)]
    ]
    for urg, cnt in data['urgency_distribution'].items():
        urgency_rows.append([Paragraph(urg, cell_style), Paragraph(str(cnt), cell_style)])
    urgency_table = Table(urgency_rows, colWidths=[160, 80])
    urgency_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_GRAY)),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor(SPUS_LIGHT_BG)]),
    ]))

    # Needs by Category
    cat_rows = [
        [Paragraph("Need Category", header_cell_style), Paragraph("Cases", header_cell_style)]
    ]
    for cat, cnt in data['type_distribution'].items():
        cat_rows.append([Paragraph(cat, cell_style), Paragraph(str(cnt), cell_style)])
    cat_table = Table(cat_rows, colWidths=[180, 80])
    cat_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_GRAY)),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor(SPUS_LIGHT_BG)]),
    ]))

    side_by_side = Table([
        [urgency_table, cat_table]
    ], colWidths=[260, 280])
    side_by_side.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(side_by_side)
    elements.append(Spacer(1, 12))

    # --- Top Topics Table ---
    elements.append(Paragraph("Trending Inquiries & Student Confusion Topics", h2_style))
    topic_data = [
        [
            Paragraph("Inquiry Category", header_cell_style),
            Paragraph("Volume", header_cell_style),
            Paragraph("Share", header_cell_style)
        ]
    ]
    for t in data['trending_topics'][:8]:
        topic_data.append([
            Paragraph(t['category'], cell_bold_style),
            Paragraph(str(t['count']), cell_style),
            Paragraph(f"{t['percentage']}%", cell_style)
        ])
    topic_table = Table(topic_data, colWidths=[260, 120, 160])
    topic_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F766E')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_GRAY)),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor(SPUS_LIGHT_BG)]),
    ]))
    elements.append(topic_table)
    elements.append(Spacer(1, 14))

    # --- High Priority Flagged Cases ---
    if data['high_priority_cases']:
        elements.append(KeepTogether([
            Paragraph("Active High-Priority Student Cases (Critical / High Urgency)", h2_style),
            Paragraph("The following student cases have been automatically escalated and require institutional follow-up:", subtitle_style),
            Spacer(1, 4),
        ]))
        case_rows = [
            [
                Paragraph("Student ID", header_cell_style),
                Paragraph("Name", header_cell_style),
                Paragraph("Type", header_cell_style),
                Paragraph("Urgency", header_cell_style),
                Paragraph("Status", header_cell_style),
                Paragraph("Advisor", header_cell_style),
            ]
        ]
        for c in data['high_priority_cases'][:8]:
            case_rows.append([
                Paragraph(c['student_id'], cell_style),
                Paragraph(c['name'], cell_bold_style),
                Paragraph(c['need_type'], cell_style),
                Paragraph(f"<font color='{'#DC2626' if c['urgency'] == 'Critical' else '#D97706'}'><b>{c['urgency']}</b></font>", cell_style),
                Paragraph(c['status'], cell_style),
                Paragraph(c['advisor'], cell_style),
            ])
        case_table = Table(case_rows, colWidths=[75, 130, 95, 75, 75, 90])
        case_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), primary_color),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_GRAY)),
            ('TOPPADDING', (0, 0), (-1, -1), 3.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor(SPUS_LIGHT_BG)]),
        ]))
        elements.append(case_table)
        elements.append(Spacer(1, 20))

    # --- Sign-off / Signature Block ---
    sign_block = [
        [
            Paragraph("<b>Prepared by:</b><br/><br/><br/>_____________________________________<br/>PauliBot Administrative System", cell_style),
            Paragraph("<b>Noted and Approved by:</b><br/><br/><br/>_____________________________________<br/>Dean / Director of Student Affairs", cell_style)
        ]
    ]
    sign_table = Table(sign_block, colWidths=[270, 270])
    sign_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(sign_table)

    doc.build(elements)
    return buffer.getvalue()


# ==============================================================================
# READY-TO-PRINT HTML TEMPLATE
# ==============================================================================

def render_print_html(report_type='summary'):
    """
    Renders a standalone, fully styled, ready-to-print HTML view.
    Designed with @media print CSS for clean output on any printer or PDF save.
    """
    data = get_analytics_summary_data()
    kpis = data['kpis']

    trending_html = "".join([
        f"""
        <tr>
            <td style="font-weight: 600;">{t['category']}</td>
            <td style="text-align: right; font-weight: bold;">{t['count']}</td>
            <td style="text-align: right;">{t['percentage']}%</td>
            <td>
                <div style="background: #E5E7EB; border-radius: 4px; height: 10px; width: 100%;">
                    <div style="background: #0A4D2E; border-radius: 4px; height: 10px; width: {min(100, t['percentage'] * 2)}%;"></div>
                </div>
            </td>
        </tr>
        """
        for t in data['trending_topics']
    ])

    urgency_html = "".join([
        f"""
        <tr>
            <td style="font-weight: 500;">{urg}</td>
            <td style="text-align: right; font-weight: bold;">{cnt}</td>
        </tr>
        """
        for urg, cnt in data['urgency_distribution'].items()
    ])

    type_html = "".join([
        f"""
        <tr>
            <td style="font-weight: 500;">{cat}</td>
            <td style="text-align: right; font-weight: bold;">{cnt}</td>
        </tr>
        """
        for cat, cnt in data['type_distribution'].items()
    ])

    cases_html = "".join([
        f"""
        <tr>
            <td style="font-family: monospace; font-size: 11px;">{c['student_id']}</td>
            <td style="font-weight: 600;">{c['name']}</td>
            <td>{c['need_type']}</td>
            <td>
                <span class="badge badge-{c['urgency'].lower()}">{c['urgency']}</span>
            </td>
            <td>
                <span class="badge badge-{c['status'].lower().replace(' ', '-')}">{c['status']}</span>
            </td>
            <td>{c['advisor']}</td>
            <td style="font-size: 11px; color: #6B7280;">{c['date']}</td>
        </tr>
        """
        for c in data['high_priority_cases']
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PauliBot Institutional Analytics Report — SPUS</title>
    <style>
        :root {{
            --spus-green: #0A4D2E;
            --spus-gold: #D4AF37;
            --text-dark: #1F2937;
            --text-gray: #4B5563;
            --border: #E5E7EB;
            --bg-light: #F9FAFB;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: var(--text-dark);
            background: #F3F4F6;
            padding: 24px;
            font-size: 13px;
            line-height: 1.5;
        }}
        .report-paper {{
            max-width: 960px;
            margin: 0 auto;
            background: #ffffff;
            padding: 48px;
            border-radius: 8px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.08);
            border: 1px solid var(--border);
        }}
        /* Header */
        .report-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 3px solid var(--spus-gold);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        .header-title h1 {{
            font-size: 20px;
            color: var(--spus-green);
            letter-spacing: -0.01em;
            font-weight: 800;
        }}
        .header-title p {{
            color: var(--text-gray);
            font-size: 12px;
            margin-top: 2px;
        }}
        .header-meta {{
            text-align: right;
            font-size: 11px;
            color: var(--text-gray);
        }}
        .header-meta strong {{
            color: var(--spus-green);
            font-size: 12px;
        }}
        /* Action Bar (hidden when printing) */
        .action-bar {{
            max-width: 960px;
            margin: 0 auto 16px auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #ffffff;
            padding: 12px 20px;
            border-radius: 8px;
            border: 1px solid var(--border);
        }}
        .btn {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 600;
            border-radius: 6px;
            cursor: pointer;
            border: none;
            text-decoration: none;
            transition: all 0.2s;
        }}
        .btn-primary {{
            background: var(--spus-green);
            color: #ffffff;
        }}
        .btn-primary:hover {{
            background: #083c24;
        }}
        .btn-secondary {{
            background: #E5E7EB;
            color: var(--text-dark);
        }}
        .btn-secondary:hover {{
            background: #D1D5DB;
        }}
        /* Section Titles */
        .section-title {{
            font-size: 14px;
            font-weight: 700;
            color: var(--spus-green);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin: 20px 0 10px 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .section-title::after {{
            content: '';
            flex: 1;
            height: 1px;
            background: var(--border);
        }}
        /* KPI Cards Grid */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }}
        .kpi-card {{
            border: 1px solid var(--border);
            padding: 14px;
            border-radius: 6px;
            background: var(--bg-light);
            text-align: left;
        }}
        .kpi-num {{
            font-size: 22px;
            font-weight: 800;
            color: var(--spus-green);
        }}
        .kpi-label {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            color: var(--text-gray);
            margin-top: 4px;
        }}
        /* Tables */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 16px;
        }}
        th, td {{
            padding: 8px 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            background: #F3F4F6;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-gray);
            font-weight: 700;
        }}
        tr:nth-child(even) td {{
            background: #FAFAFA;
        }}
        /* Two columns */
        .two-col {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 16px;
        }}
        /* Badges */
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
        }}
        .badge-critical {{ background: #FEE2E2; color: #DC2626; }}
        .badge-high {{ background: #FEF3C7; color: #D97706; }}
        .badge-medium {{ background: #DBEAFE; color: #2563EB; }}
        .badge-low {{ background: #DCFCE7; color: #16A34A; }}
        .badge-open {{ background: #FEE2E2; color: #DC2626; }}
        .badge-in-progress {{ background: #FEF3C7; color: #D97706; }}
        .badge-resolved {{ background: #DCFCE7; color: #16A34A; }}
        /* Signature */
        .signature-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
        }}
        .signature-box {{
            font-size: 12px;
        }}
        .signature-line {{
            margin-top: 48px;
            border-top: 1px solid #000;
            padding-top: 4px;
            font-weight: 600;
        }}

        /* Print Media Styles */
        @media print {{
            body {{
                background: #ffffff;
                padding: 0;
                font-size: 11pt;
            }}
            .action-bar {{
                display: none !important;
            }}
            .report-paper {{
                max-width: 100%;
                border: none;
                box-shadow: none;
                padding: 0;
                margin: 0;
            }}
            .page-break {{
                page-break-before: always;
            }}
            @page {{
                margin: 1.5cm;
                size: letter portrait;
            }}
        }}
    </style>
</head>
<body>

    <div class="action-bar">
        <div>
            <strong>PauliBot Institutional Reporting</strong>
            <span style="color: var(--text-gray); margin-left: 8px; font-size: 12px;">Format: Ready to Print</span>
        </div>
        <div style="display: flex; gap: 10px;">
            <button class="btn btn-primary" onclick="window.print()">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M19 8H5c-1.66 0-3 1.34-3 3v6h4v4h12v-4h4v-6c0-1.66-1.34-3-3-3zm-3 11H8v-5h8v5zm3-7c-.55 0-1-.45-1-1s.45-1 1-1 1 .45 1 1-.45 1-1 1zm-1-9H6v4h12V3z"/></svg>
                Print / Save PDF
            </button>
            <a href="/api/admin/reports/export/pdf/" class="btn btn-secondary">Download Native PDF</a>
            <a href="/api/admin/reports/export/csv/" class="btn btn-secondary">Download CSV</a>
            <button class="btn btn-secondary" onclick="window.close()">Close</button>
        </div>
    </div>

    <div class="report-paper">
        <!-- Header -->
        <div class="report-header">
            <div class="header-title">
                <h1>SAINT PAUL UNIVERSITY SURIGAO</h1>
                <p>Office of Student Affairs & Technology Services • Surigao City, Philippines</p>
                <p style="margin-top: 4px; font-weight: 700; color: var(--spus-green); font-size: 14px;">PauliBot AI Analytics & Campus Pulse Report</p>
            </div>
            <div class="header-meta">
                <strong>OFFICIAL INSTITUTIONAL RECORD</strong><br/>
                Date: {data['generated_at']}<br/>
                Reporting Scope: {data['date_range']}<br/>
                System: PauliBot v2.0 Production
            </div>
        </div>

        <!-- KPIs -->
        <div class="section-title">Executive Key Performance Indicators</div>
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-num">{kpis['total_queries']}</div>
                <div class="kpi-label">Total Inquiries</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-num">{kpis['satisfaction_rate']}%</div>
                <div class="kpi-label">Student Satisfaction</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-num" style="color: #DC2626;">{kpis['at_risk_students']}</div>
                <div class="kpi-label">At-Risk Students</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-num">{kpis['open_needs'] + kpis['in_progress_needs']}</div>
                <div class="kpi-label">Active Cases</div>
            </div>
        </div>

        <!-- Distributions -->
        <div class="two-col">
            <div>
                <div class="section-title">Student Needs by Category</div>
                <table>
                    <thead>
                        <tr><th>Need Category</th><th style="text-align: right;">Count</th></tr>
                    </thead>
                    <tbody>
                        {type_html}
                    </tbody>
                </table>
            </div>
            <div>
                <div class="section-title">Student Needs by Urgency</div>
                <table>
                    <thead>
                        <tr><th>Urgency Level</th><th style="text-align: right;">Count</th></tr>
                    </thead>
                    <tbody>
                        {urgency_html}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Trending Topics -->
        <div class="section-title">Trending Inquiries & Student Confusion Topics</div>
        <table>
            <thead>
                <tr>
                    <th style="width: 40%;">Topic Category</th>
                    <th style="width: 15%; text-align: right;">Volume</th>
                    <th style="width: 15%; text-align: right;">Share</th>
                    <th style="width: 30%;">Volume Distribution</th>
                </tr>
            </thead>
            <tbody>
                {trending_html}
            </tbody>
        </table>

        <!-- High Priority Flagged Cases -->
        <div class="section-title">Escalated Flagged Cases (Critical / High Urgency)</div>
        <table>
            <thead>
                <tr>
                    <th>Student ID</th>
                    <th>Name</th>
                    <th>Need Type</th>
                    <th>Urgency</th>
                    <th>Status</th>
                    <th>Advisor</th>
                    <th>Date Filed</th>
                </tr>
            </thead>
            <tbody>
                {cases_html or '<tr><td colspan="7" style="text-align:center; color:#6B7280;">No critical cases currently flagged.</td></tr>'}
            </tbody>
        </table>

        <!-- Sign-off -->
        <div class="signature-grid">
            <div class="signature-box">
                <p>Prepared by:</p>
                <div class="signature-line">PauliBot Administration & Research Team</div>
                <p style="color: var(--text-gray); font-size: 11px;">Saint Paul University Surigao</p>
            </div>
            <div class="signature-box">
                <p>Noted and Certified by:</p>
                <div class="signature-line">Office of the Dean / Student Affairs Director</div>
                <p style="color: var(--text-gray); font-size: 11px;">Saint Paul University Surigao</p>
            </div>
        </div>
    </div>

</body>
</html>
"""
