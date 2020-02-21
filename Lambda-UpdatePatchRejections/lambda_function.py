import boto3
from datetime import datetime, date, timedelta
import os
import json
import calendar
import pprint
import time
import sys

# Setting the timezone for accurate days calculation
# print(datetime.now())
os.environ['TZ'] = 'US/Eastern'
# os.environ['TZ'] = 'US/Pacific'
# os.environ['TZ'] = 'Pacific/Honolulu'
time.tzset()
print(f"Current time zone: {time.tzname}")
print(datetime.now())


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


def collect_all_patch_baselines(client, patch_baselines):
    try:
        paginator = client.get_paginator('describe_patch_baselines')
        marker = None
        response_pages = {}
        response_iterator = paginator.paginate(
            Filters=[
                {
                    'Key': 'NAME_PREFIX',
                    'Values': patch_baselines
                }
            ],
            PaginationConfig={
                'StartingToken': marker
            }
        )

        for page in response_iterator:
            for each_item in page["BaselineIdentities"]:
                base_line_id = each_item["BaselineId"]
                response = client.get_patch_baseline(
                    BaselineId=base_line_id
                )
                patch_rules = response.get("ApprovalRules", {}).get("PatchRules", {})
                response_pages[base_line_id] = patch_rules
            return response_pages
    except Exception as Err:
        print(Err)
        return False


def updated_rejected_patches(client, to_be_modified_baselines, rejected_patches=[]):
    response_list = []
    for each_base_line in to_be_modified_baselines:
        response = client.update_patch_baseline(BaselineId=each_base_line,
                                                RejectedPatches=rejected_patches)
        response_list.append(response)
    return response_list


def collect_rejected_patches(s3bucket, filename):
    """
    implement logic to read the file from s3 bucket
    :return:
    """
    s3client = boto3.client('s3', region_name='us-east-1')
    file_obj = s3client.get_object(
        Bucket=s3bucket,
        Key=filename
    )
    file_data = file_obj['Body'].read().decode("utf-8")
    return [string for string in file_data.split("\n") if string != ""]


def lambda_handler(event, context):
    print(event)
    regions = ["us-east-1", "us-east-2"]
    all_regions_response = {}
    try:
        patch_baselines = os.environ['patch_baselines'].split(",")
    except Exception as err:
        print("Env Variable 'patch_baselines' doesn't exits")
        # patch_baselines = ["WindowsApprovedPatches", "AmazonLinuxApprovedPatches", "LinuxApprovedPatches"]
        patch_baselines = ["WindowsApprovedPatches"]

    try:
        s3_bucket = os.environ['bucket_name']
    except Exception as err:
        print("Environment Variable 'bucket_name' doesn't exits")
        sys.exit()

    try:
        file_name = os.environ['patch_reject_filename']
    except Exception as err:
        print("Environment Variable 'patch_reject_filename' doesn't exits")
        sys.exit()

    for each_region in regions:
        client = boto3.client('ssm', region_name=each_region)
        print("Connected to region: " + each_region)
        patches_to_be_edited = collect_all_patch_baselines(client, patch_baselines)
        rejected_kbs = collect_rejected_patches(s3_bucket, file_name)
        response = updated_rejected_patches(client, patches_to_be_edited, rejected_patches=rejected_kbs)
        all_regions_response[each_region] = response
        print("Finished processing in region: " + each_region)
    return {
        'statusCode': 200,
        'body': json.loads(json.dumps(all_regions_response, default=json_serial))
    }


if __name__ == "__main__":
    import pdb
    pdb.set_trace()
    pprint.pprint(lambda_handler({}, {}))
