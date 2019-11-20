import boto3

client = boto3.client('ssm', region_name="us-west-2")


final_response = []

from datetime import datetime, date
import json

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))

# response = client.describe_instance_information()
#
# for each_instance in response["InstanceInformationList"]:
#     instance_id = each_instance["InstanceId"]
#     response = client.describe_instance_patches(
#         InstanceId=instance_id,
#         Filters=[
#                 {
#                     'Key': 'Classification',
#                     'Values': [
#                         'Security',
#                     ]
#                 },
#                 {
#                 'Key': 'Severity',
#                 'Values': [
#                     'Critical',
#                 ]
#                 },
#             ]
#     )
#     final_response.append(response)
#
#
# print(response)

patch_baseline= 'pb-0a83efc51c00c5d48'

patch_baseline_response = client.describe_effective_patches_for_patch_baseline(
    BaselineId=patch_baseline
)

print(patch_baseline_response["EffectivePatches"])

json_serialized = json.loads(json.dumps(patch_baseline_response, default=json_serial))

for each_patch in json_serialized["EffectivePatches"]:
    header_row = list(each_patch["Patch"].keys())
    break

import xlsxwriter
workbook = xlsxwriter.Workbook('PatchReport_20_Nov_2019.xlsx')
worksheet = workbook.add_worksheet(name=patch_baseline)

count=0
for each_header in header_row:
    worksheet.write(0, count, each_header)
    count = count+1


row = 1
import pprint

def pp(item):
    pprint.pprint(item)

import pdb
pdb.set_trace()

for each_patch in json_serialized["EffectivePatches"]:
    column_marker = 0
    for each_key in each_patch["Patch"]:
        worksheet.write(row, column_marker, each_patch["Patch"][each_key])
        column_marker += 1
    row += 1

# for item, cost in (expenses):
#     worksheet.write(row, col,     item)
#     worksheet.write(row, col + 1, cost)
#     row += 1


workbook.close()





# client = boto3.client('sns',region_name="us-west-2")
#
# response = client.publish(
#     TopicArn='arn:aws:sns:us-west-2:508526137765:mytest_topic',
#     Message=str(final_response),
#     Subject='Instance Patch List',
#     MessageStructure='string'
# )
#
# print(patch_baseline_response)

# response = client.publish(
#     TopicArn='arn:aws:sns:us-west-2:508526137765:mytest_topic',
#     Message=str(patch_baseline_response),
#     Subject='Describe Patch Base line for '+patch_baseline,
#     MessageStructure='string'
# )

# print(response)