import os
import psycopg2
from bucket_handler import get_logo
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import inch
from pdf_creator import ReportPrinter
from email_utils import send_dynamic_email
import urllib.parse
# from dotenv import load_dotenv
# load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
UPLOAD_BUCKET_NAME = os.getenv('UPLOAD_BUCKET_NAME')

def fetch_fed_by_names(cursor, connection, thermal_fedby_mapping):
    fedby_data={}
    for mapping_record in thermal_fedby_mapping:
        thermal_asset_id = mapping_record[0]
        fedby_asset_name = None
        if mapping_record[2] == True:
            # get parent asset name from WOOnboardingAssets
            fedby_q_woobasset = """select wa.asset_name from "WOOnboardingAssets" wa where wa.woonboardingassets_id = %s"""
            cursor.execute(fedby_q_woobasset, (mapping_record[3],))
            fedby_asset_name = cursor.fetchone()
        else:
            # get parent asset name from Assets
            fedby_q_assets = """select a.name from "Assets" a where a.asset_id=%s """
            cursor.execute(fedby_q_assets, (mapping_record[3],))
            fedby_asset_name = cursor.fetchone()

        if fedby_asset_name is not None:
            if thermal_asset_id not in fedby_data.keys():
                fedby_data[thermal_asset_id] = [fedby_asset_name[0]]
            else:
                fedby_assets = fedby_data[thermal_asset_id]
                fedby_assets.append(fedby_asset_name[0])
                fedby_data[thermal_asset_id] = fedby_assets
    return fedby_data

#query to check for issue in asset for images
def check_issue_in_asset(cursor,connection,woobassets):
    issue_query="""select * from "WOLineIssue" wi where wi.woonboardingassets_id =%s and wi.is_deleted =false """
    cursor.execute(issue_query, (woobassets,))
    result = cursor.fetchall()
    print(' ')
    print('result',result)
    print(' ')
    return result 

# use these function when assets having issue and client need only 2 ir images
def fetch_image_labels(cursor, connection, woobassets):
    image_data = {}
    for asset in woobassets:
        if check_issue_in_asset(cursor,connection,asset[0]):
            print(f"No issues found for asset ID {asset[0]}. Skipping...")
            image_q = """WITH LatestImages AS (
                    SELECT
                        wl.irwoimagelabelmapping_id,
                        wl.modified_at,
                        ROW_NUMBER() OVER (PARTITION BY wl.irwoimagelabelmapping_id ORDER BY wl.modified_at DESC) AS rn
                    FROM
                        "WOlineIssueImagesMapping" wl
                    WHERE
                        wl.is_deleted = false
                )
                SELECT
                    ir.woonboardingassets_id,
                    ir.s3_image_folder_name,
                    ir.ir_image_label,
                    ir.visual_image_label,
                    ir.is_deleted,
                    ir.irwoimagelabelmapping_id
                FROM
                    "IRWOImagesLabelMapping" ir
                LEFT JOIN LatestImages li
                    ON ir.irwoimagelabelmapping_id = li.irwoimagelabelmapping_id AND li.rn = 1
                WHERE
                    ir.woonboardingassets_id = %s
                    AND ir.is_deleted = false
                    AND (li.irwoimagelabelmapping_id IS NULL OR li.modified_at IS NOT NULL)
                ORDER BY
                    ir.ir_image_label ASC,
                    li.modified_at DESC"""
            cursor.execute(image_q, (asset[0],  ))
            print('aasset[0]',asset[0])
            all_image_records = cursor.fetchall()
            image_records = all_image_records[:2]
            print('image_records',image_records)
            if len(image_records):
                image_data[asset[0]] = image_records
    return image_data

# use these function when assets not having issue and client need all ir photos without condition
def fetch_ir_visual_image_labels1(cursor, connection, woobassets):
    image_data = {}
    for asset in woobassets:
        image_q = """WITH LatestImages AS (
                SELECT
                    wl.irwoimagelabelmapping_id,
                    wl.modified_at,
                    ROW_NUMBER() OVER (PARTITION BY wl.irwoimagelabelmapping_id ORDER BY wl.modified_at DESC) AS rn
                FROM
                    "WOlineIssueImagesMapping" wl
                WHERE
                    wl.is_deleted = false
            )
            SELECT
                ir.woonboardingassets_id,
                ir.s3_image_folder_name,
                ir.ir_image_label,
                ir.visual_image_label,
                ir.is_deleted,
                ir.irwoimagelabelmapping_id
            FROM
                "IRWOImagesLabelMapping" ir
            LEFT JOIN LatestImages li
                ON ir.irwoimagelabelmapping_id = li.irwoimagelabelmapping_id AND li.rn = 1
            WHERE
                ir.woonboardingassets_id = %s
                AND ir.is_deleted = false
                AND (li.irwoimagelabelmapping_id IS NULL OR li.modified_at IS NOT NULL)
            ORDER BY
                ir.ir_image_label ASC,
                li.modified_at DESC"""
        cursor.execute(image_q, (asset[0],  ))
        print('aasset[0]',asset[0])
        all_image_records = cursor.fetchall()
        print('image_records',all_image_records)

        if all_image_records:
            image_data[asset[0]] = all_image_records
    return image_data

# NEC
def fetch_nec_labels(cursor, connection, wolineissue):
    image_data = {}
    for asset in wolineissue:
        image_q_nec = """select wm.wo_line_issue_id, wm.image_file_name, wl.issue_type,wm.image_duration_type_id from "WOlineIssueImagesMapping" as wm 
                            join "WOLineIssue" as wl on wm.wo_line_issue_id = wl.wo_line_issue_id where wm.wo_line_issue_id = %s  
                            AND wl.issue_type = 1
                            AND wl.issue_caused_id = 2
                            AND wm.is_deleted=false"""
        cursor.execute(image_q_nec, (asset[0],))
        nec_image_records = cursor.fetchall()
        image_records_nec = nec_image_records[:1]

        if image_records_nec:
            image_data[asset[0]] = image_records_nec
    return image_data

# OSHA
def fetch_osha_labels(cursor, connection, wolineissue):
    image_data = {}
    for asset in wolineissue:
        image_q_osha = """select wm.wo_line_issue_id, wm.image_file_name, wl.issue_type,wm.image_duration_type_id from "WOlineIssueImagesMapping" as wm 
                            join "WOLineIssue" as wl on wm.wo_line_issue_id = wl.wo_line_issue_id where wm.wo_line_issue_id = %s  
                            AND wl.issue_type = 1
                            AND wl.issue_caused_id = 1
                            AND wm.is_deleted=false"""
        cursor.execute(image_q_osha, (asset[0],))
        osha_image_records = cursor.fetchall()
        image_record_osha = osha_image_records[:1]

        if image_record_osha:
            image_data[asset[0]] = image_record_osha
    return image_data

# Repair
def fetch_repair_labels(cursor, connection, wolineissue):
    image_data = {}
    for asset in wolineissue:

        image_q_repair = """select wl.wo_line_issue_id, wm.image_file_name, wl.issue_type,wm.image_duration_type_id from "WOlineIssueImagesMapping" as wm 
                            join "WOLineIssue" as wl on wm.wo_line_issue_id = wl.wo_line_issue_id where wl.wo_line_issue_id = %s  
                            AND wl.issue_type = 3
                            AND wm.is_deleted=false"""

        cursor.execute(image_q_repair, (asset[0],))

        repair_image_records = cursor.fetchall()
        image_record_repair = repair_image_records[:1]
        if image_record_repair:
                image_data[asset[0]] = image_record_repair

    return image_data

# Replace
def fetch_replace_labels(cursor, connection, wolineissue):
    image_data = {}
    for asset in wolineissue:

        image_q_replace = """select wl.wo_line_issue_id, wm.image_file_name, wl.issue_type,wm.image_duration_type_id from "WOlineIssueImagesMapping" as wm 
                            join "WOLineIssue" as wl on wm.wo_line_issue_id = wl.wo_line_issue_id where wl.wo_line_issue_id = %s  
                            AND wl.issue_type = 4
                            AND wm.is_deleted=false"""

        cursor.execute(image_q_replace, (asset[0],))
        replace_image_records = cursor.fetchall()
        image_record_replace = replace_image_records[:1]

        if image_record_replace:
                image_data[asset[0]] = image_record_replace

    return image_data

# Other
def fetch_other_labels(cursor, connection, wolineissue):
    image_data = {}
    for asset in wolineissue:

        image_q_other = """select wl.wo_line_issue_id, wm.image_file_name, wl.issue_type,wm.image_duration_type_id from "WOlineIssueImagesMapping" as wm 
                            join "WOLineIssue" as wl on wm.wo_line_issue_id = wl.wo_line_issue_id where wl.wo_line_issue_id = %s  
                            AND wl.issue_type = 6
                            AND wm.is_deleted=false"""

        cursor.execute(image_q_other, (asset[0],))
        other_image_records = cursor.fetchall()
        image_record_other = other_image_records[:1]
        
        if image_record_other:
                image_data[asset[0]] = image_record_other

    return image_data

