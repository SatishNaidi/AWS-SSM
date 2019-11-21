import boto3
from datetime import datetime, date
import json
import xlsxwriter
import pprint


def pp(item):
    pprint.pprint(item)


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


def instance_patch_info(client):
    response = client.describe_instance_information()
    json_serialized = json.loads(json.dumps(response, default=json_serial))
    __header_row = []
    instance_ids = []

    for each_instance in json_serialized["InstanceInformationList"]:
        __header_row.extend(list(each_instance.keys()))
    headers = list(set(__header_row))

    row = 0
    column = 0
    workbook = xlsxwriter.Workbook('InstancePatchReport.xlsx')
    instance_worksheet = workbook.add_worksheet(name="All-Instances")
    for each_header in headers:
        instance_worksheet.write(row, column, each_header)
        column += 1
    row = 1
    column = 0
    for each_instance in json_serialized["InstanceInformationList"]:
        instance_ids.append(each_instance["InstanceId"])
        for each_header in headers:
            cell_value = each_instance.get(each_header, "None")
            if type(cell_value) not in [int, str, float, bool]:
                cell_value = str(cell_value)

            instance_worksheet.write(row, column, cell_value)
            column += 1
        column = 0
        row += 1

    all_instance_response = {}
    header_rows = []
    patch_worksheet = workbook.add_worksheet(name="PatchInfo")
    for each_instance in instance_ids:
        response = client.describe_instance_patches(
            InstanceId=each_instance
        )
        for each_patch in response["Patches"]:
            header_rows.extend(list(each_patch.keys()))

        all_instance_response[each_instance] = response["Patches"]

        row = 0
        column = 0
        headers = list(set(header_rows))
        patch_worksheet.write(row, column, "InstanceID")
        column += 1
        for each_header in headers:
            patch_worksheet.write(row, column, each_header)
            column += 1

        row = 1
        column = 1
        for each_instance in all_instance_response:
            for each_patch in all_instance_response[each_instance]:
                patch_worksheet.write(row, 0, each_instance)
                for each_header in headers:
                    cell_value = each_patch.get(each_header, "None")
                    if type(cell_value) not in [int, str, float, bool]:
                        cell_value = str(cell_value)
                    patch_worksheet.write(row, column, cell_value)
                    column += 1
                column = 1
                row += 1
        workbook.close()


def lambda_handler(event, context):
    client = boto3.client('ssm', region_name="us-west-2")
    instance_patch_info(client)

if __name__ == "__main__":
    import pdb
    pdb.set_trace()
    pprint.pprint(lambda_handler({}, {}))


