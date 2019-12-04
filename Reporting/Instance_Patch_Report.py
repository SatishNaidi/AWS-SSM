import boto3
from datetime import datetime, date
import json
import pprint
import os
import csv


def pp(item):
    pprint.pprint(item)


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


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


def instance_patch_info(ssm_client,ec2_client):
    pages = ssm_client.get_paginator('describe_instance_information')
    all_instances = []
    instance_ids = []
    instance_ids_dict = {}
    for page in pages.paginate():
        all_instances.extend(page.get("InstanceInformationList", []))

    for each_instance in all_instances:
        instance_ids_dict[each_instance["InstanceId"]] = ""


    pages = ec2_client.get_paginator('describe_instances')

    for page in pages.paginate(InstanceIds=list(instance_ids_dict.keys())):
        for reservation in page.get("Reservations"):
            for instance in reservation.get("Instances"):
                instance = json.loads(json.dumps(instance, default=json_serial))
                instance_profile = instance.get("IamInstanceProfile", {}).get("Arn", "NA")
                launch_time = instance["LaunchTime"]
                instance_ids_dict[instance["InstanceId"]] = {
                    "IAMProfile":instance_profile,
                    "LaunchTime":launch_time
                }
    for each_instance in all_instances:
        # to_be_updated_details = {
        #         "InstanceId": each_instance["InstanceId"],
        #         "Name": each_instance["ComputerName"]
        #     }
        # to_be_updated_details.update(instance_ids_dict[each_instance["InstanceId"]])
        each_instance.update(instance_ids_dict[each_instance["InstanceId"]])

    instance_report_csv = write_to_csv("InstanceReport.csv", all_instances)
    all_instances_patch_report = []
    for each_instance in all_instances:
        paginator = ssm_client.get_paginator('describe_instance_patches')
        try:
            page_iterator = paginator.paginate(InstanceId=each_instance["InstanceId"])
            items = []
            for each_page in page_iterator:
                # print(each_page.get("Patches", []))
                items.extend(each_page.get("Patches", []))
        except Exception as outErr:
            print(outErr)
            pass
        # Adding Instance ID to each element
        items = [dict(item, InstanceId=each_instance["InstanceId"]) for item in items]
        items = [dict(item, Name=each_instance["ComputerName"]) for item in items]
        instance_patch_report = json.loads(json.dumps(items, default=json_serial))
        all_instances_patch_report.extend(instance_patch_report)
    instance_patch_report_csv = write_to_csv("InstancePatchReport.csv", all_instances_patch_report)
    return instance_report_csv, instance_patch_report_csv


def upload_file_s3(client, bucket_name, to_be_upload_filename):
    only_filename = os.path.basename(to_be_upload_filename)

    try:
        return client.upload_file(to_be_upload_filename, bucket_name, only_filename)
    except Exception as err:
        return err


def lambda_handler(event, context):
    ssm_client = boto3.client('ssm', region_name="us-east-1")
    ec2_client = boto3.client('ec2', region_name="us-east-1")
    generated_csv = instance_patch_info(ssm_client,ec2_client)
    s3_client = boto3.client("s3",region_name="us-east-1")
    bucket_name = 'madhav-ssm-logs'
    final_response = {}
    for each_file in generated_csv:

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