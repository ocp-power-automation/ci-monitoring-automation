from bs4 import BeautifulSoup
import urllib3
from tabulate import tabulate
import monitor
import argparse


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



def main():
    parser = argparse.ArgumentParser(description='Get the daily buid updates')
    parser.add_argument('--info_type', default='brief', choices=['brief','detailed'], help='specify the job info type (brief or detailed)')
    parser.add_argument('--zone', help='specify the lease/zone', type= lambda arg:arg.split(','))
    parser.add_argument('--job_type', default='p', choices=['p','z','pa'], help='Specify the CI job type (Power(p) or s390x(z) or Power Auxillary(pa)), default is p')
    args = parser.parse_args()
    if args.job_type == 'p':
        config_file = 'p_periodic.json'
    elif args.job_type == 'z':
        config_file = 'z_periodic.json'
    elif args.job_type == 'pa':
        config_file = 'p_auxillary.json' 
    
    monitor.PROW_URL = monitor.set_prow_url(args.job_type)
    config_data = monitor.load_config(config_file)
    if args.info_type == "brief":
        summary_list = []
        for ci_name,ci_link in config_data.items():
            build_list = monitor.get_jobs(ci_link)
            summary_list.extend(monitor.get_brief_job_info(build_list,ci_name,zone=args.zone))
        if len(summary_list)==0:
            print("******************* No builds found ******************************")
        print(tabulate(summary_list, headers='keys', tablefmt="pipe", stralign='left'))
    elif args.info_type == "detailed":
        for ci_name,ci_link in config_data.items():
            build_list = monitor.get_jobs(ci_link)
            monitor.get_detailed_job_info(build_list,ci_name,zone=args.zone)

if __name__ == "__main__":
    main()
