import boto3
from datetime import datetime, date, timedelta
import os
import json
import calendar
import pprint
import time

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


def find_second_tuesday_of_month(month):
    """
    Finds the second tuesday of the month in reference to current day
    Example:
        1) if month is 9, Second Tuesday will be Sept-10-2019
        2) if month is 10, Second Tuesday will be Oct-08-2019
    :return:
    """
    now = datetime.now()
    if month == 0:
        month = 12
        year = now.year-1
    else:
        year = now.year

    # print(now.month)
    first_day_of_month = datetime(year, month, 1)
    tuesday = 1  # Selected 1 since we need Tuesday
    first_tuesday = first_day_of_month + timedelta(
        days=((tuesday - calendar.monthrange(year, month)[0]) + 7) % 7)
    # days=0 for first tuesday, days=7 for second tuesday of the month and so on
    second_tuesday = first_tuesday + timedelta(days=7)  # Finding the Second Tuesday of the month
    return second_tuesday.date()


def calculate_days_from_patchday():
    """
    :return: return the numbers of days lapsed from the second tuesday of the month, If any error returns False Boolean
    """
    try:
        today = date.today()
        month = today.month
        patch_date = find_second_tuesday_of_month(month)
        # date_object = datetime.strptime(patch_date, '%b-%d-%Y').date()

        diff = today - patch_date
        if int(diff.days) < 0:
            patch_date = find_second_tuesday_of_month(month-1)
            today = date.today()
            diff = today - patch_date
            return int(diff.days)
        return int(diff.days)

    except Exception as err:
        print(err)
        return False


def collect_all_patchbaselines(client, patch_baselines):
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
                # pprint.pprint(response)
                patch_rules = response.get("ApprovalRules", {}).get("PatchRules", {})
                response_pages[base_line_id]= patch_rules
            return response_pages
    except Exception as Err:
        print(Err)
        return False


def update_delay_for_patch_baseline(client, to_be_modified_baselines, delay_days):
    response_list = []
    for each_base_line in to_be_modified_baselines:
        for d in to_be_modified_baselines[each_base_line]:
            d.update((k, delay_days) for k, v in d.items() if k == "ApproveAfterDays")
        response = client.update_patch_baseline(
            BaselineId=each_base_line,
            ApprovalRules={
                'PatchRules': to_be_modified_baselines[each_base_line]
            }
        )
        response_list.append(response)
    return response_list


def lambda_handler(event, context):
    print(event)
    regions = ["us-east-1", "us-east-2"]
    all_regions_response = {}
    delay_days = calculate_days_from_patchday()
    print("Days from Patch Tuesday: ", delay_days)
    try:
        patch_baselines = os.environ['patch_baselines'].split(",")
    except Exception as err:
        print("Env Variable 'patch_baselines' doesn't exits")
        # return "Specified Env Variable doesn't exits")
        patch_baselines = ["WindowsApprovedPatches", "AmazonLinuxApprovedPatches", "LinuxApprovedPatches"]
        # patch_date = "Oct-08-2019"

    for each_region in regions:
        client = boto3.client('ssm', region_name=each_region)
        print("Connected to region: " + each_region)
        patches_to_be_edited = collect_all_patchbaselines(client, patch_baselines)
        response = update_delay_for_patch_baseline(client, patches_to_be_edited, delay_days)
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
