from bs4 import BeautifulSoup
import urllib3
from tabulate import tabulate
import re
from datetime import datetime,timedelta
import monitor
import argparse
import configparser

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

config_vars = configparser.ConfigParser()

config_vars.read('config.ini')

JENKINS = config_vars.get('Settings', 'JENKINS')

def get_release_date():
    '''
    Fetch release start date and end date
    Returns:
        Date: Start date
        Date: End date
    '''
    release = input("Enter the release: ") #release that needs to be checked
    assert len(release.strip()) != 0, "Release value should not be empty"
    nxt_rls = input("Enter the next release (provide latest if no next release): ") #next release or latest
    assert len(nxt_rls.strip()) != 0 , "Next release value should not be empty"
    r = re.compile(r"^\d*[.,]?\d*$")
    if re.match(r,release)==False:
        print("Enter valid release version")

    try:

        release_date_str = monitor.fetch_release_date(release)
        release_date = datetime.strptime(release_date_str,"%Y-%m-%d  %H:%M:%S")

        if nxt_rls != "latest":
            nxt_rls_str = monitor.fetch_release_date(nxt_rls)
            nxt_rls_date = datetime.strptime(nxt_rls_str,"%Y-%m-%d  %H:%M:%S")
        else:
            nxt_rls_date=datetime.now()
    except ValueError:
        print("Invalid date format")
        return None

    return nxt_rls_date,release_date


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
        node_status = ''
        match = re.search(pattern, url)
        job_id = match.group(1)
        lease,_ = monitor.get_quota_and_nightly(url)
        if zone is not None and lease not in zone :
            continue
        job_status = monitor.check_job_status(url)
        cluster_deploy_status = monitor.cluster_deploy_status(url)
        print(job_id)
        if cluster_deploy_status == 'SUCCESS' and job_status == 'FAILURE':
            node_status = monitor.get_node_status(url)
            print(node_status)
        monitor.check_node_crash(url)
        print("--------------------------------------------------------------------------------------------------")

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
        job_status=monitor.check_job_status(spylink)
        if job_status == 'FAILURE':
            cluster_status=monitor.cluster_deploy_status(spylink)
            if cluster_status == 'SUCCESS':
                j=j+1
                print(str(j)+".",job_id)
                monitor.print_all_failed_tc(spylink,job_type)
                print("\n")
    print("--------------------------------------------------------------------------------------------------")
    print("\n")

def print_tc_frequency(spylinks, zone, tc_name = None):
    """
    To display the testcases failing with its frequency

    Args:
        spylinks (list): list of builds which needs to be checked.
        zone (list): List of the zones/leases that need to checked.
        tc_name (list): list of testcase name.

    """

    frequency = monitor.get_testcase_frequency(spylinks,zone,tc_name)
    table_data = [(key,value) for key, value in frequency.items()]
    print(tabulate(table_data, headers = ['Testcase','Frequency'], tablefmt='grid'))


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
        job_status=monitor.check_job_status(spylink)
        if job_status == 'FAILURE':
            cluster_status=monitor.cluster_deploy_status(spylink)
            if cluster_status == 'SUCCESS':
                if monitor.check_testcase_failure(spylink,job_type,tc_name):
                    j=j+1
                    print(str(j)+"."+"Job_id: "+job_id)
                    print("https://prow.ci.openshift.org"+ spylink)
                    print("\n")
    print("--------------------------------------------------------------------------------------------------")
    print("\n")

def display_ci_links(config_data,filter):

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
            if filter[0]=='All':
                j=j+1
                ci_name_list.append(ci_name)
                print(j,"",ci_name)
            elif any(w in ci_name for w in filter):
                j=j+1
                ci_name_list.append(ci_name)
                print(j,"",ci_name)

        j=j+1
        print(j, " All the above")
        option = input("Select the required ci's serial number with a space ")
        selected_options = option.split()
        for ci in selected_options:
            try:
                ci_to_int = int(ci)
                if 0 < ci_to_int <= len(config_data)+1:
                    options_int_list.append(ci_to_int)
                else:
                    return_value = "Enter the options in range of 1 to " + str(len(config_data)+1)
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

   
    if options_int_list[0]==j:
       options_int_list=list(range(1,j))

    for i in options_int_list:
        config_temp_data = {ci_name_list[i-1]: config_data[ci_name_list[i-1]]}
        selected_config_data.update(config_temp_data)
        config_temp_data = {}

    return selected_config_data

