import argparse
import time
import glob
import multiprocessing
import subprocess
import os
import sys
import shutil
import re
import signal
import requests

# Test settings will be overridden by any command line arguments provided
TEST_SETTINGS = {
    # Commands to track
    'commands_to_track': ['./SvtAv1EncApp --preset -1 --passes 1 -q 57 --keyint 66 --enable-tpl-la 1 -i /home/inteladmin/stream/weekend_run_set/10bit/wikipedia_420_10bit.y4m -b svt_M-1_wikipedia_420_10bit_Q57.bin',
                        ],

    # Issue Info
    'issue_type': 'crash',                          # r2r | hang
    'max_runs' : 50,                             # Number of attempts to reproduce an issue before calling it non preset
    
    # Git settings
    'git_url': '',                                # [Optional] Constructed from settings if not provided
    'commit': '',
    'branch': '',                                 # [Optional] Default is master
    'mr': '',                                     # [Optional] Default is master
    'project_group': 'AOMediaCodec',              # [Optional] AOMediaCodec | svt-team, extrracted from git_url if provided
    
    # Tracking Settings                           # Multiple settings can be applied, track_commit is always first
    'track_commit': 0,                            # [Optional] Track the commit that introduces an issue
    'track_debug_macro': 0,                       # [Optional] Track the debug macro that causes an issue
    'track_feature': 1,                           # [Optional] Track the feature that causes an issue
    
    # System settings
    'compiler': 'gcc',                            # clang or gcc
    'cpu_count': multiprocessing.cpu_count(),     # num pool for lp
    'non_lp_divisor': 8,                          # num pool divisor for non-lp

    # Relevent to getting commands from CI pipeline
    'pipeline_id': '',                            # [Optional] If none provided, commands_to_track is used for commands
    'track_only_host_ci_jobs': 0,                 # [Optional] Only track commands from jobs on machine running the script
    'access_token': '',                           # Needs at least api_read permissions. May also be needed for cloning certain repos.
    'proxy': {'http': '', 'https': ''},           # [Optional] If empty will be filled using the machine's proxy settings

}

TEST_FUNCTION = {
    'r2r': lambda command: test_for_r2r(command),
    'hang': lambda command: test_for_hang(command),
    'crash' : lambda command: test_for_crash(command),
}

