import datetime
import os
import json
from reportlab.lib import utils, colors
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle, Paragraph, Image, PageBreak, Spacer, Frame, \
    BaseDocTemplate, PageTemplate, NextPageTemplate
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.platypus import ListFlowable, ListItem, KeepTogether,SimpleDocTemplate
from reportlab.lib.styles import getSampleStyleSheet
from functools import partial
from bucket_handler import fetch_image, store_pdf, get_logo
from enum_data import enum_thermal_classification, enum_nec_violation, enum_osha_violation, enum_maintenance_condition_index_type, enum_woline_temp_issue_type, enum_temp_panel_schedule_type, enum_temp_ultrasonic_issue_type, enum_severity_criteria_type, enum_arc_flash_label, enum_nfpa_violation_type
import traceback
from reportlab.lib.pagesizes import letter
import psycopg2
import boto3
from io import BytesIO
import io
import random
from PIL import Image as PILImage
from datetime import datetime
from reportlab.pdfgen import canvas
from urllib.request import urlopen
# from dotenv import load_dotenv
# load_dotenv()


BUCKET_NAME = os.getenv("BUCKET_NAME")
NEC_BUCKET_NAME = os.getenv("NEC_BUCKET_NAME")
ISSUE_BUCKET_NAME = os.getenv("ISSUE_BUCKET_NAME")
SITE_BUCKET_NAME = os.getenv("SITE_BUCKET_NAME")
ACCESS_KEY = os.getenv('ACCESS_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
image_unavailable = "https://condit-logo.s3.us-east-2.amazonaws.com/image_unavailable.png"

DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')


def get_image(path, height):
    img = utils.ImageReader(path)
    iw, ih = img.getSize()
    aspect = iw / float(ih)
    return Image(path, width=(height * aspect), height=height)

def check_list_issues(lst):

    if len(set(lst)) == 1:
        return f'Fail-{enum_woline_temp_issue_type[lst[0]]}'
    elif len(set(lst)) == len(lst):
        return "Fail-Multiple"
    elif len(set(lst)) > 1:
        return "Fail-Multiple"
    else:
        return "Fail-Multiple"

# Fetch Top level name
def fetch_sublevel_asset_id1(woonboarding_toplevel_asset_id, is_wo_line_for_exisiting_asset):
    connection = psycopg2.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
    cursor = connection.cursor()

    print('is_wo_line_for_exisiting_asset', is_wo_line_for_exisiting_asset)
    print(type(is_wo_line_for_exisiting_asset))

    if is_wo_line_for_exisiting_asset:
        topsublevel_asset_ids_q = '''
            SELECT w2.woonboardingassets_id, w2.sublevelcomponent_asset_id, wa.asset_name 
            FROM "WOlineSubLevelcomponentMapping" w2 
            JOIN "WOOnboardingAssets" wa 
            ON wa.woonboardingassets_id = w2.sublevelcomponent_asset_id
            WHERE wa.woonboardingassets_id = %s
            AND w2.is_sublevelcomponent_from_ob_wo = TRUE
            AND w2.is_deleted = FALSE
        '''
        cursor.execute(topsublevel_asset_ids_q, (woonboarding_toplevel_asset_id,))
        top_sub_level_asset_result_1 = cursor.fetchone()

        print('top_level_asset_result221', top_sub_level_asset_result_1)

        if top_sub_level_asset_result_1 is None:
            return 'N/A'  # No result found

        print('top_level_asset_result221[0]', top_sub_level_asset_result_1[0])

        # Fetch the asset name
        top_asset_name_query = '''
                    SELECT wa.asset_name 
                    FROM "WOOnboardingAssets" wa 
                    WHERE wa.woonboardingassets_id = %s
                    AND wa.is_deleted = FALSE
                    '''
        cursor.execute(top_asset_name_query, (top_sub_level_asset_result_1[0],))
        top_sub_level_asset_name = cursor.fetchone()

        if top_sub_level_asset_name:
            print('Top-level asset name:', top_sub_level_asset_name[0])
            return top_sub_level_asset_name[0]  # Return the asset name
        else:
            print(f"No asset name found for ID: {top_sub_level_asset_result_1[0]}")
            return 'N/A'  # No asset name found

    return 'N/A'

# Fetch Top level id
# for top-sub connect together in electrical inventory and asset table       
def fetch_sublevel_woonboardingasset_id(woonboarding_toplevel_asset_id, is_wo_line_for_exisiting_asset,wo_id):
    connection = psycopg2.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
    cursor = connection.cursor()

    print('is_wo_line_for_exisiting_asset', is_wo_line_for_exisiting_asset)
    print(type(is_wo_line_for_exisiting_asset))
    print('wo_id',wo_id)

    if is_wo_line_for_exisiting_asset:
        topsublevel_asset_ids_q = '''
                                select w2.woonboardingassets_id
                               from "WOlineSubLevelcomponentMapping" w2 left join "WOOnboardingAssets" wa 
                               on (wa.asset_id = w2.sublevelcomponent_asset_id or wa.woonboardingassets_id = w2.sublevelcomponent_asset_id)
                               left join "WOOnboardingAssets" w4 on w4.woonboardingassets_id =w2.woonboardingassets_id 
                               where wa.woonboardingassets_id =%s
                               and (w2.is_sublevelcomponent_from_ob_wo = false or w2.is_sublevelcomponent_from_ob_wo = true)
                               and w4.wo_id =%s
                               and w2.is_deleted = false
        '''
        cursor.execute(topsublevel_asset_ids_q, (woonboarding_toplevel_asset_id,wo_id))
        top_sub_level_asset_result_1 = cursor.fetchone()

        print('top_level_asset_result221', top_sub_level_asset_result_1)
    else:
        topsublevel_asset_ids_q = '''select w2.woonboardingassets_id
                                from "WOlineSubLevelcomponentMapping" w2 
                                left join "WOOnboardingAssets" wa 
                               on wa.woonboardingassets_id = w2.sublevelcomponent_asset_id 
                               where wa.woonboardingassets_id = %s
                                and w2.is_sublevelcomponent_from_ob_wo = true
                                and w2.is_deleted = false
        '''
        cursor.execute(topsublevel_asset_ids_q, (woonboarding_toplevel_asset_id,))
        top_sub_level_asset_result_1 = cursor.fetchone()
    if top_sub_level_asset_result_1 is None:
        return [ ]  # No result found
    else:
        return top_sub_level_asset_result_1
            

def fetch_verdict_labels(woobassets_id):
    connection = None
    result = 'Pass'  # Default verdict if no issues are found
    try:
        connection = psycopg2.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
        cursor = connection.cursor()
        issue_q = '''SELECT wl.issue_type,wl.is_issue_linked_for_fix FROM "WOLineIssue" wl 
                     WHERE woonboardingassets_id = %s
                     AND wl.is_deleted = false'''
        cursor.execute(issue_q, (woobassets_id,))
        issue_records = cursor.fetchall()
        id_list = [row[0] for row in issue_records]
        # if any(row[1] for row in issue_records):
        #     result = 'Pass'
        # else:
        id_list = [row[0] for row in issue_records if not row[1]]
        if id_list:
            result = check_list_issues(id_list)

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Exception in fetch_verdict_labels method: {error}")

    finally:
        if connection:
            cursor.close()
            connection.close()
            print("PostgreSQL connection is closed")

    return result


def is_valid_number(value):
    try:
        if value:
            float(value)
            return True
        else:
            return False
    except ValueError:
        return False

# Size for IR Images
def create_ir_image(asset_image_path, fixed_height=2.7 * inch, fixed_width=3.2 * inch, scale_factor=1.0):
    # Open the image
    assets1 = PILImage.open(asset_image_path)

    # Fetch EXIF data
    exif_data = assets1._getexif()
    if exif_data:
        # 274 is the EXIF tag for 'Orientation'
        orientation = exif_data.get(274)

        if orientation == 3:
            assets1 = assets1.rotate(180, expand=True)
        elif orientation == 6:
            assets1 = assets1.rotate(-90, expand=True)
        elif orientation == 8:
            assets1 = assets1.rotate(90, expand=True)

    img_byte_arr = io.BytesIO()
    # RGBA issue resolved
    # assets1.save(img_byte_arr, format='JPEG')
    if assets1.mode == 'RGB':
        assets1.save(img_byte_arr, format='JPEG')
    elif assets1.mode == 'RGBA':
        assets1.save(img_byte_arr, format='PNG')
    else:
        assets1.save(img_byte_arr)
    img_byte_arr.seek(0)  # Move to the beginning of the BytesIO object

    # Create a ReportLab Image object from the BytesIO stream
    rl_image = Image(img_byte_arr)

    # Set dimensions while maintaining the aspect ratio
    original_width, original_height = rl_image.imageWidth, rl_image.imageHeight
    if original_height > fixed_height or original_width > fixed_width:
        scale_factor = fixed_height / original_height
        rl_image.drawHeight = fixed_height
        rl_image.drawWidth = fixed_width
    else:
        rl_image.drawHeight = original_height
        rl_image.drawWidth = original_width

    return rl_image

# Size for Asset image
def create_asset_image(asset_image_path, fixed_height=3.5 * inch, fixed_width=2.5 * inch, scale_factor=1.0):
    # Open the image
    assets1 = PILImage.open(asset_image_path)

    # Fetch EXIF data
    exif_data = assets1._getexif()
    if exif_data:
        # 274 is the EXIF tag for 'Orientation'
        orientation = exif_data.get(274)

        if orientation == 3:
            assets1 = assets1.rotate(180, expand=True)
        elif orientation == 6:
            assets1 = assets1.rotate(-90, expand=True)
        elif orientation == 8:
            assets1 = assets1.rotate(90, expand=True)

    img_byte_arr = io.BytesIO()
    # RGBA issue resolved
    # assets1.save(img_byte_arr, format='JPEG')
    if assets1.mode == 'RGB':
        assets1.save(img_byte_arr, format='JPEG')
    elif assets1.mode == 'RGBA':
        assets1.save(img_byte_arr, format='PNG')
    else:
        assets1.save(img_byte_arr)
    img_byte_arr.seek(0)  # Move to the beginning of the BytesIO object

    # Create a ReportLab Image object from the BytesIO stream
    rl_image = Image(img_byte_arr)

    # Set dimensions while maintaining the aspect ratio
    original_width, original_height = rl_image.imageWidth, rl_image.imageHeight
    if original_height > fixed_height or original_width > fixed_width:
        scale_factor = fixed_height / original_height
        rl_image.drawHeight = fixed_height
        rl_image.drawWidth = fixed_width
    else:
        rl_image.drawHeight = original_height
        rl_image.drawWidth = original_width

    return rl_image

# Date for 1st page
def format_ordinal_date(date_str):
    # Parse the date string into a datetime object
    if isinstance(date_str, str):
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')  # Adjust format if needed
    else:
        date_obj = date_str  # If it's already a datetime object
    
    day = date_obj.day
    # Logic for formatting ordinal date
    suffix = 'th'
    if day in [1, 21, 31]:
        suffix = 'st'
    elif day in [2, 22]:
        suffix = 'nd'
    elif day in [3, 23]:
        suffix = 'rd'
    
    return f"{date_obj.strftime('%B')} {day}{suffix}, {date_obj.year}"
class ReportPrinter(BaseDocTemplate):

    def __init__(self, filename, headers, footers, **kw):
        self.allowSplitting = 1
        BaseDocTemplate.__init__(self, filename, **kw)
        template = PageTemplate('normal', frames=[
            Frame(self.leftMargin, self.bottomMargin - 0.2 * inch, self.width, self.height + 0.2 * inch, id='F1')],
            # , showBoundary=1
            onPage=partial(self._header_footer, headers=headers, footers=footers))
        self.addPageTemplates(template)

    def header(self, canvas, doc, headers):
        canvas.saveState()
        header = get_image(headers[0], 1.5 * inch)

        if doc.page == 1:
            w, h = header.wrap(doc.width, doc.topMargin)
            page_center_x = doc.width / 2

            # Calculate the x position to center the image
            # Center the image horizontally
            x = page_center_x - (w / 2) + (0.15 * doc.width)
            # print('header', w, h, doc.width, doc.topMargin)

            # Adjust the y-position for the image
            y = doc.height - (doc.height * 0.17) + (h / 2)

            # Draw the header image at the calculated position
            header.drawOn(canvas, x, y)
            canvas.restoreState()
        else:
            None

    def footer(self, canvas, doc, footers):
        canvas.saveState()
        company_logo = footers[1]
        max_width_in_inches = 110.5
        max_height_in_inches = 14.8
        max_width_in_pixels = max_width_in_inches * 72
        max_height_in_pixels = max_height_in_inches * 72


        # Function to resize image while maintaining aspect ratio
        def resize_image(image_path, max_width, max_height):
            """
            Resize the image to fit within the max width and height while maintaining aspect ratio.

            :param image_path: Path to the image file.
            :param max_width: Maximum width allowed (in pixels).
            :param max_height: Maximum height allowed (in pixels).
            :return: Tuple of resized width and height in inches.
            """
            img = PILImage.open(image_path)
            img_width, img_height = img.size
            # Calculate aspect ratio for scaling
            width_scale = max_width / img_width
            height_scale = max_height / img_height
            scale_factor = min(width_scale, height_scale)

            # Apply scaling to get resized dimensions
            resized_width = img_width * scale_factor
            resized_height = img_height * scale_factor

            # Convert pixels to inches for ReportLab
            return resized_width / 72, resized_height / 72


        # Resize the footer image
        resized_width, resized_height = resize_image(company_logo, max_width_in_pixels, max_height_in_pixels)

        # Create ReportLab Image object with resized dimensions
        footer6 = Image(company_logo, width=resized_width, height=resized_height)


        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='abc', fontName="Helvetica-Bold", fontSize=8,textColor='lightgrey', alignment=0))
        styles.add(ParagraphStyle(name='pagenum',fontName="Helvetica-Bold", textColor='lightgrey', fontSize=8, alignment=1))
        footer1 = Paragraph("Powered by ", styles['abc'])
        footer2 = Image(footers[0], 0.2204724 * inch, 0.2086614 * inch)
        footer3 = Paragraph("Egalvanic", styles['abc'])
        footer4 = Paragraph(str(f'{canvas.getPageNumber():02}'), styles['pagenum'])
        # footer6 = Image(footers[1], 0.7 * inch,0.5 * inch)
        w1, h1 = footer1.wrap(doc.width, doc.bottomMargin)
        w, h = footer2.wrap(doc.width, doc.bottomMargin)
        w3, h3 = footer3.wrap(doc.width, doc.bottomMargin)
        w4, h4 = footer4.wrap(doc.width, doc.bottomMargin)

        footer1.drawOn(canvas, doc.width + doc.leftMargin - 73, h)
        footer2.drawOn(canvas, doc.width + doc.leftMargin - 25, h)
        footer3.drawOn(canvas, doc.width + doc.leftMargin - 5, h)
        footer4.drawOn(canvas, doc.width / 2 + doc.leftMargin - 230, h)
        footer6_y = h - (0.01 * doc.height)  # Move it 5% lower
        footer6.drawOn(canvas, doc.width + doc.leftMargin - 485, h)

        canvas.restoreState()

    def _header_footer(self, canvas, doc, headers, footers):
        # Save the state of our canvas so we can draw on it
        self.header(canvas, doc, headers)
        self.footer(canvas, doc, footers)

    def afterFlowable(self, flowable):
        "Registers TOC entries."
        if flowable.__class__.__name__ == 'Paragraph':
            text = flowable.getPlainText()
            style = flowable.style.name
            if style == 'index':
                key = 'h2-%s' % self.seq.nextf('heading1')
                self.canv.bookmarkPage(key)
                self.notify('TOCEntry', (0, text, self.page, key))
            if style == 'sub-index':
                key = 'h2-%s' % self.seq.nextf('heading1')
                self.canv.bookmarkPage(key)
                self.notify('TOCEntry', (1, text, self.page, key))
            if style == 'sub-index1':
                key = 'h2-%s' % self.seq.nextf('heading1')
                self.canv.bookmarkPage(key)
                self.notify('TOCEntry', (2, text, self.page, key))

