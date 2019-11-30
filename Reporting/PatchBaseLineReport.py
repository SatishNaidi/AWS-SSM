import boto3
from datetime import datetime, date
import json
import os
import xlsxwriter
import pprint


def pp(item):
    pprint.pprint(item)


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


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


def write_base_lines_excel(client, patch_base_lines):
    workbook = False
    for each_base_line_id in patch_base_lines:
        try:

            patch_baseline_response = client.describe_effective_patches_for_patch_baseline(
                BaselineId=each_base_line_id
            )

            json_serialized = json.loads(json.dumps(patch_baseline_response, default=json_serial))
            for each_patch in json_serialized["EffectivePatches"]:
                header_row = list(each_patch["Patch"].keys())
                break
            workbook = xlsxwriter.Workbook('PatchReport_21_Nov_2019.xlsx')
            worksheet = workbook.add_worksheet(name=patch_base_lines[each_base_line_id])

            # Write Header to Excel
            header_column = 0
            for each_header in header_row:
                worksheet.write(0, header_column, each_header)
                header_column += 1

            row = 1
            for each_patch in json_serialized["EffectivePatches"]:
                column_marker = 0
                for each_key in each_patch["Patch"]:
                    worksheet.write(row, column_marker, each_patch["Patch"][each_key])
                    column_marker += 1
                row += 1

        except Exception as err:
            print(err)
            pass
    if workbook:
        workbook.close()
        return "Report is created"
    else:
        return "No information is available for reporting"

def lambda_handler(event, context):
    try:
        patch_baselines = os.environ['patch_baselines'].split(",")
    except Exception as err:
        print("Env Variable 'patch_baselines' doesn't exits")
        # return "Specified Env Variable doesn't exits")
        patch_baselines = ["WindowsApprovedPatches", "AmazonLinuxApprovedPatches", "LinuxApprovedPatches"]
        # patch_date = "Oct-08-2019"
    client = boto3.client('ssm', region_name="us-west-2")
    response_patch_base_lines = patch_base_line_names_to_ids(client, patch_baselines)
    return write_base_lines_excel(client, response_patch_base_lines)


if __name__ == "__main__":
    import pdb
    pdb.set_trace()
    pprint.pprint(lambda_handler({}, {}))
