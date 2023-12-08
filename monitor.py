import json
import re
from bs4 import BeautifulSoup
import urllib3
import requests
from datetime import datetime
import xml.etree.ElementTree as ET

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def load_config(config_file):
    with open(config_file,'r') as config_file:
        config = json.load(config_file)
    return config 

def get_current_date():
    return datetime.now().date()

def parse_job_date(da):
    parse_date=datetime.strptime(da,"%Y-%m-%dT%H:%M:%SZ")
    job_run_date=parse_date.date()
    return job_run_date


def get_jobs(s):
    
    url = "https://prow.ci.openshift.org/job-history/gs/origin-ci-test/logs/" + s

    response = requests.get(url, verify=False, timeout=15)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        script_elements = soup.find_all('script')
        selected_script_element = None

        for script_element in script_elements:
            script_content = script_element.string
            if script_content:
                if 'allBuilds' in script_content:
                    selected_script_element = script_content
                    break
        
        if selected_script_element:
            var_name = 'allBuilds'
            pattern = rf'{var_name}\s*=\s*(.*?);'

            match = re.search(pattern, selected_script_element)
            if match:
                all_jobs=match.group(1)
                #print(all_jobs)
                try:
                    all_jobs_parsed=json.loads(all_jobs)
                    current_date=get_current_date()
                    jobs_run_today = []
                    for ele in all_jobs_parsed:
                        job_time=parse_job_date(ele["Started"])
                        if job_time == current_date and ele["Result"] != "PENDING":
                            job_log_path = ele["SpyglassLink"]
                            jobs_run_today.append(job_log_path)
                    return jobs_run_today
                except json.JSONDecodeError as e:
                    return "Failed to extract the spy-links from spylink please check the UI!"
                    
    else:
        return "Failed to get the prowCI response"
    

def cluster_deploy_status(spy_link):
    job_type,job_platform = job_classifier(spy_link)
    job_log_url = 'https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs' + spy_link[8:] + '/artifacts/' + job_type + '/ipi-install-' + job_platform +'-install/finished.json'

    response = requests.get(job_log_url, verify=False, timeout=15)
    if response.status_code == 200:
        try:
            cluster_status = json.loads(response.text)
            return cluster_status["result"]
        except json.JSONDecodeError as e:
            return 'ERROR'
    else:
        return 'ERROR'
    
def cluster_creation_error_analysis(spylink):
    job_type,job_platform = job_classifier(spylink)
    job_log_url = 'https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs' + spylink[8:] + '/artifacts/' + job_type + '/ipi-install-' + job_platform +'-install/build-log.txt'
    
    response = requests.get(job_log_url,verify=False)

    if response.status_code == 200:

        installation_log = response.text
        if job_platform == "powervs":
            failed_line_index = installation_log.find("FAILED")
            cluster_failure_log = installation_log[failed_line_index:].splitlines()
            for line in cluster_failure_log[1:7]:
                print(line)
                    
        elif job_platform == "libvirt":
            failed_line_index_1 = installation_log.find("level-error")
            
            if failed_line_index_1 == -1:
                failed_line_index_2 = installation_log.find("level=fatal")
                if failed_line_index_2 == -1:
                    failed_line_number_3 = installation_log.find("error:")
                    cluster_failure_log = installation_log[failed_line_number_3:].splitlines()

                    for line in cluster_failure_log[:7]:
                        print(line)
                else:
                    cluster_failure_log = installation_log[failed_line_index_2:].splitlines()

                    for line in cluster_failure_log[:7]:
                        print(line)
            else:
                cluster_failure_log = installation_log[failed_line_index_1:].splitlines()
                for line in cluster_failure_log[1:7]:
                    print(line)
    else:
        print("Error while fetching cluster installation logs")

def get_node_status(spy_link):
    '''Function to fetch the node status and determine if all nodes are up and running'''
    job_type,job_platform = job_classifier(spy_link)
    if job_platform == "powervs":
        job_type += "/gather-extra"
    else:
        job_type += "/gather-libvirt"
    
    node_log_url = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs" + spy_link[8:] + \
        "/artifacts/" + job_type +"/artifacts/oc_cmds/nodes"
    node_log_response = requests.get(node_log_url, verify=False, timeout=15)
    if "NAME" in node_log_response.text:
        response_str=node_log_response.text
        if "NotReady" in response_str:
            return "Some Nodes are in NotReady state"
        elif response_str.count("master-") != 3:
            return "Not all master nodes are up and running"
        elif response_str.count("worker-") != 2:
            return "Not all worker nodes are up and running"
    else:
        return "Node details not found"
    return "All nodes are in Ready state"