# Ultrasonic
def fetch_ultrasonic_labels(cursor, connection, wolineissue):
    image_data = {}
    for asset in wolineissue:

        image_q_ultrasonic = """select wl.wo_line_issue_id, wm.image_file_name, wl.issue_type,wm.image_duration_type_id from "WOlineIssueImagesMapping" as wm 
                                join "WOLineIssue" as wl on wm.wo_line_issue_id = wl.wo_line_issue_id 
                                where wl.wo_line_issue_id = %s  
                                AND wl.issue_type = 9
                                AND wm.is_deleted=false"""

        cursor.execute(image_q_ultrasonic, (asset[0],))
        ultrasonic_image_records = cursor.fetchall()
        image_records_ultra = ultrasonic_image_records[:1]

        if image_records_ultra:
                image_data[asset[0]] = image_records_ultra

    return image_data

# use these function when assets having issue and client need only 2 images for profile,shcedule photo        
def fetch_asset_labels(cursor, connection, woobassets,all_assets_feature_flag,assets_having_issues):
    image_data = {}
    for asset in woobassets:
        if not all_assets_feature_flag:
            if asset[0]  not in assets_having_issues:
                continue
            else:
                pass
        if check_issue_in_asset(cursor,connection,asset[0]):
            print(f"No issues found for asset ID {asset[0]}. Skipping...")
                
            image_q_asset = """select wa.woonboardingassets_id, waim.asset_photo, waim.asset_photo_type 
                                from "WOOnboardingAssetsImagesMapping" as waim 
                                join "WOOnboardingAssets" as wa on waim.woonboardingassets_id = wa.woonboardingassets_id 
                                where wa.woonboardingassets_id = %s  
                                AND waim.is_deleted=false
                                AND (waim.asset_photo_type = 1 OR waim.asset_photo_type = 14)  
                                ORDER BY waim.asset_photo_type, waim.created_at"""
            cursor.execute(image_q_asset, (asset[0],))
            asset_image_records = cursor.fetchall()

            # Separate asset photos and schedule photos
            asset_photos = [record for record in asset_image_records if record[2] == 1]  # Asset photo (type 1)
            schedule_photos = [record for record in asset_image_records if record[2] == 14]  # Schedule photo (type 14)

            # Ensure that only one asset photo and one schedule photo are selected
            if len(asset_photos) > 0 and len(schedule_photos) > 0:
                image_data[asset[0]] = [asset_photos[0], schedule_photos[0]]  # Store the first asset and first schedule photo
            elif len(asset_photos) == 0 and len(schedule_photos) > 0:
                image_data[asset[0]] = ['   ',schedule_photos[0]]  # Store the first asset and first schedule photo
            elif len(asset_photos) > 0 and len(schedule_photos) == 0:
                image_data[asset[0]] = [asset_photos[0],'   ']  # Store the first asset and first schedule photo

    return image_data

# use these function when assets not having issue and client need all photos without condition
def fetch_asset_labels1(cursor, connection, woobassets,all_assets_feature_flag,assets_having_issues):
    image_data = {}
    for asset in woobassets:
        if not all_assets_feature_flag:
            if asset[0]  not in assets_having_issues:
                continue
            else:
                pass
        
        image_q_asset = """select wa.woonboardingassets_id, waim.asset_photo,waim.asset_photo_type from "WOOnboardingAssetsImagesMapping" as waim 
                            join "WOOnboardingAssets" as wa on waim.woonboardingassets_id = wa.woonboardingassets_id 
                            where wa.woonboardingassets_id = %s  
                            AND waim.is_deleted=false
                            and (waim.asset_photo_type = 1  OR waim.asset_photo_type = 2 OR waim.asset_photo_type = 14)  
                            ORDER BY waim.created_at"""
        cursor.execute(image_q_asset, (asset[0],))
        asset_image_records = cursor.fetchall()
    
        if asset_image_records:
                image_data[asset[0]] = asset_image_records

    return image_data


def fetch_sublevel_woonboardingasset_id(cursor,woonboarding_toplevel_asset_id):
    sublevel_asset_ids_q = '''select sublevelcomponent_asset_id 
                                from "WOlineSubLevelcomponentMapping" wslm 
                                where wslm.woonboardingassets_id = %s
                                and wslm.is_sublevelcomponent_from_ob_wo = True 
                                and wslm.is_deleted = False'''
                        
    cursor.execute(sublevel_asset_ids_q, (woonboarding_toplevel_asset_id, ))  
    sub_level_asset_result = cursor.fetchall()
    sub_level_asset = [row[0] for row in sub_level_asset_result]
    return sub_level_asset
                      

def arrange_assets(cursor,assets_dict):
    arranged_assets = []
    for asset_id, asset_data in assets_dict.items():

        if asset_data['level'] == 1:

            arranged_assets.append(asset_data['row'])

            sublevel_ids = fetch_sublevel_woonboardingasset_id(cursor,asset_id)

            if sublevel_ids:
                for sub_id in sublevel_ids:
                    if sub_id in assets_dict.keys():
                        arranged_assets.append(assets_dict[sub_id]['row'])

    return arranged_assets

def arrange_assets2(cursor,assets_dict):
    arranged_assets = []
    top_level_asset = []
    
    for asset_id, asset_data in assets_dict.items():
        if asset_data['level'] == 1:
            top_level_asset.append(asset_id)
            arranged_assets.append(asset_data['row'])
            sublevel_ids = fetch_sublevel_woonboardingasset_id(cursor,asset_id)
            if sublevel_ids:
                for sub_id in sublevel_ids:
                    if sub_id in assets_dict.keys():
                        arranged_assets.append(assets_dict[sub_id]['row'])


    return arranged_assets

# overview
def fetch_asset_is_top(cursor,woonboarding_asset_id):
    is_asset_top_q = '''SELECT ta.component_level_type_id , wa.asset_name
            FROM "WOOnboardingAssets" wa 
            JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id
            where wa.woonboardingassets_id = %s'''
                        
    cursor.execute(is_asset_top_q, (woonboarding_asset_id,))  
    is_asset_top_result = cursor.fetchone()
    if is_asset_top_result[0] == 1:
        print('true')
        return True
    else:
        return False

#top level data from sub level 
def fetch_toplevel_asset_id(cursor,woonboarding_toplevel_asset_id,is_wo_line_for_exisiting_asset,wo_id):
    print('is_wo_line_for_exisiting_asset',is_wo_line_for_exisiting_asset)
    print(type(is_wo_line_for_exisiting_asset))  
    print('wo_id_12',wo_id)    
    top_level_asset_result_1 = None                      
    if is_wo_line_for_exisiting_asset:
        toplevel_asset_ids_q = '''select w2.woonboardingassets_id,w2.toplevelcomponent_asset_id,wa.asset_name 
                               from "WOlineTopLevelcomponentMapping" w2 left join "WOOnboardingAssets" wa 
                               on (wa.asset_id = w2.toplevelcomponent_asset_id or wa.woonboardingassets_id = w2.toplevelcomponent_asset_id)
                               left join "WOOnboardingAssets" w3 on w3.woonboardingassets_id =w2.woonboardingassets_id 
                               where w2.woonboardingassets_id =%s
                               and w2.is_toplevelcomponent_from_ob_wo = true
                               and w3.wo_id =%s
                               and w2.is_deleted = false'''
        cursor.execute(toplevel_asset_ids_q, (woonboarding_toplevel_asset_id,wo_id))  
        top_level_asset_result_1 = cursor.fetchone()  
        print('top_level_asset_result21',top_level_asset_result_1)

    if top_level_asset_result_1 is None:
        # print("No results found.")
        return '   '
   
    return top_level_asset_result_1

