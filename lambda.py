import json
from db_handler import get_report_data
def lambda_handler(event, context):
    print(event)
    try:
        print("--------lambda start--------")
        for record in event['Records']:
            print("record", record)
            body = json.loads(record["body"])
            print("body", body)
            wo_id = body["wo_id"]
            manual_wo_num = body["manual_wo_number"]
            wo_start_date = body["wo_start_date"]
            user_id = body["user_id"]
            print("input data wo-uuid: ", wo_id, ' wo-id: ', manual_wo_num)
            user_id = body["user_id"]
        if wo_id == None and manual_wo_num == None:
            print("Failure! Report Data is missing!")
        else:
            print(get_report_data(wo_id, manual_wo_num, wo_start_date,user_id))
    
    except Exception as e:
        print(f"Unexpected error occurred: {e}")