def test_for_crash(command):
    pipe = subprocess.Popen(command, shell=True, cwd=os.getcwd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = pipe.communicate()
    pipe.wait()
    print('output',output)
    print('error',error)
    if 'double free or corruption' in str(output) or 'double free or corruption' in str(error):
        return True, 1
    return False, 1
    
def main():
    # Step 1: Initialize the tracking_results dictionary to store the tracking information.
    tracking_results = dict()

    # Step 2: Record the start time to measure the tracking duration.
    t0 = time.time()

    # Step 3: Parse command-line arguments to get necessary input.
    access_token, pipeline_id, commit, branch, mr, project_group, track_commit, track_debug_macro, track_feature, track_only_host_ci_jobs, compiler = parse_command_line()

    # Step 4: Get the Git info for the specified project.
    access_token, project_group, TEST_SETTINGS['git_url'] = get_git_info(access_token,project_group,TEST_SETTINGS['git_url'])

    # Step 5: Set the compiler environment for the tracking process.
    set_compiler_environment(compiler)

    # Step 6: Determine the modes to test based on the provided settings.
    modes = set_modes_to_test(track_commit, track_debug_macro, track_feature)

    # Step 7: Print the tracking information (MR, branch, and commit) for user reference.
    if mr or branch or commit:
        print("Tracking on {} {} {}\n".format(mr, branch, commit))
    else:
        print('Tracking on master')

    # Step 8: If access_token and pipeline_id are provided, obtain the failed r2r commands from the CI job.
    if access_token and pipeline_id:
        TEST_SETTINGS['commands_to_track'] = get_commands_from_ci(track_only_host_ci_jobs, access_token, pipeline_id, project_group)
        print("Testing r2r commands from failed CI jobs: {}".format(TEST_SETTINGS['commands_to_track']))
    elif pipeline_id:
        print('Warning: cannot get commands from CI pipeline without an access token. Using script commands instead')

    # Step 9: Iterate over the selected modes for tracking (0, 1, or 2).
    for mode in modes:

        # Step 10: Iterate through the list of r2r commands.
        for command in TEST_SETTINGS['commands_to_track']:
            
            # Step 11: Check if the culprit has already been set or if there is a culprit_commit to use
            # If it doesn't exist, create a new dictionary entry for the current command in the tracking_results.
            tracking_results, culprit_commit, tracked = check_past_results(command, tracking_results, mode)
            if tracked:
                continue
            if culprit_commit:
                commit = culprit_commit

            # Step 12: If the test_name contains 'nonlp', reduce the CPU count to a fraction for non-lp tests.
            if '--lp' not in command or '--lp 0' in command:
                TEST_SETTINGS['cpu_count'] = int(multiprocessing.cpu_count()) // TEST_SETTINGS['non_lp_divisor']  # num pool for non-lp

            # Step 13: Set up the environment for tracking the command in the specified git repository.
            setup_environment(TEST_SETTINGS['git_url'], branch, commit, mr)

            # Step 14: Check that the issue is reproducible with a large number of runs; otherwise, skip it as a likely fake/memory issue.
            culprit_result, tracking_results[command]['num_runs'] = reproduce_issue(command)

            # Step 15 If the command could not be reproduced, skip it and continue to the next command.
            if not culprit_result:
                print("{} could not be reproduced, skipping".format(command))
                continue

            # Step 16: Track the issue for the current command based on the selected mode and functional preset (if applicable).
            culprit_patch = track_issue(mode, command)
            
            # Step 17: Check all commands with the same culprit patch and update tracking_results accordingly.
            tracking_results = check_all_commands_with_culprit(TEST_SETTINGS['commands_to_track'], command, culprit_patch,mode,tracking_results)
          
            # Step 18: Print the time taken for tracking the current command.
            print('Tracking took {}\n'.format(time.time() - t0))


    # Step 19: Provide the final tracking summary for all commands.
    summarize_results(tracking_results)

def check_past_results(command, tracking_results, mode):
    commit = None
    tracked = False
    if command in tracking_results:
        if mode == '2':
            if 'culprit_commit' in tracking_results[command]:
                tracked = True
        elif mode == '1':
            if 'culprit_macro' in tracking_results[command]:
                tracked = True
            elif 'culprit_commit' in tracking_results[command]:
                commit = tracking_results[command]['culprit_commit']
                tracked = False
        elif mode == '0':
            if 'culprit_feature' in tracking_results[command]:
                tracked = True
            elif 'culprit_commit' in tracking_results[command]:
                commit = tracking_results[command]['culprit_commit']
                tracked = False
        
    else:
        tracking_results[command] = dict()
        tracking_results[command]['test_name'] = parse_test_name(command)
        tracked = False
    return tracking_results, commit, tracked

def set_modes_to_test(track_commit, track_debug_macro, track_feature):
    modes = []
    mode_phrase = 'tracking '
    if track_commit:
        modes.append('2')
        mode_phrase += 'commit '
    if track_debug_macro:
        modes.append('1')
        mode_phrase += 'debug macro '
    if track_feature:
        modes.append('0')
        mode_phrase += 'feature '

    print(mode_phrase)
            
    return modes


def track_issue(mode, command):
    if mode == '0':
        functional_preset,culprit_preset = get_functional_and_culprit_preset(command)

        if functional_preset == None or culprit_preset == None:
            return None

        feature_lines = get_features(culprit_preset, functional_preset)
        culprit_patch = find_all_culprits(feature_lines, command,culprit_preset,functional_preset)

    elif mode == '1':
        macro_lines = get_debug_macros()
        issue_present, issue_not_present = find_culprit(macro_lines, command)
        culprit_patch = issue_not_present

    elif mode == '2':
        repo_folder = os.path.join(os.getcwd(), 'svt')
        commit_list = get_commits(repo_folder)
        issue_present, issue_not_present = find_culprit(commit_list, command)
        culprit_patch = issue_present
        
    return culprit_patch


def get_commits(encoder_dir):
    '''get desired commit'''
    commits = execute_command(["git log -n 100 --oneline", encoder_dir])
    commits = [str(commit).split(' ')[0].split("'")[-1].split('"')[-1] for commit in commits.splitlines()]

    return commits


def setup_environment(git_url, branch, commit, mr):
    subprocess.call("rm -rf svt", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.call("git clone {} svt".format(git_url), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    if mr:
        subprocess.call("git -C svt fetch origin merge-requests/{}/head".format(mr), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.call("git -C svt checkout FETCH_HEAD", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
    if branch:
        subprocess.call("git -C svt checkout {}".format(branch), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
    if commit:
        subprocess.call("git -C svt checkout {} --quiet".format(commit), shell=True)
    subprocess.call("mkdir -p svt/patches", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def get_debug_macros():
    subprocess.call("git -C svt reset --hard", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    macro_lines = []
    target_file = os.path.join(os.getcwd(), 'svt', 'Source', 'API', 'EbDebugMacros.h')

    with open(target_file) as lines:
        for line_number, line in enumerate(lines):
            if r'#define' in line and ' 1 ' in line:
                macro_lines.append([target_file, line_number,line])

    return macro_lines[::-1]


def get_features(culprit_preset, functional_preset):
    subprocess.call("git -C svt reset --hard", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    feature_lines = []

    target_dirs = [os.path.join(os.getcwd(), 'svt', 'Source', 'Lib', 'Encoder', 'Codec'),
                   os.path.join(os.getcwd(), 'svt', 'Source', 'Lib', 'Encoder', 'Globals')]

    for target_dir in target_dirs:
        for file in glob.glob('{}/*'.format(target_dir)):
            with open(file) as lines:
                for line_number, line in enumerate(lines):
                    if int(functional_preset) < int(culprit_preset):
                        if re.search(r'<=\s*ENC_M\d*',line) and functional_preset in line and '<' in line and r'#' not in line and '/' not in line:
                            feature_lines.append([file, line_number])
                    else:
                        if re.search(r'<=\s*ENC_M\d*',line) and culprit_preset in line and '<' in line and r'#' not in line and '/' not in line:
                            feature_lines.append([file, line_number])

    return feature_lines

def patch_debug_macro(suspected_culprit,macro_lines):
    lines_to_patch = []
    
    subprocess.call("git -C svt reset --hard", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    file_to_patch = suspected_culprit[0]
    line_number_to_patch = suspected_culprit[1]
    line_to_patch = suspected_culprit[2]
    cleaned_line = re.sub(r'\s+', ' ', line_to_patch)
    print("Patching line {} of {} :{}".format(line_number_to_patch,file_to_patch,cleaned_line))
    
    '''Get list of lines to patch going from bottom to top'''

    for target_file, line_number,line in macro_lines:
        lines_to_patch.append([target_file, line_number])
        if line == line_to_patch:
            break

    patch_file = generate_patch(lines_to_patch)

    subprocess.call("git -C svt apply {} -C1 --ignore-whitespace".format(patch_file), shell=True)
    return patch_file


def patch_features(lines_to_patch,culprit_preset,functional_preset):
    subprocess.call("git -C svt reset --hard", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    print("Patching line {} of {}".format(lines_to_patch[1],lines_to_patch[0]))
    patch_file = generate_patch([lines_to_patch],culprit_preset,functional_preset)
    
  
    pipe = subprocess.Popen("git -C svt apply {} -C1 --ignore-whitespace".format(patch_file), shell=True, cwd=os.getcwd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    output, error = pipe.communicate()
    
    if output or error:
        print("Git apply output: {} error: {}".format(output,error))
    
    return patch_file


def generate_patch(lines_to_patch,culprit_preset=None,functional_preset=None):
    subprocess.call("git -C svt reset --hard", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    for file_name, line_number in lines_to_patch:
        with open(file_name, 'r') as file:
            lines = file.readlines()

        if 'EbDebugMacros' in file_name:
            lines[line_number] = lines[line_number].replace(' 1 ', ' 0 ')
        else:
            lines[line_number] = lines[line_number].replace('<=', '>')
            
        with open(file_name, 'w') as file:
            file.writelines(lines)

    patch_name = '{}_{}.patch'.format(os.path.split(file_name)[-1], line_number + 1)
    patch_file = os.path.join(os.getcwd(), 'svt', 'patches', patch_name)

    
    subprocess.call("git -C svt diff > {}".format(patch_file), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    subprocess.call("git -C svt reset --hard", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return patch_file


def find_all_culprits(patches, command,culprit_preset,functional_preset):
    culprit_patches = []
    
    for lines_to_patch in patches[:]:
        patch_features(lines_to_patch,culprit_preset,functional_preset)
        build_status = build_encoder()
        
        if build_status is None:
            print('Build Failed, skipping')
            continue
        
        test = TEST_FUNCTION.get(TEST_SETTINGS['issue_type'])
        culprit_result, number_of_runs = test(command)

        if not culprit_result:
            culprit_patches.append(lines_to_patch)
            
    return culprit_patches


def find_culprit(patches, command):

    macros_list = list(patches)
    if len(patches) == 1:
        return patches
    issue_present = ''
    issue_not_present = ''

    left = 0
    right = len(patches) - 1

    while left <= right:
        mid = (left + right) // 2
        # print("total: {} mid {}".format(len(patches),mid))
        if isinstance(patches[mid], list):
            patch_debug_macro(patches[mid], macros_list)
            build_status = build_encoder()            
        else:
            '''Is a commit'''
            print("Testing commit {}".format(patches[mid]))
            build_status = build_encoder(str(patches[mid]))

        if build_status is None:
            print('Faulty build, removing from patch list')
            patches.remove(patches[mid])
            continue

        os.system('./SvtAv1EncApp --version')

        test = TEST_FUNCTION.get(TEST_SETTINGS['issue_type'])
        culprit_result, number_of_runs = test(command)
    
        if culprit_result:
            issue_present = patches[mid]
            left = mid + 1  # Continue searching for an earlier solution
        else:
            issue_not_present = patches[mid]
            right = mid - 1  # Refine the patch and search for a later solution

    return issue_present, issue_not_present


def build_encoder(commit=None):
        
    repo_folder = os.path.join(os.getcwd(), 'svt')
    build_file_path = os.path.join(repo_folder, 'Build', 'linux', 'build.sh')
    bin_folder = os.path.join(repo_folder, 'Bin', 'Release')

    if commit:
        subprocess.call('git reset --hard {}'.format(commit), cwd=repo_folder, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    pipe = subprocess.Popen('chmod +x {}'.format(build_file_path), shell=True, cwd=os.getcwd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pipe.wait()

    pipe = subprocess.Popen('{} static'.format(build_file_path), shell=True, cwd=os.getcwd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = pipe.communicate()
    pipe.wait()

    if 'failed' in str(output) or 'failed' in str(error):
        return False

    for file in glob.glob('{}/*'.format(bin_folder)):
        shutil.copy(file, os.getcwd())

    return True

def get_functional_and_culprit_preset(command):
    test = TEST_FUNCTION.get(TEST_SETTINGS['issue_type'])

    functional_presets = []
    testing_preset = 13
    culprit_presets = []

    while testing_preset != -2:
        test_command = re.sub(r'--preset\s*-?\d*', '--preset {}'.format(testing_preset), command)
        print("\nChecking if issue is preset with preset {}".format(testing_preset))
       
        culprit_result, number_of_runs = test(test_command)
        print("Culprit result {} for preset {}".format(culprit_result, testing_preset))
        
        if not culprit_result:
            functional_presets.append(testing_preset)
        else:
            culprit_presets.append(testing_preset)
        
        # Check for valid presets within 1 of each other
        if functional_presets and culprit_presets:
            functional_presets = sorted(functional_presets, reverse=True)
            culprit_presets = sorted(culprit_presets, reverse=True)

            for functional_preset in functional_presets:
                for culprit_preset in culprit_presets:
                    if abs(functional_preset - culprit_preset) <= 1:
                        print("Functional Preset found: {}".format(functional_preset))
                        print("Culprit Preset found: {}".format(culprit_preset))
                        return str(functional_preset), str(culprit_preset)
        
        testing_preset -= 1
    
    print("Error: No functional and culprit presets within 1 of each other.")
    return None, None


def check_all_commands_with_culprit(commands, tracked_command, culprit_patches, mode, tracking_results):
    print("\n*****Checking All Commands with Culprit*****\n")

    if culprit_patches:
        if not isinstance(culprit_patches,list) or not isinstance(culprit_patches[0],list):
            culprit_patches = [culprit_patches]
    else:
        return tracking_results 
    for command in commands:
        if mode == '0':
            functional_preset, culprit_preset = get_functional_and_culprit_preset(command)
        else:
            functional_preset = None
            culprit_preset = None
        for culprit_patch in culprit_patches:
            tracking_results, culprit_commit, tracked = check_past_results(command, tracking_results, mode)
            if tracked:
                continue
            print("Testing culprit on {}".format(command))

            if default_has_issue(culprit_patch, command, mode,tracking_results,culprit_commit) and mod_does_not_have_issue(culprit_patch, command, mode,functional_preset, culprit_preset):
                print('Culprit found for {}\n'.format(command))
                tracking_results = summarize_tracking_results(mode, culprit_patch, tracking_results, command)
            else:
                print('{} is not the culprit for {}\n'.format(culprit_patch,command))

    return tracking_results


def parse_test_name(command):
    test_pattern_name = r'bitstreams\/(.*?)\/'
    test_name_found = re.search(test_pattern_name, command)

    if test_name_found:
        test_name = test_name_found.group(1)
        return test_name.strip()
    else:
        return 'Default'


def get_git_info(access_token, project_group, git_url):
    if not git_url:
        if access_token:
            git_url = 'https://oauth2:{}@gitlab.com/{}/SVT-AV1.git'.format(access_token, project_group)
        else:
            git_url = 'https://gitlab.com/{}/SVT-AV1.git'.format(project_group)
    else:
        if 'oauth2:' in TEST_SETTINGS['git_url']:
            access_token = git_url.split('oauth2:')[-1].split('@')[0]
        project_group = git_url.split("/")[-2]
    
    return access_token, project_group, git_url


def set_compiler_environment(compiler):
    if compiler == "clang":
        os.environ['CC'] = 'clang'
        os.environ['CXX'] = 'clang++'
    elif compiler == "gcc":
        os.environ['CC'] = 'gcc'
        os.environ['CXX'] = 'g++'
    else:
        print('Compiler {} not recognized, exiting'.format(compiler))
        sys.exit(-1)

def default_has_issue(culprit, command, mode,tracking_results,culprit_commit):
    if mode == '2':
        build_status = build_encoder(culprit)
        print('Checking suspected culprit commit')
    else:
        if not culprit_commit:
            culprit_commit = TEST_SETTINGS['commit']
        print('Checking for issue without patch')
        build_status = build_encoder(culprit_commit)

    if not build_status:
        return False
            
    test = TEST_FUNCTION.get(TEST_SETTINGS['issue_type'])
    culprit_result, number_of_runs = test(command)

    return culprit_result

def mod_does_not_have_issue(culprit, command, mode, functional_preset, culprit_preset):
    if mode == '2':
        print('Checking commit immediately before suspected culprit')
        git_command = "git log --pretty=format:%H -n 2 {}".format(culprit)
        repo_folder = os.path.join(os.getcwd(), 'svt')
        commit_list = execute_command((git_command, repo_folder)).splitlines()
        previous_commit = commit_list[1].decode('utf-8')
        build_status = build_encoder(previous_commit)
    elif mode == '1':
        print('Checking for issue with suspected culprit debug macro patched')
        macro_lines = get_debug_macros()
        patch_file = patch_debug_macro(culprit,macro_lines)
        build_status = build_encoder()
    else:
        print('Checking for issue with suspected culprit feature patched')
        if not functional_preset or not culprit:
            return False
        patch_features(culprit,culprit_preset,functional_preset)
        build_status = build_encoder()
    if not build_status:
        return False
            
    test = TEST_FUNCTION.get(TEST_SETTINGS['issue_type'])
    culprit_result, number_of_runs = test(command)
    return not culprit_result

def get_proxy():
    with open('/etc/environment', 'r') as env_file:
        for line in env_file:
            line = line.strip()
            if line.startswith('http_proxy='):
                TEST_SETTINGS['proxy']['http'] = line.split('=')[1]
            elif line.startswith('https_proxy'):
                TEST_SETTINGS['proxy']['https'] = line.split('=')[1]
    return TEST_SETTINGS['proxy']


def get_commands_from_ci(track_only_host_ci_jobs, access_token, pipeline_id, project_group):
    if track_only_host_ci_jobs:
        hostname = subprocess.run(['hostname'], stdout=subprocess.PIPE)
        hostname = hostname.stdout.strip().decode()

    if not TEST_SETTINGS['proxy']['http'] or not TEST_SETTINGS['proxy']['https']:
        TEST_SETTINGS['proxy'] = get_proxy()

    # Grabing only failed Jobs
    jobs_api_call = "jobs?scope[]=failed&per_page=100"

    api_url_template = "https://oauth2:{}@gitlab.com/api/v4/projects/{}%2FSVT-AV1/pipelines".format(access_token, project_group)
    trace_url_template = "https://oauth2:{}@gitlab.com/api/v4/projects/{}%2FSVT-AV1/jobs".format(access_token, project_group)

    api_url = '{}/{}/{}'.format(api_url_template, pipeline_id, jobs_api_call)
    gitlab_response = requests.get(api_url, headers={'PRIVATE-TOKEN': '%s' % access_token}, proxies=TEST_SETTINGS['proxy'])
    failed_jobs = gitlab_response.json()

    if 'error' in failed_jobs or 'message' in failed_jobs:
        print('Error calling gitlab api: {}'.format(failed_jobs))
        sys.exit(-1)

    for failed_job in failed_jobs:
        job_machine = failed_job['tag_list'][0]
        if track_only_host_ci_jobs and hostname not in job_machine:
            continue

        job_id = str(failed_job['id'])
        print('Found job matching machine: {}'.format(job_machine))

        trace_url = '{}/{}/trace'.format(trace_url_template, job_id)
        job_log = requests.get(trace_url, headers={'PRIVATE-TOKEN': '%s' % access_token}, proxies=TEST_SETTINGS['proxy'])
        if job_log.status_code != 200:
            print("Failed to download trace with status code {}".format(job_log.status_code))
            exit(-1)

        if 'R2R Found' not in job_log.text:
            print("Failed test was not an R2R")
            continue

        commands = sorted(re.findall(r'\| (.*) \|', job_log.text), key=lambda x: int(re.search(r'--preset\s*(-?\d+)', x).group(1)), reverse=True)
        print('Failed R2R commands: {}'.format(commands))

    return commands


def reproduce_issue(command):
    print("Reproducing {}".format(command))\
    
    build_status = build_encoder()
    if not build_status:
        print("Initial commit could not be built, exiting")
        sys.exit(-1)
           
    test = TEST_FUNCTION.get(TEST_SETTINGS['issue_type'])
    culprit_result, number_of_runs = test(command)
    if not culprit_result:
        number_of_runs = None

    return culprit_result, number_of_runs

def summarize_tracking_results(mode, culprit_patch, tracking_results, command):
    if mode == '0':
        if culprit_patch:
            with open(str(culprit_patch[0])) as feature_file:
                line_to_patch = culprit_patch[1]
                lines = feature_file.readlines()
                culprit_feature = lines[int(line_to_patch) + 1]
                culprit_feature = re.sub(r'\s+', ' ', culprit_feature)
                print('Culprit feature {}'.format(culprit_feature))
                if not tracking_results[command].get('culprit_feature'):
                    tracking_results[command]['culprit_feature'] = list()
                tracking_results[command]['culprit_feature'].append([culprit_patch[0],line_to_patch,culprit_feature])
        else:
            print("No culprit feature found for {}".format(command))
    elif mode == '1':
        if culprit_patch:
            file_to_patch = culprit_patch[0]
            line_number_to_patch = culprit_patch[1]
            line_to_patch = culprit_patch[2]
            line_to_patch = re.sub(r'\s+', ' ', line_to_patch)
            tracking_results[command]['culprit_macro'] = line_to_patch
        else:
            print("No culprit feature found for {}".format(command))
    elif mode == '2':
        print("The R2R was introduced by commit {}".format(culprit_patch))
        tracking_results[command]['culprit_commit'] = culprit_patch

    return tracking_results


def summarize_results(tracking_results):
    print("\n\n***** Tracking Results *****\n")
    if tracking_results:
        grouped_results = {}  # Create a dictionary to group results by test name

        for command, testing_results in tracking_results.items():
            test_name = testing_results.get('test_name', 'N/A')
            num_runs = testing_results.get('num_runs', 'N/A')
            culprit_commit = testing_results.get('culprit_commit', 'N/A')
            culprit_macro = testing_results.get('culprit_macro', 'N/A')
            culprit_feature = testing_results.get('culprit_feature', 'N/A')

            if test_name not in grouped_results:
                grouped_results[test_name] = []

            result_str = "Command {}\nNumber of runs to reproduce {}\nCulprit Commit: {}\nCulprit Debug Macro: {}\nCulprit Feature: {}\n".format(
                command, num_runs, culprit_commit, culprit_macro, culprit_feature)
            grouped_results[test_name].append(result_str)

        for test_name, results in grouped_results.items():
            print("Failed Test: {}".format(test_name))        
            print("\n".join(results))

        print("Tracking successful!")



##################################### ISSUE TESTS ########################################


def test_for_r2r(r2r_command):

    upper_limit = TEST_SETTINGS['max_runs']
    bitstream_directory = 'tracking_bitstreams'  # Folder for storing bitstreams, can be relative or absolute path
    create_folders(bitstream_directory)

    preset = re.search(r'--preset\s(-?\d+)', r2r_command).group(1)
    result, number_of_runs = run_r2r_command(r2r_command, upper_limit, bitstream_directory, preset, TEST_SETTINGS['cpu_count'])

    if result:
        print('R2R reproduced in {} runs\n'.format(number_of_runs))
    else:
        print('R2R was not reproduced after {} runs\n'.format(number_of_runs))

    return result, number_of_runs


def create_folders(bitstream_dir):
    if os.path.isdir(bitstream_dir):
        shutil.rmtree(bitstream_dir)
    os.mkdir(bitstream_dir)


def run_r2r_command(command, upper_limit, bitstream_dir, preset, CPU_COUNT):
    hash_file = {}

    output_stream = ' -b {}'
    r2r_commands = [re.sub(r'-b\s.*?.bin', output_stream.format(os.path.join(bitstream_dir, '{}_M{}.bin'.format(i, preset))), command) for i in range(CPU_COUNT)]
    if '.stat' in command:
        r2r_commands = [re.sub(r'--stats\s.*?.stat', output_stream.format(os.path.join(bitstream_dir, '{}_M{}.stat'.format(i, preset))), x) for i,x in enumerate(r2r_commands)]

    with open('r2r.txt', 'w') as r2r_file:
        for r2r_command in r2r_commands:
            r2r_file.write(r2r_command)
            r2r_file.write('\n')

    md5_commands = ['md5sum  {}.bin'.format(os.path.join(bitstream_dir, '{}_M{}'.format(i, preset))) for i in range(CPU_COUNT)]
    r2r_commands = [x.replace('output', str(i)) for i, x in enumerate(r2r_commands)]
    # print('r2r_commands', r2r_commands[0])
    for count in range(0, upper_limit, CPU_COUNT):
        # print('on run {}'.format(count + CPU_COUNT))
        run_parallel(CPU_COUNT, 'r2r.txt', 'r2r', encoder_exec_name='svt')
        md5_output = execute_parallel_commands(CPU_COUNT, md5_commands, os.getcwd())
        for md5 in md5_output:
            md5_parts = str(md5).split(' ')
            hash_file[md5_parts[0]] = md5_parts[-1].strip('\n')

        if len(hash_file) > 1:
            number_of_runs = count + CPU_COUNT
            return True, number_of_runs
    number_of_runs = count + CPU_COUNT

    return False, number_of_runs


def run_parallel(num_pool, run_cmds_file, test_name, encoder_exec_name='svt'):
    if encoder_exec_name == 'aomenc':
        cmd = '/bin/bash -c \'(/usr/bin/time --verbose parallel -j {} < {} ) > time_enc_{}.log 2>&1 \' &'.format(num_pool, run_cmds_file, test_name)
    else:
        cmd = "/bin/bash -c \'(/usr/bin/time --verbose parallel -j {} < {} ) \' ".format(num_pool, run_cmds_file, test_name)
        # cmd = "/bin/bash -c \'(/usr/bin/time --verbose parallel -j {} < {} ) &> time_enc_{}.log\' &".format(num_pool, run_cmds_file, test_name)

    execute_command((cmd, os.getcwd()))


    

def execute_parallel_commands(number_of_processes, command_list, execution_directory):
    command_lines = [command.strip() for command in command_list]
    execution_directory_list = [execution_directory for i in enumerate(command_lines)]
    inputs = zip(command_lines, execution_directory_list)

    Pooler = multiprocessing.Pool(processes=number_of_processes, maxtasksperchild=30)
    output = Pooler.map(execute_command, inputs)
    Pooler.close()
    Pooler.join()

    return output


def execute_command(inputs):
    cmd, work_dir = inputs
    pipe = subprocess.Popen(cmd, shell=True, cwd=work_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = pipe.communicate()
    pipe.wait()
    for error_pattern in ERROR_PATTERNS:
            if str(error_pattern) in str(error):
                print('Error: {}'.format(error))
                sys.exit(-1)

    return output


def test_for_hang(cmd):
    num_runs = 0
    processes = 64
    commands = ['{} && rm {}.txt'.format(cmd, i) for i in range(processes)]
    commands = [cmd for i in range(processes)]

    output = []
    while True not in output:
        num_runs += processes
        print('num_runs', num_runs)
        output = execute_parallel_hang_commands(processes, commands)
        if num_runs > 10000:
            print('no Hang Detected')
            return False
        print(set(output))
    return True


def execute_parallel_hang_commands(number_of_processes, command_list):
    command_lines = [command.strip() for command in command_list]
    output_files = ['{}.txt'.format(i) for i, cmd in enumerate(command_lines)]
    inputs = zip(command_lines, output_files)

    Pooler = multiprocessing.Pool(processes=number_of_processes, maxtasksperchild=30)
    output = Pooler.map(detect_hang, inputs)
    Pooler.close()
    Pooler.join()

    return output


def terminate_process(process):
    """
    Attempts to terminate a process using platform-specific commands.

    Args:
        process (subprocess.Popen): The process to terminate.
    """

    os.killpg(os.getpgid(process.pid), signal.SIGTERM)


def detect_hang(inputs):
    command, output_file = inputs
    old_log = 'start'
    hang_count = 0
    with open(output_file, 'w') as file:
        process = subprocess.Popen(command, cwd=os.getcwd(), stderr=file, universal_newlines=True, shell=True)

        try:
            while process.poll() is None:
                time.sleep(0.001)
                if hang_count > 10000:
                    print('Hang detected, process killed')
                    process.terminate()
                    process.kill()
                    os.system('pkill SvtAv1EncApp')
                    # terminate_process(process)
                    return True
                with open(output_file, 'r') as output:
                    content = output.read()
                    new_log = content

                    if new_log != old_log:
                        hang_count = 0
                    else:
                        hang_count += 1

                    old_log = content

        except subprocess.CalledProcessError as e:
            process.kill()
            raise e
        finally:
            process.wait()

    return False

def parse_command_line():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--gitlab-token', help='Gitlab Access Token', default=TEST_SETTINGS['access_token'])
    parser.add_argument('-id', '--pipeline-id', help='Pipeline ID', default=TEST_SETTINGS['pipeline_id'])
    parser.add_argument('-c', '--commit', help='Specify git commit', default=TEST_SETTINGS['commit'])
    parser.add_argument('-b', '--branch', help='Specify git branch', default=TEST_SETTINGS['branch'])
    parser.add_argument('-mr', '--mr', help='Specify git MR number', default=TEST_SETTINGS['mr'])
    parser.add_argument('-pg', '--project_group', help='Specify git project', default=TEST_SETTINGS['project_group'])
    parser.add_argument('-tc','--track_commit', help='Find Culprit Commit', default=TEST_SETTINGS['track_commit'])
    parser.add_argument('-tm','--track_debug_macro', help='Use Debug Macro Patches', default=TEST_SETTINGS['track_debug_macro'])
    parser.add_argument('-tf','--track_feature', help='0: Use feature preset Patches', default=TEST_SETTINGS['track_feature'])
    parser.add_argument('-oh', '--track_only_host_ci_jobs', help='If true, only failed jobs that ran on the same machine as the script will be collected', default=TEST_SETTINGS['track_only_host_ci_jobs'])
    parser.add_argument('-compiler', '--compiler', help='Set the compiler to be used Ex. clang or gcc', default=TEST_SETTINGS['compiler'])

    args = parser.parse_args()

    return args.gitlab_token, args.pipeline_id, args.commit, args.branch, args.mr, args.project_group, args.track_commit, args.track_debug_macro, args.track_feature,int(args.track_only_host_ci_jobs), args.compiler

ERROR_PATTERNS = ["failed to allocate compressed data buffer",
              "Invalid parameter '-i' with value",
              "failed to read full temporal unit",
              "failed to read frame size",
              "failed to read full frame",
              "failed to read proper y4m frame delimiter",
              "failed to allocate system of equations of size",
              "failed to init",
              "failed to init equation system for block_size",
              "failed to alloc a or at_a_inv or block_size",
              "failed to allocate memory for block of size",
              "failed to allocate noise state for channel",
              "can't add memory entry",
              "you have memory leak or you need increase mem_entry_size",
              "something wrong. you freed a unallocated memory",
              "not enough memory for memory profile",
              "leaked at",
              "cdf error, frame_idx_r",
              "unhandled quarter_pel_refinement_method",
              "no center selected",
              "bug, too many frames in undisplayed queue",
              "bug, no frame in undisplayed queue",
              "unable to allocate temp values of size",
              "unable to allocate copy of A",
              "failed to init lut",
              "invalid noise param: lag",
              "invalid noise param: lag",
              "failed to allocate noise state for channel",
              "invalid shape",
              "unable to allocate buffer of size",
              "not enough flat blocks to update noise estimate",
              "adding block observation failed",
              "solving latest noise equation system failed",
              "solving latest noise strength failed",
              "solving combined noise equation system failed",
              "solving combined noise strength failed",
              "unable to init flat block finder",
              "unable to realloc buffers",
              "unable to denoise image",
              "unable to get grain parameters",
              "unsupported block size",
              'Error',
              'Error instance 1',
              'Segmentation fault (core dumped)',
              'double free or corruption (out)',
              'Aborted (core dumped)'
]

if __name__ == '__main__':
    main()
