from bs4 import BeautifulSoup
import urllib3
from tabulate import tabulate
import re
from datetime import datetime
import monitor
import argparse
import configparser

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

config_vars = configparser.ConfigParser()

config_vars.read('config.ini')

JENKINS = config_vars.get('Settings', 'JENKINS')



def get_date_input():

    '''
    Gets start and end date input.

    Returns:
        Date: Start date
        Date: End date
    '''

    if JENKINS == "False":
        date_str_1 = input("Enter Before date (YYYY-MM-DD): ") #example  2023-11-14
        date_str_2 = input("Enter After date (YYYY-MM-DD): ")  #example  2023-11-13
    elif JENKINS == "True":
        date_str_1 = config_vars.get('Settings', 'before_date')
        date_str_2 = config_vars.get('Settings', 'after_date')

    try:
        start_date = datetime.strptime(date_str_1,"%Y-%m-%d")
        end_date = datetime.strptime(date_str_2,"%Y-%m-%d")
        start_date = start_date.date()
        end_date = end_date.date()
        return start_date,end_date
    except ValueError:
        print("Invalid date format")
        return None


def check_for_node_crashes(job_list, zone):
    """
    Check for node crash across all the provided job list
 
    Args:
        job_list (list): List of jobs which needs to be checked.
        zone (list): List of the zones/leases that need to checked.
    """
    pattern = r'/(\d+)'   
    for url in job_list:
        match = re.search(pattern, url)
        job_id = match.group(1)
        lease,_ = monitor.get_quota_and_nightly(url)
        if zone is not None and lease not in zone :
            continue
        cluster_deploy_status = monitor.cluster_deploy_status(url)
        if cluster_deploy_status == 'SUCCESS':
            node_status = monitor.get_node_status(url)
            print(job_id,node_status)
        monitor.check_node_crash(url)

def get_failed_testcases(spylinks, zone):
    """
    To get all the failed tescases in all the provided job list
 
    Args:
        spylinks (list): List of jobs which needs to be checked.
        zone (list): List of the zones/leases that need to checked.
    """

    pattern = r'/(\d+)'
    j=0
    for spylink in spylinks:
        match = re.search(pattern, spylink)
        job_id = match.group(1)
        job_type,_ = monitor.job_classifier(spylink)
        lease,_ = monitor.get_quota_and_nightly(spylink)
        if zone is not None and lease not in zone :
            continue
        cluster_status=monitor.cluster_deploy_status(spylink)
        if cluster_status == 'SUCCESS' and "4.15" not in spylink:
            j=j+1
            print(str(j)+".",job_id)
            monitor.print_all_failed_tc(spylink,job_type)
            print("\n")
    print("--------------------------------------------------------------------------------------------------")
    print("\n")

def print_tc_frequency(spylinks, zone):
    """
    To display the testcases failing with its frequency

    Args:
        spylinks (list): list of builds which needs to be checked.
        zone (list): List of the zones/leases that need to checked.

    """

    frequency = {}
    for spylink in spylinks:
        job_type,_ = monitor.job_classifier(spylink)
        lease,_ = monitor.get_quota_and_nightly(spylink)
        if zone is not None and lease not in zone :
            continue
        cluster_status=monitor.cluster_deploy_status(spylink)
        if cluster_status == 'SUCCESS' and "4.15" not in spylink:
            tc_failures,_ = monitor.get_all_failed_tc(spylink,job_type)
            for _,value in tc_failures.items():
                if len(value) !=0:
                    for tc in value:
                        if tc in frequency:
                            frequency[tc]+= 1
                        else:
                            frequency[tc] = 1
    sorted_frequency = dict(sorted(frequency.items(),key = lambda item: item[1], reverse=True))
    table_data = [(key,value) for key, value in sorted_frequency.items()]
    print(tabulate(table_data, headers = ['Testcase','Frequency'], tablefmt='grid'))
print("--------------------------------------------------------------------------------------------------")
print("\n")

def get_testcase_failure(spylinks, zone, tc_name):
    """
    To get all the builds with the particular testcase failure.

    Args:
        spylinks (list): list of builds which needs to be checked.
        zone (list): List of the zones/leases that need to checked.
        tc_name (string): Name of the testcase.
    """
    pattern = r'/(\d+)'
    j=0
    for spylink in spylinks:
        match = re.search(pattern, spylink)
        job_id = match.group(1)
        job_type,_ = monitor.job_classifier(spylink)
        lease,_ = monitor.get_quota_and_nightly(spylink)
        if zone is not None and lease not in zone :
            continue
        cluster_status=monitor.cluster_deploy_status(spylink)
        if cluster_status == 'SUCCESS':
                if monitor.check_testcase_failure(spylink,job_type,tc_name):
                    j=j+1
                    print(str(j)+"."+"Job_id: "+job_id)
                    print("https://prow.ci.openshift.org"+ spylink)
                    print("\n")
    print("--------------------------------------------------------------------------------------------------")
    print("\n")

