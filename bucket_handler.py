import botocore
from botocore.exceptions import NoCredentialsError
import boto3
import requests
import os
from io import BytesIO

ACCESS_KEY =  os.getenv('ACCESS_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
UPLOAD_BUCKET_NAME = os.getenv('UPLOAD_BUCKET_NAME')
NO_IMAGE_BUCKET = os.getenv('NO_IMAGE_BUCKET')
NO_IMAGE_FILE = os.getenv('NO_IMAGE_FILE')

def store_pdf(local_file, folder_name):
    print('local file name', local_file)
    s3 = boto3.client('s3', aws_access_key_id=ACCESS_KEY,
                      aws_secret_access_key=SECRET_KEY)
    try:
        save_file = local_file.replace('/tmp/', '')

        save_file = folder_name + '/' + save_file
        print(save_file)

        # with open(local_file, "rb") as f:
        s3.upload_file(local_file, UPLOAD_BUCKET_NAME, save_file,ExtraArgs={'ACL': 'public-read'})
        print("Upload Successful")
        url = "https://s3-us-east-2.amazonaws.com/{}/{}".format(UPLOAD_BUCKET_NAME,save_file)
        print('url',url)

        if os.path.exists(local_file):
            os.remove(local_file)
            print("Removed the file %s" % local_file)     
        else:
            print("Sorry, file %s does not exist." % local_file)

        print('url',url)

        return save_file
    except FileNotFoundError:
        print("The file was not found")
        return False
    except NoCredentialsError:
        print("Credentials not available")
        return False
    except Exception as e:
        print("exception in store pdf", e)


def fetch_image(folder_name, image_name, bucket_name):
    print('set',folder_name,image_name,bucket_name)
    try:
        image_path=''
        if folder_name is not None:
            image_path = '{0}/{1}'.format(folder_name, image_name)
        else:
            image_path = '{0}'.format(image_name)

        print(image_path)
        download_url='https://s3.us-east-2.amazonaws.com/{}/{}'.format(bucket_name, image_path)
        print(download_url)
        r = requests.get(download_url, stream=True)
        r.raise_for_status()
        print(r, r.status_code)

        if r.status_code == 200:
            image_stream = BytesIO(r.content)
            return image_stream

        # If image not found, insert no image found logo
        elif r.status_code == 403:
            print('Downloding No Image Found Logo!')

            download_url='https://s3.us-east-2.amazonaws.com/{}/{}'.format(NO_IMAGE_BUCKET, NO_IMAGE_FILE)
            print(download_url)
            r = requests.get(download_url, stream=True)
            r.raise_for_status()
            image_stream = BytesIO(r.content)
            print('No image found logo fetched from s3',r.status_code)
            return image_stream
        else:
            print("from else------------", r.content)
            return fetch_fallback_image()
            
    except Exception as e:
        print("Exception occurred while fetching image -", e)
        return fetch_fallback_image()

def fetch_fallback_image():
    try:
        image_unavailable = "https://condit-logo.s3.us-east-2.amazonaws.com/Upload_pending.png"
        print("Downloading fallback image:", image_unavailable)
        r = requests.get(image_unavailable, stream=True)
        r.raise_for_status()
        if r.status_code == 200:
            image_stream = BytesIO(r.content)
            print("Fallback image fetched successfully.")
            return image_stream
    except Exception as e:
        print("Exception occurred while fetching fallback image -", e)
        return None


def get_logo(image_path):
    try:
        print("inside get_logo", image_path)
        # print("inside get_logo", local_name)
        r = requests.get(image_path,stream=True)
        r.raise_for_status()  # Check if the request was successful
        print(r)
        image_stream = BytesIO(r.content)
        return image_stream
    except Exception as e:
        print("Exception occured while logo fetch - ", e)
        return False