def check_node_crash(spy_link):
    job_type,_ = job_classifier(spy_link)
    crash_log_url = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs" + spy_link[8:] + "/artifacts/" +job_type + "/ipi-conf-debug-kdump-gather-logs/artifacts/"
    crash_log_response = requests.get(crash_log_url, verify=False, timeout=15)
    if "kdump.tar" in crash_log_response.text:
        print("*********************************")
        print ("ERROR- Crash observed in the job")
        print("*********************************")
    else:
        print("No crash observed")
        
def get_quota_and_nightly(spy_link):
    _,job_platform = job_classifier(spy_link)


    if 'ppc64le' in spy_link:
        build_log_url = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs" + spy_link[8:] + "/build-log.txt"
        if job_platform == "libvirt":
            job_platform+="-ppc64le"
        elif job_platform == "powervs":
            job_platform+="-[1-9]"

        zone_log_re = re.compile('(Acquired 1 lease\(s\) for {}-quota-slice: \[)([^]]+)(\])'.format(job_platform), re.MULTILINE|re.DOTALL)
        build_log_response = requests.get(build_log_url, verify=False, timeout=15)
        zone_log_match = zone_log_re.search(build_log_response.text)
        if zone_log_match is None:
            lease = "Failed to fetch lease information"
        else:
            lease = zone_log_match.group(2)
    # Fetch the nightly information for non-upgrade jobs
        if "upgrade" not in build_log_url:
            nightly_log_re = re.compile('(Resolved release ppc64le-latest to (\S+))', re.MULTILINE|re.DOTALL)
            nightly_log_match = nightly_log_re.search(build_log_response.text)
            if nightly_log_match is None:
                rc_nightly_log_re = re.compile('(Using explicitly provided pull-spec for release ppc64le-latest \((\S+)\))', re.MULTILINE|re.DOTALL)
                rc_nightly_log_match = rc_nightly_log_re.search(build_log_response.text)
                if rc_nightly_log_match is None:
                    nightly = "Unable to fetch nightly information- No match found"
                else:
                    nightly = rc_nightly_log_match.group(2)
            else:
                nightly = "ppc64le-latest-"+ nightly_log_match.group(2)
    # Fetch nightly information for upgrade jobs- fetch both ppc64le-initial and ppc64le-latest
        else:
            nightly_initial_log_re = re.compile('(Resolved release ppc64le-initial to (\S+))', re.MULTILINE|re.DOTALL)
            nightly_initial_log_match = nightly_initial_log_re.search(build_log_response.text)
            if nightly_initial_log_match is None:
                nightly = "Unable to fetch nightly ppc64le-initial information- No match found"
            else:
                nightly = "ppc64le-initial-"+ nightly_initial_log_match.group(2)
            nightly_latest_log_re = re.compile('(Resolved release ppc64le-latest to (\S+))', re.MULTILINE|re.DOTALL)
            nightly_latest_log_match = nightly_latest_log_re.search(build_log_response.text)
            if nightly_latest_log_match is None:
                nightly = nightly + " Unable to fetch nightly ppc64le-latest information- No match found"
            else:
                nightly = nightly + " ppc64le-latest-"+ nightly_latest_log_match.group(2)
        return lease, nightly
    
    elif 's390x' in spy_link:
        build_log_url = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs" + spy_link[8:] + "/build-log.txt"
        if job_platform == "libvirt":
            job_platform+="-s390x"

        zone_log_re = re.compile('(Acquired 1 lease\(s\) for {}-quota-slice: \[)([^]]+)(\])'.format(job_platform), re.MULTILINE|re.DOTALL)
        build_log_response = requests.get(build_log_url, verify=False, timeout=15)
        zone_log_match = zone_log_re.search(build_log_response.text)
        if zone_log_match is None:
            lease = "Failed to fetch lease information"
        else:
            lease = zone_log_match.group(2)
        nightly_log_re = re.compile('(Resolved release s390x-latest to (\S+))', re.MULTILINE|re.DOTALL)
        nightly_log_match = nightly_log_re.search(build_log_response.text)
        if nightly_log_match is None:
            rc_nightly_log_re = re.compile('(Using explicitly provided pull-spec for release s390x-latest \((\S+)\))', re.MULTILINE|re.DOTALL)
            rc_nightly_log_match = rc_nightly_log_re.search(build_log_response.text)
            if rc_nightly_log_match is None:
                nightly = "Unable to fetch nightly information- No match found"
            else:
                nightly = rc_nightly_log_match.group(2)
        else:
            nightly = "s390x-latest-"+ nightly_log_match.group(2)
        return lease, nightly