# Span for building
    def dynamic_span(self, table_data, style, building_list):
        for row_idx, row in enumerate(table_data):
            for col_idx, cell in enumerate(row):
                if isinstance(cell, Paragraph):
                    building_list = [b.strip().lower() for b in building_list] 
                    cell_text = cell.text.strip().lower() 
                    print(f"Checking cell: {cell_text} {building_list}(Row {row_idx}, Column {col_idx})")
                    if cell_text in building_list:
                        print(f"Merging row {row_idx} for building: {cell_text}")
                        style.add('SPAN', (0, row_idx), (4, row_idx))  
                        style.add('ALIGN', (0, row_idx), (4, row_idx), 'CENTER')
                        style.add('VALIGN', (0, row_idx), (4, row_idx), 'BOTTOM')
                    else:
                        if row_idx == 0:
                            print(f"Merging row {row_idx} for building: {cell_text}")
                            style.add('SPAN', (0, row_idx), (4, row_idx))  
                            style.add('ALIGN', (0, row_idx), (4, row_idx), 'CENTER')
                            style.add('VALIGN', (0, row_idx), (4, row_idx), 'BOTTOM')
                elif isinstance(cell, str):
                    print(f"Checking cell: '{cell}' against {building_list} (Row {row_idx}, Column {col_idx})")
                    if cell in building_list:
                        style.add('SPAN', (0, row_idx), (4, row_idx))
                        style.add('ALIGN', (0, row_idx), (4, row_idx), 'CENTER')
                        style.add('VALIGN', (0, row_idx), (4, row_idx), 'BOTTOM')

    def show_inspection(self, wo_start_date, company_data, all_assets, all_fedby_data, thermal_assets,
                        thermal_fedby_asstes, thermal_image_data, nec_assets, nec_fedby_assets,
                        nec_image_data,osha_assets, osha_fedby_assets,
                        osha_image_data, repair_image_data, repair_assets, repair_fedby_data,
                        replace_assets, replace_image_data, replace_fedby_data,
                        other_assets, other_image_data, other_fedby_data,
                        ultrasonic_assets, ultrasonic_image_data, ultrasonic_fedby_data,
                        all_assets1, asset_image_data, ir_image_data, asset_fedby_data,
                        all_assets_feature_flag, assets_having_issues, thermal_ir_image_data, nfpa_assets, nfpa_image_data):
        try:
            s = getSampleStyleSheet()
            style = getSampleStyleSheet()
            table_style = ParagraphStyle(name='table_data', fontSize=9, fontName="Helvetica", textColor="black", alignment=0)
            table_style2 = ParagraphStyle(name='table_data1', fontSize=10, fontName="Helvetica", textColor="black", alignment=1)
            asset_comment_style = ParagraphStyle(name='table_data2', leftIndent=-39, fontSize=9, fontName="Helvetica", textColor="black", alignment=0, spaceBefore=-9)
            tight_style = ParagraphStyle(name='tight_style', parent=style['Normal'], alignment=0,
                                         leftIndent=0,      # No left indentation
                                         rightIndent=0,     # No right indentation
                                         spaceBefore=0,     # No space before the paragraph
                                         spaceAfter=0,      # No space after the paragraph
                                         )
            s = s["BodyText"]
            s.wordWrap = 'LTR'
            style.add(ParagraphStyle(name='index', fontName="Helvetica-Bold",fontSize=14, alignment=0, leftIndent=-41))
            style.add(ParagraphStyle(name='index1', fontName="Helvetica-Bold",fontSize=14, alignment=0, leftIndent=-61))
            style.add(ParagraphStyle(name='sub-index', fontName="Helvetica-Bold",fontSize=14, textColor='black', alignment=0, leftIndent=-40))
            style.add(ParagraphStyle(name='sub-index1', fontName="Helvetica-Bold",fontSize=14, textColor='black', alignment=0, leftIndent=-40))
            style.add(ParagraphStyle(name='cover-header',fontName="Helvetica-Bold", fontSize=16, alignment=1))
            style.add(ParagraphStyle(name='cover-header-big',fontName="Helvetica-Bold", fontSize=20, alignment=1))
            style.add(ParagraphStyle(name='cover',fontName="Helvetica", fontSize=12, alignment=1))
            style.add(ParagraphStyle(name='cover-add', fontName="Helvetica",fontSize=10, textColor="dimgray", alignment=1))
            style.add(ParagraphStyle(name='table_data_forward', fontSize=10,leftIndent=-40, fontName="Helvetica", textColor="black", alignment=0))
            style.add(ParagraphStyle(name='table_data_forward2', fontSize=10,leftIndent=-20, fontName="Helvetica", textColor="black", alignment=0))
            style.add(ParagraphStyle(name='table_data_forward1', fontSize=9,fontName="Helvetica", textColor="black", alignment=1))
            style.add(ParagraphStyle(name='table_data_forward1_1', fontSize=9,fontName="Helvetica-bold", textColor="black", alignment=1, bottompadding=20))
            style.add(ParagraphStyle(name='table_data_result', fontSize=10,fontName="Helvetica", textColor="black", alignment=0))
            style.add(ParagraphStyle(name='table_data_result1', fontSize=10,leftIndent=-1, fontName="Helvetica", textColor="black", alignment=0))
            style.add(ParagraphStyle(name='table_data_result2', fontSize=10,leftIndent=-40, fontName="Helvetica", textColor="black", alignment=0))
            style.add(ParagraphStyle(name='table_data_result3', fontSize=10, leftIndent=-30, fontName="Helvetica", textColor="black", leading=2, alignment=0))
            style.add(ParagraphStyle(name='table_headers_ei', fontSize=10,fontName="Helvetica-Bold", textColor="black", alignment=0,backColor='whitesmoke'))
            style.add(ParagraphStyle(name='table_data_ei', fontSize=9,fontName="Helvetica", textColor="black", alignment=0))
            style.add(ParagraphStyle(name='build_style',fontName="Helvetica-Bold", fontSize=10, alignment=1))
            style.add(ParagraphStyle(name='image-caption', fontName="Helvetica",textColor="black", fontSize=8, alignment=1))
            style.add(ParagraphStyle(name='image-caption1',fontName="Helvetica", fontSize=10, textColor="black", alignment=1))
            style.add(ParagraphStyle(name='image-caption2', fontName="Helvetica", fontSize=10, textColor="black", alignment=1))
            style.add(ParagraphStyle(name='table_headers_abc', fontSize=10,fontName="Helvetica-Bold", textColor="black", alignment=1)) 
            style.add(ParagraphStyle(name='table_style_thermal', fontSize=8,fontName="Helvetica", textColor="dimgray", alignment=1))
            style.add(ParagraphStyle(name='right_align', fontSize=14,fontName="Helvetica-Bold", alignment=2,spaceBefore=-35))

            style.add(tight_style)
            # style.add(sub_index_style)

            t_style = TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 10),
                                  ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                                  ('TEXTALIGN', (0, 0), (-1, -1), "MIDDLE"),
                                  ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                                  ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                                  ('VALIGN', (0, 0), (-1, -1), "MIDDLE")])

            t_header = TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica-Bold", 16),
                                   ("TEXTCOLOR", (0, 0), (-1, -1), "BLACK"),
                                   ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                                   ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                                   ('VALIGN', (0, 0), (-1, -1), "MIDDLE")])

            t_attri_style = TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 7),
                                        ('LINEBELOW', (0, 0), (-1, -1),
                                         0.25, colors.darkgray),
                                        ('BOX', (0, 0), (-1, -1),
                                         0.25, colors.darkgray),
                                        # ('GRID', (0, 0), (-1, -1), 1, colors.black),
                                        ('ALIGN', (0, 0), (-1, -1), "CENTRE"),
                                        ('VALIGN', (0, 0), (-1, -1), "MIDDLE")])

            flow_obj = []
            FIXED_HEIGHT = 2.7 * inch


            # /////////////////////// page 1 ///////////////////////
            IMAGE_DIMENSIONS = (200, 100)  # width, height
            SPACING = {
                'header': 195,
                'between_sections': 40,
                'line': 3,
                'address_gap': 30,
                'image_gap': 10,
                'footer': 20
            }


            # /////////////////////// page 1 ///////////////////////
            # Header section
            flow_obj.append(Spacer(700, SPACING['header']))
            report_name = Paragraph("Electrical<br/><br/>Maintenance Report",style['cover-header-big'])
            flow_obj.append(report_name)
            
            # Client information section
            flow_obj.append(Spacer(700, SPACING['between_sections']))
            flow_obj.extend([
                Paragraph(str(company_data[1]), style['cover']),  # client company
                Spacer(700, SPACING['line']),
                Paragraph(company_data[2] or "", style['cover-add']),  # address
            ])
            
            # Site information section
            flow_obj.extend([
                Spacer(700, SPACING['address_gap']),
                Paragraph(str(company_data[0]), style['cover']),  # site name
                Spacer(700, SPACING['line']),
                Paragraph(str(company_data[5]), style['cover-add']),  # site address
            ])
            
            # Site image
            flow_obj.append(Spacer(700, SPACING['image_gap']))
            if company_data[8]:  # site_profile_image
                try:
                    image_stream = urlopen(company_data[8])
                    site_image = Image(image_stream, width=IMAGE_DIMENSIONS[0],height=IMAGE_DIMENSIONS[1])
                    flow_obj.append(site_image)
                except Exception as e:
                    logging.error(f"Failed to load image from {company_data[8]}: {e}")
            
            # Footer section
            flow_obj.extend([
                Spacer(700, SPACING['footer']),
                Paragraph(str(company_data[6]), style['cover']),  # company name
                Spacer(700, SPACING['line']),
                Paragraph(format_ordinal_date(company_data[7]), style['cover-add']),  # date
                PageBreak()
            ])


            # /////////////////////// Table Of Content ///////////////////////
            h1 = Table([["Table Of Content"]], hAlign="CENTER")
            h1.setStyle(t_header)
            flow_obj.append(h1)
            flow_obj.append(Spacer(500, 12))

            toc = TableOfContents()
            toc.levelStyles = [
                ParagraphStyle(fontName='Helvetica-Bold', fontSize=10, name='index',leftIndent=-10, firstLineIndent=2, spaceBefore=3, leading=6,
                               textColor="LightSlateGray"),
                ParagraphStyle(fontName='Helvetica', fontSize=9, name='sub-index',leftIndent=6, firstLineIndent=-10, spaceBefore=1, leading=4,
                               bulletText=u'\u2013', bulletIndent=10),
                ParagraphStyle(fontName='Helvetica', fontSize=9, name='sub-index1',leftIndent=45, firstLineIndent=-10, spaceBefore=1, leading=4,
                               bulletText=u'\u2013', bulletIndent=25)

            ]
            flow_obj.append(toc)
            flow_obj.append(PageBreak())

            # /////////////////////// Forward ///////////////////////
            content = []
            hall = Paragraph("Foreword",style['index'])
            flow_obj.append(hall)
            flow_obj.append(Spacer(500, 13))
           
            foreword_text = """Thermographic analysis identifies potential heat-related issues that can impact equipment performance and safety. Elevated temperatures indicate problems such as loose connections, overloaded circuits, or degraded components. Addressing these anomalies helps prevent unscheduled outages, equipment failures, and safety hazards, ensuring the reliability and efficiency of the system.<br/><br/>"""
            text2 = """To interpret the temperature differences (ΔT) effectively, three comparison methods are used:<br/><br/>"""
            text3 = ["<b><b>•</b></b> &nbsp;&nbsp;  <b>Similar Method:</b> Compare the temperatures of similar components operating under similar load &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;conditions to identify discrepancies."]
            text3_1 = ["<b><b>•</b></b> &nbsp;&nbsp;  <b>Ambient Method:</b> Compare the temperature of a component to the surrounding ambient air &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;temperature to detect unusual heat patterns."]
            text3_2 = ["<b><b>•</b></b> &nbsp;&nbsp;  <b>Indirect Method:</b> Identify components exceeding their rated temperature limits or operating &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;otherwise hotter than is reasonably expected, without a direct reference &nbsp;&nbsp;&nbsp;comparison."]
            text4 = """The following table outlines the recommended actions based on temperature differences identified during a thermographic survey for the Similar and Ambient comparison criteria. Indirect Anomalies are highly situational, and thus left up to the discretion of the qualified Thermographer to identify and classify appropriately."""
            text3_paragraph = '<br/>'.join(text3)
            text3_1_paragraph = '<br/>'.join(text3_1)
            text3_2_paragraph = '<br/>'.join(text3_2)

            flow_obj.append(Paragraph(foreword_text, style['table_data_forward']))
            flow_obj.append(Paragraph(text2, style['table_data_forward']))
            flow_obj.append(Paragraph(text3_paragraph,style['table_data_forward2']))
            flow_obj.append(Spacer(1, 6))
            flow_obj.append(Paragraph(text3_1_paragraph,style['table_data_forward2']))
            flow_obj.append(Spacer(1, 6))
            flow_obj.append(Paragraph(text3_2_paragraph,style['table_data_forward2']))
            flow_obj.append(Spacer(1, 6))
            flow_obj.append(Paragraph(text4, style['table_data_forward']))
            flow_obj.append(Spacer(1, 12))

            
            data = [
                [
                    Paragraph('ΔT - Similar Method',style['table_data_forward1_1']),
                    Paragraph('ΔT - Ambient Method',style['table_data_forward1_1']),
                    Paragraph('Thermal Classification',style['table_data_forward1_1']),
                    Paragraph('Recommended Corrective Action',style['table_data_forward1_1'])
                ],
                [
                    Paragraph('1.8 - 5.4 °F',style['table_data_forward1']),
                    Paragraph('1.8 - 18.0 °F',style['table_data_forward1']),
                    Paragraph('Nominal', style['table_data_forward1']),
                    Paragraph('Possible deficiency; warrants investigation', style['table_data_forward1'])
                ],
                [
                    Paragraph('5.5 - 27.0 °F',style['table_data_forward1']),
                    Paragraph('18.1 - 36.0 °F',style['table_data_forward1']),
                    Paragraph('Intermediate',style['table_data_forward1']),
                    Paragraph('Indicates probable deficiency; repair as time permits', style['table_data_forward1'])
                ],
                [
                    Paragraph('-----', style['table_data_forward1']),
                    Paragraph('36.1 - 72.0 °F',style['table_data_forward1']),
                    Paragraph('Serious', style['table_data_forward1']),
                    Paragraph('Monitor until corrective measures can be accomplished', style['table_data_forward1'])
                ],
                [
                    Paragraph('> 27.0 °F', style['table_data_forward1']),
                    Paragraph('> 72.0 °F', style['table_data_forward1']),
                    Paragraph('Critical', style['table_data_forward1']),
                    Paragraph('Major discrepancy; repair immediately',style['table_data_forward1'])
                ]
            ]

            text5 = """More information about Infrared Thermography can be found in NETA® MTS, Table 100.18."""
            col_widths = [110, 125, 130, 150, 150]
            table = Table(data, hAlign='CENTER', colWidths=col_widths)

            # Define the TableStyle
            table_style1 = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('TEXTALIGN', (0, 0), (-1, -1), 'CENTER'),
            ])

            table.setStyle(table_style1)
            flow_obj.append(table)
            flow_obj.append(Spacer(1, 12))
            flow_obj.append(Paragraph(text5, style['table_data_forward']))
            flow_obj.append(PageBreak())

            # /////////////////////// Results Summary ///////////////////////
            if len(all_assets) > 0:
                index1 = Paragraph("Results Summary", style['index'])
                flow_obj.append(index1)
                flow_obj.append(Spacer(500, 16))

                # print(f"{str(len(thermal_assets)) , str(len(ultrasonic_assets)) , len(nec_assets),len(osha_assets) , len(nfpa_assets) ,len(replace_assets) , len(repair_assets) , len(other_assets)})")
                # result_text = Paragraph(f"In total, the thermographer inspected {str(len(all_assets))} items, and in so doing, identified "
                #                         f"{len(thermal_assets) + len(ultrasonic_assets) + len(nec_assets) + len(osha_assets) + len(nfpa_assets) + len(replace_assets) + len(repair_assets) + len(other_assets)} issues of the following types:", style['table_data_result2'])

                # flow_obj.append(result_text)
                # flow_obj.append(Spacer(500, 10))
                printed_issue_count =0
                # Initialize counters for each issue type
                thermal_issue_count = 0
                ultrasonic_issue_count = 0
                nec_issue_count = 0
                osha_issue_count = 0
                nfpa_issue_count = 0
                replace_issue_count = 0
                repair_issue_count = 0
                other_issue_count = 0

                # Iterate through all assets and count issues
                for an_asset in all_assets:
                    asset_id = an_asset[0]  # Get the asset ID

                    # Filter and count issues for the current asset
                    thermal_issues = [issue for issue in thermal_assets if issue[0] == asset_id]
                    thermal_issue_count += len(thermal_issues)

                    ultrasonic_issues = [issue for issue in ultrasonic_assets if issue[-1] == asset_id]
                    ultrasonic_issue_count += len(ultrasonic_issues)

                    nec_issues = [issue for issue in nec_assets if issue[-1] == asset_id]
                    nec_issue_count += len(nec_issues)

                    osha_issues = [issue for issue in osha_assets if issue[-1] == asset_id]
                    osha_issue_count += len(osha_issues)

                    nfpa_issues = [issue for issue in nfpa_assets if issue[-1] == asset_id]
                    nfpa_issue_count += len(nfpa_issues)

                    replace_issues = [issue for issue in replace_assets if issue[-1] == asset_id]
                    replace_issue_count += len(replace_issues)

                    repair_issues = [issue for issue in repair_assets if issue[-1] == asset_id]
                    repair_issue_count += len(repair_issues)

                    other_issues = [issue for issue in other_assets if issue[-1] == asset_id]
                    other_issue_count += len(other_issues)

                # Create the consolidated summary data
                data = []
                if thermal_issue_count > 0:
                    data.append(Paragraph(f" - &nbsp; {thermal_issue_count} Thermal Anomaly", style['table_data_result3']))
                if ultrasonic_issue_count > 0:
                    data.append(Paragraph(f" - &nbsp; {ultrasonic_issue_count} Ultrasonic Anomaly", style['table_data_result3']))
                if nec_issue_count > 0:
                    data.append(Paragraph(f" - &nbsp; {nec_issue_count} NEC Violation", style['table_data_result3']))
                if osha_issue_count > 0:
                    data.append(Paragraph(f" - &nbsp; {osha_issue_count} OSHA Violation", style['table_data_result3']))
                if nfpa_issue_count > 0:
                    data.append(Paragraph(f" - &nbsp; {nfpa_issue_count} NFPA 70B Violation", style['table_data_result3']))
                if replace_issue_count > 0:
                    data.append(Paragraph(f" - &nbsp; {replace_issue_count} Replacement Needed", style['table_data_result3']))
                if repair_issue_count > 0:
                    data.append(Paragraph(f" - &nbsp; {repair_issue_count} Repair Needed", style['table_data_result3']))
                if other_issue_count > 0:
                    data.append(Paragraph(f" - &nbsp; {other_issue_count} Other", style['table_data_result3']))


               
                grouped_issues = {
                    'Thermal Anomaly': {issue[0]: [] for issue in thermal_assets},
                    'Ultrasonic Anomaly': {issue[-1]: [] for issue in ultrasonic_assets},
                    'NEC Violation': {issue[-1]: [] for issue in nec_assets},
                    'OSHA Violation': {issue[-1]: [] for issue in osha_assets},
                    'NFPA 70B Violation': {issue[-1]: [] for issue in nfpa_assets},
                    'Replacement Needed': {issue[-1]: [] for issue in replace_assets},
                    'Repair Needed': {issue[-1]: [] for issue in repair_assets},
                    'Other': {issue[-1]: [] for issue in other_assets}
                }

                # Populate and sort the grouped issues directly
                for issue in thermal_assets:
                    grouped_issues['Thermal Anomaly'][issue[0]].append(issue)
                    # grouped_issues['Thermal Anomaly'][issue[0]].sort(key=get_thermal_priority)
                    print('thermal')
                for issue in ultrasonic_assets:
                    grouped_issues['Ultrasonic Anomaly'][issue[-1]].append(issue)
                    print('ultra')
                for issue in nec_assets:
                    grouped_issues['NEC Violation'][issue[-1]].append(issue)
                    print('NEC')
                for issue in osha_assets:
                    grouped_issues['OSHA Violation'][issue[-1]].append(issue)
                    print('OSHA')
                for issue in nfpa_assets:
                    grouped_issues['NFPA 70B Violation'][issue[-1]].append(issue)
                    print('nfpa')
                for issue in replace_assets:
                    grouped_issues['Replacement Needed'][issue[-1]].append(issue)
                    print('replace')
                for issue in repair_assets:
                    grouped_issues['Repair Needed'][issue[-1]].append(issue)
                    print('repair')
                for issue in other_assets:
                    grouped_issues['Other'][issue[-1]].append(issue)
                    print('other')
                
                resolved_count = 0
                open_count = 0

                overview_details_dummy = [
                    Paragraph("<b>Asset Name</b>", style['table_data_result']),
                    Paragraph("<b>Issue Type</b>", style['table_data_result']),
                    Paragraph("<b>Thermal Classification</b>",style['table_data_result']),
                    Paragraph("<b>Issue Status</b>",style['table_data_result'])
                ]

                table_data = []
                print(f"Total assets to process: {len(all_assets)}")
                for an_asset in all_assets:
                    asset_id = an_asset[0]
                    print('asset_id',asset_id)
                    print(len(an_asset))
                    assets_name = an_asset[1]
                    issue_types = enum_woline_temp_issue_type[an_asset[13]] if an_asset[13] else '-'

                    if not isinstance(issue_types, list):
                        issue_types = [issue_types]
                    print('issue_types',issue_types)
                    filtered_issues=[]
                    issue_dict={}
                    for issue_name, issue_dict in grouped_issues.items():
                    # print('issue_dict',issue_name)
                        if asset_id  in issue_dict:
                            filtered_issues = issue_dict[asset_id]
                            print('filtered_issues',filtered_issues)
                            issue_count = len(filtered_issues)
                            print(f"Found {issue_count} {issue_name} issues")

                            for issue in filtered_issues:  # Iterate over each specific issue
                                if issue[10] == 1:
                                    issue_status = 'Resolved' if issue[-2] else 'Open'  # Use issue-specific status
                                elif issue[10] == 9:
                                    issue_status = 'Resolved' if issue[-2] else 'Open'  # Use issue-specific status
                                else:
                                    issue_status = 'Resolved' if issue[-3] else 'Open'  # Use issue-specific status
                                print('issue_status',issue_status,issue[-5])
                                    
                                if issue[10] == 2: 
                                    thermal_index = int(issue[11]) if issue[11] else None  # Convert to int safely
                                    print(thermal_index)
                                    thermal_classification = enum_thermal_classification[thermal_index] if thermal_index is not None else ' '
                                else:
                                    thermal_classification=' '
                                print('thermal_classification',thermal_classification)
                                table_data.append([
                                    Paragraph(assets_name, style['table_data_result1']),
                                    Paragraph(issue_name, style['table_data_result1']),
                                    Paragraph(thermal_classification, style['table_data_result1']),
                                    Paragraph(issue_status, style['table_data_result1'])
                                ])
                                printed_issue_count+=1

                                if issue_status == 'Resolved':
                                    resolved_count += 1
                                else:
                                    open_count += 1
                            # print('table_data',table_data)

                result_text1 = Paragraph(
                    f"Of these issues, the thermographer was able to resolve {resolved_count}, leaving a total of {open_count} open issues at your site.", style['table_data_result2'])
                print(f"{printed_issue_count})")
                result_text = Paragraph(f"In total, the thermographer inspected {str(len(all_assets))} items, and in so doing, identified "
                                        f"{printed_issue_count} issues of the following types:", style['table_data_result2'])

                flow_obj.append(result_text)
                flow_obj.append(Spacer(500, 10))

                for item in data:
                    flow_obj.append(item)
                    flow_obj.append(Spacer(1, 11))
                flow_obj.append(Spacer(500, 10))
                
                flow_obj.append(result_text1)
                flow_obj.append(Spacer(500, 10))
                table_data.insert(0, overview_details_dummy)
                table_overview = Table(table_data, hAlign='CENTER', vAlign='LEFT', colWidths=[133, 133, 133, 115, 115])

                t_style1 = TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                    ('TOPPADDING', (0, 0), (-1, 0), 5),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ])

                table_overview.setStyle(t_style1)
                flow_obj.append(table_overview)
                print('end')
                flow_obj.append(PageBreak())
            # //////////////////////////// Issue Pages //////////////////////////// #

            issue_pages_added = False
            processed_assets = set()
            print(len(all_assets1))
            if not issue_pages_added:
                for asset_data1 in all_assets1:
                    if asset_data1[-4] or asset_data1[-3]:  # Check if any asset has issues
                        asset_name12 = Paragraph('<font color="white">Issue Pages</font>', style['index'])
                        flow_obj.append(asset_name12)
                        issue_pages_added = True
                        break 
            for asset_data1 in all_assets1:
                if asset_data1[0] in processed_assets:
                        continue
                if not all_assets_feature_flag:

                    if asset_data1[0] not in assets_having_issues:
                        continue
                    else:
                        pass
                # /////////////////////// Thermal Issue  ///////////////////////
                print('thermal_assets1',thermal_assets)
                if len(thermal_assets) > 0:
                    print('thermal')
                    for asset_data in thermal_assets:
                        if asset_data[0] == asset_data1[0]:
                            issue_data_name = asset_data[1]
                            thermal_classification_id = enum_thermal_classification[asset_data[11]] if asset_data[11] else ' '
                            if thermal_classification_id == 'Ok':
                                color = '#2A9D55'
                            elif thermal_classification_id == 'Nominal':
                                color = '#005BBB'
                            elif thermal_classification_id == 'Intermediate':
                                color = '#C75A00'
                            elif thermal_classification_id == 'Serious':
                                color = '#C75A00'
                            elif thermal_classification_id == 'Critical':
                                color = '#D00000'
                            else:
                                color = '#D00000'
                            condition_thermal_classification = f'<font color="{color}">{thermal_classification_id}</font>'
                            if asset_data[-3]:
                                issue_thermal_status = 'Resolved'
                                if issue_thermal_status == 'Resolved':
                                    color = '#2A9D55'
                                thermal_resolved = f'<font color="{color}">{issue_thermal_status}</font>'
                                page_name = 'Thermal Anomaly ({}) - {} - {}'.format(condition_thermal_classification,asset_data[1],thermal_resolved)
                            else:
                                page_name = 'Thermal Anomaly ({}) - {}'.format(condition_thermal_classification,asset_data[1])
                            h1 = Paragraph(page_name, style['sub-index'])
                                
                            flow_obj.append(h1)
                            flow_obj.append(Spacer(500, 18))
                            image_array = []
                            flag_image_array = []
                            thermal_images_before=[]
                            thermal_images_after=[]

                            PL1 = Paragraph(''' <para align=left><b> </b></para>''',style['image-caption1'])
                            PR1 = Paragraph('''<para align=left><b></b></para>''',style['image-caption1'])
                            PLA = Paragraph('''<para align=left><b>Before Photo:</b></para>''', style['image-caption1'])
                            PL3 = Paragraph('''<para align=left><b>After Photo:</b></para>''', style['image-caption1'])
                            issue_type = enum_woline_temp_issue_type[asset_data[10]
                                                                    ] if asset_data[10] else '-'
                            thermal_classification = enum_thermal_classification[asset_data[11]
                                                                                ] if asset_data[11] else '-'
                            building = asset_data[3] if asset_data[3] else '-'
                            floor = asset_data[4] if asset_data[4] else '-'
                            room = asset_data[5] if asset_data[5] else '-'
                            probable_cause = asset_data[15] if asset_data[15] else '-'
                            recommendation = asset_data[14] if asset_data[14] else '-'
                            sub_componant = asset_data[12] if asset_data[12] else '-'
                            refrence_temp = asset_data[13] if is_valid_number(asset_data[13])  else '-'
                            measured_temp = asset_data[16] if is_valid_number(asset_data[16]) else '-'
                            measured_amp = asset_data[17] if asset_data[17] else '-'
                            anomaly_location = asset_data[18] if asset_data[18] else '-'
                            panel_schedule = enum_temp_panel_schedule_type[asset_data[20]
                                                                        ] if asset_data[20] else '-'
                            severity_criteria = enum_severity_criteria_type[asset_data[24]] if asset_data[24] else '-'
                            condition_thermal = enum_maintenance_condition_index_type[asset_data[9]] if asset_data[9] else '-'
                            comments = asset_data[8] if asset_data[8] else 'N/A'
                            if is_valid_number(measured_temp) and is_valid_number(refrence_temp):
                                if '.' in str(measured_temp) or '.' in str(refrence_temp):
                                    # If either number is a float, return the difference as float
                                    temp_diff = round(abs(float(measured_temp) - float(refrence_temp)),2)
                                else:
                                    # If both numbers are integers, return the difference as int
                                    temp_diff = abs(int(measured_temp) - int(refrence_temp))
                            elif measured_temp == '-' and refrence_temp == '-':
                                # Both temperatures are '-'
                                temp_diff = '-'
                            elif measured_temp == '-':
                                # If measured_temp is '-', use refrence_temp
                                temp_diff = float(refrence_temp) if '.' in str(refrence_temp) else int(refrence_temp)
                            elif refrence_temp == '-':
                                # If refrence_temp is '-', use measured_temp
                                temp_diff = float(measured_temp) if '.' in str(measured_temp) else int(measured_temp)
                            else:
                                # Handle the case where one is invalid or not present
                                temp_diff = 'N/A'

                            if asset_data1[12] == 2:
                                asset_top_level_t = fetch_sublevel_asset_id1(asset_data1[0], asset_data1[-1])
                                print('asset_top_level_t', asset_top_level_t)
                                data4 = [
                                    [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_data[1]), table_style),
                                    Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                                    [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_data[2]), table_style),
                                    Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                                    [Paragraph("<b>Contained Within: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_top_level_t), table_style),
                                    Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                                    [Paragraph("<b>Serviceability: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(condition_thermal), table_style),'',''],
                                    [Paragraph("<b>Criteria: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(severity_criteria), table_style),
                                    Paragraph("<b>Problem Description: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(probable_cause), table_style)],
                                    [Paragraph("<b>Measured Temp: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(measured_temp), table_style)],
                                    [Paragraph("<b>Reference Temp: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(refrence_temp), table_style),
                                    Paragraph("<b>Recommended Corrective Action: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(recommendation), table_style)],
                                    [Paragraph("<b> ΔT: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(temp_diff), table_style)],
                                    [Paragraph("<b>Classification: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(thermal_classification), table_style)]
                                    ]

                                detail_style = [('BOX', (0, 0), (10,10), 0.7, colors.black),
                                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                            ('SPAN', (2, 6), (2, 7)),  # Room
                                            ('ALIGN', (2, 6), (2, 7), 'CENTER'),  # Center-align Issue Description
                                            ('VALIGN', (2, 6), (2, 7), 'MIDDLE'),
                                            ('SPAN', (3, 6), (3, 7)),  # Room
                                            ('ALIGN', (3, 6), (3, 7), 'CENTER'),  # Center-align Issue Description
                                            ('VALIGN', (3, 6), (3, 7), 'MIDDLE'),
                                            ('SPAN', (2, 8), (2, 10)),  # Room
                                            ('ALIGN', (2, 8), (2, 10), 'CENTER'),  # Center-align Issue Description
                                            ('VALIGN', (2, 8), (2, 10), 'MIDDLE'),
                                            ('SPAN', (3, 8), (3, 10)),  # Room
                                            ('ALIGN', (3, 8), (3, 10), 'CENTER'),  # Center-align Issue Description
                                            ('VALIGN', (3, 8), (3, 10), 'MIDDLE'),
                                            ('LINEBELOW', (0, 1), (0, 1),0.7,colors.black), # draw line after image
                                            ('LINEBELOW', (1, 1), (1, 1),0.7,colors.black), # draw line after image
                                            ('LINEBELOW', (2, 1), (2, 1),0.7,colors.black), # draw line after image
                                            ('LINEBELOW', (3, 1), (3, 1),0.7,colors.black), # draw line after image
                                            ('LINEBELOW', (0, 5), (0, 5),0.7,colors.black), # draw line after serviceability
                                            ('LINEBELOW', (1, 5), (1, 5),0.7,colors.black), # draw line after serviceability
                                            ('LINEBELOW', (2, 5), (2, 5),0.7,colors.black), # draw line after Room
                                            ('LINEBELOW', (3, 5), (3, 5),0.7,colors.black), # draw line after Room
                                            ('LINEBELOW', (2, 7), (2, 7),0.7,colors.black), # draw line after Problem Description
                                            ('LINEBELOW', (3, 7), (3, 7),0.7,colors.black), # draw line after Problem Description
                                            ('LINEBELOW', (4, 7), (4, 7),0.7,colors.black), # draw line after Problem Description
                                            ('LINEBEFORE', (2, 2), (2, 2),0.7,colors.black),  # Before "Building" V line
                                            ('LINEBEFORE', (2, 3), (2, 3),0.7,colors.black),  # Before "Floor"
                                            ('LINEBEFORE', (2, 4), (2, 4),0.7,colors.black),  # Before "Room"
                                            ('LINEBEFORE', (2, 5), (2, 5),0.7, colors.black), # Before ""
                                            ('LINEBEFORE', (2, 6), (2, 6),0.7, colors.black), # Before "Recommended Corrective Action:"
                                            ('LINEBEFORE', (3, 6), (3, 6),0.7, colors.black), # After "Recommended Corrective Action:"
                                            ('LINEBEFORE', (3, 7), (3, 7),0.7, colors.black), # After "Problem Description:"
                                            ('LINEBEFORE', (3, 8), (3, 8),0.7, colors.black), # After "Recommended Corrective Action:"
                                            ('LINEBEFORE', (3, 9), (3, 9),0.7, colors.black), # After "Recommended Corrective Action:"
                                            ('LINEBEFORE', (3, 10), (3, 10),0.7, colors.black), # After "Recommended Corrective Action:"
                                            ('LINEBEFORE', (2, 7), (2, 7),0.7, colors.black), # Before ""
                                            ('LINEBEFORE', (2, 8), (2, 8),0.7, colors.black), # Before ""
                                            ('LINEBEFORE', (2, 9), (2, 9),0.7, colors.black), # Before ""
                                            ('LINEBEFORE', (2, 10), (2, 10),0.7, colors.black), # Before ""
                                            
                                            ]
                            else:

                                data4 = [
                                        [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_data[1]), table_style),
                                        Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                                        [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_data[2]), table_style),
                                        Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                                        [Paragraph("<b>Serviceability: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(condition_thermal), table_style),
                                        Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                                        [Paragraph("<b>Criteria: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(severity_criteria), table_style),
                                        Paragraph("<b>Problem Description: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(probable_cause), table_style)],
                                        [Paragraph("<b>Measured Temp: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(measured_temp), table_style)],
                                        [Paragraph("<b>Reference Temp: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(refrence_temp), table_style),
                                        Paragraph("<b>Recommended Corrective Action: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(recommendation), table_style)],
                                        [Paragraph("<b> ΔT: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(temp_diff), table_style)],
                                        [Paragraph("<b>Classification: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(thermal_classification), table_style)]
                                    ]
                        

                                detail_style = [('BOX', (0, 0), (9,9), 0.7, colors.black),
                                                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                                ('SPAN', (2, 5), (2, 6)),  # Room
                                                ('ALIGN', (2, 5), (2, 6), 'CENTER'),  # Center-align Issue Description
                                                ('VALIGN', (2, 5), (2, 6), 'MIDDLE'),
                                                ('SPAN', (3, 5), (3, 6)),  # Room
                                                ('ALIGN', (3, 5), (3, 6), 'CENTER'),  # Center-align Issue Description
                                                ('VALIGN', (3, 5), (3, 6), 'MIDDLE'),
                                                ('SPAN', (2, 7), (2, 9)),  # Room
                                                ('ALIGN', (2, 7), (2, 9), 'CENTER'),  # Center-align Issue Description
                                                ('VALIGN', (2, 7), (2, 9), 'MIDDLE'),
                                                ('SPAN', (3, 7), (3, 9)),  # Room
                                                ('ALIGN', (3, 7), (3, 9), 'CENTER'),  # Center-align Issue Description
                                                ('VALIGN', (3, 7), (3, 9), 'MIDDLE'),
                                                ('LINEBELOW', (0, 1), (0, 1),0.7,colors.black), # draw line after image
                                                ('LINEBELOW', (1, 1), (1, 1),0.7,colors.black), # draw line after image
                                                ('LINEBELOW', (2, 1), (2, 1),0.7,colors.black), # draw line after image
                                                ('LINEBELOW', (3, 1), (3, 1),0.7,colors.black), # draw line after image
                                                ('LINEBELOW', (0, 4), (0, 4),0.7,colors.black), # draw line after serviceability
                                                ('LINEBELOW', (1, 4), (1, 4),0.7,colors.black), # draw line after serviceability
                                                ('LINEBELOW', (2, 4), (2, 4),0.7,colors.black), # draw line after Room
                                                ('LINEBELOW', (3, 4), (3, 4),0.7,colors.black), # draw line after Room
                                                ('LINEBELOW', (2, 6), (2, 6),0.7,colors.black), # draw line after Problem Description
                                                ('LINEBELOW', (3, 6), (3, 6),0.7,colors.black), # draw line after Problem Description
                                                ('LINEBELOW', (4, 6), (4, 6),0.7,colors.black), # draw line after Problem Description
                                                ('LINEBEFORE', (2, 2), (2, 2),0.7,colors.black),  # Before "Building" V line
                                                ('LINEBEFORE', (2, 3), (2, 3),0.7,colors.black),  # Before "Floor"
                                                ('LINEBEFORE', (2, 4), (2, 4),0.7,colors.black),  # Before "Room"
                                                ('LINEBEFORE', (2, 5), (2, 5),0.7, colors.black), # Before "Problem Description:"
                                                ('LINEBEFORE', (2, 6), (2, 6),0.7, colors.black), # Before "Recommended Corrective Action:"
                                                ('LINEBEFORE', (3, 5), (3, 5),0.7, colors.black), # After "Problem Description:"
                                                ('LINEBEFORE', (3, 6), (3, 6),0.7, colors.black), # After "Recommended Corrective Action:"
                                                ('LINEBEFORE', (3, 7), (3, 7),0.7, colors.black), # After "Problem Description:"
                                                ('LINEBEFORE', (3, 8), (3, 8),0.7, colors.black), # After "Recommended Corrective Action:"
                                                ('LINEBEFORE', (3, 9), (3, 9),0.7, colors.black), # After "Recommended Corrective Action:"
                                                ('LINEBEFORE', (2, 7), (2, 7),0.7, colors.black), # Before ""
                                                ('LINEBEFORE', (2, 8), (2, 8),0.7, colors.black), # Before ""
                                                ('LINEBEFORE', (2, 9), (2, 9),0.7, colors.black), # Before ""
                                                
                                                ]
                            
                            if asset_data[22] in thermal_ir_image_data.keys():
                                print('image_data_t1',thermal_ir_image_data)
                                
                                for image_data in thermal_ir_image_data.get(asset_data[22]):
                                    print('image_data_t',image_data)
                                    if image_data[0] is not None and image_data[3] is not None:
                                        visual_images = fetch_image(
                                            image_data[1], image_data[3], BUCKET_NAME)

                                        if visual_images:
                                            IL = create_ir_image(visual_images,scale_factor=0.75)

                                            PL2 = Paragraph(''' <para align=center><b>{}</b></para>'''.format(
                                                image_data[3].split(".")[0]),
                                                style['image-caption'])
                                            image_array.append([IL,Spacer(0,3),PL2])
                                            flag_image_array.append(1)

                                        else:
                                            print("couldnot fetch image")

                                            PNI = Paragraph(''' <para align=center><b>{} </b></para>'''.format(
                                                    image_data[3].split(".")[0]),
                                                style['image-caption'])
                                            image_array=[]
                                            flag_image_array.append(0)

                                    else:
                                        # SHOW HERE NOTHING AND PUT IF ONLY 1 IMAGE is there then in center
                                        flag_image_array.append(0)

                                        PNI = Paragraph(''' <para align=left><b>No image found! </b></para>''',
                                            style['image-caption'])
                                        image_array.append([PNI])


                                    print("visual done")

                                    if image_data[0] is not None and image_data[2] is not None:
                                        ir_images = fetch_image(
                                            image_data[1], image_data[2], BUCKET_NAME)
                                        if ir_images:
                                            IR = create_ir_image(ir_images,scale_factor=0.75)
                                            PR2 = Paragraph('''<para align=center><b>{}</b></para>'''.format(
                                                image_data[2].split(".")[0]),
                                                style['image-caption'])
                                            image_array.append([IR, Spacer(0,3),PR2])
                                            flag_image_array.append(1)
                                        else:
                                            print("could not fetch image")
                                            PNI = Paragraph(
                                                ''' <para align=left><b>{} </b></para>'''.format(
                                                    image_data[2].split(".")[0]),
                                                style['image-caption'])
                                            image_array=[]
                                            flag_image_array.append(0)
                                    else:
                                        print("No  image to display")
                                        PNI = Paragraph(''' <para align=left><b>No image found! </b></para>''',
                                            style['image-caption'])
                                        image_array.append([PNI])
                                        flag_image_array.append(0)


                                    print("ir done")
                            else:
                                print("No  image to display")
                            # THERMAL IR/VISUAL
                            startrow = 0
                            ir_photo_added = None
                            if len(image_array) == 2: 
                                image_array.append(Paragraph(''))
                            print('image_array',len(image_array),image_array)
                            
                            if len(image_array) > 0:
                                for image_pair_index in range(0, image_array.__len__(), 2):
                                    print('IMAGE_PAIR_INDEX',image_pair_index)
                                    if image_pair_index < len(flag_image_array) and image_pair_index + 1 < len(flag_image_array):
                                        print('ir_images_f',image_array)
                                        if flag_image_array[image_pair_index] != 0 and flag_image_array[image_pair_index + 1] != 0:
                                            data4.insert(startrow, [image_array[image_pair_index], '',image_array[image_pair_index + 1],''])
                                            detail_style.extend([('SPAN', (0, startrow), (1, startrow)), ('SPAN', (2, startrow), (3, startrow))])
                                            detail_style.append(('ALIGN', (2, startrow), (3, startrow), 'LEFT'))  # Align second image to the left
                                            detail_style.append(('LEFTPADDING', (2, startrow), (3, startrow), 10))
                                            startrow += 1

                                        elif flag_image_array[image_pair_index] == 0 and flag_image_array[image_pair_index + 1] != 0:
                                            data4.insert(startrow, [image_array[image_pair_index + 1]])
                                            detail_style.append(('SPAN', (0, startrow), (3, startrow)))
                                            detail_style.append(('ALIGN', (0, startrow), (3, startrow), 'CENTER'))  # Align second image to the center
                                            startrow += 1

                                        elif flag_image_array[image_pair_index + 1] == 0 and flag_image_array[image_pair_index] != 0:
                                            data4.insert(startrow, [image_array[image_pair_index]])
                                            detail_style.append(('SPAN', (0, startrow), (3, startrow)))
                                            detail_style.append(('ALIGN', (0, startrow), (3, startrow), 'CENTER'))  # Align first image to the center
                                            startrow += 1
                                    else:
                                        data4.insert(startrow, ['', '', '',''])
                                        startrow += 1
                                        print(f"Index out of range for flag_image_array at index {image_pair_index} or {image_pair_index + 1}")
                    

                            if len(image_array) == 0:
                                if asset_data1[12] == 2:
                                    detail_style = [('BOX', (0, 0), (9,9), 0.7, colors.black),
                                                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                                ('SPAN', (2, 4), (2, 5)),  # combine 2 rows upside down for problem description
                                                ('SPAN', (3, 4), (3, 5)),  # combine 2 rows upside down for problem description Data
                                                ('ALIGN', (2, 4), (2, 5), 'CENTER'),  # Center-align Issue Description
                                                ('VALIGN', (2, 4), (2, 5), 'MIDDLE'),
                                                ('ALIGN', (3, 4), (3, 5), 'CENTER'),  # Center-align Issue Description
                                                ('VALIGN', (3, 4), (3, 5), 'MIDDLE'),
                                                ('SPAN', (2, 6), (2, 8)),  # combine 2 rows upside down for problem description
                                                ('SPAN', (3, 6), (3, 8)),  # combine 2 rows upside down for problem description
                                                ('ALIGN', (2, 6), (2, 8), 'CENTER'),  # Center-align Issue Description
                                                ('VALIGN', (2, 6), (2, 8), 'MIDDLE'),
                                                ('ALIGN', (3, 6), (3, 8), 'CENTER'),  # Center-align Issue Description
                                                ('VALIGN', (3, 6), (3, 8), 'MIDDLE'),
                                                ('LINEBELOW', (0, 3), (0, 3),0.7,colors.black), # draw line after serviceability
                                                ('LINEBELOW', (1, 3), (1, 3),0.7,colors.black), # draw line after serviceability
                                                ('LINEBELOW', (2, 3), (2, 3),0.7,colors.black), # draw line after Room
                                                ('LINEBELOW', (3, 3), (3, 3),0.7,colors.black), # draw line after Room
                                                ('LINEBELOW', (2, 5), (2, 5),0.7,colors.black), # draw line after Problem Description
                                                ('LINEBELOW', (3, 5), (3, 5),0.7,colors.black), # draw line after Problem Description
                                                ('LINEBELOW', (4, 5), (4, 5),0.7,colors.black), # draw line after Problem Description
                                                ('LINEBEFORE', (2, 0), (2, 0),0.7,colors.black),  # Before "Building" V line
                                                ('LINEBEFORE', (2, 1), (2, 1),0.7,colors.black),  # Before "Building" V line
                                                ('LINEBEFORE', (2, 2), (2, 2),0.7,colors.black),  # Before "Building" V line
                                                ('LINEBEFORE', (2, 3), (2, 3),0.7,colors.black),  # Before "Floor"
                                                ('LINEBEFORE', (2, 4), (2, 4),0.7,colors.black),  # Before "Room"
                                                ('LINEBEFORE', (2, 5), (2, 5),0.7, colors.black), # Before "Problem Description:"
                                                ('LINEBEFORE', (2, 6), (2, 6),0.7, colors.black), # Before "Recommended Corrective Action:"
                                                ('LINEBEFORE', (3, 4), (3, 4),0.7, colors.black), # After "Problem Description:"
                                                ('LINEBEFORE', (3, 5), (3, 5),0.7, colors.black), # After "Problem Description:"
                                                ('LINEBEFORE', (3, 6), (3, 6),0.7, colors.black), # After "Recommended Corrective Action:"
                                                ('LINEBEFORE', (3, 7), (3, 7),0.7, colors.black), # After "Problem Description:"
                                                ('LINEBEFORE', (3, 8), (3, 8),0.7, colors.black), # After "Problem Description:"
                                                ('LINEBEFORE', (2, 7), (2, 7),0.7, colors.black), # Before ""
                                                ('LINEBEFORE', (2, 8), (2, 8),0.7, colors.black), # Before ""
                                                
                                                ]
                                else:
                                    detail_style = [('BOX', (0, 0), (8,8), 0.7, colors.black),
                                                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                                ('SPAN', (2, 3), (2, 4)),  # combine 2 rows upside down for problem description
                                                ('SPAN', (3, 3), (3, 4)),  # combine 2 rows upside down for problem description Data
                                                ('ALIGN', (2, 3), (2, 4), 'CENTER'),  # Center-align Issue Description
                                                ('VALIGN', (2, 3), (2, 4), 'MIDDLE'),
                                                ('ALIGN', (3, 3), (3, 4), 'CENTER'),  # Center-align Issue Description
                                                ('VALIGN', (3, 3), (3, 4), 'MIDDLE'),
                                                ('SPAN', (2, 5), (2, 7)),  # combine 2 rows upside down for problem description
                                                ('SPAN', (3, 5), (3, 7)),  # combine 2 rows upside down for problem description
                                                ('ALIGN', (2, 5), (2, 7), 'CENTER'),  # Center-align Issue Description
                                                ('VALIGN', (2, 5), (2, 7), 'MIDDLE'),
                                                ('ALIGN', (3, 5), (3, 7), 'CENTER'),  # Center-align Issue Description
                                                ('VALIGN', (3, 5), (3, 7), 'MIDDLE'),
                                                ('LINEBELOW', (0, 2), (0, 2),0.7,colors.black), # draw line after serviceability
                                                ('LINEBELOW', (1, 2), (1, 2),0.7,colors.black), # draw line after serviceability
                                                ('LINEBELOW', (2, 2), (2, 2),0.7,colors.black), # draw line after Room
                                                ('LINEBELOW', (3, 2), (3, 2),0.7,colors.black), # draw line after Room
                                                ('LINEBELOW', (2, 4), (2, 4),0.7,colors.black), # draw line after Problem Description
                                                ('LINEBELOW', (3, 4), (3, 4),0.7,colors.black), # draw line after Problem Description
                                                ('LINEBELOW', (4, 4), (4, 4),0.7,colors.black), # draw line after Problem Description
                                                ('LINEBEFORE', (2, 0), (2, 0),0.7,colors.black),  # Before "Building" V line
                                                ('LINEBEFORE', (2, 1), (2, 1),0.7,colors.black),  # Before "Building" V line
                                                ('LINEBEFORE', (2, 2), (2, 2),0.7,colors.black),  # Before "Building" V line
                                                ('LINEBEFORE', (2, 3), (2, 3),0.7,colors.black),  # Before "Floor"
                                                ('LINEBEFORE', (2, 4), (2, 4),0.7,colors.black),  # Before "Room"
                                                ('LINEBEFORE', (2, 5), (2, 5),0.7, colors.black), # Before "Problem Description:"
                                                ('LINEBEFORE', (2, 6), (2, 6),0.7, colors.black), # Before "Recommended Corrective Action:"
                                                ('LINEBEFORE', (3, 3), (3, 3),0.7, colors.black), # After "Problem Description:"
                                                ('LINEBEFORE', (3, 4), (3, 4),0.7, colors.black), # After "Problem Description:"
                                                ('LINEBEFORE', (3, 5), (3, 5),0.7, colors.black), # After "Problem Description:"
                                                ('LINEBEFORE', (3, 6), (3, 6),0.7, colors.black), # After "Recommended Corrective Action:"
                                                ('LINEBEFORE', (3, 7), (3, 7),0.7, colors.black), # After "Problem Description:"
                                                ('LINEBEFORE', (2, 7), (2, 7),0.7, colors.black), # Before ""
                                                
                                                ]
                                t = Table(data4, colWidths=129 ,style=detail_style)
                                flow_obj.append(t)
                            else:
                                t = Table(data4, colWidths=129, style=detail_style)
                                flow_obj.append(t)
                        
                            thermal_details_dummy_flag = asset_data[25]
                            thermal_details_dummy = [
                                Paragraph("<b>Phase</b>",style['table_headers_abc']),
                                Paragraph("<b>Circuit</b>",style['table_headers_abc']),
                                Paragraph("<b>Current Rating (Amp)</b>",style['table_headers_abc']),
                                Paragraph("<b>Current Draw (Amp)</b>",style['table_headers_abc']),
                                Paragraph("<b>Voltage Drop (Millivolts)</b>",style['table_headers_abc'])]

                            thermal_details = [thermal_details_dummy]
                            fixed_phases = ['A', 'B', 'C', 'Neutral']

                            current_wo_id = asset_data[22]
                            current_thermal_assets = [
                                ta for ta in thermal_assets if ta[22] == current_wo_id]
                            print('len_of_thermal_details',len(thermal_details))
                            for phase in fixed_phases:
                                found = False
                                for ta in current_thermal_assets:
                                    dynamic_field_json = ta[21] if ta[21] else ''
                                    dynamic_data = {}
                                    if dynamic_field_json.strip():
                                        try:
                                            dynamic_data = json.loads(dynamic_field_json)
                                        except json.JSONDecodeError as e:
                                            print(f"JSONDecodeError: {e}")
                                    for data in dynamic_data:
                                        if isinstance(data, dict) and data.get('phase') == phase:
                                            if not any(data.get(field) for field in ['circuit', 'current_rating_amp', 'current_draw_amp', 'voltage_drop_millivolts']) and len(thermal_details)<1:
                                                # Skip this phase if all relevant fields are empty
                                                continue
                                            centered_style = ParagraphStyle(name='CenteredStyle', alignment=1)
                                            centered_style1 = ParagraphStyle(name='CenteredStyle1',fontName="Helvetica-Bold", alignment=1)
                                            
                                            display_phase = 'N' if phase == 'Neutral' else phase
                                            asset = [
                                                Paragraph(display_phase,centered_style1),
                                                Paragraph(str(data.get('circuit', 'N/A')),centered_style),
                                                Paragraph(str(data.get('current_rating_amp', 'N/A')),centered_style),
                                                Paragraph(str(data.get('current_draw_amp', 'N/A')),centered_style),
                                                Paragraph(str(data.get('voltage_drop_millivolts', 'N/A')),centered_style)
                                            ]
                                            thermal_details.append(asset)
                                            found = True
                                            break

                                if not found:
                                    continue

                            # Creating the table
                            if len(thermal_details) >1:
                                table2 = Table(thermal_details, hAlign='CENTER',colWidths=[83, 83, 114, 114, 120])
                                table2.setStyle(TableStyle([
                                    ('GRID', (0, 0), (-1, -1), 0.7, colors.black),
                                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                    ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                                    ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
                                    ('TEXTALIGN', (0, 0), (-1, 0), 'CENTER'),
                                ]))                           
                            if len(thermal_details) > 1 and thermal_details_dummy_flag == True:
                                flow_obj.append(Spacer(1, 16))
                                flow_obj.append(KeepTogether([table2]))
                            comments_thermal = Paragraph("<b>Comments: </b><font color='black'>{}</font>".format(comments),asset_comment_style)
                            flow_obj.append(Spacer(1, 13))
                            flow_obj.append(comments_thermal)
                            flow_obj.append(PageBreak())
                        
                # /////////////////////// Ultrasonic Issue ///////////////////////
                if len(ultrasonic_assets) > 0:
                    for ultrasonic_issue_data in ultrasonic_assets:
                        if ultrasonic_issue_data[16] == asset_data1[0]:
                            
                            if ultrasonic_issue_data[-2]:
                                issue_ultra_status = 'Resolved'
                                if issue_ultra_status == 'Resolved':
                                    color = '#2A9D55'
                                ultra_resolved = f'<font color="{color}">{issue_ultra_status}</font>'
                                    
                                page_name = "Ultrasonic Anomaly - {} - {}".format(ultrasonic_issue_data[1],ultra_resolved)
                                
                            else:
                                page_name = "Ultrasonic Anomaly - {}".format(ultrasonic_issue_data[1])
                            h1 = Paragraph(page_name, style['sub-index'])
                                
                            flow_obj.append(h1)
                            flow_obj.append(Spacer(500, 18))

                            ultrasonic_images_before = []
                            ultrasonic_images_after = []

                            is_issue_linked_for_fix = ultrasonic_issue_data[15]  # This should be set based on your actual data structure
                            PL1 = Paragraph('''<para align=left><b>Before Photo:</b></para>''', style['image-caption1'])
                            PL3 = Paragraph('''<para align=left><b>After Photo:</b></para>''', style['image-caption1'])
                            building = ultrasonic_issue_data[3] if ultrasonic_issue_data[3] else '-'
                            floor = ultrasonic_issue_data[4] if ultrasonic_issue_data[4] else '-'
                            room = ultrasonic_issue_data[5] if ultrasonic_issue_data[5] else '-'
                            issue_type_ultra = enum_woline_temp_issue_type[ultrasonic_issue_data[10]] if [
                                ultrasonic_issue_data[10]] else ''
                            comments_ultra = ultrasonic_issue_data[8] if ultrasonic_issue_data[8] else 'N/A'
                            size_of_anomaly = ultrasonic_issue_data[12] if ultrasonic_issue_data[12] else '-'
                            location_of_anomaly = ultrasonic_issue_data[11] if ultrasonic_issue_data[11] else '-'
                            type_of_anomaly = enum_temp_ultrasonic_issue_type[ultrasonic_issue_data[13]] if ultrasonic_issue_data[13] else '-'
                            panel_schedule = enum_temp_panel_schedule_type[ultrasonic_issue_data[14]] if ultrasonic_issue_data[14] else '-'
                            condition = enum_maintenance_condition_index_type[ultrasonic_issue_data[9]] if ultrasonic_issue_data[9] else '-'
                            if condition == 'Serviceable':
                                color = '#37d482'
                            elif condition == 'Limited':
                                color = '#ff950a'
                            else:
                                color = '#f64949' 
                            condition_paragraph = f'<font color="{color}">{condition}</font>'

                            if asset_data1[12] == 2:
                                asset_top_level_u = fetch_sublevel_asset_id1(asset_data1[0], asset_data1[-1])
                                print('asset_top_level_u', asset_top_level_u)
                                ultrasonicData = [
                                    [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(ultrasonic_issue_data[1]), table_style),
                                    Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                                    [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(ultrasonic_issue_data[2]), table_style),
                                    Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                                    [Paragraph("<b>Contained Within: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_top_level_u), table_style),
                                     Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                                    [Paragraph("<b>Type Of Anomaly: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(type_of_anomaly),table_style),
                                    Paragraph("<b>Size Of Anomaly: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(size_of_anomaly),table_style)],
                                    [Paragraph("<b>Location Of Anomaly: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(location_of_anomaly),table_style)],
                                    [Paragraph("<b>Issue Type: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_type_ultra),table_style)],
                                
                                    ]

                            else:
                                ultrasonicData = [
                                [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(ultrasonic_issue_data[1]), table_style),
                                Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                                [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(ultrasonic_issue_data[2]), table_style),
                                Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                                ['', '',Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                                [Paragraph("<b>Type Of Anomaly: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(type_of_anomaly),table_style),
                                Paragraph("<b>Size Of Anomaly: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(size_of_anomaly),table_style)],
                                [Paragraph("<b>Location Of Anomaly: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(location_of_anomaly),table_style)],
                                [Paragraph("<b>Issue Type: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_type_ultra),table_style)],
                            
                                ]

                            ultrasonic_style = [('BOX', (0, 0), (6, 6), 0.7, colors.black),   
                                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                                    ('TOPPADDING', (0, 0), (-1, 0), 5),
                                    ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                    ('LINEBELOW', (0, 0), (0, 0),0.7,colors.black), # draw line after image
                                    ('LINEBELOW', (1, 0), (1, 0),0.7,colors.black), # draw line after image
                                    ('LINEBELOW', (2, 0), (2, 0),0.7,colors.black), # draw line after image
                                    ('LINEBELOW', (3, 0), (3, 0),0.7,colors.black), # draw line after image
                                    ('LINEBELOW', (0, 3), (0, 3),0.7,colors.black), # draw line after image
                                    ('LINEBELOW', (1, 3), (1, 3),0.7,colors.black), # draw line after image
                                    ('LINEBELOW', (2, 3), (2, 3),0.7,colors.black), # draw line after image
                                    ('LINEBELOW', (3, 3), (3, 3),0.7,colors.black), # draw line after image
                                    ('LINEBEFORE', (2, 1), (2, 1),0.7,colors.black),  # Before "Building" V line
                                    ('LINEBEFORE', (2, 2), (2, 2),0.7,colors.black),  # Before "Floor"
                                    ('LINEBEFORE', (2, 3), (2, 3),0.7,colors.black),  # Before "Room"
                                    ('LINEBEFORE', (2, 4), (2, 4),0.7,colors.black),  # Before "Size Of Anomaly"
                                    ('LINEBEFORE', (2, 5), (2, 5),0.7,colors.black),  # Before "Size Of Anomaly"
                                    ('LINEBEFORE', (3, 4), (3, 4),0.7, colors.black), # After "Problem Description:"
                                    ('LINEBEFORE', (3, 5), (3, 5),0.7, colors.black), # After "Problem Description:"
                                    ('LINEBEFORE', (3, 6), (3, 6),0.7, colors.black), # After "Problem Description:"
                                    ('LINEBEFORE', (2, 6), (2, 6),0.7, colors.black), # After "Problem Description:"
                                    ('SPAN', (2, 4), (2, 6)),  # Room
                                    ('ALIGN', (2, 4), (2, 6), 'CENTER'),  # Center-align Issue Description
                                    ('VALIGN', (2, 4), (2, 6), 'MIDDLE'),
                                    ('SPAN', (3, 4), (3, 6)),  # Room
                                    ('ALIGN', (3, 4), (3, 6), 'CENTER'),  # Center-align Issue Description
                                    ('VALIGN', (3, 4), (3, 6), 'MIDDLE'),
                                    
                                    ]
                            if ultrasonic_issue_data[0] in ultrasonic_image_data.keys():

                                for image_data in ultrasonic_image_data.get(ultrasonic_issue_data[0]):

                                    if image_data[0] is not None and image_data[1] is not None:

                                        ultrasonic_image = fetch_image(None, image_data[1], ISSUE_BUCKET_NAME)

                                        if ultrasonic_image:

                                            ultra = create_asset_image(ultrasonic_image,scale_factor=0.75)
                                            PL2 = Paragraph(''' <para align=left><b>{}</b></para>'''.format(image_data[1].split(".")[0]), style['image-caption'])

                                            if image_data[3] == 1:
                                                ultrasonic_images_before.append([ultra, Spacer(0, 3)])
                                            elif image_data[3] == 2:
                                                ultrasonic_images_after.append([ultra, Spacer(0, 3)])
                                        else:
                                            print("couldnot fetch image")
                                            PNI = Paragraph(''' <para align=left><b>{} </b></para>'''.format(image_data[1].split(".")[0]), style['image-caption'])
                                            if image_data[3] == 1:
                                                ultrasonic_images_before.append([PNI])
                                            elif image_data[3] == 2:
                                                ultrasonic_images_after.append([PNI])
                            startrow = 0
                            if len(ultrasonic_images_before) > 0:
                            

                                for i in range(0, len(ultrasonic_images_before), 2):
                                    if i + 1 < len(ultrasonic_images_before):
                                        ultrasonicData.insert(startrow, [ultrasonic_images_before[i], '', ultrasonic_images_before[i + 1], ''])
                                        ultrasonic_style.append(('SPAN', (0, startrow), (1, startrow)))
                                        ultrasonic_style.append(('ALIGN', (0, startrow), (1, startrow), 'LEFT'))
                                        ultrasonic_style.append(('VALIGN', (0, startrow), (1, startrow), 'MIDDLE'))
                                        ultrasonic_style.append(('SPAN', (2, startrow), (3, startrow)))
                                        ultrasonic_style.append(('ALIGN', (2, startrow), (3, startrow), 'LEFT'))
                                        ultrasonic_style.append(('VALIGN', (2, startrow), (3, startrow), 'MIDDLE'))
                                    else:
                                        ultrasonicData.insert(startrow, [ultrasonic_images_before[i], '', '', ''])
                                        ultrasonic_style.append(('SPAN', (0, startrow), (-1, startrow)))

                                    startrow += 1
                            

                            if len(ultrasonic_images_before) == 0:
                                ultrasonic_style = [('BOX', (0, 0), (6, 6), 0.7, colors.black),   
                                        ('LINEBELOW', (0, 2), (0, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 2), (1, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 2), (2, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 2), (3, 2),0.7,colors.black), # draw line after image
                                        ('LINEBEFORE', (2, 0), (2, 0),0.7,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 1), (2, 1),0.7,colors.black),  # Before "Floor" V line
                                        ('LINEBEFORE', (2, 2), (2, 2),0.7,colors.black),  # Before "Room"
                                        ('LINEBEFORE', (2, 3), (2, 3),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (2, 4), (2, 4),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (2, 5), (2, 5),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (3, 3), (3, 3),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (3, 4), (3, 4),0.7, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 5), (3, 5),0.7, colors.black), # After "Problem Description:"
                                        ('SPAN', (2, 3), (2, 5)),  # Room
                                        ('ALIGN', (2, 3), (2, 5), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (2, 3), (2, 5), 'MIDDLE'),
                                        ('SPAN', (3, 3), (3, 5)),  # Room
                                        ('ALIGN', (3, 3), (3, 5), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (3, 3), (3, 5), 'MIDDLE'),
                                        ]
                                t = Table(ultrasonicData, colWidths=129 ,style=ultrasonic_style)
                                flow_obj.append(t)
                            
                            else:
                                t = Table(ultrasonicData, colWidths=129,
                                    style=ultrasonic_style)
                                flow_obj.append(t)
                                
                            commments = Paragraph("<b>Comments: </b><font color='black'>{}</font>".format(comments_ultra), asset_comment_style)
                            flow_obj.append(Spacer(1, 13))
                            flow_obj.append(commments)

                            flow_obj.append(PageBreak())

                # # /////////////////////// NEC Violation ///////////////////////
                if len(nec_assets) > 0:
                    for asset_datas in nec_assets:
                        if asset_datas[15] == asset_data1[0]:
                            
                            if asset_datas[-2]:
                                issue_nec_status = 'Resolved'
                                if issue_nec_status == 'Resolved':
                                    color = '#2A9D55'
                                nec_resolved = f'<font color="{color}">{issue_nec_status}</font>'
                                    
                                page_name = "NEC Violation - {} - {}".format(asset_datas[1],nec_resolved)
                            
                            else:
                                page_name = "NEC Violation - {}".format(asset_datas[1])
                            h1 = Paragraph(page_name, style['sub-index'])
                            flow_obj.append(h1)
                            flow_obj.append(Spacer(500, 18))

                            nec_images_before = []
                            nec_images_after = []
                            is_issue_linked_for_fix = asset_datas[14]  # This should be set based on your actual data structure
                            PL1 = Paragraph('''<para align=left><b>Before Photo:</b></para>''', style['image-caption1'])
                            PL3 = Paragraph('''<para align=left><b>After Photo:</b></para>''', style['image-caption1'])
                            building = asset_datas[3] if asset_datas[3] else '-'
                            floor = asset_datas[4] if asset_datas[4] else '-'
                            room = asset_datas[5] if asset_datas[5] else '-'
                            issue_type_nec = enum_woline_temp_issue_type[asset_datas[10]] if [
                                asset_datas[10]] else '-'
                            comments_nec = asset_datas[8] if asset_datas[8] else 'N/A'
                            title = enum_nec_violation[asset_datas[11]] if asset_datas[11] else '-'
                            
                            panel_schedule = enum_temp_panel_schedule_type[asset_datas[13]
                                                                        ] if asset_datas[13] else '-'
                            description = '-'
                            condition = enum_maintenance_condition_index_type[asset_datas[9]] if asset_datas[9] else '-'
                            if condition == 'Serviceable':
                                color = '#37d482'
                            elif condition == 'Limited':
                                color = '#ff950a'
                            else:
                                color = '#f64949' 
                            condition_paragraph = f'<font color="{color}">{condition}</font>'
                            if asset_data1[12] == 2:
                                asset_top_level_n = fetch_sublevel_asset_id1(asset_data1[0], asset_data1[-1])
                                print('asset_top_level_u', asset_top_level_n)
                                necData = [
                                    [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_datas[1]), table_style),
                                    Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                                    [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_datas[2]), table_style),
                                    Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                                    [Paragraph("<b>Contained Within: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_top_level_n), table_style),
                                    Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                                    [Paragraph("<b>Issue Title: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(title),table_style),
                                    Paragraph("<b>Issue Description: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(description),table_style)],
                                    [Paragraph("<b>Issue Type: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_type_nec),table_style)],
                                    ]
                            else:
                                necData = [
                                    [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_datas[1]), table_style),
                                    Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                                    [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_datas[2]), table_style),
                                    Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                                    ['','',Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                                    [Paragraph("<b>Issue Title: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(title),table_style),
                                    Paragraph("<b>Issue Description: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(description),table_style)],
                                    [Paragraph("<b>Issue Type: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_type_nec),table_style)],
                                    ]

                            nec_style = [('BOX', (0, 0), (5, 5), 0.7, colors.black),  
                                        # ('GRID',(0,0),(-1,-1),2,colors.black),
                                        ('LEFTPADDING', (0, 0), (-1, -1), 6),
                                        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                                        ('TOPPADDING', (0, 0), (-1, 0), 5),
                                        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                        ('LINEBELOW', (0, 0), (0, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 0), (1, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 0), (2, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 0), (3, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (0, 3), (0, 3),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 3), (1, 3),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 3), (2, 3),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 3), (3, 3),0.7,colors.black), # draw line after image
                                        ('LINEBEFORE', (2, 1), (2, 1),0.7,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 2), (2, 2),0.7,colors.black),  # Before "Floor"
                                        ('LINEBEFORE', (2, 3), (2, 3),0.7,colors.black),  # Before "Room"
                                        ('LINEBEFORE', (2, 4), (2, 4),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (2, 5), (2, 5),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (3, 4), (3, 4),0.7, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 5), (3, 5),0.7, colors.black), # After "Problem Description:"
                                        ('SPAN', (2, 4), (2, 5)),  # Room
                                        ('ALIGN', (2, 4), (2, 5), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (2, 4), (2, 5), 'MIDDLE'),
                                         ('SPAN', (3, 4), (3, 5)),  # Room
                                        ('ALIGN', (3, 4), (3, 5), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (3, 4), (3, 5), 'MIDDLE'),
                                        ]
                            if asset_datas[0] in nec_image_data.keys():

                                for image_data in nec_image_data.get(asset_datas[0]):

                                    if image_data[0] is not None and image_data[1] is not None:

                                        nec_image = fetch_image(None, image_data[1], ISSUE_BUCKET_NAME)
                                        print('image_data_nec/osha', image_data[1])

                                        if nec_image:
                                            nec = create_asset_image(nec_image,scale_factor=0.75)
                                            PL2 = Paragraph(''' <para align=left><b>{}</b></para>'''.format(
                                                image_data[1].split(".")[0]), style['image-caption'])

                                            if image_data[3] == 1:
                                                nec_images_before.append([nec, Spacer(0, 3)])
                                            elif image_data[3] == 2:
                                                nec_images_after.append([nec, Spacer(0, 3)])
                                        else:
                                            print("couldnot fetch image")
                                            PNI = Paragraph(''' <para align=left><b>{} </b></para>'''.format(
                                                image_data[1].split(".")[0]), style['image-caption'])
                                            if image_data[3] == 1:
                                                nec_images_before.append([PNI])
                                            elif image_data[3] == 2:
                                                nec_images_after.append([PNI])

                            startrow = 0
                            if len(nec_images_before) > 0:

                                for i in range(0, len(nec_images_before), 2):
                                    if i + 1 < len(nec_images_before):
                                        necData.insert(startrow, [nec_images_before[i], '', nec_images_before[i + 1], ''])
                                        nec_style.append(('SPAN', (0, startrow), (1, startrow)))
                                        nec_style.append(('ALIGN', (0, startrow), (1, startrow), 'CENTER'))
                                        nec_style.append(('VALIGN', (0, startrow), (1, startrow), 'MIDDLE'))
                                        nec_style.append(('SPAN', (2, startrow), (3, startrow)))
                                        nec_style.append(('ALIGN', (2, startrow), (3, startrow), 'LEFT'))
                                        nec_style.append(('VALIGN', (2, startrow), (3, startrow), 'MIDDLE'))
                                    else:
                                        necData.insert(startrow, [nec_images_before[i], '', '', ''])
                                        nec_style.append(('SPAN', (0, startrow), (-1, startrow)))
                                        nec_style.append(('ALIGN', (0, startrow), (-1, startrow), 'CENTER'))
                                        nec_style.append(('VALIGN', (0, startrow), (-1, startrow), 'MIDDLE'))

                                    startrow += 1
                                

                            if len(nec_images_before) == 0:
                                nec_style = [('BOX', (0, 0), (5, 5), 0.7, colors.black),  
                                        # ('GRID',(0,0),(-1,-1),2,colors.black),
                                        ('LEFTPADDING', (0, 0), (-1, -1), 6),
                                        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                                        ('TOPPADDING', (0, 0), (-1, 0), 5),
                                        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                        ('LINEBELOW', (0, 2), (0, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 2), (1, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 2), (2, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 2), (3, 2),0.7,colors.black), # draw line after image
                                        ('LINEBEFORE', (2, 0), (2, 0),0.7,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 1), (2, 1),0.7,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 2), (2, 2),0.7,colors.black),  # Before "Floor"
                                        ('LINEBEFORE', (2, 3), (2, 3),0.7,colors.black),  # Before "Room"
                                        ('LINEBEFORE', (2, 4), (2, 4),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (2, 5), (2, 5),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (3, 3), (3, 3),0.7, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 4), (3, 4),0.7, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 5), (3, 5),0.7, colors.black), # After "Problem Description:"
                                        ('SPAN', (2, 3), (2, 4)),  # Room
                                        ('ALIGN', (2, 3), (2, 4), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (2, 3), (2, 4), 'MIDDLE'),
                                         ('SPAN', (3, 3), (3, 4)),  # Room
                                        ('ALIGN', (3, 3), (3, 4), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (3, 3), (3, 4), 'MIDDLE'),
                                        ]
                                t = Table(necData, colWidths=129, style=nec_style)
                                flow_obj.append(t)

                            else:
                                t = Table(necData, colWidths=129,
                                    style=nec_style)

                                flow_obj.append(t)

                            comment_nec = Paragraph("<b>Comments: </b><font color='black'>{}</font>".format(comments_nec),asset_comment_style)
                            flow_obj.append(Spacer(1, 13))
                            flow_obj.append(comment_nec)
                            flow_obj.append(PageBreak())

                # # /////////////////////// OSHA Violation ///////////////////////
                if len(osha_assets) > 0:
                    for asset_datas in osha_assets:
                        if asset_datas[15] == asset_data1[0]:
                            
                            if asset_datas[-2]:
                                issue_osha_status = 'Resolved'
                                if issue_osha_status == 'Resolved':
                                    color = '#2A9D55'
                                osha_resolved = f'<font color="{color}">{issue_osha_status}</font>'
                                page_name = "OSHA Violation - {} - {}".format(asset_datas[1],osha_resolved)
                            
                            else:
                                page_name = "OSHA Violation - {}".format(asset_datas[1])
                            
                            h1 = Paragraph(page_name, style['sub-index'])
                            flow_obj.append(h1)
                            flow_obj.append(Spacer(500, 18))

                            osha_images_before = []
                            osha_images_after = []
                            is_issue_linked_for_fix = asset_datas[14]  # This should be set based on your actual data structure
                            PL1 = Paragraph('''<para align=left><b>Before Photo:</b></para>''', style['image-caption1'])
                            PL3 = Paragraph('''<para align=left><b>After Photo:</b></para>''', style['image-caption1'])

                            building = asset_datas[3] if asset_datas[3] else '-'
                            floor = asset_datas[4] if asset_datas[4] else '-'
                            room = asset_datas[5] if asset_datas[5] else '-'
                            issue_type_osha = enum_woline_temp_issue_type[asset_datas[10]] if [
                                asset_datas[10]] else '-'
                            comments_osha = asset_datas[8] if asset_datas[8] else 'N/A'
                        
                            title = enum_osha_violation[asset_datas[12]] if asset_datas[12] else '-'
                            description_osha ='-'
                            panel_schedule = enum_temp_panel_schedule_type[asset_datas[13]
                                                                        ] if asset_datas[13] else '-'
                            condition = enum_maintenance_condition_index_type[asset_datas[9]] if asset_datas[9] else '-'
                            if condition == 'Serviceable':
                                color = '#37d482'
                            elif condition == 'Limited':
                                color = '#ff950a'
                            else:
                                color = '#f64949' 
                            condition_paragraph = f'<font color="{color}">{condition}</font>'
                            if asset_data1[12] == 2:
                                asset_top_level_o = fetch_sublevel_asset_id1(asset_data1[0], asset_data1[-1])
                                print('asset_top_level_o', asset_top_level_o)
                                oshaData = [
                                [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_datas[1]), table_style),
                                Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                                [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_datas[2]), table_style),
                                Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                                [Paragraph("<b>Contained Within: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_top_level_o), table_style),
                                Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                                [Paragraph("<b>Issue Title: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(title),table_style),
                                Paragraph("<b>Issue Description: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(description_osha),table_style)],
                                [Paragraph("<b>Issue Type: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_type_osha),table_style)],
                                ]
                            else:
                                oshaData = [
                                    [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_datas[1]), table_style),
                                    Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                                    [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_datas[2]), table_style),
                                    Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                                    ['', '',Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                                    [Paragraph("<b>Issue Title: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(title),table_style),
                                    Paragraph("<b>Issue Description: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(description_osha),table_style)],
                                    [Paragraph("<b>Issue Type: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_type_osha),table_style)],
                                    ]
                            osha_style = [('BOX', (0, 0), (5, 5), 0.7, colors.black),  
                                        # ('GRID',(0,0),(-1,-1),2,colors.black),
                                        ('LEFTPADDING', (0, 0), (-1, -1), 6),
                                        ('TOPPADDING', (0, 0), (-1, 0), 5),
                                        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                        ('LINEBELOW', (0, 0), (0, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 0), (1, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 0), (2, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 0), (3, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (0, 3), (0, 3),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 3), (1, 3),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 3), (2, 3),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 3), (3, 3),0.7,colors.black), # draw line after image
                                        ('LINEBEFORE', (2, 1), (2, 1),0.7,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 2), (2, 2),0.7,colors.black),  # Before "Floor"
                                        ('LINEBEFORE', (2, 3), (2, 3),0.7,colors.black),  # Before "Room"
                                        ('LINEBEFORE', (2, 4), (2, 4),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (2, 5), (2, 5),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (3, 4), (3, 4),0.7, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 5), (3, 5),0.7, colors.black), # After "Problem Description:"
                                        ('SPAN', (2, 4), (2, 5)),  # Room
                                        ('ALIGN', (2, 4), (2, 5), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (2, 4), (2, 5), 'MIDDLE'),
                                         ('SPAN', (3, 4), (3, 5)),  # Room
                                        ('ALIGN', (3, 4), (3, 5), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (3, 4), (3, 5), 'MIDDLE'),
                                        ]
                            if asset_datas[0] in osha_image_data.keys():

                                for image_data in osha_image_data.get(asset_datas[0]):

                                    if image_data[0] is not None and image_data[1] is not None:

                                        nec_image = fetch_image(None, image_data[1], ISSUE_BUCKET_NAME)
                                        print('image_data_nec/osha', image_data[1])

                                        if nec_image:

                                            # image_name = '/tmp/' + image_data[1]
                                            nec = create_asset_image(nec_image,scale_factor=0.75)
                                            PL2 = Paragraph(''' <para align=left><b>{}</b></para>'''.format(
                                                image_data[1].split(".")[0]), style['image-caption'])

                                            if image_data[3] == 1:
                                                osha_images_before.append([nec, Spacer(0, 3)])
                                            elif image_data[3] == 2:
                                                osha_images_after.append([nec, Spacer(0, 3)])
                                        else:
                                            print("couldnot fetch image")
                                            PNI = Paragraph(''' <para align=left><b>{} </b></para>'''.format(
                                                image_data[1].split(".")[0]), style['image-caption'])
                                            if image_data[3] == 1:
                                                osha_images_before.append([PNI])
                                            elif image_data[3] == 2:
                                                osha_images_after.append([PNI])

                            startrow = 0
                            if len(osha_images_before) > 0:

                                for i in range(0, len(osha_images_before), 2):
                                    if i + 1 < len(osha_images_before):
                                        oshaData.insert(startrow, [osha_images_before[i], '', osha_images_before[i + 1], ''])
                                        osha_style.append(('SPAN', (0, startrow), (1, startrow)))
                                        osha_style.append(('ALIGN', (0, startrow), (1, startrow), 'LEFT'))
                                        osha_style.append(('VALIGN', (0, startrow), (1, startrow), 'MIDDLE'))
                                        osha_style.append(('SPAN', (2, startrow), (3, startrow)))
                                        osha_style.append(('ALIGN', (2, startrow), (3, startrow), 'LEFT'))
                                        osha_style.append(('VALIGN', (2, startrow), (3, startrow), 'MIDDLE'))
                                    else:
                                        oshaData.insert(startrow, [osha_images_before[i], '', '', ''])
                                        osha_style.append(('SPAN', (0, startrow), (-1, startrow)))

                                    startrow += 1

                            if len(osha_images_before) == 0:
                                osha_style = [('BOX', (0, 0), (5, 5), 0.7, colors.black),  
                                        # ('GRID',(0,0),(-1,-1),2,colors.black),
                                        ('LEFTPADDING', (0, 0), (-1, -1), 6),
                                        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                        ('LINEBELOW', (0, 2), (0, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 2), (1, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 2), (2, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 2), (3, 2),0.7,colors.black), # draw line after image
                                        ('LINEBEFORE', (2, 0), (2, 0),0.7,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 1), (2, 1),0.7,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 2), (2, 2),0.7,colors.black),  # Before "Floor"
                                        ('LINEBEFORE', (2, 3), (2, 3),0.7,colors.black),  # Before "Room"
                                        ('LINEBEFORE', (2, 4), (2, 4),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (2, 5), (2, 5),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (3, 3), (3, 3),0.7, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 4), (3, 4),0.7, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 5), (3, 5),0.7, colors.black), # After "Problem Description:"
                                        ('SPAN', (2, 3), (2, 4)),  # Room
                                        ('ALIGN', (2, 3), (2, 4), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (2, 3), (2, 4), 'MIDDLE'),
                                         ('SPAN', (3, 3), (3, 4)),  # Room
                                        ('ALIGN', (3, 3), (3, 4), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (3, 3), (3, 4), 'MIDDLE'),
                                        ]
                                t = Table(oshaData, colWidths=129, style=osha_style)
                                flow_obj.append(t)

                            else:
                                t = Table(oshaData, colWidths=129,
                                    style=osha_style)

                                flow_obj.append(t)

                            comment_osha = Paragraph("<b>Comments: </b><font color='black'>{}</font>".format(comments_osha),asset_comment_style)
                            flow_obj.append(Spacer(1, 13))
                            flow_obj.append(comment_osha)
                            flow_obj.append(PageBreak())

                # # /////////////////////// NFPA Issue ///////////////////////
                if len(nfpa_assets) > 0:
                    for nfpa_asset_datas in nfpa_assets:
                        if nfpa_asset_datas[14] == asset_data1[0]:
                            
                            if nfpa_asset_datas[13]:
                                issue_nfpa_status = 'Resolved'
                                if issue_nfpa_status == 'Resolved':
                                    color = '#2A9D55'
                                nfpa_resolved = f'<font color="{color}">{issue_nfpa_status}</font>'
                                page_name = "NFPA 70B Violation - {} - {}".format(nfpa_asset_datas[1],nfpa_resolved)
                            else:
                                page_name = "NFPA 70B Violation - {}".format(nfpa_asset_datas[1])
                                
                            h1 = Paragraph(page_name, style['sub-index'])
                            flow_obj.append(h1)
                            flow_obj.append(Spacer(500, 18))

                            nfpa_images_before = []
                            nfpa_images_after = []
                            is_issue_linked_for_fix = nfpa_asset_datas[13]  # This should be set based on your actual data structure
                            PL1 = Paragraph('''<para align=center><b>Before Photo</b></para>''', style['image-caption2'])
                            PL3 = Paragraph('''<para align=center><b>After Photo</b></para>''', style['image-caption2'])
                            building = nfpa_asset_datas[3] if nfpa_asset_datas[3] else '-'
                            floor = nfpa_asset_datas[4] if nfpa_asset_datas[4] else '-'
                            room = nfpa_asset_datas[5] if nfpa_asset_datas[5] else '-'
                            issue_type_nfpa = enum_woline_temp_issue_type[nfpa_asset_datas[10]] if [
                                nfpa_asset_datas[10]] else '-'
                            comments_nfpa = nfpa_asset_datas[8] if nfpa_asset_datas[8] else 'N/A'
                            description_nfpa='-'
                            nfpa_issue_title = enum_nfpa_violation_type[nfpa_asset_datas[11]
                                                                        ] if nfpa_asset_datas[11] else '-'
                            panel_schedule = enum_temp_panel_schedule_type[nfpa_asset_datas[13]
                                                                        ] if nfpa_asset_datas[13] else '-'
                            condition = enum_maintenance_condition_index_type[nfpa_asset_datas[9]] if nfpa_asset_datas[9] else '-'
                            if condition == 'Serviceable':
                                color = '#37d482'
                            elif condition == 'Limited':
                                color = '#ff950a'
                            else:
                                color = '#f64949' 
                            condition_paragraph = f'<font color="{color}">{condition}</font>'

                            if asset_data1[12] == 2:
                                asset_top_level_nfpa = fetch_sublevel_asset_id1(asset_data1[0], asset_data1[-1])
                                print('asset_top_level_nfpa', asset_top_level_nfpa)
                                nfpaData = [
                                    [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(nfpa_asset_datas[1]), table_style),
                                    Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                                    [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(nfpa_asset_datas[2]), table_style),
                                    Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                                    [Paragraph("<b>Contained Within: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_top_level_nfpa), table_style),
                                    Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                                    [Paragraph("<b>Issue Title: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(nfpa_issue_title),table_style),
                                    Paragraph("<b>Issue Description: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(description_nfpa),table_style)],
                                    [Paragraph("<b>Issue Type: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_type_nfpa),table_style)],
                                    ]
                            else:
                                nfpaData = [
                                    [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(nfpa_asset_datas[1]), table_style),
                                    Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                                    [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(nfpa_asset_datas[2]), table_style),
                                    Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                                    ['', '',Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                                    [Paragraph("<b>Issue Title: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(nfpa_issue_title),table_style),
                                    Paragraph("<b>Issue Description: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(description_nfpa),table_style)],
                                    [Paragraph("<b>Issue Type: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_type_nfpa),table_style)],
                                    ]
                            nfpa_style = [('BOX', (0, 0), (6, 6), 0.7, colors.black),  
                                        # ('GRID',(0,0),(-1,-1),2,colors.black),
                                        ('SPAN', (0, 0), (1, 0)),  # Center align PL1
                                        ('SPAN', (2, 0), (3, 0)),  # Center align PL3
                                        ('TOPPADDING', (0, 0), (-1, 0), 5),
                                        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                                        ('ALIGN', (0, 0), (1, 0), 'CENTER'),
                                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                        ('LINEBELOW', (0, 0), (0, 0),0.7,colors.black),
                                        ('LINEBELOW', (1, 0), (1, 0),0.7,colors.black), # draw line Before image
                                        ('LINEBELOW', (2, 0), (2, 0),0.7,colors.black), # draw line Before image
                                        ('LINEBELOW', (3, 0), (3, 0),0.7,colors.black), # draw line Before image
                                        ('LINEBELOW', (0, 1), (0, 1),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 1), (1, 1),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 1), (2, 1),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 1), (3, 1),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (0, 4), (0, 4),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 4), (1, 4),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 4), (2, 4),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 4), (3, 4),0.7,colors.black), # draw line after image
                                        ('LINEBEFORE', (2, 1), (2, 1),0.7,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 2), (2, 2),0.7,colors.black),  # Before "Floor"
                                        ('LINEBEFORE', (2, 3), (2, 3),0.7,colors.black),  # Before "Room"
                                        ('LINEBEFORE', (2, 4), (2, 4),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (2, 5), (2, 5),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (2, 6), (2, 6),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (3, 5), (3, 5),0.7, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 6), (3, 6),0.7, colors.black), # After "Problem Description:"
                                        ('SPAN', (2, 5), (2, 6)),  # Room
                                        ('ALIGN', (2, 5), (2, 6), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (2, 5), (2, 6), 'MIDDLE'),
                                         ('SPAN', (3, 5), (3, 6)),  # Room
                                        ('ALIGN', (3, 5), (3, 6), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (3, 5), (3, 6), 'MIDDLE'),

                                        ]
                            if nfpa_asset_datas[0] in nfpa_image_data.keys():

                                for image_data in nfpa_image_data.get(nfpa_asset_datas[0],[]):
                                    if image_data is None:
                                        continue
                                    if image_data[0] is not None and image_data[1] is not None:

                                        nfpa_image = fetch_image(None, image_data[1], ISSUE_BUCKET_NAME)
                                        print('image_data_nfpa', image_data[1])

                                        if nfpa_image:

                                            # image_name = '/tmp/' + image_data[1]
                                            nfpa = create_asset_image(nfpa_image,scale_factor=0.75)
                                            PL2 = Paragraph(''' <para align=left><b>{}</b></para>'''.format(
                                                image_data[1].split(".")[0]), style['image-caption'])

                                            if image_data[3] == 1:
                                                if len(nfpa_images_before) <= 1: 
                                                    nfpa_images_before.append([nfpa, Spacer(0, 3)])
                                            elif image_data[3] == 2:
                                                if len(nfpa_images_after) <= 1: 
                                                    nfpa_images_after.append([nfpa, Spacer(0, 3)])
                                        else:
                                            print("couldnot fetch image")
                                            PNI = Paragraph(''' <para align=left><b>{} </b></para>'''.format(
                                                image_data[1].split(".")[0]), style['image-caption'])
                                            if image_data[3] == 1:
                                                nfpa_images_before.append([PNI])
                                            elif image_data[3] == 2:
                                                nfpa_images_after.append([PNI])
                                   
                            startrow = 0
                            if len(nfpa_images_before) > 0 and len(nfpa_images_after) > 0:
                                nfpaData.insert(startrow, [PL1, '', PL3, ''])
                                nfpa_style.append(('TEXTALIGN', (0, startrow), (1, startrow), 'CENTER'))
                                nfpa_style.append(('ALIGN', (0, startrow), (1, startrow), 'CENTER'))
                                nfpa_style.append(('VALIGN', (0, startrow), (1, startrow), 'MIDDLE'))
                                nfpa_style.append(('LINEBEFORE', (2, 0), (2, 0),0.7,colors.black))

                                nfpa_style.append(('TEXTALIGN', (2, startrow), (3, startrow), 'CENTER'))
                                nfpa_style.append(('ALIGN', (2, startrow), (3, startrow), 'CENTER'))
                                nfpa_style.append(('VALIGN', (2, startrow), (3, startrow), 'MIDDLE'))
                                nfpa_style.append(('BACKGROUND', (0, startrow), (3, startrow), colors.whitesmoke))
                                
                                startrow += 1
                                if len(nfpa_images_before) > 0 and len(nfpa_images_after) > 0:
                                    # Insert both images side by side
                                    nfpaData.insert(startrow, [nfpa_images_before, '', nfpa_images_after, ''])
                                    nfpa_style.append(('SPAN', (0, startrow), (1, startrow)))
                                    nfpa_style.append(('ALIGN', (0, startrow), (1, startrow), 'CENTER'))
                                    nfpa_style.append(('VALIGN', (0, startrow), (1, startrow), 'MIDDLE'))
                                    nfpa_style.append(('SPAN', (2, startrow), (3, startrow)))
                                    nfpa_style.append(('ALIGN', (2, startrow), (3, startrow), 'CENTER'))
                                    nfpa_style.append(('VALIGN', (2, startrow), (3, startrow), 'MIDDLE'))
                                
                                startrow += 1

                            elif len(nfpa_images_before) > 0 and len(nfpa_images_after) == 0:
                                nfpaData.insert(startrow, [PL1])
                                nfpa_style.append(('TEXTALIGN', (0, startrow), (3, startrow), 'CENTER'))
                                nfpa_style.append(('ALIGN', (0, startrow), (3, startrow), 'CENTER'))
                                nfpa_style.append(('VALIGN', (0, startrow), (3, startrow), 'MIDDLE'))
                                nfpa_style.append(('SPAN', (0, 0), (3, 0)))

                                nfpa_style.append(('BACKGROUND', (0, startrow), (3, startrow), colors.whitesmoke))
                                
                                startrow += 1

                                if nfpa_images_before:
                                    # Insert only before image
                                    nfpaData.insert(startrow, [nfpa_images_before, '', '', ''])
                                    nfpa_style.append(('SPAN', (0, startrow), (-1, startrow)))
                                    nfpa_style.append(('ALIGN', (0, startrow), (-1, startrow), 'CENTER'))
                                    nfpa_style.append(('VALIGN', (0, startrow), (-1, startrow), 'MIDDLE'))
                                startrow += 1
                                    
                            elif len(nfpa_images_after) > 0 and len(nfpa_images_before) == 0:
                                nfpaData.insert(startrow, [PL3])
                                nfpa_style.append(('TEXTALIGN', (0, startrow), (3, startrow), 'CENTER'))
                                nfpa_style.append(('ALIGN', (0, startrow), (3, startrow), 'CENTER'))
                                nfpa_style.append(('VALIGN', (0, startrow), (3, startrow), 'MIDDLE'))
                                nfpa_style.append(('SPAN', (0, 0), (3, 0)))

                                nfpa_style.append(('BACKGROUND', (0, startrow), (3, startrow), colors.whitesmoke))
                                
                                startrow += 1

                                if nfpa_images_after:
                                    # Insert only after image
                                    nfpaData.insert(startrow, [nfpa_images_after, '', '', ''])
                                    nfpa_style.append(('SPAN', (0, startrow), (-1, startrow)))
                                    nfpa_style.append(('ALIGN', (0, startrow), (-1, startrow), 'CENTER'))
                                    nfpa_style.append(('VALIGN', (0, startrow), (-1, startrow), 'MIDDLE'))

                                startrow += 1

                            if len(nfpa_images_before) == 0 and len(nfpa_images_after) == 0:
                                nfpa_style = [('BOX', (0, 0), (5, 5), 0.7, colors.black),  
                                        # ('GRID',(0,0),(-1,-1),2,colors.black),
                                        ('LEFTPADDING', (0, 0), (-1, -1), 6),
                                        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                        ('LINEBELOW', (0, 2), (0, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 2), (1, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 2), (2, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 2), (3, 2),0.7,colors.black), # draw line after image
                                        ('LINEBEFORE', (2, 0), (2, 0),0.7,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 1), (2, 1),0.7,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 2), (2, 2),0.7,colors.black),  # Before "Floor"
                                        ('LINEBEFORE', (2, 3), (2, 3),0.7,colors.black),  # Before "Room"
                                        ('LINEBEFORE', (2, 4), (2, 4),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (2, 5), (2, 5),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (3, 3), (3, 3),0.7, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 4), (3, 4),0.7, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 5), (3, 5),0.7, colors.black), # After "Problem Description:"
                                        ('SPAN', (2, 3), (2, 4)),  # Room
                                        ('ALIGN', (2, 3), (2, 4), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (2, 3), (2, 4), 'MIDDLE'),
                                        ('SPAN', (3, 3), (3, 4)),  # Room
                                        ('ALIGN', (3, 3), (3, 4), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (3, 3), (3, 4), 'MIDDLE'),
                                        ]
                                t = Table(nfpaData, colWidths=129, style=nfpa_style)
                                flow_obj.append(t)

                            else:
                                t = Table(nfpaData, colWidths=129,
                                    style=nfpa_style)

                                flow_obj.append(t)

                            comment_nfpa = Paragraph("<b>Comments: </b><font color='black'>{}</font>".format(comments_nfpa),asset_comment_style)
                            flow_obj.append(Spacer(1, 13))
                            flow_obj.append(comment_nfpa)
                            flow_obj.append(PageBreak())

                # /////////////////////// Replace Issue ///////////////////////
                if len(replace_assets) > 0:
                    for replace_issue_data in replace_assets:
                        if replace_issue_data[15] == asset_data1[0]:
                            
                            if replace_issue_data[13]:
                                issue_replace_status = 'Resolved'
                                if issue_replace_status == 'Resolved':
                                    color = '#2A9D55'
                                replace_resolved = f'<font color="{color}">{issue_replace_status}</font>'
                                    
                                page_name = "Replacement Needed - {} - {}".format(replace_issue_data[1],replace_resolved)
                            else:
                                page_name = "Replacement Needed - {}".format(replace_issue_data[1])
                            h1 = Paragraph(page_name, style['sub-index'])
                            flow_obj.append(h1)
                            flow_obj.append(Spacer(300, 18))

                            replace_images_before = []
                            replace_images_after = []

                            is_issue_linked_for_fix = replace_issue_data[13]  # This should be set based on your actual data structure
                            PL1 = Paragraph('''<para align=left><b>Before Photo:</b></para>''', style['image-caption1'])
                            PL3 = Paragraph('''<para align=left><b>After Photo:</b></para>''', style['image-caption1'])
                            building = replace_issue_data[3] if replace_issue_data[3] else '-'
                            floor = replace_issue_data[4] if replace_issue_data[4] else '-'
                            room = replace_issue_data[5] if replace_issue_data[5] else '-'
                            issue_type_replace = enum_woline_temp_issue_type[replace_issue_data[10]] if [
                                replace_issue_data[10]] else '-'
                            issue_title_replace = replace_issue_data[11] if replace_issue_data[11] else '-'
                            comments_replace = replace_issue_data[8] if replace_issue_data[8] else 'N/A'
                            description_replace = replace_issue_data[12] if replace_issue_data[12] else '-'
                            condition = enum_maintenance_condition_index_type[replace_issue_data[9]] if replace_issue_data[9] else '-'
                            if condition == 'Serviceable':
                                color = '#37d482'
                            elif condition == 'Limited':
                                color = '#ff950a'
                            else:
                                color = '#f64949' 
                            condition_paragraph = f'<font color="{color}">{condition}</font>'
                            
                            panel_schedule = enum_temp_panel_schedule_type[replace_issue_data[14]
                                                                        ] if replace_issue_data[14] else '-'
                            if asset_data1[12] == 2:
                                asset_top_level_replace = fetch_sublevel_asset_id1(asset_data1[0], asset_data1[-1])
                                print('asset_top_level_replace', asset_top_level_replace)
                                replaceData = [
                                    [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(replace_issue_data[1]), table_style),
                                    Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                                    [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(replace_issue_data[2]), table_style),
                                    Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                                    [Paragraph("<b>Contained Within: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_top_level_replace), table_style),
                                    Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                                    [Paragraph("<b>Issue Title: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_title_replace),table_style),
                                    Paragraph("<b>Issue Description: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(description_replace),table_style)],
                                    [Paragraph("<b>Issue Type: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_type_replace),table_style)],
                                    ]
                            else:
                                replaceData = [
                                    [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(replace_issue_data[1]), table_style),
                                    Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                                    [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(replace_issue_data[2]), table_style),
                                    Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                                    ['', '',Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                                    [Paragraph("<b>Issue Title: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_title_replace),table_style),
                                    Paragraph("<b>Issue Description: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(description_replace),table_style)],
                                    [Paragraph("<b>Issue Type: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_type_replace),table_style)],
                                    ]
                            replace_style = [('BOX', (0, 0), (5, 5), 0.7, colors.black),  
                                        # ('GRID',(0,0),(-1,-1),2,colors.black),
                                        ('LEFTPADDING', (0, 0), (-1, -1), 6),
                                        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                                        ('TOPPADDING', (0, 0), (-1, 0), 5),
                                        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                        ('LINEBELOW', (0, 0), (0, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 0), (1, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 0), (2, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 0), (3, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (0, 3), (0, 3),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 3), (1, 3),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 3), (2, 3),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 3), (3, 3),0.7,colors.black), # draw line after image
                                        ('LINEBEFORE', (2, 1), (2, 1), 1,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 2), (2, 2), 1,colors.black),  # Before "Floor"
                                        ('LINEBEFORE', (2, 3), (2, 3), 1,colors.black),  # Before "Room"
                                        ('LINEBEFORE', (2, 4), (2, 4), 1,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (2, 5), (2, 5), 1,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (3, 4), (3, 4), 1, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 5), (3, 5), 1, colors.black), # After "Problem Description:"
                                        ('SPAN', (2, 4), (2, 5)),  # Room
                                        ('ALIGN', (2, 4), (2, 5), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (2, 4), (2, 5), 'MIDDLE'),
                                         ('SPAN', (3, 4), (3, 5)),  # Room
                                        ('ALIGN', (3, 4), (3, 5), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (3, 4), (3, 5), 'MIDDLE'),
                                        ]
                            if replace_issue_data[0] in replace_image_data.keys():

                                for image_data in replace_image_data.get(replace_issue_data[0]):

                                    if image_data[0] is not None and image_data[1] is not None:

                                        replace_image = fetch_image(None, image_data[1], ISSUE_BUCKET_NAME)

                                        if replace_image:

                                            # image_name = '/tmp/' + image_data[1]
                                            replace = create_asset_image(replace_image,scale_factor=0.75)
                                            PL2 = Paragraph(''' <para align=left><b>{}</b></para>'''.format(
                                                image_data[1].split(".")[0]), style['image-caption'])

                                            if image_data[3] == 1:
                                                replace_images_before.append([replace, Spacer(0, 3)])
                                            elif image_data[3] == 2:
                                                replace_images_after.append([replace, Spacer(0, 3)])
                                        else:
                                            print("couldnot fetch image")
                                            PNI = Paragraph(''' <para align=left><b>{} </b></para>'''.format(
                                                image_data[1].split(".")[0]), style['image-caption'])
                                            if image_data[3] == 1:
                                                replace_images_before.append([PNI])
                                            elif image_data[3] == 2:
                                                replace_images_after.append([PNI])


                            startrow = 0

                            if len(replace_images_before) > 0:

                                for i in range(0, len(replace_images_before), 2):
                                    if i + 1 < len(replace_images_before):
                                        replaceData.insert(startrow, [replace_images_before[i], '', replace_images_before[i + 1], ''])
                                        replace_style.append(('SPAN', (0, startrow), (1, startrow)))
                                        replace_style.append(('ALIGN', (0, startrow), (1, startrow), 'LEFT'))
                                        replace_style.append(('VALIGN', (0, startrow), (1, startrow), 'MIDDLE'))
                                        replace_style.append(('SPAN', (2, startrow), (3, startrow)))
                                        replace_style.append(('ALIGN', (2, startrow), (3, startrow), 'LEFT'))
                                        replace_style.append(('VALIGN', (2, startrow), (3, startrow), 'MIDDLE'))
                                    else:
                                        replaceData.insert(startrow, [replace_images_before[i], '', '', ''])
                                        replace_style.append(('SPAN', (0, startrow), (-1, startrow)))

                                    startrow += 1

                            if len(replace_images_before) == 0:
                                replace_style = [('BOX', (0, 0), (5, 5), 0.7, colors.black),  
                                        # ('GRID',(0,0),(-1,-1),2,colors.black),
                                        ('LEFTPADDING', (0, 0), (-1, -1), 6),
                                        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                                        ('TOPPADDING', (0, 0), (-1, 0), 5),
                                        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                        ('LINEBELOW', (0, 2), (0, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 2), (1, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 2), (2, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 2), (3, 2),0.7,colors.black), # draw line after image
                                        ('LINEBEFORE', (2, 0), (2, 0),0.7,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 1), (2, 1),0.7,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 2), (2, 2),0.7,colors.black),  # Before "Floor"
                                        ('LINEBEFORE', (2, 3), (2, 3),0.7,colors.black),  # Before "Room"
                                        ('LINEBEFORE', (2, 4), (2, 4),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (2, 5), (2, 5),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (3, 3), (3, 3),0.7, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 4), (3, 4),0.7, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 5), (3, 5),0.7, colors.black), # After "Problem Description:"
                                        ('SPAN', (2, 3), (2, 4)),  # Room
                                        ('ALIGN', (2, 3), (2, 4), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (2, 3), (2, 4), 'MIDDLE'),
                                         ('SPAN', (3, 3), (3, 4)),  # Room
                                        ('ALIGN', (3, 3), (3, 4), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (3, 3), (3, 4), 'MIDDLE'),
                                        ]
                                t = Table(replaceData, colWidths=129, style=replace_style)
                                flow_obj.append(t)
                                
                            else:
                                t = Table(replaceData, colWidths=129,
                                        style=replace_style)

                                flow_obj.append(t)

                            comment_replace = Paragraph("<b>Comments: </b><font color='black'>{}</font>".format(comments_replace),asset_comment_style)
                            flow_obj.append(Spacer(1, 13))
                            flow_obj.append(comment_replace)
                            flow_obj.append(PageBreak())

                # # /////////////////////// Repair Issue ///////////////////////
                if len(repair_assets) > 0:
                    for repair_issue_data in repair_assets:
                        if repair_issue_data[15] == asset_data1[0]:
                            
                            if repair_issue_data[13]:
                                issue_repair_status = 'Resolved'
                                if issue_repair_status == 'Resolved':
                                    color = '#2A9D55'
                                repair_resolved = f'<font color="{color}">{issue_repair_status}</font>'
                                    
                                page_name = "Repair Needed - {} - {}".format(repair_issue_data[1],repair_resolved)
                            else:
                                page_name = "Repair Needed - {}".format(repair_issue_data[1])
                                
                            h1 = Paragraph(page_name, style['sub-index'])
                            flow_obj.append(h1)
                            flow_obj.append(Spacer(500, 18))

                            repair_images_before = []
                            repair_images_after = []
                            is_issue_linked_for_fix = repair_issue_data[13]  # This should be set based on your actual data structure
                            PL1 = Paragraph('''<para align=left><b>Before Photo:</b></para>''', style['image-caption1'])
                            PL3 = Paragraph('''<para align=left><b>After Photo:</b></para>''', style['image-caption1'])

                            building = repair_issue_data[3] if repair_issue_data[3] else '-'
                            floor = repair_issue_data[4] if repair_issue_data[4] else '-'
                            room = repair_issue_data[5] if repair_issue_data[5] else '-'
                            issue_type_repair = enum_woline_temp_issue_type[repair_issue_data[10]] if [repair_issue_data[10]] else '-'
                            issue_title_repair = repair_issue_data[11] if repair_issue_data[11] else '-'
                            comments_repair = repair_issue_data[8] if repair_issue_data[8] else 'N/A'
                            description_repair = repair_issue_data[12] if repair_issue_data[12] else '-'
                            panel_schedule = enum_temp_panel_schedule_type[repair_issue_data[14]] if repair_issue_data[14] else '-'
                            if asset_data1[12] == 2:
                                asset_top_level_repair = fetch_sublevel_asset_id1(asset_data1[0], asset_data1[-1])
                                print('asset_top_level_repair', asset_top_level_repair)
                                repairData = [
                                    [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(repair_issue_data[1]), table_style),
                                    Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                                    [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(repair_issue_data[2]), table_style),
                                    Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                                    [Paragraph("<b>Contained Within: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_top_level_repair), table_style),
                                    Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                                    [Paragraph("<b>Issue Title: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_title_repair),table_style),
                                    Paragraph("<b>Issue Description: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(description_repair),table_style)],
                                    [Paragraph("<b>Issue Type: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_type_repair),table_style)],
                                    ]
                            else: 
                                repairData = [
                                    [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(repair_issue_data[1]), table_style),
                                    Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                                    [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(repair_issue_data[2]), table_style),
                                    Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                                    ['', '',Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                                    [Paragraph("<b>Issue Title: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_title_repair),table_style),
                                    Paragraph("<b>Issue Description: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(description_repair),table_style)],
                                    [Paragraph("<b>Issue Type: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_type_repair),table_style)],
                                    ]
                            repair_style = [('BOX', (0, 0), (5, 5), 0.7, colors.black),
                                        # ('GRID',(0,0),(-1,-1),2,colors.black),
                                        ('LEFTPADDING', (0, 0), (-1, -1), 6),
                                        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                                        ('TOPPADDING', (0, 0), (-1, 0), 5),
                                        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                        ('LINEBELOW', (0, 0), (0, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 0), (1, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 0), (2, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 0), (3, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (0, 3), (0, 3),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 3), (1, 3),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 3), (2, 3),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 3), (3, 3),0.7,colors.black), # draw line after image
                                        ('LINEBEFORE', (2, 1), (2, 1),0.7,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 2), (2, 2),0.7,colors.black),  # Before "Floor"
                                        ('LINEBEFORE', (2, 3), (2, 3),0.7,colors.black),  # Before "Room"
                                        ('LINEBEFORE', (2, 4), (2, 4),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (2, 5), (2, 5),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (3, 4), (3, 4),0.7, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 5), (3, 5),0.7, colors.black), # After "Problem Description:"
                                        ('SPAN', (2, 4), (2, 5)),  # Room
                                        ('ALIGN', (2, 4), (2, 5), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (2, 4), (2, 5), 'MIDDLE'),
                                         ('SPAN', (3, 4), (3, 5)),  # Room
                                        ('ALIGN', (3, 4), (3, 5), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (3, 4), (3, 5), 'MIDDLE'),
                                        ]
                            if repair_issue_data[0] in repair_image_data.keys():

                                for image_data in repair_image_data.get(repair_issue_data[0]):

                                    if image_data[0] is not None and image_data[1] is not None:

                                        repair_image = fetch_image(None, image_data[1], ISSUE_BUCKET_NAME)

                                        if repair_image:

                                            # image_name = '/tmp/' + image_data[1]
                                            repair = create_asset_image(repair_image,scale_factor=0.75)
                                            PL2 = Paragraph(''' <para align=left><b>{}</b></para>'''.format(
                                                image_data[1].split(".")[0]), style['image-caption'])

                                            if image_data[3] == 1:
                                                repair_images_before.append([repair, Spacer(0, 3)])
                                            elif image_data[3] == 2:
                                                repair_images_after.append([repair, Spacer(0, 3)])
                                        else:
                                            print("couldnot fetch image")
                                            PNI = Paragraph(''' <para align=left><b>{} </b></para>'''.format(
                                                image_data[1].split(".")[0]), style['image-caption'])
                                            if image_data[3] == 1:
                                                repair_images_before.append([PNI])
                                            elif image_data[3] == 2:
                                                repair_images_after.append([PNI])


                            startrow = 0

                            if len(repair_images_before) > 0:

                                for i in range(0, len(repair_images_before), 2):
                                    if i + 1 < len(repair_images_before):
                                        repairData.insert(startrow, [repair_images_before[i], '', repair_images_before[i + 1], ''])
                                        repair_style.append(('SPAN', (0, startrow), (1, startrow)))
                                        repair_style.append(('ALIGN', (0, startrow), (1, startrow), 'LEFT'))
                                        repair_style.append(('VALIGN', (0, startrow), (1, startrow), 'MIDDLE'))
                                        repair_style.append(('SPAN', (2, startrow), (3, startrow)))
                                        repair_style.append(('ALIGN', (2, startrow), (3, startrow), 'LEFT'))
                                        repair_style.append(('VALIGN', (2, startrow), (3, startrow), 'MIDDLE'))
                                    else:
                                        repairData.insert(startrow, [repair_images_before[i], '', '', ''])
                                        repair_style.append(('SPAN', (0, startrow), (-1, startrow)))

                                    startrow += 1

                            if len(repair_images_before) == 0:
                                
                                repair_style = [('BOX', (0, 0), (5, 5), 0.7, colors.black),  
                                        # ('GRID',(0,0),(-1,-1),2,colors.black),
                                        ('LEFTPADDING', (0, 0), (-1, -1), 6),
                                        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                                        ('TOPPADDING', (0, 0), (-1, 0), 5),
                                        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                        ('LINEBELOW', (0, 2), (0, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 2), (1, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 2), (2, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 2), (3, 2),0.7,colors.black), # draw line after image
                                        ('LINEBEFORE', (2, 0), (2, 0),0.7,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 1), (2, 1),0.7,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 2), (2, 2),0.7,colors.black),  # Before "Floor"
                                        ('LINEBEFORE', (2, 3), (2, 3),0.7,colors.black),  # Before "Room"
                                        ('LINEBEFORE', (2, 4), (2, 4),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (2, 5), (2, 5),0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (3, 3), (3, 3),0.7, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 4), (3, 4),0.7, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 5), (3, 5),0.7, colors.black), # After "Problem Description:"
                                        ('SPAN', (2, 3), (2, 4)),  # Room
                                        ('ALIGN', (2, 3), (2, 4), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (2, 3), (2, 4), 'MIDDLE'),
                                         ('SPAN', (3, 3), (3, 4)),  # Room
                                        ('ALIGN', (3, 3), (3, 4), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (3, 3), (3, 4), 'MIDDLE'),
                                        ]
                                t = Table(repairData, colWidths=129, style=repair_style)
                                flow_obj.append(t)
                                
                            else:
                                t = Table(repairData, colWidths=129,
                                    style=repair_style)

                                flow_obj.append(t)

                            comment_repair = Paragraph("<b>Comments: </b><font color='black'>{}</font>".format(comments_repair),asset_comment_style)
                            flow_obj.append(Spacer(1, 13))
                            flow_obj.append(comment_repair)
                            flow_obj.append(PageBreak())
                
                # /////////////////////// Other Issue ///////////////////////
                if len(other_assets) > 0:

                    for other_issue_data in other_assets:
                        if other_issue_data[15] == asset_data1[0]:
                            
                            if other_issue_data[13]:
                                issue_other_status = 'Resolved'
                                if issue_other_status == 'Resolved':
                                    color = '#2A9D55'
                                other_resolved = f'<font color="{color}">{issue_other_status}</font>'
                                    
                                page_name = "{} - {} - {}".format(other_issue_data[11],other_issue_data[1],other_resolved)
                            else:
                                page_name = "{} - {}".format(other_issue_data[11],other_issue_data[1])
                                
                            h1 = Paragraph(page_name, style['sub-index'])
                            flow_obj.append(h1)
                            flow_obj.append(Spacer(700, 18))

                            other_images_before = []
                            other_images_after = []

                            is_issue_linked_for_fix = other_issue_data[13]  # This should be set based on your actual data structure
                            PL1 = Paragraph('''<para align=left><b>Before Photo:</b></para>''', style['image-caption1'])
                            PL3 = Paragraph('''<para align=left><b>After Photo:</b></para>''', style['image-caption1'])
                            building = other_issue_data[3] if other_issue_data[3] else '-'
                            floor = other_issue_data[4] if other_issue_data[4] else '-'
                            room = other_issue_data[5] if other_issue_data[5] else '-'
                            issue_type_other = enum_woline_temp_issue_type[other_issue_data[10]] if [
                                other_issue_data[10]] else ''
                            issue_title_other = other_issue_data[11] if other_issue_data[11] else '-'
                            comments_other = other_issue_data[8] if other_issue_data[8] else 'N/A'
                            description_other = other_issue_data[12] if other_issue_data[12] else '-'
                            panel_schedule = enum_temp_panel_schedule_type[other_issue_data[14]] if other_issue_data[14] else '-'

                            if asset_data1[12] == 2:
                                asset_top_level_other = fetch_sublevel_asset_id1(asset_data1[0], asset_data1[-1])
                                print('asset_top_level_other', asset_top_level_other)
                                otherData = [
                                    [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(other_issue_data[1]), table_style),
                                    Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                                    [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(other_issue_data[2]), table_style),
                                    Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                                    [Paragraph("<b>Contained Within: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_top_level_other), table_style),
                                    Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                                    [Paragraph("<b>Issue Title: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_title_other),table_style),
                                    Paragraph("<b>Issue Description: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(description_other),table_style)],
                                    [Paragraph("<b>Issue Type: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_type_other),table_style)],
                                    ]
                            else:
                                otherData = [
                                    [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(other_issue_data[1]), table_style),
                                    Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                                    [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(other_issue_data[2]), table_style),
                                    Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                                    ['', '',Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                                    [Paragraph("<b>Issue Title: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_title_other),table_style),
                                    Paragraph("<b>Issue Description: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(description_other),table_style)],
                                    [Paragraph("<b>Issue Type: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(issue_type_other),table_style)],
                                    ]
                            other_style = [('BOX', (0, 0), (5, 5), 0.7, colors.black), 
                                        # ('GRID',(0,0),(-1,-1),2,colors.black),
                                        ('LEFTPADDING', (0, 0), (-1, -1), 6),
                                        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                                        ('TOPPADDING', (0, 0), (-1, 0), 5),
                                        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                        ('LINEBELOW', (0, 0), (0, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 0), (1, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 0), (2, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 0), (3, 0),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (0, 3), (0, 3),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 3), (1, 3),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 3), (2, 3),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 3), (3, 3),0.7,colors.black), # draw line after image
                                        ('LINEBEFORE', (2, 1), (2, 1), 0.7,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 2), (2, 2), 0.7,colors.black),  # Before "Floor"
                                        ('LINEBEFORE', (2, 3), (2, 3), 0.7,colors.black),  # Before "Room"
                                        ('LINEBEFORE', (2, 4), (2, 4), 0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (2, 5), (2, 5), 0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (3, 4), (3, 4), 0.7, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 5), (3, 5), 0.7, colors.black), # After "Problem Description:"
                                        ('SPAN', (2, 4), (2, 5)),  # Room
                                        ('ALIGN', (2, 4), (2, 5), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (2, 4), (2, 5), 'MIDDLE'),
                                         ('SPAN', (3, 4), (3, 5)),  # Room
                                        ('ALIGN', (3, 4), (3, 5), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (3, 4), (3, 5), 'MIDDLE'),

                                        ]
                            if other_issue_data[0] in other_image_data.keys():

                                for image_data in other_image_data.get(other_issue_data[0]):

                                    if image_data[0] is not None and image_data[1] is not None:

                                        other_image = fetch_image(None, image_data[1], ISSUE_BUCKET_NAME)

                                        if other_image:

                                            # image_name = '/tmp/' + image_data[1]
                                            other = create_asset_image(other_image,scale_factor=0.75)
                                            PL2 = Paragraph(''' <para align=left><b>{}</b></para>'''.format(
                                                image_data[1].split(".")[0]), style['image-caption'])

                                            if image_data[3] == 1:
                                                other_images_before.append([other, Spacer(0, 3)])
                                            elif image_data[3] == 2:
                                                other_images_after.append([other, Spacer(0, 3)])
                                        else:
                                            print("couldnot fetch image")
                                            PNI = Paragraph(''' <para align=left><b>{} </b></para>'''.format(
                                                image_data[1].split(".")[0]), style['image-caption'])
                                            if image_data[3] == 1:
                                                other_images_before.append([PNI])
                                            elif image_data[3] == 2:
                                                other_images_after.append([PNI])


                            startrow = 0

                            if len(other_images_before) > 0:

                                for i in range(0, len(other_images_before), 2):
                                    if i + 1 < len(other_images_before):
                                        otherData.insert(startrow, [other_images_before[i], '', other_images_before[i + 1], ''])
                                        other_style.append(('SPAN', (0, startrow), (1, startrow)))
                                        other_style.append(('ALIGN', (0, startrow), (1, startrow), 'LEFT'))
                                        other_style.append(('VALIGN', (0, startrow), (1, startrow), 'MIDDLE'))
                                        other_style.append(('SPAN', (2, startrow), (3, startrow)))
                                        other_style.append(('ALIGN', (2, startrow), (3, startrow), 'LEFT'))
                                        other_style.append(('VALIGN', (2, startrow), (3, startrow), 'MIDDLE'))
                                    else:
                                        otherData.insert(startrow, [other_images_before[i], '', '', ''])
                                        other_style.append(('SPAN', (0, startrow), (-1, startrow)))

                                    startrow += 1
                            

                            if len(other_images_before) == 0:
                                other_style = [('BOX', (0, 0), (5, 5), 0.7, colors.black),  
                                        # ('GRID',(0,0),(-1,-1),2,colors.black),
                                        ('LINEBELOW', (0, 2), (0, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (1, 2), (1, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (2, 2), (2, 2),0.7,colors.black), # draw line after image
                                        ('LINEBELOW', (3, 2), (3, 2),0.7,colors.black), # draw line after image
                                        ('LINEBEFORE', (2, 0), (2, 0), 0.7,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 1), (2, 1), 0.7,colors.black),  # Before "Building" V line
                                        ('LINEBEFORE', (2, 2), (2, 2), 0.7,colors.black),  # Before "Floor"
                                        ('LINEBEFORE', (2, 3), (2, 3), 0.7,colors.black),  # Before "Room"
                                        ('LINEBEFORE', (2, 4), (2, 4), 0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (2, 5), (2, 5), 0.7,colors.black),  # Before "Size Of Anomaly"
                                        ('LINEBEFORE', (3, 3), (3, 3), 0.7, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 4), (3, 4), 0.7, colors.black), # After "Problem Description:"
                                        ('LINEBEFORE', (3, 5), (3, 5), 0.7, colors.black), # After "Problem Description:"
                                       ('SPAN', (2, 3), (2, 4)),  # Room
                                        ('ALIGN', (2, 3), (2, 4), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (2, 3), (2, 4), 'MIDDLE'),
                                         ('SPAN', (3, 3), (3, 4)),  # Room
                                        ('ALIGN', (3, 3), (3, 4), 'CENTER'),  # Center-align Issue Description
                                        ('VALIGN', (3, 3), (3, 4), 'MIDDLE'),
                                        ]
                                t = Table(otherData, colWidths=129, style=other_style)
                            else:
                                t = Table(otherData, colWidths=129,
                                    style=other_style)

                            flow_obj.append(t)

                            comment_other = Paragraph("<b>Comments: </b><font color='black'>{}</font>".format(comments_other),asset_comment_style)
                            flow_obj.append(Spacer(1, 13))
                            flow_obj.append(comment_other)
                            flow_obj.append(PageBreak())

            # # /////////////////////// Electrical Inventory List ///////////////////////
            processed_asset_ids = set()
            building_names = []  # Collect building names here
            sorted_assets = []
                        # Sorting the final list based on the required location data (building, floor, room, etc.)
            all_assets1 = sorted(all_assets1, key=lambda x: (
                str(x[3]).strip().lower() if len(x) > 3 and x[3] else '',  # Temp master building name
                str(x[4]).strip().lower() if len(x) > 4 and x[4] else '',  # Temp master floor name
                str(x[5]).strip().lower() if len(x) > 5 and x[5] else '',  # Temp master room name
                str(x[1]).strip().lower() if len(x) > 1 and x[1] else '',  # Asset name (alphabetical order)
                {
                    3: 1,  # Map maintenance index type to sorting priority
                    2: 2,
                    1: 3
                }.get(x[9], 4) if len(x) > 6 else 4
            ))
            # Ite
            # Iterate over all assets and process them line by line
            top_level_assets = []
            sub_level_mapping = {}

            # Separate top-level and sub-level assets
            for asset in all_assets1:
                if asset[12] == 1:  # Top-level asset
                    top_level_assets.append(asset)
                elif asset[12] == 2:  # Sub-level asset
                    # Map sub-level assets to their parent (woonboardingassets_id)
                    parent_id = fetch_sublevel_woonboardingasset_id(asset[0],asset[-3], asset[-2])
                    if parent_id:
                        if parent_id[0] not in sub_level_mapping:
                            sub_level_mapping[parent_id[0]] = []
                        sub_level_mapping[parent_id[0]].append(asset)

            # Rebuild the sorted list in Top -> Sub hierarchy
            sorted_assets = []
            for top_asset in top_level_assets:
                # Add the top-level asset
                sorted_assets.append(top_asset)
                
                # Add its sub-level assets (if any)
                if top_asset[0] in sub_level_mapping:
                    sorted_assets.extend(sub_level_mapping[top_asset[0]])

            # Replace all_assets1 with the sorted assets
            all_assets1 = sorted_assets
            if len(all_assets1) > 0:

                hall = Paragraph("Electrical Inventory List", style['index'])
                flow_obj.append(hall)
                flow_obj.append(Spacer(700, 18))

                assets = []

                last_printed_building = None
                processed_rooms = {}
                # all_assets = sorted(all_assets, key=lambda x: (x[3] or '', x[4] or '', x[5] or ''))
                for an_asset in all_assets1:
                    asset_id = an_asset[0]
                    if asset_id in processed_asset_ids:
                        continue

                    processed_asset_ids.add(asset_id)

                    fed_by = "-"
                    verdict = fetch_verdict_labels(an_asset[0])
                    if an_asset[0] in all_fedby_data.keys():
                        fed_by_list = all_fedby_data.get(an_asset[0], '-')
                        if isinstance(fed_by_list, list):
                            fed_by = ', '.join(fed_by_list)
                        else:
                            fed_by = fed_by_list

                    asset_class = an_asset[2] if an_asset[2] else 'Unknown'

                    building_location = an_asset[3]
                    room = an_asset[4]  # floor
                    subroom = an_asset[5]  # room
                    print('building_names', building_names)
                    print('building_location', building_location)

                    if building_location != last_printed_building:
                        building_names.append(building_location)
                        if assets:
                            header = [
                                Paragraph("<b>Location </b>",style['table_headers_ei']),
                                Paragraph("<b>Asset Name </b>",style['table_headers_ei']),
                                Paragraph("<b>Asset Class</b>",style['table_headers_ei']),
                                Paragraph("<b>Serviceability</b>",style['table_headers_ei']),
                                Paragraph("<b>Verdict</b>",style['table_headers_ei'])
                            ]

                            assets.insert(1, header)

                            col_widths = [100, 120, 105, 112, 80]
                            table_all = Table(assets, colWidths=col_widths)
                            t_style = TableStyle([
                                ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
                                ('BACKGROUND', (0, 1), (-1, 1), colors.whitesmoke),
                                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                                ('BOTTOMPADDING', (0, 0), (-1, 0), 3),
                                ('BACKGROUND', (0, 2), (-1, -1), colors.white),
                                ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),
                                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                                ('VALIGN', (0, 1), (-1, -1), 'TOP'),
                            ])
                            self.dynamic_span(assets, t_style, building_names)
                            table_all.setStyle(t_style)
                            flow_obj.append(table_all)
                            # Add a small spacer after building name
                            flow_obj.append(Spacer(1, 12))

                        assets = []
                        if building_location:
                            # Building Name
                            assets.append([Paragraph(building_location, style['build_style'])])
                        else:
                            assets.append([Paragraph("Unknown Building", style['build_style'])])

                        last_printed_building = building_location
                        processed_rooms[building_location] = {}

                    # Check if the room is new for this building
                    if room not in processed_rooms[building_location]:
                        processed_rooms[building_location][room] = []
                        print('floor', processed_rooms)

                    # Check if the subroom is new for this room
                    if subroom not in processed_rooms[building_location][room]:
                        location = f"{room}-{subroom}"
                        processed_rooms[building_location][room].append(
                            subroom)
                        print('room', processed_rooms)

                    else:
                        location = f"<p>{room}-{subroom}</p>"

                    condition_e = enum_maintenance_condition_index_type[an_asset[9]
                                                                      ] if an_asset[9] else ''
                    asset_name = an_asset[1]

                    assets.append(
                        [Paragraph(location.title(), style['table_data_ei'],),
                         Paragraph(asset_name, style['table_data_ei']),
                         Paragraph(asset_class, style['table_data_ei']),
                         Paragraph(condition_e, style['table_data_ei']),
                         Paragraph(verdict.title(), style['table_data_ei'])])
                if assets:

                    header = [Paragraph("<b>Location </b>", style['table_headers_ei']),
                              Paragraph("<b>Asset Name </b>",style['table_headers_ei']),
                              Paragraph("<b>Asset Class</b>",style['table_headers_ei']),
                              Paragraph("<b>Serviceability</b>",style['table_headers_ei']),
                              Paragraph("<b>Verdict</b>", style['table_headers_ei'])]

                    assets.insert(1, header)

                    col_widths = [100, 120, 105, 112, 80]
                    table_all = Table(assets, colWidths=col_widths)
                    t_style = TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
                        ('BACKGROUND', (0, 1), (-1, 1), colors.whitesmoke),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                        ('GRID', (0, 0), (-1, -1), 0.7, colors.black),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 3),
                        ('BACKGROUND', (0, 2), (-1, -1), colors.white),
                        # ('BOX', (0, 0), (-1, -1), 1, colors.whitesmoke),
                        ('LINEBELOW', (0, 0), (-1, 0), 0.7, colors.black),
                        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                        ('VALIGN', (0, 1), (-1, -1), 'TOP'),
                    ])
                    self.dynamic_span(assets, t_style, building_names)
                    table_all.setStyle(t_style)
                    flow_obj.append(table_all)
                flow_obj.append(PageBreak())


            # # /////////////////////// Asset Page ///////////////////////
            processed_assets = set()
            print(all_assets1)
            asset_pages_added = False
            print(len(all_assets1))
            if not asset_pages_added:
                for asset_data1 in all_assets1:
                    if asset_data1[1]:  # Check if any asset has issues
                        asset_name1 = Paragraph('<font color="white" size="2">Asset Pages</font>', style['index'])
                        flow_obj.append(asset_name1)
                        flow_obj.append(Spacer(1, -10))
                        asset_pages_added = True
                        break 
            sorted_assets = []
                        # Sorting the final list based on the required location data (building, floor, room, etc.)
            if all_assets_feature_flag: 
                all_assets1 = sorted(all_assets1, key=lambda x: (
                    str(x[3]).strip().lower() if len(x) > 3 and x[3] else '',  # Temp master building name
                    str(x[4]).strip().lower() if len(x) > 4 and x[4] else '',  # Temp master floor name
                    str(x[5]).strip().lower() if len(x) > 5 and x[5] else '',  # Temp master room name
                    str(x[1]).strip().lower() if len(x) > 1 and x[1] else '',   # Asset name (alphabetical order)
                    {
                        3: 1,  # Map maintenance index type to sorting priority
                        2: 2,
                        1: 3
                    }.get(x[9], 4) if len(x) > 6 else 4
                ))
            # Iterate over all assets and process them line by line
            top_level_assets = []
            sub_level_mapping = {}

            # Separate top-level and sub-level assets
            for asset in all_assets1:
                if asset[12] == 1:  # Top-level asset
                    top_level_assets.append(asset)
                elif asset[12] == 2:  # Sub-level asset
                    # Map sub-level assets to their parent (woonboardingassets_id)
                    parent_id = fetch_sublevel_woonboardingasset_id(asset[0], asset[-3],asset[-2])
                    if parent_id:
                        if parent_id[0] not in sub_level_mapping:
                            sub_level_mapping[parent_id[0]] = []
                        sub_level_mapping[parent_id[0]].append(asset)

            # Rebuild the sorted list in Top -> Sub hierarchy
            sorted_assets = []
            for top_asset in top_level_assets:
                # Add the top-level asset
                sorted_assets.append(top_asset)
                
                # Add its sub-level assets (if any)
                if top_asset[0] in sub_level_mapping:
                    sorted_assets.extend(sub_level_mapping[top_asset[0]])

            # Replace all_assets1 with the sorted assets
            all_assets1 = sorted_assets

            for asset_data1 in all_assets1:
                # count = 1
                if asset_data1[0] in processed_assets:
                    continue
                if not all_assets_feature_flag:

                    if asset_data1[0] not in assets_having_issues:
                        continue
                    else:
                        pass
                print(
                    f"Asset {asset_data1[0]} with asset_id {asset_data1[1]}")
                print(len(asset_data1))
                if len(asset_data1) > 0:
                    processed_assets.add(asset_data1[0])
                    asset_data_name = asset_data1[1]
                        
                    if asset_data1[12] == 2:
                        print("Using style 'sub1-index'")
                        page_name = '{}'.format(asset_data_name)
                        asset_h1 = Paragraph(page_name, style['sub-index1'])
                        
                    else:
                        page_name = '{}'.format(asset_data_name)
                    
                        asset_h1 = Paragraph(page_name, style['sub-index'])
                    flow_obj.append(asset_h1)
                    flow_obj.append(Spacer(300, 18))
                    asset_images = []
                    flag_asset_images = []
                    ir_images = []
                    flag_ir_images = []

                    PL4 = Paragraph('''<b>PHOTOS</b>''',style['image-caption1'])
                    PL5 = Paragraph('''<b>PROFILE PHOTO</b>''',style['image-caption2'])
                    PL6 = Paragraph('''<b>SCHEDULE PHOTO</b>''',style['image-caption2'])
                    PLIR = Paragraph('''<b>IR PHOTOS</b>''',style['image-caption1'])
                    building = asset_data1[3] if asset_data1[3] else '-'
                    floor = asset_data1[4] if asset_data1[4] else '-'
                    room = asset_data1[5] if asset_data1[5] else '-'
                    section = asset_data1[6] if asset_data1[6] else '-'
                    comment = asset_data1[8] if asset_data1[8] else 'N/A'
                    panel_schedule = enum_temp_panel_schedule_type[asset_data1[10]] if asset_data1[10] else '-'
                    print('panel_schedule', panel_schedule)
                    print('issue_true',asset_data1[-3])
                    condition_asset = enum_maintenance_condition_index_type[asset_data1[9]] if asset_data1[9] else '-'
                    arch_flash_label = enum_arc_flash_label[asset_data1[11]] if asset_data1[11] else '-'
                    asset_type = "Top-Component" if asset_data1[12] == 1 else "Sub-Component"
                    top_asset_name = asset_data1[-1] if asset_data1[-1] else 'N/A'
                    if asset_data1[12] == 2:
                        asset_top_level = fetch_sublevel_asset_id1(asset_data1[0], asset_data1[-1])
                        print('asset_top_level', asset_top_level)

                        data5 = [

                            [Paragraph('<b>BASIC INFO</b>', table_style2)],
                            [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_data1[1]), table_style),
                             Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                            [Paragraph("<b>Panel Schedule: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(panel_schedule), table_style),
                             Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                            [Paragraph("<b>Serviceability: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(condition_asset), table_style),
                             Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                            [Paragraph("<b>Arc Flash Label: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(arch_flash_label), table_style),
                             Paragraph("<b>Component Type: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_type), table_style)],
                            [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_data1[2]), table_style),
                             Paragraph("<b>Contained Within: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_top_level), table_style)]

                        ]
                    else:
                        data5 = [
                           [Paragraph('<b>BASIC INFO</b>', table_style2)],
                            [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_data1[1]), table_style),
                             Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                            [Paragraph("<b>Panel Schedule: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(panel_schedule), table_style),
                             Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                            [Paragraph("<b>Serviceability: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(condition_asset), table_style),
                             Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                            [Paragraph("<b>Arc Flash Label: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(arch_flash_label), table_style),
                             Paragraph("<b>Component Type: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_type), table_style)],
                            [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_data1[2]), table_style)]

                        ]

                    print('asset_type', asset_type)
                    asset_style = [('BOX', (0, 0), (-1, -1), 0.7, colors.black),
                                ('BACKGROUND', (0, 0),(-1, 0), colors.whitesmoke),
                                #    ('GRID',(0,0),(-1,-1),2,colors.black),
                                ('LINEBELOW', (0, 0), (-1, 0), 0.7, colors.black),
                                ('LINEBELOW', (0, 5), (-1, 5), 0.7, colors.black),
                                ('LINEBELOW', (0, 6), (-1, 6), 0.7, colors.black),
                                ('LINEBEFORE', (2, 1), (2, 1), 0.7,colors.black),  # Before "Building"
                                ('LINEBEFORE', (2, 2), (2, 2), 0.7,colors.black),  # Before "Floor"
                                ('LINEBEFORE', (2, 3), (2, 3), 0.7,colors.black),  # Before "Room"
                                ('LINEBEFORE', (2, 4), (2, 4), 0.7, colors.black),# Before "Component Type"
                                ('LINEBEFORE', (2, 5), (2, 5), 0.7, colors.black),# Before "Contained Within"
                                ('LINEBEFORE', (2, 6), (2, 6), 0.7,colors.black), 
                                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                ('SPAN', (0, 0), (-1, 0)),
                                ]
                    if asset_data1[0] in asset_image_data:
                        for image_data in asset_image_data.get(asset_data1[0], []):

                            if image_data[0] is not None and image_data[1] is not None:

                                folder = None

                                asset_image = fetch_image(
                                    folder, image_data[1], NEC_BUCKET_NAME)

                                if asset_image:
                                    assets1 = create_asset_image(
                                        asset_image, scale_factor=0.75)
                                    asset_images.append(
                                        [assets1, Spacer(0, 3)])
                                    flag_asset_images.append(1)

                                else:
                                    print("couldnot fetch image")

                                    PNI = Paragraph(''' <para align=left><b>{} </b></para>'''.format(
                                        image_data[1].split(".")[0]), style['image-caption'])
                                    asset_images.append([PNI])
                                    flag_asset_images.append(0)

                            else:

                                # SHOW HERE NOTHING AND PUT IF ONLY 1 IMAGE is there then in center
                                flag_asset_images.append(0)

                                PNI = Paragraph(
                                    ''' <para align=left spaceb=3><b> </b></para>''', style['image-caption'])
                                asset_images.append([PNI])
                                # print("Asset Done")
                    ir_image = False
                    print('ir_image_data',ir_image_data)
                    if asset_data1[0] in ir_image_data:

                        for image_data in ir_image_data.get(asset_data1[0], []):

                            if image_data[0] is not None and image_data[3] is not None:
                                visual_image = fetch_image(
                                    image_data[1], image_data[3], BUCKET_NAME)

                                if visual_image:
                                    IL = create_ir_image(
                                        visual_image, scale_factor=0.75)

                                    PL2 = Paragraph(''' <para align=center><b>{}</b></para>'''.format(
                                        image_data[3].split(".")[0]),
                                        style['image-caption'])
                                    ir_images.append([IL, Spacer(0, 3), PL2])
                                    flag_ir_images.append(1)

                                else:
                                    # print("couldnot fetch image")

                                    PNI = Paragraph(''' <para align=left><b>{} </b></para>'''.format(
                                        image_data[3].split(".")[0]),
                                        style['image-caption'])
                                    ir_images.append([PNI])
                                    flag_ir_images.append(0)

                            else:
                                flag_ir_images.append(0)
                                PNI = Paragraph(''' <para align=left><b>No image found! </b></para>''',
                                                style['image-caption'])
                                ir_images.append([PNI])

                            if image_data[0] is not None and image_data[2] is not None:
                                ir_image = fetch_image(
                                    image_data[1], image_data[2], BUCKET_NAME)
                                if ir_image:
                                    IR = create_ir_image(
                                        ir_image, scale_factor=0.75)
                                    PR2 = Paragraph('''<para align=center><b>{}</b></para>'''.format(
                                        image_data[2].split(".")[0]),
                                        style['image-caption'])
                                    ir_images.append([IR, PR2])
                                    flag_ir_images.append(1)
                                else:
                                    # print("could not fetch image")
                                    PNI = Paragraph(
                                        ''' <para align=left><b>{} </b></para>'''.format(
                                            image_data[2].split(".")[0]),
                                        style['image-caption'])
                                    ir_images.append([PNI])
                                    flag_ir_images.append(0)
                            else:
                                PNI = Paragraph(''' <para align=left><b>No image found! </b></para>''',
                                                style['image-caption'])
                                ir_images.append([PNI])
                                flag_ir_images.append(0)

                    startrow = len(data5)

                    asset_photo_added = None
                    if len(asset_images) > 0:
                        for image_pair_index in range(0, asset_images.__len__(), 2):
                           
                            if not asset_photo_added:
                                data5.insert(startrow, [PL4, '', ''])
                                asset_style.append(('SPAN', (0, startrow), (3, startrow)))
                                asset_style.append(('ALIGN', (0, startrow), (3, startrow), 'CENTER'))
                                asset_style.append(('TEXTALIGN', (0, startrow), (3, startrow), 'CENTER'))
                                asset_style.append(('VALIGN', (0, startrow), (3, startrow), 'MIDDLE'))
                                asset_style.append(('BACKGROUND', (0, startrow), (3, startrow), colors.whitesmoke))
                                
                                startrow += 1
                                asset_photo_added = True
                            # multiple images
                            if (image_pair_index + 1 < len(flag_asset_images) and flag_asset_images[image_pair_index] != 0 and flag_asset_images[image_pair_index+1] != 0):
                                # odd
                                print('len_flag_asset_images',len(flag_asset_images))
                                if len(flag_asset_images) % 2 != 0:
                                    
                                    data5.insert(startrow, [asset_images[image_pair_index], '', asset_images[image_pair_index + 1], ''], )
                                    asset_style.append(('SPAN', (0, startrow), (1, startrow)))
                                    asset_style.append(('ALIGN', (0, startrow), (1, startrow), 'CENTER'))
                                    asset_style.append(('VALIGN', (0, startrow), (1, startrow),'MIDDLE'))
                                    asset_style.append(('SPAN', (2, startrow), (3, startrow)))
                                    asset_style.append(('ALIGN', (2, startrow), (3, startrow), 'CENTER'))
                                    asset_style.append(('VALIGN', (2, startrow), (3, startrow),'MIDDLE'))
                                    startrow = startrow + 1
                                    
                                # even
                                elif len(flag_asset_images) % 2 == 0:

                                    data5.insert(startrow, [asset_images[image_pair_index], '', asset_images[image_pair_index + 1], ''], )
                                    asset_style.append(('SPAN', (0, startrow), (1, startrow)))
                                    asset_style.append(('ALIGN', (0, startrow), (1, startrow), 'CENTER'))
                                    asset_style.append(('VALIGN', (0, startrow), (1, startrow),0.7, colors.black,'MIDDLE'))
                                    asset_style.append(('SPAN', (2, startrow), (3, startrow)))
                                    asset_style.append(('ALIGN', (2, startrow), (3, startrow), 'CENTER'))
                                    asset_style.append(('VALIGN', (2, startrow), (3, startrow), 0.7, colors.black,'MIDDLE'))
                                    asset_style.append(('LINEBEFORE', (2, startrow), (2, startrow), 0.7, colors.black))
                                    startrow = startrow + 1

                            else:
                                if (image_pair_index + 1 < len(flag_asset_images) and flag_asset_images[image_pair_index] == 0 and flag_asset_images[image_pair_index+1] != 0):
                                    asset_style.append(('ALIGN', (0, startrow), (3, startrow), 'CENTER'))
                                    asset_style.append(('VALIGN', (0, startrow), (3, startrow), 'MIDDLE'))
                                    asset_style.append(('SPAN', (0, startrow), (3, startrow)))
                                    startrow = startrow + 1
                                    data5.insert(startrow, [asset_images[image_pair_index+1],'', '', ''])
                                    asset_style.append(('SPAN', (0, startrow), (3, startrow)))
                                    asset_style.append(('ALIGN', (0, startrow), (3, startrow), 'CENTER'))
                                    asset_style.append(('VALIGN', (0, startrow), (3, startrow), 'MIDDLE'))
                                    startrow = startrow + 1
                                else:
                                    asset_style.append(('ALIGN', (0, startrow), (3, startrow), 'CENTER'))
                                    asset_style.append(('VALIGN', (0, startrow), (3, startrow), 'MIDDLE'))
                                    asset_style.append(('SPAN', (0, startrow), (3, startrow)))
                                    startrow = startrow + 1
                                    data5.insert(startrow, [asset_images[image_pair_index],'', '', ''])
                                    asset_style.append(('SPAN', (0, startrow), (3, startrow)))
                                    asset_style.append(('ALIGN', (0, startrow), (3, startrow), 'CENTER'))
                                    asset_style.append(('VALIGN', (0, startrow), (3, startrow), 'MIDDLE'))
                                    startrow = startrow+1
                    startrow = len(data5)
                    ir_photo_added = None
                    print('len of ir images', len(ir_images))

                    if ir_images == False:
                        data5.insert(startrow, ['', '', '', ''])
                        startrow += 1
                    else:
                        print('len of ir images', len(ir_images))
                        if len(ir_images) > 0:

                            for image_pair_index in range(0, ir_images.__len__(), 2):

                                if image_pair_index < len(flag_ir_images) and image_pair_index + 1 < len(flag_ir_images):
                                    if not ir_photo_added:
                                        # Add the main PLIR content
                                        data5.insert(startrow, [PLIR])
                                        asset_style.append(('SPAN', (0, startrow), (3, startrow)))
                                        asset_style.append(('ALIGN', (0, startrow), (3, startrow), 'CENTER'))
                                        asset_style.append(('VALIGN', (0, startrow), (3, startrow), 'MIDDLE'))
                                        asset_style.append(('TEXTALIGN', (0, startrow), (3, startrow), 'CENTER'))
                                        asset_style.append(('LINEABOVE', (0, startrow), (3, startrow), 0.7, colors.black))
                                        asset_style.append(('LINEBELOW', (0, startrow), (3, startrow), 0.7, colors.black))
                                        asset_style.append(('BACKGROUND', (0, startrow), (3, startrow), colors.whitesmoke))
                                       
                                        startrow += 1
                                        ir_photo_added = True

                                    if flag_ir_images[image_pair_index] != 0 and flag_ir_images[image_pair_index+1] != 0:
                                        data5.insert(startrow,[ir_images[image_pair_index], '', ir_images[image_pair_index + 1], ''])
                                        asset_style.append(('SPAN', (0, startrow), (1, startrow)))
                                        asset_style.append(('SPAN', (2, startrow), (3, startrow)))
                                        asset_style.append(('ALIGN', (0, startrow), (1, startrow), 'LEFT'))
                                        asset_style.append(('ALIGN', (2, startrow), (3, startrow), 'LEFT'))
                                        asset_style.append(('VALIGN', (0, startrow), (1, startrow),0.7, colors.black,'MIDDLE'))
                                        asset_style.append(('VALIGN', (2, startrow), (3, startrow),0.7, colors.black,'MIDDLE'))
                                        startrow = startrow + 1
                                    else:
                                        if flag_ir_images[image_pair_index] == 0 and flag_ir_images[image_pair_index+1] != 0:
                                            data5.insert(startrow, [ir_images[image_pair_index+1], '', '', ''])
                                            asset_style.append(('SPAN', (0, startrow), (3, startrow)))
                                            asset_style.append(('ALIGN', (0, startrow), (3, startrow), 'CENTER'))
                                            asset_style.append(('VALIGN', (0, startrow), (3, startrow),'MIDDLE'))
                                            startrow = startrow+1
                                        elif flag_ir_images[image_pair_index+1] == 0 and flag_ir_images[image_pair_index] != 0:
                                            data5.insert(startrow, [ir_images[image_pair_index], '', '', ''])
                                            asset_style.append(('SPAN', (0, startrow), (3, startrow)))
                                            asset_style.append(('ALIGN', (0, startrow), (3, startrow), 'CENTER'))
                                            asset_style.append(('VALIGN', (0, startrow), (3, startrow),'MIDDLE'))
                                            startrow = startrow + 1

                    if len(asset_images) == 0 and len(ir_images) == 0:

                        if asset_type == 'Sub-Component':
                            asset_top_level = fetch_sublevel_asset_id1(asset_data1[0], asset_data1[-1])
                            print('asset_top_level1', asset_top_level)

                            data5 = [

                            [Paragraph('<b>BASIC INFO</b>', table_style2)],
                            [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_data1[1]), table_style),
                             Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                            [Paragraph("<b>Panel Schedule: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(panel_schedule), table_style),
                             Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                            [Paragraph("<b>Serviceability: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(condition_asset), table_style),
                             Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                            [Paragraph("<b>Arc Flash Label: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(arch_flash_label), table_style),
                             Paragraph("<b>Component Type: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_type), table_style)],
                            [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_data1[2]), table_style),
                             Paragraph("<b>Contained Within: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_top_level), table_style)]

                            ]
                            asset_style = [('BOX', (0, 0), (5, 5), 0.7, colors.black),
                                           ('BACKGROUND', (0, 0),(-1, 0), colors.whitesmoke),
                                           #    ('GRID',(0,0),(-1,-1),2,colors.black),
                                           ('LINEBELOW', (0, 0),(1, 0), 0, colors.black),
                                           ('LINEBELOW', (0, 0),(2, 0), 0, colors.black),
                                           ('LINEBELOW', (0, 0),(3, 0), 0, colors.black),
                                           ('LINEBEFORE', (2, 1), (2, 1), 0.7,colors.black),  # Before "Building"
                                           ('LINEBEFORE', (2, 2), (2, 2), 0.7,colors.black),  # Before "Floor"
                                           ('LINEBEFORE', (2, 3), (2, 3), 0.7,colors.black),  # Before "Room"
                                           ('LINEBEFORE', (2, 4),(2, 4), 0.7, colors.black),   # Before "Component Type"
                                           ('LINEBEFORE', (2, 5),(2, 5), 0.7, colors.black),    # Before "Contained Within"
                                           ('VALIGN', (1, 0), (1, 1), 'LEFT'),
                                           ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                                           ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                           ('SPAN', (0, 0), (-1, 0)),
                                           ]
                        else:
                            data5 = [
                            [Paragraph('<b>BASIC INFO</b>', table_style2)],
                            [Paragraph("<b>Asset Name: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_data1[1]), table_style),
                             Paragraph("<b>Building: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(building), table_style)],
                            [Paragraph("<b>Panel Schedule: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(panel_schedule), table_style),
                             Paragraph("<b>Floor:  </b>",table_style),Paragraph("<font color='black'>{}</font>".format(floor), table_style)],
                            [Paragraph("<b>Serviceability: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(condition_asset), table_style),
                             Paragraph("<b>Room: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(room), table_style)],
                            [Paragraph("<b>Arc Flash Label: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(arch_flash_label), table_style),
                             Paragraph("<b>Component Type: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_type), table_style)],
                            [Paragraph("<b>Asset Class: </b>",table_style),Paragraph("<font color='black'>{}</font>".format(asset_data1[2]), table_style)]

                            ]
                            asset_style = [('BOX', (0, 0), (5, 5), 0.7, colors.black),
                                           ('BACKGROUND', (0, 0),(-1, 0), colors.whitesmoke),
                                           #    ('GRID',(0,0),(-1,-1),2,colors.black),
                                           ('LINEBELOW', (0, 0),(1, 0), 0, colors.black),
                                           ('LINEBELOW', (0, 0),(2, 0), 0, colors.black),
                                           ('LINEBELOW', (0, 0),(3, 0), 0, colors.black),
                                           ('LINEBEFORE', (2, 1), (2, 1), 0.7,colors.black),  # Before "Building"
                                           ('LINEBEFORE', (2, 2), (2, 2), 0.7,colors.black),  # Before "Floor"
                                           ('LINEBEFORE', (2, 3), (2, 3), 0.7,colors.black),  # Before "Room"
                                           ('LINEBEFORE', (2, 4),(2, 4), 0.7, colors.black),  # Before "Component Type"
                                           ('LINEBEFORE', (2, 5), (2, 5), 0.7, colors.black), # Before "Contained Within"
                                           ('VALIGN', (1, 0), (1, 1), 'LEFT'),
                                           ('LEFTPADDING', (0, 0), (-1, -1), 5),
                                           ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                                           ('TOPPADDING', (0, 0), (-1, 0), 5),
                                           ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                                           ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                                           ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                           ('SPAN', (0, 0), (-1, 0)),
                                      
                                           ]
                        data5.insert(startrow, ['', '', '', ''])
                        startrow += 1
                        t = Table(data5, colWidths=129, style=asset_style)
                        flow_obj.append(t)
                        commments = Paragraph("<b>Comments: </b><font color='black'>{}</font>".format(comment), asset_comment_style)
                        flow_obj.append(commments)
                    else:
                        t = Table(data5, colWidths=129, style=asset_style)

                        flow_obj.append(t)
                        commments = Paragraph("<b>Comments: </b><font color='black'>{}</font>".format(comment), asset_comment_style)
                        flow_obj.append(Spacer(1, 13))
                        flow_obj.append(commments)
                    asset_style.append(('LINEABOVE', (0, -1), (-1, -1), 1, colors.black))
                    flow_obj.append(PageBreak())

            return flow_obj
        except Exception as e:
            traceback.print_exc()
            print('Exception ocuured while showing inspection in PDF', e)
            return False

    def create_pdf(self, report_name, wo_id, wo_start_date, company_data, all_assets, all_fedby_data, thermal_data,
                   thermal_fedby_data, thermal_image_data, nec_data, nec_fedby_data,
                    nec_image_data,osha_data, osha_fedby_data,osha_image_data,
                   repair_image_data, repair_assets, repair_fedby_data, replace_assets, replace_image_data, replace_fedby_data,
                   other_assets, other_image_data, other_fedby_data, ultrasonic_assets, ultrasonic_image_data, ultrasonic_fedby_data,
                   all_assets1, asset_image_data, ir_image_data, asset_fedby_data, all_assets_feature_flag, assets_having_issues,
                   thermal_ir_image_data, nfpa_assets, nfpa_image_data):

        try:
            report_title = report_name.replace('/tmp/', '')
            self.title = report_title

            print("Calling Show_Inspection")
            x = self.show_inspection(wo_start_date, company_data, all_assets, all_fedby_data, thermal_data,
                                     thermal_fedby_data, thermal_image_data, nec_data, nec_fedby_data,
                                     nec_image_data,osha_data, osha_fedby_data,
                                     osha_image_data, repair_image_data, repair_assets, repair_fedby_data,
                                     replace_assets, replace_image_data, replace_fedby_data,
                                     other_assets, other_image_data, other_fedby_data,
                                     ultrasonic_assets, ultrasonic_image_data, ultrasonic_fedby_data,
                                     all_assets1, asset_image_data, ir_image_data, asset_fedby_data,
                                     all_assets_feature_flag, assets_having_issues, thermal_ir_image_data, nfpa_assets, nfpa_image_data)

            if x is not False:
                print('building report file')
                self.multiBuild(x)
                print('build complete', report_name)
                res = store_pdf(report_name, wo_id)
                print(res)
            else:
                return False
            if res is not False:
                return report_title
            else:
                return False
        except Exception as e:
            traceback.print_exc()
            print('Exception in create_pdf function', e)