def get_query_options():

    """
    Displays or retrieves the user-selected query option for job history functionalities.

    Behavior:
        - If running in a non-Jenkins environment (JENKINS == "False"):
            Prompts the user to select one of the available job history options:
                1. Check Node Crash
                2. Brief Job Information
                3. Detailed Job Information
                4. Failed Testcases
                5. Get Builds with Testcase Failure
                6. Get Testcase Failure Frequency
                7. Get Build Based on Release
            Returns the user's selected option.
        
        - If running in a Jenkins environment (JENKINS == "True"):
            Reads the preconfigured option from the Jenkins configuration (config_vars).

    Returns:
        str: The selected option (as input or configuration value).
    """
    if JENKINS == "False":
        print("Please select one of the option from Job History functionalities: ")
        print("1. Check Node Crash")
        print("2. Brief Job information")
        print("3. Detailed Job information")
        print("4. Failed testcases")
        print("5. Get builds with testcase failure")
        print("6. Get testcase failure frequency")
        print("7. Get build based on release ")
        option = input("Enter the option: ")

    elif JENKINS == "True":
        option = config_vars.get('Settings','query_option')

    return option

def get_testcase_names():

    """
    Retrieves a list of testcase names either from user input or from Jenkins configuration.

    Behavior:
        - If running in a non-Jenkins environment (JENKINS == "False"):
            Prompts the user to manually enter testcase names separated by commas.
            Example: test_case_1,test_case_2,test_case_3
            Returns a list of those testcase names.

        - If running in a Jenkins environment (JENKINS == "True"):
            Reads the testcase names from the Jenkins configuration variable
            (under the 'Settings' section, key 'tc_name') and splits them into a list.

    Returns:
        list[str] | None: 
            A list of testcase names.
    """
    tc_list=[]
    if JENKINS == "False":
        tc_name = input("Enter the testcase names comma seperated: ")
        if len(tc_name) == 0:
            return None
        elif len(tc_name) > 0: 
            tc_list =  tc_name.split(",")
            return tc_list
    if JENKINS == "True":
        tc_name = config_vars.get('Settings','tc_name')
        if len(tc_name) == 0:
            return None
        elif len(tc_name) > 0: 
            tc_list =  tc_name.split(",")
            return tc_list



def main():
    parser = argparse.ArgumentParser(description='Get the job history')
    parser.add_argument('--zone', help='specify the lease/zone', type= lambda arg:arg.split(','))
    parser.add_argument('--job_type', default='p', choices=['p','z','pa'], help= 'Specify the CI job type (Power(p) or s390x(z) or Power Auxillary(pa)), default is p')
    parser.add_argument('--filter',default='All',type= lambda arg:arg.split(','), help='Specify the filter string to fetch jobs (Example heavy build / libvirt / powervs / upgrade / 4.14 / 4.15 / 4.16 / 4.17/ 4.18 )')
    args = parser.parse_args()
    filter=args.filter

    if args.job_type == 'p':
        config_file = 'p_periodic.json'
    elif args.job_type == 'z':
        config_file = 'z_periodic.json'
    elif args.job_type == 'pa':
        config_file = 'p_auxillary.json'
    
    monitor.PROW_URL = monitor.set_prow_url(args.job_type)
    config_data = monitor.load_config(config_file)

    ci_list = display_ci_links(config_data,filter)
    if isinstance(ci_list,dict):
        option = get_query_options()

        if option == '7':
            start_date,end_date = get_release_date()
        else:
            start_date,end_date = get_date_input()

        if start_date != None and end_date != None:
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
                    spy_links = monitor.get_jobs_with_date(ci_link,start_date,end_date)
                    summary_list.extend(monitor.get_brief_job_info(spy_links,ci_name,zone=args.zone))
                    monitor.final_job_list = []
                print(tabulate(summary_list, headers='keys', tablefmt="pipe", stralign='left'))
            
            if option == '3':
                for ci_name,ci_link in ci_list.items():
                    spy_links = monitor.get_jobs_with_date(ci_link,start_date,end_date)
                    monitor.get_detailed_job_info(spy_links,ci_name,zone=args.zone)
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
                tc_list =  get_testcase_names()

                if tc_list == None:
                    print("Please provide atleast one testcase name:")
                    return 1

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
                  tc_list = get_testcase_names()
                    
                  for ci_name,ci_link in ci_list.items():
                    print("-------------------------------------------------------------------------------------------------")
                    print(ci_name)
                    if "sno" in ci_link:
                        print("Tests execution is not yet supported in SNO")
                        continue
                    spy_links = monitor.get_jobs_with_date(ci_link,start_date,end_date)
                    print(len(spy_links),"builds have run in the date range of",start_date,"to",end_date)
                    print_tc_frequency(spy_links,zone=args.zone,tc_name=tc_list)
                    monitor.final_job_list = []
            if option == '7':
                for ci_name,ci_link in ci_list.items():
                    spy_links = monitor.get_jobs_with_date(ci_link,start_date,end_date)
                    monitor.get_detailed_job_info(spy_links,ci_name,zone=args.zone)
                    monitor.final_job_list = []

if __name__ == "__main__":
    main()

