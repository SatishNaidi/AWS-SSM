import boto3
import pprint
import csv
from datetime import datetime, date
import json
from glob import glob
import os


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


def pp(item):
    """Pretty Prints the output based on Content"""
    pprint.pprint(item)


def download_directory_from_s3(s3_resource, bucketName, remoteDirectoryName):
    bucket = s3_resource.Bucket(bucketName)
    if __name__ == "__main__":
        if not os.path.exists("tmp/"):
            os.mkdir("tmp")
        dir_name = "tmp/"
    else:
        dir_name = "/tmp/"
    for object in bucket.objects.filter(Prefix=remoteDirectoryName):
        if not os.path.exists(dir_name+os.path.dirname(object.key)):
            os.makedirs(dir_name+os.path.dirname(object.key))
        bucket.download_file(object.key, dir_name+object.key)
    return dir_name+remoteDirectoryName


def upload_file_s3(client, bucket_name, to_be_upload_filename):
    only_filename = os.path.basename(to_be_upload_filename)

    try:
        res = client.upload_file(to_be_upload_filename, bucket_name, only_filename)
        return "File: "+only_filename + "Uploaded to bucket : "+bucket_name
    except Exception as err:
        print(err)
        return err


def lambda_handler(event, context):
    """
    Default Handler
    """
    # Connection Objects
    s3_resource = boto3.resource('s3', region_name="us-east-1")

    try:
        bucket_name = os.environ['bucket_name']
    except Exception as err:
        print("Env Variable 'bucket_name' doesn't exits")
        bucket_name = 'madhav-ssm-logs'

    folder_str = datetime.now().strftime("%Y/%m/%d/")
    local_dir = download_directory_from_s3(s3_resource, bucket_name, folder_str)

    current_date = datetime.now()
    dt_string = current_date.strftime("%d_%b_%Y_%H_%M")

    if __name__ == "__main__":
        if not os.path.exists("tmp/"):
            os.mkdir("tmp")
        ec2_patch_report = "tmp/"+"InstancePatchReport_"+dt_string + ".csv"
    else:
        ec2_patch_report = "/tmp/"+"InstancePatchReport_"+dt_string + ".csv"

    with open(ec2_patch_report, 'a') as singleFile:
        for csvFile in glob(local_dir+'*.csv'):
            for line in open(csvFile, 'r'):
                singleFile.write(line)

    s3_client = boto3.client("s3", region_name="us-east-1")
    result = upload_file_s3(s3_client, bucket_name, ec2_patch_report)

    final_response = {}
    return {
        'statusCode': 200,
        'body': final_response
    }


if __name__ == "__main__":
    import pdb
    pdb.set_trace()
    pprint.pprint(lambda_handler({}, {}))