def job_classifier(spy_link):

    pattern = r'ocp.*?/'
    match = re.search(pattern,spy_link)

    if match:
        job_type = match.group(0)
        job_type = job_type.rstrip('/')

    if spy_link.find("powervs") != -1:
        job_platform = "powervs"
        return job_type,job_platform
    elif spy_link.find("libvirt") != -1:
        job_platform = "libvirt"
        return job_type,job_platform


def get_failed_monitor_testcases(spy_link,job_type):
    test_log_junit_dir_url = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs" + spy_link[8:] + "/artifacts/" + job_type + "/openshift-e2e-libvirt-test/artifacts/junit/"

    response = requests.get(test_log_junit_dir_url, verify=False, timeout=15)

    if response.status_code == 200:
        monitor_test_failure_summary_filename_re = re.compile('(test-failures-summary_monitor_2[^.]*\.json)')
        monitor_test_failure_summary_filename_match = monitor_test_failure_summary_filename_re.search(response.text, re.MULTILINE|re.DOTALL)
        
        if monitor_test_failure_summary_filename_match is not None:
            monitor_test_failure_summary_filename_str = monitor_test_failure_summary_filename_match.group(1)
            test_log_url="https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs" + spy_link[8:] + "/artifacts/" + job_type + "/openshift-e2e-libvirt-test/artifacts/junit/" + monitor_test_failure_summary_filename_str
            response_2 = requests.get(test_log_url,verify=False, timeout=15)
            if response_2.status_code == 200:
                try:
                    data = response_2.json()
                    e2e_failure_list = data['Tests']
                    return e2e_failure_list
                except json.JSONDecodeError as e:
                    return "Failed to parse the data from e2e-test log file!"
            else:
                return "Failed to get response from e2e-test log file url!"
        else:
            return "Test summary file not found"
    else:
        return "Failed to get response from e2e-test directory url"


def get_failed_e2e_testcases(spy_link,job_type):

    test_log_junit_dir_url = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs" + spy_link[8:] + "/artifacts/" + job_type + "/openshift-e2e-libvirt-test/artifacts/junit/"

    response = requests.get(test_log_junit_dir_url, verify=False, timeout=15)

    if response.status_code == 200:
        test_failure_summary_filename_re = re.compile('(test-failures-summary_2[^.]*\.json)')
        test_failure_summary_filename_match = test_failure_summary_filename_re.search(response.text, re.MULTILINE|re.DOTALL)
        
        if test_failure_summary_filename_match is not None:
            test_failure_summary_filename_str = test_failure_summary_filename_match.group(1)
            test_log_url="https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs" + spy_link[8:] + "/artifacts/" + job_type + "/openshift-e2e-libvirt-test/artifacts/junit/" + test_failure_summary_filename_str
            response_2 = requests.get(test_log_url,verify=False, timeout=15)
            if response_2.status_code == 200:
                try:
                    data = response_2.json()
                    e2e_failure_list = data['Tests']
                    return e2e_failure_list
                except json.JSONDecodeError as e:
                    return "Failed to parse the data from e2e-test log file!"
            else:
                return "Failed to get response from e2e-test log file url!"
        else:
            return "Test summary file not found"
    else:
        return "Failed to get response from e2e-test directory url" 