# sub level
def fetch_toplevel_woonboardingasset_id(cursor,woonboarding_toplevel_asset_id,is_wo_line_for_exisiting_asset,wo_id):
    print('is_wo_line_for_exisiting_asset',is_wo_line_for_exisiting_asset)
    print(type(is_wo_line_for_exisiting_asset))   
    print('wo_id21',wo_id)                         
    if is_wo_line_for_exisiting_asset:
        toplevel_asset_ids_q = '''select w2.woonboardingassets_id
                               from "WOlineSubLevelcomponentMapping" w2 left join "WOOnboardingAssets" wa 
                               on (wa.asset_id = w2.sublevelcomponent_asset_id or wa.woonboardingassets_id = w2.sublevelcomponent_asset_id)
                               left join "WOOnboardingAssets" w3 on w3.woonboardingassets_id =w2.woonboardingassets_id 
                               where wa.woonboardingassets_id =%s
                               and (w2.is_sublevelcomponent_from_ob_wo = false)
                               and w3.wo_id =%s
                               and w2.is_deleted = false'''
        cursor.execute(toplevel_asset_ids_q, (woonboarding_toplevel_asset_id,wo_id))  
        top_level_asset_result = cursor.fetchone()  
        print('top_level_asset_result',top_level_asset_result)

    else:
        toplevel_asset_ids_q = '''select w2.woonboardingassets_id
                                from "WOlineSubLevelcomponentMapping" w2 
                                left join "WOOnboardingAssets" wa 
                               on wa.woonboardingassets_id = w2.sublevelcomponent_asset_id 
                               where wa.woonboardingassets_id = %s
                                and w2.is_sublevelcomponent_from_ob_wo = true
                                and w2.is_deleted = false'''
        # if toplevel_asset_ids_q:
        cursor.execute(toplevel_asset_ids_q, (woonboarding_toplevel_asset_id,))  
        top_level_asset_result = cursor.fetchone() 
    # when top level is not assigned to sub level
    # if top_level_asset_result is None:
    #     fallback_query = '''select woonboardingassets_id
    #                         from "WOOnboardingAssets" 
    #                         where woonboardingassets_id = %s'''
    #     cursor.execute(fallback_query, (woonboarding_toplevel_asset_id,))
    #     top_level_asset_result = cursor.fetchone()
    #     print('Fallback top_level_asset_result from WOOnboardingAssets:', top_level_asset_result)   
    if top_level_asset_result is None:
        print('No top-level asset found. Returning placeholder value.')
        return "NO_PARENT"
    return top_level_asset_result[0]

def flatten_list(nested_list):
    flattened = []
    seen = set()  # To track unique elements
    for item in nested_list:
        if isinstance(item, list):
            flattened.extend(flatten_list(item))
        else:
            if item not in seen:
                flattened.append(item)
                seen.add(item)  # Add to the set to prevent duplicates
    return flattened

# Top level
def all_asset_list1(cursor,asset_dict):
    final_list = {}
    added_top_lst = []

    for i in asset_dict.keys():
        print(f"Processing asset {i}")
        
        # Determine if the asset is top-level or sub-level
        is_asset_top = fetch_asset_is_top(cursor, i)
        print(f"Is asset {i} top-level? {is_asset_top}")
        
        if is_asset_top:
            # If it's a top-level asset and not already added, initialize the list
            if i not in added_top_lst:
                final_list[i] = [asset_dict[i]]
                added_top_lst.append(i)
                print(f"Added top-level asset {i}")
        else:
            print(f"Skipping sub-level asset {i}")
    # Initialize an empty list to store the fully flattened result
    fully_flattened_list1 = []

    # Flatten all lists and sublists in final_list in order
    for top_level_asset, sub_assets in final_list.items():
        fully_flattened_list1.extend(flatten_list(sub_assets))

    return fully_flattened_list1

# Top+Sub Level overview table
def all_asset_list(cursor,asset_dict):
    final_list = {}
    added_top_lst = []
    print('asset_dict21',asset_dict)
    for i in asset_dict.keys():
        print(f"Processing asset {i}")
        is_asset_top = fetch_asset_is_top(cursor, i)
        print(f"Is asset {i} top-level? {is_asset_top}")

        if is_asset_top:
            if i not in added_top_lst:
                final_list[i] = [asset_dict[i]]
                added_top_lst.append(i)
                print(f"Added top-level asset {i}")
        else:
            print('asset_dict:', asset_dict[i][-1])
            top_of_sub = fetch_toplevel_woonboardingasset_id(cursor, i, asset_dict[i][-2], asset_dict[i][-1])
            print(f"Top-level asset for sub-level {i} is {top_of_sub}")
            if top_of_sub:

                if top_of_sub in added_top_lst:
                    print('final_list[top_of_sub]',final_list[top_of_sub])
                    final_list[top_of_sub].append(asset_dict[i])
                    print('final_list[top_of_sub[1]]',final_list)
                    print('asset_dict[i]',asset_dict[i])
                    print(f"Appended sub-level asset {i} to top-level asset {top_of_sub}")
                else:
                    if asset_dict.get(top_of_sub):
                        final_list[top_of_sub] = [asset_dict[top_of_sub], asset_dict[i]]
                        added_top_lst.append(top_of_sub)
                        print(f"Added both top-level asset {top_of_sub} and sub-level asset {i}")
                    else:
                        print(f"Warning: Top-level asset {top_of_sub} not found in asset_dict for sub-level asset {i}")
    # Initialize the flattened list
    fully_flattened_list = []

    for top_level_asset, sub_assets in final_list.items():
        fully_flattened_list.extend(flatten_list(sub_assets))
        print('fully_flattened_list',fully_flattened_list)
        print(len(fully_flattened_list))
        
    return fully_flattened_list

# asset table 
def fetch_asset_is_top1(cursor,woonboarding_asset_id):
    is_asset_top_q = '''SELECT ta.component_level_type_id,wi.is_deleted 
            FROM "WOOnboardingAssets" wa 
            join "WOLineIssue" wi on wa.woonboardingassets_id  = wi.woonboardingassets_id 
            JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id
            where wa.woonboardingassets_id=%s
            and wi.is_deleted = false '''
                        
    cursor.execute(is_asset_top_q, (woonboarding_asset_id, ))  
    is_asset_top_result = cursor.fetchone()
    if is_asset_top_result is None:
        # If no result, do nothing and continue
        pass
    elif is_asset_top_result[0] == 1:
        return True
    else:
        return False

# Top+Sub Level asset table
def all_asset_list2(cursor,asset_dict):
    final_list = {}
    added_top_lst = []
    print('asset_dict21',asset_dict)
    for i in asset_dict.keys():
        print(f"Processing asset {i}")
        is_asset_top = fetch_asset_is_top(cursor, i)
        print(f"Is asset {i} top-level? {is_asset_top}")

        if is_asset_top:
            if i not in added_top_lst:
                final_list[i] = [asset_dict[i]]
                added_top_lst.append(i)
                print(f"Added top-level asset {i}")
        else:
            print('asset_dict:', asset_dict[i][-1])
            top_of_sub = fetch_toplevel_woonboardingasset_id(cursor, i, asset_dict[i][-2], asset_dict[i][-1])
            print(f"Top-level asset for sub-level {i} is {top_of_sub}")
            top_level_asset_name = "N/A" 
            if top_of_sub:

                top_level_asset_data = fetch_toplevel_asset_id(cursor, i, asset_dict[i][-2], asset_dict[i][-1])
                if top_level_asset_data:
                    top_level_asset_name = top_level_asset_data[2]
                    print(f"Top-level asset name: {top_level_asset_name}")
                else:
                    print("Top-level asset data is None, skipping.")
                    # top_level_asset_name = 'None'
                print(f"Top-level asset name: {top_level_asset_name}")
                print('asset_dict[i]1',asset_dict[i])
                asset_dict_temp = list(asset_dict[i])  # Convert to list if it's a tuple
                asset_dict_temp.append(top_level_asset_name)
                asset_dict[i] = tuple(asset_dict_temp)
                if top_of_sub in added_top_lst:
                    print('final_list[top_of_sub]',final_list[top_of_sub])
                    final_list[top_of_sub].append(asset_dict[i])
                    print('final_list[top_of_sub[1]]',final_list)
                    print('asset_dict[i]',asset_dict[i])

                    print(f"Appended sub-level asset {i} to top-level asset {top_of_sub} with it's top level name {top_level_asset_name}")
                else:
                    if asset_dict.get(top_of_sub):
                        final_list[top_of_sub] = [asset_dict[top_of_sub], asset_dict[i]]
                        added_top_lst.append(top_of_sub)
                        print(f"Added both top-level asset {top_of_sub} and sub-level asset {i}")
                    else:
                        print(f"Warning: Top-level asset {top_of_sub} not found in asset_dict for sub-level asset {i}")
    # Initialize the flattened list
    fully_flattened_list = []

    for top_level_asset, sub_assets in final_list.items():
        fully_flattened_list.extend(flatten_list(sub_assets))
        print('fully_flattened_list',fully_flattened_list)
        print(len(fully_flattened_list))
        
    return fully_flattened_list

