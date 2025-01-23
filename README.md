# Egalvanic IR Report Backend
## Structure
- `bucket_handler.py`: Handles S3 bucket interactions.
- `db_handler.py`: Manages database connections.
- `email_utils.py`: Email utility functions.
- `enum_data.py`: Enums for standardized data.
- `lambda.py`: Entry point for AWS Lambda function.
- `pdf_creator.py`: Generates PDFs.
- `requirements.txt`: Lists dependencies.

## Setup
1. Clone the repository.
2. Install dependencies using `pip install -r requirements.txt`.
3. Configure `.env` with the necessary variables.

Clone the code to your local directory  
`$ git clone https://github.com/kinjal2311-prog/Conduit-backend.git`  

## Generate Report
1. Add below given keys and values in lambda.py
 - wo_id = ''
 - wo_num = ''
 - wo_start_date = ''
 - user_id = ''
 - pdf_create = get_report_data(wo_id=wo_id,wo_num=wo_num, wo_start_date=wo_start_date)
2. Run
 - (Windows) python lambda.py
 - (Linux) python3 lambda.py