def get_junit_symptom_detection_testcase_failures(spy_link,job_type):
    test_log_junit_dir_url = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs" + spy_link[8:] + "/artifacts/" + job_type + "/gather-extra/artifacts/junit/junit_symptoms.xml"
    symptom_detection_failed_testcase = []
    response = requests.get(test_log_junit_dir_url,verify=False,timeout=15)
    if response.status_code == 200:
        root = ET.fromstring(response.content)
        for testcase in root.findall('.//testcase'):
            testcase_name = testcase.get('name')
            if testcase.find('failure') is not None:
                symptom_detection_failed_testcase.append(testcase_name)
        return symptom_detection_failed_testcase
    else:
        return 'Error fetching junit symptom detection test results'


def print_e2e_testcase_failures(spylink,jobtype):
    e2e_result = False
    e2e_failures = get_failed_e2e_testcases(spylink,jobtype)
    if isinstance(e2e_failures,list):
        if not e2e_failures:
            print("All e2e conformance test cases passed")
            e2e_result = True
        else:
            print("Failed testcases: ")
            for e in e2e_failures:
                print(e["Test"]["Name"])
    elif isinstance(e2e_failures,str):
        print(e2e_failures)
    return e2e_result

def print_monitor_testcase_failures(spylink,jobtype):
    e2e_result = False
    monitor_e2e_failures = get_failed_monitor_testcases(spylink,jobtype)
    if isinstance(monitor_e2e_failures,list):
        if not monitor_e2e_failures:
            print("All monitor test cases passed")
            e2e_result = True
        else:
            print("Failed monitor testcases: ")
            for e in monitor_e2e_failures:
                print(e["Test"]["Name"])
    elif isinstance(monitor_e2e_failures,str):
        print(monitor_e2e_failures)
    return e2e_result


final_job_list=[]


#fetches all the job spylinks in the given date range

def get_jobs_with_date(prowci_url,start_date,end_date):

    url = "https://prow.ci.openshift.org/job-history/gs/origin-ci-test/logs/" + prowci_url

    
    response = requests.get(url, verify=False, timeout=15)


    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')

        td_element = soup.find_all('td')
        td_element2 = str(td_element)
        next_link_pattern = r'/job[^>"]*'
        next_link_match = re.search(next_link_pattern,td_element2)
        if next_link_match != None:
            next_link = next_link_match.group()

        script_elements = soup.find_all('script')
        selected_script_element = None

        # print(script_elements) prints the list of scripts elements

        for script_element in script_elements:
            script_content = script_element.string
            if script_content:
                if 'allBuilds' in script_content:
                    selected_script_element = script_content
                    break
        
        # print(type(selected_script_element)) ##prints script element with a var name

        if selected_script_element:
            var_name = 'allBuilds'
            pattern = rf'{var_name}\s*=\s*(.*?);'

            match = re.search(pattern, selected_script_element)
            
            if match:
                all_jobs=match.group(1)
                try:
                    all_jobs_parsed=json.loads(all_jobs)
                    for ele in all_jobs_parsed:
                        job_time=parse_job_date(ele["Started"])
                        
                        if end_date <= job_time <= start_date and ele["Result"] != "PENDING" :
                            job_log_path = ele["SpyglassLink"]
                            final_job_list.append(job_log_path)

                    if next_link_match != None:
                        next_page_spylink=next_link[35:]
                        check=get_next_page_first_build_date(next_page_spylink,end_date)
                    
                        if check == True:
                            get_jobs_with_date(next_page_spylink,start_date,end_date)
                        elif check == 'ERROR':
                            print("Error while fetching the job-links please check the UI")
                    return final_job_list
                except json.JSONDecodeError as e:
                    print("Failed to extract data from the script tag")
                    return "ERROR"
    else:
        print("Failed to get response from the prowCI link")
        return 'ERROR'


#Checks if the jobs next page are in the given date range
 
def get_next_page_first_build_date(ci_next_page_spylink,end_date):

    ci_next_page_link = 'https://prow.ci.openshift.org/job-history/gs/origin-ci-test/logs/' + ci_next_page_spylink

    response = requests.get(ci_next_page_link, verify=False, timeout=15)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        script_elements = soup.find_all('script')
        selected_script_element = None

        for script_element in script_elements:
            script_content = script_element.string
            if script_content:
                if 'allBuilds' in script_content:
                    selected_script_element = script_content
                    break
        
        if selected_script_element:
            var_name = 'allBuilds'
            pattern = rf'{var_name}\s*=\s*(.*?);'

            match = re.search(pattern, selected_script_element)
            if match:
                all_jobs=match.group(1)
                
                try:
                    all_jobs_parsed=json.loads(all_jobs)
                    job_date=all_jobs_parsed[0]["Started"]
                    parsed_job_date = parse_job_date(job_date)
                    if end_date <= parsed_job_date:
                        return True
                    elif end_date > parsed_job_date:
                        return False
                except json.JSONDecodeError as e:
                    print("Failed to extract the spy-links from spylink please check the UI!")
                    return "ERROR"
    else:
        print("Failed to get the prowCI response")
        return 'ERROR'

