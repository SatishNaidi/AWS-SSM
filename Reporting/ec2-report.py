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


def _flatten_json(y):
    """
    Flattens json, ex:
    {
    "id":
        {
        "name":"value"
        }
    } will be converted to { "id_name":"value" }
    """
    out = {}

    def flatten(x, name=''):
        if type(x) is dict:
            for a in x:
                flatten(x[a], name + a + '_')
        elif type(x) is list:
            i = 0
            for a in x:
                flatten(a, name + str(i) + '_')
                i += 1
        else:
            out[name[:-1]] = x

    flatten(y)
    return out


def format_nested_keys(input_dict):
    all_keys = list(input_dict.keys())
    for each_key in all_keys:
        if each_key == "Tags":
            for value in input_dict["Tags"]:
                input_dict["Tag_"+value["Key"]] = value["Value"]
            del input_dict["Tags"]
        elif each_key == "SecurityGroups":
            attr = []
            for value in input_dict["SecurityGroups"]:
                attr.append(value["GroupName"] + ":" + value["GroupId"])
            input_dict["SecurityGroups"] = ",".join(attr)
        elif each_key == "IamInstanceProfile":
            input_dict["IamInstanceProfile"] = input_dict["IamInstanceProfile"]["Arn"]
        else:
            pass
    return _flatten_json(input_dict)


def gather_ec2_instance_info(ec2_client):
    pages = ec2_client.get_paginator('describe_instances')
    all_instances_info = []
    for page in pages.paginate():
        for reservation in page.get("Reservations"):
            for instance in reservation.get("Instances"):
                all_instances_info.append(instance)
    return all_instances_info


def filter_needed_fields(input_dict, filter_keys):
    final_out = []
    for each_instance in input_dict:
        json_formatted = json.loads(json.dumps(each_instance, default=json_serial))
        input_dict_keys = json_formatted.keys()
        each_instance_dict = {}
        for each_key in filter_keys:
            if each_key in input_dict_keys:
                each_instance_dict[each_key] = json_formatted[each_key]
        final_out.append(format_nested_keys(each_instance_dict))
    return final_out


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


def lambda_handler(event, context):
    ec2_client = boto3.client('ec2', region_name="us-east-1")
    field_names = ['InstanceId', 'InstanceType', 'ImageId', 'State_Name', 'KeyName', 'IamInstanceProfile',
                   'SecurityGroups', 'Tags', 'LaunchTime', 'PrivateDnsName', 'PrivateIpAddress', 'PublicIpAddress']
    ec2_info = gather_ec2_instance_info(ec2_client)
    required_info = filter_needed_fields(ec2_info, field_names)

    generated_csv = [write_to_csv("ec2_report.csv", required_info)]
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