"""
This function generates the effective patch information for Windows patchBaseline with name : PatchBaseLineReport.csv
"""
import boto3
import pprint
import csv
from datetime import datetime, date
import json
import os


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


def pp(item):
    """Pretty Prints the output based on Content"""
    pprint.pprint(item)


def write_to_csv(filename, list_of_dict):
    """
    :param filename:
    :param list_of_dict:
    :return:
    """
    # Making sure to write to /tmp dir if running on AWS Lambda other wise to current dir
    if __name__ != "__main__":
        filename = "/tmp/"+filename

    json_serialized = json.loads(json.dumps(list_of_dict, default=json_serial))
    columns = []
    all_rows = []
    for each_item in json_serialized:
        row = ["" for col in columns]
        for key, value in each_item.items():
            try:
                index = columns.index(key)
            except ValueError:
                # this column hasn't been seen before
                columns.append(key)
                row.append("")
                index = len(columns) - 1
            row[index] = value
        all_rows.append(row)
    with open(filename, "w", newline='') as csvfile:
        writer = csv.writer(csvfile)
        # first row is the headers
        writer.writerow(columns)
        # then, the rows
        writer.writerows(all_rows)
    return filename


def upload_file_s3(client, bucket_name, to_be_upload_filename):
    only_filename = os.path.basename(to_be_upload_filename)

    try:
        return client.upload_file(to_be_upload_filename, bucket_name, only_filename)
    except Exception as err:
        return err


def patch_base_line_names_to_ids(client, patch_baselines):
    try:
        paginator = client.get_paginator('describe_patch_baselines')
        marker = None
        response_base_lines = {}
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
                base_line_name = each_item["BaselineName"]
                response_base_lines[base_line_id] = base_line_name
        return response_base_lines
    except Exception as Err:
        print(Err)
        return False


def get_effective_patches(client, patch_base_lines):
    list_of_patches = []
    for pbid, pbname in patch_base_lines.items():
        try:
            patch_baseline_response = client.describe_effective_patches_for_patch_baseline(
                BaselineId=pbid
            )
            json_serialized = json.loads(json.dumps(patch_baseline_response, default=json_serial))
            for each_patch in json_serialized["EffectivePatches"]:
                new_item = each_patch["Patch"]
                new_item.update(each_patch["PatchStatus"])
                new_item.update({"PBName": pbname, "PBId": pbid})
                list_of_patches.append(new_item)
        except Exception as err:
            print(err, pbname, pbid)
            pass
    return list_of_patches

def lambda_handler(event, context):
    """
    Default Handler
    """
    try:
        patch_baselines = os.environ['patch_baselines'].split(",")
    except Exception as err:
        print("Env Variable 'patch_baselines' doesn't exits")
        # return "Specified Env Variable doesn't exits")
        patch_baselines = ["WindowsApprovedPatches", "AmazonLinuxApprovedPatches", "LinuxApprovedPatches"]
        # patch_date = "Oct-08-2019"
    ssm_client = boto3.client('ssm', region_name="us-east-1")
    response_patch_base_lines = patch_base_line_names_to_ids(ssm_client, patch_baselines)
    list_of_patches = get_effective_patches(ssm_client, response_patch_base_lines)

    csvs_list = []

    csvs_list.append(write_to_csv("PatchBaseLineReport.csv", list_of_patches))
    s3_client = boto3.client("s3",region_name="us-east-1")
    bucket_name = 'madhav-ssm-logs'
    final_response = {}
    for each_file in csvs_list:
        try:
            upload_file_s3(s3_client,bucket_name, each_file)
            print("Uploaded file : " + each_file)
            final_response[os.path.basename(each_file)] = "Upload Success"
        except Exception as err:
            print("Error in Uploading file : " + each_file)
            final_response[os.path.basename(each_file)] = "Upload Failed"
    return {
        'statusCode': 200,
        'body': final_response
    }


if __name__ == "__main__":
    import pdb
    pdb.set_trace()
    pprint.pprint(lambda_handler({}, {}))