def get_brief_job_info(prow_ci_name,prow_ci_link,start_date=None,end_date=None,zone=None):
    

    if start_date is not None and end_date is not None:
        job_list = get_jobs_with_date(prow_ci_link,start_date,end_date)
    else:
        job_list = get_jobs(prow_ci_link)

    if isinstance(job_list,str):
        print(job_list)
        return 1
    summary_list = []   
    if len(job_list) == 0:
        print ("No job runs on {} ".format(prow_ci_name))

    deploy_count = 0
    e2e_count = 0
    i=0

    pattern_job_id =  r'/(\d+)'

    for job in job_list:
        match = re.search(pattern_job_id, job)
        job_id = match.group(1)
        lease, _ = get_quota_and_nightly(job)
        if zone is not None and lease not in zone :
            continue
        e2e_test_result = e2e_monitor_result = False
        cluster_status=cluster_deploy_status(job)
        i=i+1
        job_dict = {}
        job_dict["Build"] = prow_ci_name
        job_dict["Prow Job ID"] = job_id
        job_dict["Install Status"] = cluster_status
        job_dict["Lease"]=lease
        
        if cluster_status == 'SUCCESS' and "4.15" not in prow_ci_link:
            deploy_count += 1
            job_type,_ = job_classifier(job)
            e2e_test_result = get_failed_e2e_testcases(job,job_type)
            if isinstance(e2e_test_result,list):
                if len(e2e_test_result) == 0:
                    e2e_count += 1
                    job_dict["Test result"] = "PASS"   
                elif len(e2e_test_result) != 0:
                    job_dict["Test result"] = str(len(e2e_test_result)) + " testcases failed"   
            elif isinstance(e2e_test_result,str):
                job_dict["Test result"] = e2e_test_result

        elif cluster_status == 'SUCCESS' and "4.15" in prow_ci_link:
            deploy_count += 1
            job_type,_ = job_classifier(job)
            e2e_test_result = get_failed_e2e_testcases(job,job_type)
            e2e_monitor_result = get_failed_monitor_testcases(job,job_type)
            if isinstance(e2e_test_result,list) and isinstance(e2e_monitor_result,list):        
                total_e2e_failure = len(e2e_test_result)+len(e2e_monitor_result)
                if total_e2e_failure != 0:
                    job_dict["Test result"] = str(total_e2e_failure) + " testcases failed"
                elif total_e2e_failure == 0:
                    e2e_count += 1
                    job_dict["Test result"] = "PASS"
            elif isinstance(e2e_test_result,list) and isinstance(e2e_monitor_result,str): 
                job_dict["Test result"] = e2e_monitor_result #the error message received while fetching monitor testcase results
                if len(e2e_test_result) !=0:
                    job_dict["Test result"] += str(len(e2e_test_result)) + " conformance testcases failed"
                elif len(e2e_test_result) == 0:
                    job_dict["Test result"] += "PASS"
            elif isinstance(e2e_test_result,str) and isinstance(e2e_monitor_result,list):
                job_dict["Test result"] = e2e_test_result #the error message received while fetching conformance testcase results
                if len(e2e_monitor_result) !=0:
                    job_dict["Test result"] += str(len(e2e_monitor_result)) + " monitor testcases failed"
                elif len(e2e_monitor_result) == 0:
                    job_dict["Test result"] += "PASS"
            elif isinstance(e2e_test_result,str) and isinstance(e2e_monitor_result,str):
                job_dict["Test result"] = e2e_test_result + " " + e2e_monitor_result
        summary_list.append(job_dict)
    return summary_list