#thermal before after images
def fetch_thermal_labels(cursor, connection, wolineissue):
    image_data = {}
    for thermal_asset in wolineissue:

        image_q_thermal = """select wm.wo_line_issue_id,wl.wo_line_issue_id, wm.image_file_name, wl.issue_type,wm.image_duration_type_id 
                            from "WOlineIssueImagesMapping" as wm 
                            join "WOLineIssue" as wl on wm.wo_line_issue_id = wl.wo_line_issue_id where wm.wo_line_issue_id = %s  
                            AND wl.issue_type = 2
                            AND wm.is_deleted=false"""
        print('image_q_thermal',image_q_thermal)

        cursor.execute(image_q_thermal, (thermal_asset[22],))
        thermal_image_records = cursor.fetchall()
        print('asset[0]',thermal_asset[22])
        print("Query executed:", image_q_thermal)
        print("Parameters:", (thermal_asset[22],))
        print('thermal_image',thermal_image_records)
    
        if thermal_image_records:
                image_data[thermal_asset[22]] = thermal_image_records

    return image_data

#with issue in asset and thermal
def fetch_ir_visual_image_labels(cursor, connection, wolineissue):
    image_data = {}
    for asset in wolineissue:
        image_q = """select wl.wo_line_issue_id ,i2.s3_image_folder_name ,i2.ir_image_label 
                    ,i2.visual_image_label,w1.wo_line_issue_id, w1.image_duration_type_id  
                    from "WOlineIssueImagesMapping" w1 
                    left join "WOLineIssue" wl on w1.wo_line_issue_id = wl.wo_line_issue_id
                    left join "IRWOImagesLabelMapping" i2 on w1.irwoimagelabelmapping_id =i2.irwoimagelabelmapping_id
                    where w1.wo_line_issue_id = %s 
                    and w1.image_duration_type_id = 3 and w1.is_deleted=false 
                    ORDER BY 
                    CASE 
                        WHEN i2.ir_image_label IS NOT NULL THEN i2.ir_image_label
                        ELSE i2.visual_image_label
                    END ASC,
                    i2.ir_image_label ASC, 
                    i2.visual_image_label ASC;"""
        cursor.execute(image_q, (asset[22],  ))
        print('aasset[0]',asset[22])
        all_image_records = cursor.fetchall()
        image_records = all_image_records[:2]
        # print('all_image_records',all_image_records)
        print('image_reocrds',image_records)

        if image_records:
            image_data[asset[22]] = image_records
    return image_data


def fetch_nfpa_labels(cursor, connection, wolineissue):
    image_data = {}
    for asset in wolineissue:

        image_q_nfpa = """select wl.wo_line_issue_id, wm.image_file_name, wl.issue_type,wm.image_duration_type_id 
                                from "WOlineIssueImagesMapping" as wm 
                                join "WOLineIssue" as wl on wm.wo_line_issue_id = wl.wo_line_issue_id 
                                where wl.wo_line_issue_id = %s  
                                AND wl.issue_type = 1
                                AND wl.issue_caused_id = 14
                                AND wm.is_deleted=false"""

        cursor.execute(image_q_nfpa, (asset[0],))

        nfpa_image_records = cursor.fetchall()
        # image_record_nfpa = nfpa_image_records[:2]
        print('nfpa_image_records',nfpa_image_records)
        before_image = None
        after_image = None

        for record in nfpa_image_records:
            if record[3] == 1:  # Before image
                before_image = record
            elif record[3] == 2:  # After image
                after_image = record

            # Break the loop early if we already have both images
            if before_image and after_image:
                break

        # Include only if both before and after images are available
        if before_image and after_image:
            image_data[asset[0]] = [before_image, after_image]
        elif after_image and not before_image:  # Only after image exists
            image_data[asset[0]] = [after_image]
        elif before_image and not after_image:  # Only before image exists
            image_data[asset[0]] = [before_image]

    return image_data


def fetch_user_email(cursor, connection, user_id):

    user_email_q = """select u.firstname, u.email from "User" u where u."uuid" = %s"""
    cursor.execute(user_email_q, (user_id,))
    email_record = cursor.fetchone()
    return email_record[0], email_record[1]