def display_ci_links(config_data):

    '''
    Gets selected CI input.

    Parameter:
        config_data (dict): Dictionary of all the CI's mentioned in the config file

    Returns:
        List(int): Serial number of selected CI's 
    '''

    j=0

    ci_name_list = []
    options_int_list = []
    selected_config_data = {}

    if JENKINS == "False":
        for ci_name in config_data.keys():
            j=j+1
            ci_name_list.append(ci_name)
            print(j,'',ci_name)

        option = input("Select the required ci's serial number with a space ")

        selected_options = option.split()

   
        for ci in selected_options:
            try:
                ci_to_int = int(ci)
                if 0 < ci_to_int <= len(config_data):
                    options_int_list.append(ci_to_int)
                else:
                    return_value = "Enter the options in range of 1 to " + str(len(config_data))
                    print(return_value)
                    return "ERROR"
            except ValueError:
                return "Enter valid options"
    elif JENKINS == "True":
        for ci_name in config_data.keys():
            j=j+1
            ci_name_list.append(ci_name)

        selected_ci = config_vars.get('Settings', 'selected_ci')
        options_int_list = [int(value) for value in selected_ci.split(',')]

    for i in options_int_list:
        config_temp_data = {ci_name_list[i-1]: config_data[ci_name_list[i-1]]}
        selected_config_data.update(config_temp_data)
        config_temp_data = {}
    
    return selected_config_data


def main():
    parser = argparse.ArgumentParser(description='Get the job history')
    parser.add_argument('--zone', help='specify the lease/zone', type= lambda arg:arg.split(','))
    parser.add_argument('--ci_arch', default='p', choices=['p','z'], help='Specify the CI architecture type (p or z), default is p')

    args = parser.parse_args()

    if args.ci_arch == 'p':
        config_file = 'p_config.json'
    elif args.ci_arch == 'z':
        config_file = 'z_config.json'
    else:
        print("Invalid argument. Please use p or z")
        return 

    config_data = monitor.load_config(config_file)

    ci_list = display_ci_links(config_data)
    if isinstance(ci_list,dict):
        start_date,end_date = get_date_input()
        if start_date != None and end_date != None:
            if JENKINS == "False":
                print("Please select one of the option from Job History functionalities: ")
                print("1. Check Node Crash")
                print("2. Brief Job information")
                print("3. Detailed Job information")
                print("4. Failed testcases")
                print("5. Get builds with testcase failure")
                print("6. Get testcase frequency")

                option = input("Enter the option: ")
            elif JENKINS == "True":
                option = config_vars.get('Settings','query_option')

            print("Checking runs from",end_date,"to",start_date)
    
            if option == '1':
                for ci_name,ci_link in ci_list.items():
                    print("-------------------------------------------------------------------------------------------------")
                    print(ci_name)
                    if "sno" in ci_link or "mce" in ci_link:
                        print("Node crash check is not supported in SNO/MCE jobs")
                        continue
                    spy_links = monitor.get_jobs_with_date(ci_link,start_date,end_date)
                    check_for_node_crashes(spy_links,zone=args.zone)
                    monitor.final_job_list = []
            
            if option == '2':
                summary_list = []
                for ci_name,ci_link in ci_list.items():
                    summary_list.extend(monitor.get_brief_job_info(ci_name,ci_link,start_date,end_date,zone=args.zone))
                    monitor.final_job_list = []
                print(tabulate(summary_list, headers='keys', tablefmt="pipe", stralign='left'))
            
            if option == '3':
                for ci_name,ci_link in ci_list.items():
                    monitor.get_detailed_job_info(ci_name,ci_link,start_date,end_date,zone=args.zone)
                    monitor.final_job_list = []
            
            if option == '4':
                for ci_name,ci_link in ci_list.items():
                    print("-------------------------------------------------------------------------------------------------")
                    print(ci_name)
                    if "sno" in ci_link:
                        print("Tests execution is not yet supported in SNO")
                        continue
                    spy_links = monitor.get_jobs_with_date(ci_link,start_date,end_date)
                    get_failed_testcases(spy_links,zone=args.zone)
                    monitor.final_job_list = []
            
            if option == '5':
                tc_name = input("Enter the testcase names comma seperated: ")
                tc_list =  tc_name.split(",")

                for ci_name,ci_link in ci_list.items():
                    print("-------------------------------------------------------------------------------------------------")
                    print(ci_name)
                    if "sno" in ci_link:
                        print("Tests execution is not yet supported in SNO")
                        continue
                    spy_links = monitor.get_jobs_with_date(ci_link,start_date,end_date)
                    for tc in tc_list:
                        print("TESTCASE NAME: " + tc)
                        get_testcase_failure(spy_links,zone=args.zone,tc_name=tc)
                    monitor.final_job_list = []

            if option == '6':
                  for ci_name,ci_link in ci_list.items():
                    print("-------------------------------------------------------------------------------------------------")
                    print(ci_name)
                    if "sno" in ci_link:
                        print("Tests execution is not yet supported in SNO")
                        continue
                    spy_links = monitor.get_jobs_with_date(ci_link,start_date,end_date)
                    print_tc_frequency(spy_links,zone=args.zone)
                    monitor.final_job_list = []

if __name__ == "__main__":
    main()