def get_detailed_job_info(prow_ci_name,prow_ci_link,start_date=None,end_date=None,zone=None):

    if start_date is not None and end_date is not None:
        job_list = get_jobs_with_date(prow_ci_link,start_date,end_date)
    else:
        job_list = get_jobs(prow_ci_link)
    print("--------------------------------------------------------------------------------------------------")
    print(prow_ci_name)

    if isinstance(job_list,str):
        print(job_list)
        return 1
        

    deploy_count = 0
    e2e_count = 0
    i=0

    pattern_job_id =  r'/(\d+)'

    jobs_to_deleted = []
    for job in job_list:
        match = re.search(pattern_job_id, job)
        job_id = match.group(1)
        e2e_test_result = e2e_monitor_result = False
        lease, nightly = get_quota_and_nightly(job)
        if zone is not None and lease not in zone:
            jobs_to_deleted.append(job)
            continue
        cluster_status=cluster_deploy_status(job)
        i=i+1
        print(i,".","Job ID: ",job_id)
        print("Job link: https://prow.ci.openshift.org/"+job)
        
        print("Lease Quota-", lease,"\nNightly info-", nightly)
        check_node_crash(job)
        node_status = get_node_status(job)
        print(node_status)

        if cluster_status == 'SUCCESS' and "4.15" not in prow_ci_link:
            deploy_count += 1
            job_type,_ = job_classifier(job)
            e2e_test_result = get_failed_e2e_testcases(job,job_type)
            if isinstance(e2e_test_result,list):
                if len(e2e_test_result) == 0:
                    e2e_count += 1
                    print("All e2e testcases passed")
                elif len(e2e_test_result) != 0:
                    print_e2e_testcase_failures(job,job_type)
                    print(len(e2e_test_result),"testcases failed")
            elif isinstance(e2e_test_result,str):
                print(e2e_test_result)

        elif cluster_status == 'SUCCESS' and "4.15" in prow_ci_link:
            deploy_count += 1
            job_type,_ = job_classifier(job)
            e2e_test_result = get_failed_e2e_testcases(job,job_type)
            e2e_monitor_result = get_failed_monitor_testcases(job,job_type)
            if isinstance(e2e_test_result,list) and isinstance(e2e_monitor_result,list):        
                total_e2e_failure = len(e2e_test_result)+len(e2e_monitor_result)
                if total_e2e_failure != 0:
                    print_e2e_testcase_failures(job,job_type)
                    print_monitor_testcase_failures(job,job_type)
                    print(total_e2e_failure,"testcases failed")
                elif total_e2e_failure == 0:
                    e2e_count += 1
                    print("All e2e testcases passed")
            elif isinstance(e2e_test_result,list) and isinstance(e2e_monitor_result,str):
                print(e2e_monitor_result) #prints the error message recived while fetching monitor testcase results
                if len(e2e_test_result) !=0:
                    print_e2e_testcase_failures(job,job_type)
                    print(len(e2e_test_result), "conformance testcases failed")
                elif len(e2e_test_result) == 0:
                    print("All conformance e2e testcases passed")
            elif isinstance(e2e_test_result,str) and isinstance(e2e_monitor_result,list):
                print(e2e_test_result) #prints the error message recived while fetching conformance testcase results
                if len(e2e_monitor_result) !=0:
                    print_monitor_testcase_failures(job,job_type)
                    print(len(e2e_monitor_result), "monitor testcases failed")
                elif len(e2e_monitor_result) == 0:
                    print("All monitor e2e testcases passed")
            elif isinstance(e2e_test_result,str) and isinstance(e2e_monitor_result,str):
                print(e2e_test_result)
                print(e2e_monitor_result)

        elif cluster_status == 'FAILURE':
                print("Cluster Creation Failed")
                cluster_creation_error_analysis(job)

        elif cluster_status == 'ERROR':
            print('Unable to get cluster status please check prowCI UI ')

        print("\n")
        
    job_list = list(set(job_list) - set(jobs_to_deleted))
    if len(job_list) != 0:
        print ("\n{}/{} deploys succeeded".format(deploy_count, len(job_list)))
        print ("{}/{} e2e tests succeeded".format(e2e_count, len(job_list)))
        print("--------------------------------------------------------------------------------------------------")
    else:
        print ("No job runs on {} ".format(prow_ci_name))
    
