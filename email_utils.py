import os
import time
import base64
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import traceback

SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
TEMPLATE_ID = os.getenv('TEMPLATE_ID')

print('SENDGRID_API_KEY',SENDGRID_API_KEY)
print('SENDER_EMAIL',SENDER_EMAIL)
print('TEMPLATE_ID',TEMPLATE_ID)
def get_mime_type(file_name):
    """Get MIME type based on file extension."""
    if file_name.endswith('.pdf'):
        return 'application/pdf'
    elif file_name.endswith('.xlsx'):
        return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        return 'application/octet-stream' 
    
def send_dynamic_email( receiver_name,receiver_email, manual_wo_num, report_link,site,company,company_logo):

    print("report_link - ",report_link)

    message = Mail(
        from_email = SENDER_EMAIL,
        to_emails= receiver_email,
    )
    print('message',message)
    message.template_id = os.environ.get('TEMPLATE_ID')
    print('TEMPLATE_ID1',message.template_id)
    message.dynamic_template_data = {"user_name":receiver_name,"manual_workorder_number": manual_wo_num,"report_link":report_link,"workorder_site":site,"workorder_company":company,"company_logo":company_logo}
    print(message)
    attempt = 0
    max_attempts=3
    delay=2

    while attempt < max_attempts:
        try:
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            print('sg',sg)
            response = sg.send(message)
            print('response',response)
            print("Email sent successfully")
            return True  
        except Exception as e:
            print(f"Error sending email (attempt {attempt + 1}): {e}")
            traceback.print_exc() 
            attempt += 1
            time.sleep(delay)