def get_report_data(wo_id, wo_num, wo_start_date,user_id):
    
    try:
        connection = psycopg2.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
        cursor = connection.cursor()

        print("Connected to db", connection)
        all_assets1 = []
        asset_image_data = {}
        ir_image_data = {}
        asset_fedby_data = {}
        thermal_assets = []
        nec_assets = []
        osha_assets = []
        thermal_image_data = {}
        thermal_ir_image_data = {}
        nec_image_data = {}
        osha_image_data = {}
        nfpa_assets = []
        nfpa_fedby_data = {}
        nfpa_image_data = {}
        thermal_fedby_data = {}
        nec_fedby_data = {}
        osha_fedby_data = {}
        all_fedby_data = {}
        repair_fedby_data = {}
        repair_image_data = {}
        repair_assets = []
        replace_fedby_data = {}
        replace_image_data = {}
        replace_assets = []
        other_fedby_data ={}
        other_image_data ={}
        other_assets = []
        ultrasonic_fedby_data = {}
        ultrasonic_image_data = {}
        ultrasonic_assets = []
        assets_having_issues = []

        all_assets_q = '''select wa.woonboardingassets_id, 
                        ta.asset_name, 
                        wa.asset_class_name, 
                        tmib.temp_master_building_name, 
                        tmf.temp_master_floor_name,
                        tmir.temp_master_room_name,
                        ta.temp_master_section ,
                        ta.created_at, 
                        wa.other_notes,
                        ta.maintenance_index_type,
                        ta.panel_schedule,
                        ta.arc_flash_label_valid,
                        ta.component_level_type_id,
                        wl.issue_type,
                        wl.thermal_classification_id,
                        wl.is_issue_linked_for_fix,
                        wl.wo_line_issue_id,
                        wa.is_wo_line_for_exisiting_asset,
                        wa.wo_id
                        from "WOOnboardingAssets" wa 
                        LEFT JOIN "WOLineIssue" wl ON wa.woonboardingassets_id = wl.woonboardingassets_id
                        JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id
                        JOIN "TempMasterBuilding" tmib ON ta.temp_master_building_id = tmib.temp_master_building_id
                        JOIN "TempMasterFloor" tmf ON ta.temp_master_floor_id = tmf.temp_master_floor_id
                        JOIN "TempMasterRoom" tmir ON ta.temp_master_room_id = tmir.temp_master_room_id 
                        where wa.wo_id = %s
                        and wa.status=15
                        and wa.is_deleted = false
                        ORDER BY 
                            CASE
                                WHEN wl.issue_type = 2 THEN 0 -- Highest priority
                                WHEN wl.issue_type = 9 THEN 1   
                                WHEN wl.issue_type = 1 THEN 2 
                                WHEN wl.issue_type = 4 THEN 3
                                WHEN wl.issue_type = 3 THEN 4 
                                WHEN wl.issue_type = 6 THEN 5
                                ELSE 6 -- All other issue types
                            END,
                            CASE wl.thermal_classification_id
                                WHEN 5 THEN 1
                                WHEN 4 THEN 2
                                WHEN 6 THEN 3
                                WHEN 3 THEN 4
                                WHEN 2 THEN 5
                                WHEN 1 THEN 6
                                ELSE 7
                            END ASC,
                            CASE ta.maintenance_index_type
                                WHEN 3 THEN 1
                                WHEN 2 THEN 2
                                WHEN 1 THEN 3
                                ELSE 4
                            END asc,
                            CASE ta.component_level_type_id
                                WHEN 1 THEN 1
                                WHEN 2 THEN 2
                                ELSE 3
                            END asc;'''
        
        
        cursor.execute(all_assets_q, (wo_id, ))

        all_assets_temp = cursor.fetchall()
        print(len(all_assets_temp))

        asset_dict = {}
        for asset in all_assets_temp:
            if asset[0] not in asset_dict:
                asset_dict[asset[0]] = asset

        # The final count of unique assets
        all_assets = list(asset_dict.values())
        all_assets = all_asset_list(cursor,asset_dict)
        print(len(all_assets))
       
        company_q = """select s.site_name ,cc.client_company_name , cc.owner_address ,c.company_logo , 
                        c.company_thumbnail_logo,s.customer_address,c.company_name,wa.ir_wo_export_pdf_at, s.profile_image,
                        c.company_id, s.site_id
                        from "WorkOrders" wa join "Sites" s on wa.site_id =s.site_id  
                        join "Company" c on s.company_id=c.company_id 
                        join "ClientCompany" cc on cc.client_company_id = s.client_company_id
                        where wo_id = %s limit 1 """
        cursor.execute(company_q, (wo_id,))
        company_data = cursor.fetchone()
        print(len(company_data))

        # Asset Flag
        company_all_asset_feature_q = """select cfm.is_required 
                        from "Features" f 
                        join "CompanyFeatureMappings" cfm 
                        on f.feature_id = cfm.feature_id
                        where f.feature_name = 'generate_ir_report_for_all_assets'
                        and cfm.company_id = %s """
        cursor.execute(company_all_asset_feature_q, (company_data[-2],))
        all_assets_feature_flag = cursor.fetchone()
        print(all_assets_feature_flag)

        # top-sub level flag
        company_top_sub_feature_q = """select cfm.is_required 
                        from "Features" f 
                        join "CompanyFeatureMappings" cfm 
                        on f.feature_id = cfm.feature_id
                        where f.feature_name = 'is_toplevel_required_for_report'
                        and cfm.company_id = %s """
        cursor.execute(company_top_sub_feature_q, (company_data[-2],))
        all_top_sub_feature_flag = cursor.fetchone()
        print("all_top_sub_feature_flag > ", all_top_sub_feature_flag)
        if not all_assets_feature_flag[0]:
                
            assets_having_issues_q = """
            SELECT wa.woonboardingassets_id
            FROM "WOOnboardingAssets" wa
            JOIN "WOLineIssue" wl ON wa.woonboardingassets_id = wl.woonboardingassets_id
            JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id
            WHERE wa.wo_id = %s
            AND wa.status = 15
            AND wl.is_deleted = false"""

            cursor.execute(assets_having_issues_q, (wo_id,))
            result = cursor.fetchall()
            assets_having_issues = [row[0] for row in result]
            print(len(assets_having_issues))
            print(len(result))
    
        

        # ################### assets records #######################
        if len(all_assets) > 0:
            all_assets_q = '''select wa.woonboardingassets_id, 
                        ta.asset_name, 
                        wa.asset_class_name, 
                        tmib.temp_master_building_name, 
                        tmf.temp_master_floor_name,
                        tmir.temp_master_room_name,
                        ta.temp_master_section,
                        ta.created_at, 
                        wa.other_notes,
                        ta.maintenance_index_type,
                        ta.panel_schedule,
                        ta.arc_flash_label_valid,
                        ta.component_level_type_id,
                        wl.issue_type,
                        wl.thermal_classification_id,
                        wl.is_issue_linked_for_fix,
                        wl.wo_line_issue_id,
                        wa.is_wo_line_for_exisiting_asset,
                        wa.wo_id
                        from "WOOnboardingAssets" wa 
                        LEFT JOIN "WOLineIssue" wl ON wa.woonboardingassets_id = wl.woonboardingassets_id
                        JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id
                        JOIN "TempMasterBuilding" tmib ON ta.temp_master_building_id = tmib.temp_master_building_id
                        JOIN "TempMasterFloor" tmf ON ta.temp_master_floor_id = tmf.temp_master_floor_id
                        JOIN "TempMasterRoom" tmir ON ta.temp_master_room_id = tmir.temp_master_room_id 
                        WHERE wa.wo_id = %s
                        AND wa.status = 15
                        and wl.is_deleted = false
                        AND tmib.is_deleted = false
                        AND tmf.is_deleted = false
                        AND tmir.is_deleted = false
                        ORDER BY 
                            CASE
                                WHEN wl.issue_type = 2 THEN 0 -- Highest priority
                                WHEN wl.issue_type = 9 THEN 1   
                                WHEN wl.issue_type = 1 THEN 2 
                                WHEN wl.issue_type = 4 THEN 3
                                WHEN wl.issue_type = 3 THEN 4 
                                WHEN wl.issue_type = 6 THEN 5
                                ELSE 6 -- All other issue types
                            END,
                            CASE wl.thermal_classification_id
                                WHEN 5 THEN 1
                                WHEN 4 THEN 2
                                WHEN 6 THEN 3
                                WHEN 3 THEN 4
                                WHEN 2 THEN 5
                                WHEN 1 THEN 6
                                ELSE 7
                            END ASC,
                            CASE ta.maintenance_index_type
                                WHEN 3 THEN 1
                                WHEN 2 THEN 2
                                WHEN 1 THEN 3
                                ELSE 4
                            END asc,
                            CASE ta.component_level_type_id
                                WHEN 1 THEN 1
                                WHEN 2 THEN 2
                                ELSE 3
                            END asc;'''


            cursor.execute(all_assets_q, (wo_id, ))
            all_assets1_temp = cursor.fetchall()
            print(len(all_assets1_temp))
            asset_dict1 = {}
            for count, asset in enumerate(all_assets1_temp,start=1):
                if asset[0] not in asset_dict1:
                    count_tuple = (count,)
                    asset_dict1[asset[0]] = asset
            all_assets1 = list(asset_dict1.values())
            print(len(all_assets1))
            if all_top_sub_feature_flag[0]:
                all_assets1 = all_asset_list1(cursor, asset_dict)  # Fetch data from all_asset_list1
            else:
                all_assets1 = all_asset_list2(cursor, asset_dict)
            print('all_assets1',all_assets1)
            print(len(all_assets1))
            if len(all_assets1) != 0:
                ir_image_data = fetch_ir_visual_image_labels1(cursor, connection, all_assets1)
                print('Asset Image Data:', ir_image_data)

                asset_image_data = fetch_asset_labels1(cursor, connection, all_assets1, all_assets_feature_flag[0],assets_having_issues)
                print('asset_image_data',asset_image_data)

            asset_fedby_mapping_q = """select wa.woonboardingassets_id , ta.asset_name , wfbm.is_parent_from_ob_wo ,wfbm.parent_asset_id 
                                    from "WOOnboardingAssets" wa  JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id join "WOOBAssetFedByMapping" wfbm on wa.woonboardingassets_id =wfbm .woonboardingassets_id 
                                    where wa.wo_id = %s
                                    and wa.flag_issue_thermal_anamoly_detected=true  and wa.status =15 and wfbm.is_deleted=false order by ta.created_at asc"""
            cursor.execute(asset_fedby_mapping_q, (wo_id, ))
            asset_fedby_mapping = cursor.fetchall()

            if asset_fedby_mapping is not None:
                asset_fedby_data = fetch_fed_by_names(
                    cursor, connection, asset_fedby_mapping)
        
            # ################### thermal records #######################

            thermal_assets_q = '''SELECT wa.woonboardingassets_id, ta.asset_name, wa.asset_class_name, tmib.temp_master_building_name, tmf.temp_master_floor_name,
                                tmir.temp_master_room_name, ta.temp_master_section,
                                ta.created_at, wa.other_notes, ta.maintenance_index_type,
                                wl.issue_type, wl.thermal_classification_id, wl.thermal_anomaly_sub_componant, wl.thermal_anomaly_refrence_temps,
                                wl.thermal_anomaly_corrective_action, wl.thermal_anomaly_problem_description, wl.thermal_anomaly_measured_temps,
                                wl.thermal_anomaly_measured_amps, wl.thermal_anomaly_location, wl.thermal_anomaly_additional_ir_photo, ta.panel_schedule,
                                wl.dynamic_field_json, wl.wo_line_issue_id, wl.is_issue_linked_for_fix, wl.thermal_anomaly_severity_criteria,wl.is_abc_phase_required_for_report
                                FROM "WOOnboardingAssets" wa
                                JOIN "WOLineIssue" wl ON wa.woonboardingassets_id = wl.woonboardingassets_id
                                JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id
                                JOIN "TempMasterBuilding" tmib ON ta.temp_master_building_id = tmib.temp_master_building_id
                                JOIN "TempMasterFloor" tmf ON ta.temp_master_floor_id = tmf.temp_master_floor_id
                                JOIN "TempMasterRoom" tmir ON ta.temp_master_room_id = tmir.temp_master_room_id
                                WHERE wa.wo_id = %s
                                AND wl.issue_type = 2
                                AND wa.status = 15
                                AND tmib.is_deleted = false
                                AND tmf.is_deleted = false
                                AND tmir.is_deleted = false
                                AND wl.is_deleted = false
                                AND (
                                    wl.thermal_classification_id IS NOT NULL OR 
                                    wl.thermal_anomaly_location IS NOT NULL OR
                                    wl.thermal_anomaly_problem_description IS NOT NULL OR 
                                    wl.thermal_anomaly_corrective_action IS NOT NULL OR
                                    wl.thermal_anomaly_sub_componant IS NOT NULL OR 
                                    wl.thermal_anomaly_measured_amps IS NOT NULL OR
                                    wl.thermal_anomaly_measured_temps IS NOT NULL OR 
                                    wl.thermal_anomaly_refrence_temps IS NOT NULL
                                )
                                ORDER BY 
                                CASE wl.thermal_classification_id
                                    WHEN 5 THEN 1  -- Critical
                                    WHEN 4 THEN 2  -- Serious
                                    WHEN 6 THEN 3  -- ALERt
                                    WHEN 3 THEN 4  -- Intermidiate 
                                    WHEN 2 THEN 5  -- Nominal
                                    WHEN 1 THEN 6  -- ok
                                    ELSE 7
                                END,
                                tmib.temp_master_building_name ASC, 
                                tmf.temp_master_floor_name ASC, 
                                tmir.temp_master_room_name ASC, 
                                ta.asset_name ASC;'''

            cursor.execute(thermal_assets_q, (wo_id, ))
            thermal_assets = cursor.fetchall()
        
            if len(thermal_assets) != 0:
                thermal_image_data = fetch_thermal_labels(cursor, connection, thermal_assets)

                thermal_ir_image_data = fetch_ir_visual_image_labels(cursor, connection, thermal_assets)
                print('thermal_data_1',thermal_ir_image_data)

            thermal_fedby_mapping_q = """select wa.woonboardingassets_id , ta.asset_name , wfbm.is_parent_from_ob_wo ,wfbm.parent_asset_id 
                                    from "WOOnboardingAssets" wa  JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id join "WOOBAssetFedByMapping" wfbm on wa.woonboardingassets_id =wfbm .woonboardingassets_id 
                                    where wa.wo_id = %s
                                    and wa.flag_issue_thermal_anamoly_detected=true  and wa.status =15 and wfbm.is_deleted=false order by ta.created_at asc"""
            cursor.execute(thermal_fedby_mapping_q, (wo_id, ))
            thermal_fedby_mapping = cursor.fetchall()

            if thermal_fedby_mapping is not None:
                thermal_fedby_data = fetch_fed_by_names(
                    cursor, connection, thermal_fedby_mapping)

            # ############### NEC recoreds###################


            nec_assets_q = '''SELECT wl.wo_line_issue_id, ta.asset_name, wa.asset_class_name, 
                        tmib.temp_master_building_name,tmf.temp_master_floor_name, tmir.temp_master_room_name, 
                        ta.temp_master_section,ta.created_at, wa.other_notes,
                        ta.maintenance_index_type,wl.issue_type,wl.nec_violation,wl.osha_violation,
                        ta.panel_schedule,wl.is_issue_linked_for_fix,wl.woonboardingassets_id
                        FROM "WOOnboardingAssets" wa
                        JOIN "WOLineIssue" wl ON wa.woonboardingassets_id = wl.woonboardingassets_id
                        JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id
                        JOIN "TempMasterBuilding" tmib ON ta.temp_master_building_id = tmib.temp_master_building_id
                        JOIN "TempMasterFloor" tmf ON ta.temp_master_floor_id = tmf.temp_master_floor_id
                        JOIN "TempMasterRoom" tmir ON ta.temp_master_room_id = tmir.temp_master_room_id
                        WHERE wa.wo_id = %s
                        AND wl.issue_type = 1
                        AND wl.issue_caused_id = 2
                        AND wa.status = 15
                        AND tmib.is_deleted = false
                        AND tmf.is_deleted = false
                        AND tmir.is_deleted = false
                        AND wl.is_deleted = false
                        AND wl.nec_violation IS NOT NULL
                        ORDER BY tmib.temp_master_building_name ASC, tmf.temp_master_floor_name  ASC, tmir.temp_master_room_name  ASC, ta.temp_master_section  ASC, wa.asset_name ASC'''

            cursor.execute(nec_assets_q, (wo_id, ))
            nec_assets = cursor.fetchall()
            if len(nec_assets) != 0:
                nec_image_data = fetch_nec_labels(
                    cursor, connection, nec_assets)


            nec_fedby_mapping_q = """select wa.woonboardingassets_id , ta.asset_name , wfbm.is_parent_from_ob_wo ,wfbm.parent_asset_id 
                                    from "WOOnboardingAssets" wa  JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id join "WOOBAssetFedByMapping" wfbm on wa.woonboardingassets_id =wfbm .woonboardingassets_id 
                                    where wa.wo_id = %s
                                    and wa.flag_issue_nec_violation =true and wa.status =15 and wfbm.is_deleted=false order by ta.created_at asc"""
            cursor.execute(nec_fedby_mapping_q, (wo_id,))
            nec_fedby_mapping = cursor.fetchall()

            if nec_fedby_mapping is not None:
                nec_fedby_data = fetch_fed_by_names(
                    cursor, connection, nec_fedby_mapping)

            all_fedby_mapping_q = """select wa.woonboardingassets_id , ta.asset_name , wfbm.is_parent_from_ob_wo ,wfbm.parent_asset_id 
                                    from "WOOnboardingAssets" wa  JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id
                                    join "WOOBAssetFedByMapping" wfbm on wa.woonboardingassets_id =wfbm .woonboardingassets_id 
                                    where wa.wo_id = %s  and wa.status =15 and wfbm.is_deleted=false order by ta.created_at asc"""
            cursor.execute(all_fedby_mapping_q, (wo_id, ))
            all_fedby_mapping = cursor.fetchall()

            if all_fedby_mapping is not None:
                all_fedby_data = fetch_fed_by_names(
                    cursor, connection, all_fedby_mapping)
            
            # ############### OSHA recoreds###################

            osha_assets_q = '''SELECT wl.wo_line_issue_id, ta.asset_name, wa.asset_class_name, 
                        tmib.temp_master_building_name,tmf.temp_master_floor_name, tmir.temp_master_room_name, 
                        ta.temp_master_section,ta.created_at, wa.other_notes,
                        ta.maintenance_index_type,wl.issue_type,wl.nec_violation,wl.osha_violation,
                        ta.panel_schedule,wl.is_issue_linked_for_fix,wl.woonboardingassets_id
                        FROM "WOOnboardingAssets" wa
                        JOIN "WOLineIssue" wl ON wa.woonboardingassets_id = wl.woonboardingassets_id
                        JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id
                        JOIN "TempMasterBuilding" tmib ON ta.temp_master_building_id = tmib.temp_master_building_id
                        JOIN "TempMasterFloor" tmf ON ta.temp_master_floor_id = tmf.temp_master_floor_id
                        JOIN "TempMasterRoom" tmir ON ta.temp_master_room_id = tmir.temp_master_room_id
                        WHERE wa.wo_id = %s
                        AND wl.issue_type = 1
                        AND wa.status = 15
                        AND wl.issue_caused_id = 1
                        AND tmib.is_deleted = false
                        AND tmf.is_deleted = false
                        AND tmir.is_deleted = false
                        AND wl.is_deleted = false
                        AND wl.osha_violation IS NOT NULL
                        ORDER BY tmib.temp_master_building_name ASC, tmf.temp_master_floor_name  ASC, tmir.temp_master_room_name  ASC, ta.temp_master_section  ASC, wa.asset_name ASC'''

            cursor.execute(osha_assets_q, (wo_id, ))
            osha_assets = cursor.fetchall()
            if len(osha_assets) != 0:
                osha_image_data = fetch_osha_labels(
                    cursor, connection, osha_assets)


            osha_fedby_mapping_q = """select wa.woonboardingassets_id , ta.asset_name , wfbm.is_parent_from_ob_wo ,wfbm.parent_asset_id 
                                    from "WOOnboardingAssets" wa  JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id join "WOOBAssetFedByMapping" wfbm on wa.woonboardingassets_id =wfbm .woonboardingassets_id 
                                    where wa.wo_id = %s
                                    and wa.flag_issue_osha_violation = true and wa.status =15 and wfbm.is_deleted=false order by ta.created_at asc"""
            cursor.execute(osha_fedby_mapping_q, (wo_id,))
            osha_fedby_mapping = cursor.fetchall()

            if osha_fedby_mapping is not None:
                osha_fedby_data = fetch_fed_by_names(
                    cursor, connection, osha_fedby_mapping)

            all_fedby_mapping_q = """select wa.woonboardingassets_id , ta.asset_name , wfbm.is_parent_from_ob_wo ,wfbm.parent_asset_id 
                                    from "WOOnboardingAssets" wa  JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id
                                    join "WOOBAssetFedByMapping" wfbm on wa.woonboardingassets_id =wfbm .woonboardingassets_id 
                                    where wa.wo_id = %s  and wa.status =15 and wfbm.is_deleted=false order by ta.created_at asc"""
            cursor.execute(all_fedby_mapping_q, (wo_id, ))
            all_fedby_mapping = cursor.fetchall()

            if all_fedby_mapping is not None:
                all_fedby_data = fetch_fed_by_names(
                    cursor,connection, all_fedby_mapping)
                
            # ############### NFPA 70B Violation recoreds ###################

            nfpa_assets_q = '''SELECT wl.wo_line_issue_id, ta.asset_name, wa.asset_class_name, 
                    tmib.temp_master_building_name,tmf.temp_master_floor_name, tmir.temp_master_room_name, 
                    ta.temp_master_section,ta.created_at, wa.other_notes,
                    ta.maintenance_index_type,wl.issue_type,wl.nfpa_70b_violation,
                    ta.panel_schedule,wl.is_issue_linked_for_fix,wl.woonboardingassets_id
                    FROM "WOOnboardingAssets" wa
                    LEFT JOIN "WOLineIssue" wl ON wa.woonboardingassets_id = wl.woonboardingassets_id
                    JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id
                    JOIN "TempMasterBuilding" tmib ON ta.temp_master_building_id = tmib.temp_master_building_id
                    JOIN "TempMasterFloor" tmf ON ta.temp_master_floor_id = tmf.temp_master_floor_id
                    JOIN "TempMasterRoom" tmir ON ta.temp_master_room_id = tmir.temp_master_room_id
                    WHERE wa.wo_id = %s
                    AND wl.issue_type = 1
                    AND wl.issue_caused_id = 14
                    AND wa.status = 15
                    AND tmib.is_deleted = false
                    AND tmf.is_deleted = false
                    AND tmir.is_deleted = false
                    AND wl.is_deleted = false
                    AND wl.nfpa_70b_violation IS NOT NULL
                    ORDER BY tmib.temp_master_building_name ASC, tmf.temp_master_floor_name  ASC, tmir.temp_master_room_name  ASC, ta.temp_master_section  ASC, wa.asset_name ASC'''

            cursor.execute(nfpa_assets_q, (wo_id, ))
            nfpa_assets = cursor.fetchall()
            print('nfpa_assets', nfpa_assets)
            if len(nfpa_assets) != 0:

                nfpa_image_data = fetch_nfpa_labels(cursor, connection, nfpa_assets)
                # print(nfpa_image_data)
                # print(nfpa_assets)

            nfpa_fedby_mapping_q = """select wa.woonboardingassets_id , ta.asset_name , wfbm.is_parent_from_ob_wo ,wfbm.parent_asset_id 
                                    from "WOOnboardingAssets" wa  JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id join "WOOBAssetFedByMapping" wfbm on wa.woonboardingassets_id =wfbm .woonboardingassets_id 
                                    where wa.wo_id = %s
                                    and wa.status =15 and wfbm.is_deleted=false order by ta.created_at asc"""
            cursor.execute(nfpa_fedby_mapping_q, (wo_id,))
            nfpa_fedby_mapping = cursor.fetchall()

            if nfpa_fedby_mapping is not None:
                nfpa_fedby_data = fetch_fed_by_names(cursor, connection, nfpa_fedby_mapping)

            nfpa_fedby_mapping_q = """select wa.woonboardingassets_id , ta.asset_name , wfbm.is_parent_from_ob_wo ,wfbm.parent_asset_id 
                                    from "WOOnboardingAssets" wa  JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id
                                    join "WOOBAssetFedByMapping" wfbm on wa.woonboardingassets_id =wfbm .woonboardingassets_id 
                                    where wa.wo_id = %s  and wa.status =15 and wfbm.is_deleted=false order by ta.created_at asc"""
            cursor.execute(nfpa_fedby_mapping_q, (wo_id, ))
            nfpa_fedby_mapping = cursor.fetchall()

            if nfpa_fedby_mapping is not None:
                nfpa_fedby_data = fetch_fed_by_names(cursor, connection, nfpa_fedby_mapping)
      
                
            # ################### repair records #######################

            repair_asstes_q = '''SELECT wl.wo_line_issue_id, ta.asset_name, wa.asset_class_name, tmib.temp_master_building_name,
                            tmf.temp_master_floor_name, tmir.temp_master_room_name, ta.temp_master_section,
                            ta.created_at, wa.other_notes,ta.maintenance_index_type,wl.issue_type,wl.issue_title,wl.issue_description
                            ,wl.is_issue_linked_for_fix,ta.panel_schedule,wl.woonboardingassets_id
                            FROM "WOOnboardingAssets" wa
                            JOIN "WOLineIssue" wl ON wa.woonboardingassets_id = wl.woonboardingassets_id
                            JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id
                            JOIN "TempMasterBuilding" tmib ON ta.temp_master_building_id = tmib.temp_master_building_id
                            JOIN "TempMasterFloor" tmf ON ta.temp_master_floor_id = tmf.temp_master_floor_id
                            JOIN "TempMasterRoom" tmir ON ta.temp_master_room_id = tmir.temp_master_room_id
                            WHERE wa.wo_id = %s
                            AND wl.issue_type = 3
                            AND wa.status = 15
                            AND tmib.is_deleted = false
                            AND tmf.is_deleted = false
                            AND tmir.is_deleted = false
                            AND wl.is_deleted = false
                            ORDER BY tmib.temp_master_building_name ASC, tmf.temp_master_floor_name  ASC, tmir.temp_master_room_name  ASC, ta.temp_master_section  ASC, wa.asset_name ASC'''

            cursor.execute(repair_asstes_q, (wo_id, ))
            repair_assets = cursor.fetchall()

            if len(repair_assets) != 0:
                repair_image_data = fetch_repair_labels(
                    cursor, connection, repair_assets)

            repair_fedby_mapping_q = """select wa.woonboardingassets_id , ta.asset_name, wfbm.is_parent_from_ob_wo ,wfbm.parent_asset_id 
                                    from "WOOnboardingAssets" wa  JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id 
                                    join "WOOBAssetFedByMapping" wfbm on wa.woonboardingassets_id =wfbm .woonboardingassets_id 
                                    where wa.wo_id = %s
                                    and wa.status =15 and wfbm.is_deleted=false order by ta.created_at asc"""
            cursor.execute(repair_fedby_mapping_q, (wo_id, ))
            repair_fedby_mapping = cursor.fetchall()

            if repair_fedby_mapping is not None:
                repair_fedby_data = fetch_fed_by_names(cursor, connection, repair_fedby_mapping)
            
            # ################### replace records #######################

            replace_asstes_q = '''SELECT wl.wo_line_issue_id, ta.asset_name, wa.asset_class_name, tmib.temp_master_building_name,
                            tmf.temp_master_floor_name, tmir.temp_master_room_name, ta.temp_master_section,
                            ta.created_at, wa.other_notes, ta.maintenance_index_type,wl.issue_type,wl.issue_title,wl.issue_description
                            ,wl.is_issue_linked_for_fix,ta.panel_schedule,wl.woonboardingassets_id
                            FROM "WOOnboardingAssets" wa
                            JOIN "WOLineIssue" wl ON wa.woonboardingassets_id = wl.woonboardingassets_id
                            JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id
                            JOIN "TempMasterBuilding" tmib ON ta.temp_master_building_id = tmib.temp_master_building_id
                            JOIN "TempMasterFloor" tmf ON ta.temp_master_floor_id = tmf.temp_master_floor_id
                            JOIN "TempMasterRoom" tmir ON ta.temp_master_room_id = tmir.temp_master_room_id
                            WHERE wa.wo_id = %s
                            AND wl.issue_type = 4
                            AND wa.status = 15
                            AND tmib.is_deleted = false
                            AND tmf.is_deleted = false
                            AND tmir.is_deleted = false
                            AND wl.is_deleted = false
                            ORDER BY tmib.temp_master_building_name ASC, tmf.temp_master_floor_name  ASC, tmir.temp_master_room_name  ASC, ta.temp_master_section  ASC, wa.asset_name ASC'''

            cursor.execute(replace_asstes_q, (wo_id, ))
            replace_assets = cursor.fetchall()

            if len(replace_assets) != 0:
                replace_image_data = fetch_replace_labels(
                    cursor, connection, replace_assets)

            replace_fedby_mapping_q = """select wa.woonboardingassets_id , ta.asset_name, wfbm.is_parent_from_ob_wo ,wfbm.parent_asset_id 
                                    from "WOOnboardingAssets" wa  JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id join "WOOBAssetFedByMapping" wfbm on wa.woonboardingassets_id =wfbm .woonboardingassets_id 
                                    where wa.wo_id = %s
                                    and wa.flag_issue_thermal_anamoly_detected=true  and wa.status =15 and wfbm.is_deleted=false order by ta.created_at asc"""
            cursor.execute(replace_fedby_mapping_q, (wo_id, ))
            replace_fedby_mapping = cursor.fetchall()

            if replace_fedby_mapping is not None:
                replace_fedby_data = fetch_fed_by_names(cursor, connection, replace_fedby_mapping)
            
            # ################### other records #######################

            other_asstes_q = '''SELECT wl.wo_line_issue_id, ta.asset_name, wa.asset_class_name, tmib.temp_master_building_name,
                            tmf.temp_master_floor_name, tmir.temp_master_room_name, ta.temp_master_section,
                            ta.created_at, wa.other_notes, ta.maintenance_index_type,wl.issue_type,wl.issue_title,wl.issue_description
                            ,wl.is_issue_linked_for_fix,ta.panel_schedule,wl.woonboardingassets_id
                            FROM "WOOnboardingAssets" wa
                            JOIN "WOLineIssue" wl ON wa.woonboardingassets_id = wl.woonboardingassets_id
                            JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id
                           
                            JOIN "TempMasterBuilding" tmib ON ta.temp_master_building_id = tmib.temp_master_building_id
                            JOIN "TempMasterFloor" tmf ON ta.temp_master_floor_id = tmf.temp_master_floor_id
                            JOIN "TempMasterRoom" tmir ON ta.temp_master_room_id = tmir.temp_master_room_id
                            WHERE wa.wo_id = %s
                            AND wl.issue_type = 6
                            AND wa.status = 15
                            AND tmib.is_deleted = false
                            AND tmf.is_deleted = false
                            AND tmir.is_deleted = false
                            AND wl.is_deleted = false
                            ORDER BY tmib.temp_master_building_name ASC, tmf.temp_master_floor_name  ASC, tmir.temp_master_room_name  ASC, ta.temp_master_section  ASC, wa.asset_name ASC'''

            cursor.execute(other_asstes_q, (wo_id, ))
            other_assets = cursor.fetchall()

            if len(other_assets) != 0:
                other_image_data = fetch_other_labels(
                    cursor, connection, other_assets)

            other_fedby_mapping_q = """select wa.woonboardingassets_id , ta.asset_name, wfbm.is_parent_from_ob_wo ,wfbm.parent_asset_id 
                                    from "WOOnboardingAssets" wa  JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id join "WOOBAssetFedByMapping" wfbm on wa.woonboardingassets_id =wfbm .woonboardingassets_id 
                                    where wa.wo_id = %s
                                    and wa.flag_issue_thermal_anamoly_detected=true  and wa.status =15 and wfbm.is_deleted=false order by ta.created_at asc"""
            cursor.execute(other_fedby_mapping_q, (wo_id, ))
            other_fedby_mapping = cursor.fetchall()

            if other_fedby_mapping is not None:
                other_fedby_data = fetch_fed_by_names(cursor, connection, other_fedby_mapping)

            # ################### ultrasonic records #######################
            
            ultrasonic_asstes_q = '''SELECT wl.wo_line_issue_id, ta.asset_name, wa.asset_class_name, tmib.temp_master_building_name,
                            tmf.temp_master_floor_name, tmir.temp_master_room_name, ta.temp_master_section,
                            ta.created_at, wa.other_notes, ta.maintenance_index_type,wl.issue_type,wl.location_of_ultrasonic_anamoly,
                            wl.size_of_ultrasonic_anamoly,wl.type_of_ultrasonic_anamoly,ta.panel_schedule,wl.is_issue_linked_for_fix,
                            wl.woonboardingassets_id
                            FROM "WOOnboardingAssets" wa
                            JOIN "WOLineIssue" wl ON wa.woonboardingassets_id = wl.woonboardingassets_id
                            JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id
                           
                            JOIN "TempMasterBuilding" tmib ON ta.temp_master_building_id = tmib.temp_master_building_id
                            JOIN "TempMasterFloor" tmf ON ta.temp_master_floor_id = tmf.temp_master_floor_id
                            JOIN "TempMasterRoom" tmir ON ta.temp_master_room_id = tmir.temp_master_room_id
                            WHERE wa.wo_id = %s
                            AND wl.issue_type = 9
                            AND wa.status = 15
                            AND tmib.is_deleted = false
                            AND tmf.is_deleted = false
                            AND tmir.is_deleted = false
                            AND wl.is_deleted = false
                            ORDER BY tmib.temp_master_building_name ASC, tmf.temp_master_floor_name  ASC, tmir.temp_master_room_name  ASC, ta.temp_master_section  ASC, wa.asset_name ASC'''

            cursor.execute(ultrasonic_asstes_q, (wo_id, ))
            ultrasonic_assets = cursor.fetchall()

            if len(ultrasonic_assets) != 0:
                ultrasonic_image_data = fetch_ultrasonic_labels(
                    cursor, connection, ultrasonic_assets)

            ultrasonic_fedby_mapping_q = """select wa.woonboardingassets_id , ta.asset_name, wfbm.is_parent_from_ob_wo ,wfbm.parent_asset_id 
                                    from "WOOnboardingAssets" wa  JOIN "TempAsset" ta ON wa.tempasset_id = ta.tempasset_id join "WOOBAssetFedByMapping" wfbm on wa.woonboardingassets_id =wfbm .woonboardingassets_id 
                                    where wa.wo_id = %s
                                    and wa.flag_issue_thermal_anamoly_detected=true  and wa.status =15 and wfbm.is_deleted=false order by ta.created_at asc"""
            cursor.execute(ultrasonic_fedby_mapping_q, (wo_id, ))
            ultrasonic_fedby_mapping = cursor.fetchall()

            if ultrasonic_fedby_mapping is not None:
                ultrasonic_fedby_data = fetch_fed_by_names(cursor, connection, ultrasonic_fedby_mapping)

            ######################    call create pdf   ######################
        report_name = '/tmp/{}_Electrical_Maintenance_Report.pdf'.format(wo_num.replace(' ','_'))
        headers = []

        # imagename = '/tmp/' + company_data[3].split('/')[-1]
        result_logo = get_logo(company_data[3])
        result_logo1 = get_logo(company_data[4])

        if result_logo:
            headers.append(result_logo)
        
            

        footers = []
        # thumbnail_imagename = '/tmp/' + company_data[4].split('/')[-1]
        result_thumbnail = get_logo("https://condit-logo.s3.us-east-2.amazonaws.com/democompany_thumbnail.png")
        if result_thumbnail:
            footers.append(result_thumbnail)
        if result_logo:
            footers.append(result_logo1)
        footers.append(company_data[0])
        footers.append(company_data[4])
        

        doc = ReportPrinter(report_name, headers, footers,pagesizes=letter, BottomMargin=0.2 * inch, TopMargin=0.6 * inch,
                            LeftMargin=.1 * inch, RightMargin=.1 * inch)

        res = doc.create_pdf(report_name, wo_id, wo_start_date, company_data, all_assets, all_fedby_data,
                             thermal_assets, thermal_fedby_data, thermal_image_data, nec_assets, nec_fedby_data,
                             nec_image_data,osha_assets, osha_fedby_data,
                             osha_image_data,repair_image_data,repair_assets,repair_fedby_data,
                             replace_assets,replace_image_data,replace_fedby_data,other_assets,other_image_data,other_fedby_data,
                             ultrasonic_assets,ultrasonic_image_data,ultrasonic_fedby_data,
                             all_assets1,asset_image_data,ir_image_data,asset_fedby_data,all_assets_feature_flag[0],
                             assets_having_issues,thermal_ir_image_data,nfpa_assets,nfpa_image_data)
        if res:
            encoded_res = urllib.parse.quote(res)
            report_link = f"https://s3-us-east-2.amazonaws.com/{UPLOAD_BUCKET_NAME}/{wo_id}/{encoded_res}"
            sql_update_query = """Update "WorkOrders" set ir_wo_pdf_report= %s, ir_wo_pdf_report_status=18 where wo_id= %s"""
            cursor.execute(sql_update_query, (str(res), wo_id))
            print('res',res)
            connection.commit()
            count = cursor.rowcount
            user_name, user_email = fetch_user_email(cursor, connection, user_id)
            print('sql_update_query',sql_update_query)
            
            if user_email:
                send_dynamic_email(user_name, user_email, wo_num, str(report_link), company_data[0], company_data[1], company_data[3])
            return {
                "statusCode": 200,
                "body": "Success"
            }
            
        else:
            print("IR Scan report making not successful for ",wo_id)
            sql_update_query = """Update "WorkOrders" set ir_wo_pdf_report_status=19 where wo_id= %s"""
            cursor.execute(sql_update_query, (wo_id, ))
            connection.commit()
            count=cursor.rowcount
            print("record updated failure", count)
            return {
                "statusCode": 500,
                "body": "Internal server error"
            }
        # if res != False:
        #     sql_update_query = """Update "WorkOrders" set ir_wo_pdf_report= %s, ir_wo_pdf_report_status=18 where wo_id= %s"""
        #     cursor.execute(sql_update_query, (str(res), wo_id))
        #     connection.commit()
        #     count = cursor.rowcount
        #     # print("record updated success", count)
        #     return {
        #         "statusCode": 200,
        #         "body": "Success"
        #     }
        # else:
        #     print("IR Scan report making not successful for ",wo_id)
        #     sql_update_query = """Update "WorkOrders" set ir_wo_pdf_report_status=19 where wo_id= %s"""
        #     cursor.execute(sql_update_query, (wo_id, ))
        #     connection.commit()
        #     count=cursor.rowcount
        #     print("record updated failure", count)
        #     return {
        #         "statusCode": 500,
        #         "body": "Internal server error"
        #     }


    except (Exception, psycopg2.Error) as error:
        print("Error while fetching data from PostgreSQL", error)
        return {
            "statusCode": 500,
            "body": "Failure"
        }

    finally:
        # closing database connection.
        if (connection):
            cursor.close()
            connection.close()
            print("PostgreSQL connection is closed")
