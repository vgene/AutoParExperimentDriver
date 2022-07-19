# Python 3
#
# Ziyang Xu
# Feb 28, 2019 Created
# Aug 17, 2020 Updated
#
# Generate all profilings in parallel
# Run Experiment passes

# Please follow README.md in the sciprt/ directory

import argparse
import json
import sys
import os
import subprocess
import shutil
from joblib import Parallel, delayed, parallel
from collections import ChainMap
from termcolor import colored
import datetime
import time

import git

from ReportVisualizer import ReportVisualizer
from ResultParser import parseExp
import SLAMP


def printAndFlush(content):
    print(content, flush=True)

def clean_all_bmarks(root_path, bmark_list, reg_option):
    # 0: remake all
    # 1: use profiling
    # 2: 1 + use sequential
    # 3: only clean sequential time
    # 4: only parallel time

    if reg_option == 0:
        clean_tgt = "clean"
    elif reg_option == 1:
        clean_tgt = "clean-exp"
    elif reg_option == 2:
        clean_tgt = "clean-speed"
    elif reg_option == 3:
        clean_tgt = "clean-seq"
    elif reg_option == 4:
        clean_tgt = "clean-para"
    else:
        assert False, "Regression option not valid"

    for bmark in bmark_list:
        os.chdir(os.path.join(root_path, bmark, "src"))
        make_process = subprocess.Popen(["make", clean_tgt],
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.STDOUT)
        if make_process.wait() != 0:
            printAndFlush(colored("Clean failed for %s" % bmark, 'red'))

    printAndFlush("Finish cleaning")
    return 0

def get_one_prof(root_path, bmark, profile_name, profile_recipe):
    printAndFlush("Generating %s on %s " % (profile_name, bmark)) 

    os.chdir(os.path.join(root_path, bmark, "src"))
    start_time = time.time()
    with open(profile_name.replace(' ', '-')+".log", "w") as fd:
      make_process = subprocess.Popen(["make", profile_recipe],
                                      stdout=fd,
                                      stderr=fd)

    if make_process.wait() != 0:
        elapsed = time.time() - start_time
        printAndFlush(colored("%s failed for %s, took %.4fs" % (profile_name, bmark, elapsed), 'red'))
        return False
    else:
        elapsed = time.time() - start_time
        printAndFlush(colored("%s succeeded for %s, took %.4fs" % (profile_name, bmark, elapsed), 'green'))
        # if benchmark.$profile.time exists, copy it to result directory and change "benchmark" to the actual benchmark name
        # move profile_recipe.replace(".out", ".time") to results_path
        return True


def get_pdg(root_path, bmark, result_path):
    printAndFlush("Generating PDG results on %s " % (bmark))
    os.chdir(os.path.join(root_path, bmark, "src"))

    exp_name = "/u/ziyangx/SCAF/scripts/genPDG.sh"
    start_time = time.time()
    make_process = subprocess.Popen(["make", exp_name],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.STDOUT)

    enables = ""
    if not os.path.isfile("benchmark.loopProf.out"):
        printAndFlush(colored("No LoopProf for %s, abort" % bmark, 'red'))
        return False
    else:
        shutil.copy("benchmark.loopProf.out", "loopProf.out")

    if not os.path.isfile("benchmark.lamp.out"):
        printAndFlush(colored("No LAMP for %s!" % bmark, 'red'))
    else:
        shutil.copy("benchmark.lamp.out", "result.lamp.profile")
        enables += "-enable-lamp "

    if not os.path.isfile("benchmark.edgeProf.out"):
        printAndFlush(colored("No EdgeProf for %s" % bmark, 'red'))
    else:
        shutil.copy("benchmark.edgeProf.out", "llvmprof.out")
        enables += "-enable-edgeprof "

    if not os.path.isfile("benchmark.specpriv-profile.out"):
        printAndFlush(colored("No SpecPriv for %s" % bmark, 'red'))
    else:
        shutil.copy("benchmark.specpriv-profile.out", "result.specpriv.profile.txt")
        enables += "-enable-specpriv "

    start_time = time.time()
    with open("pdg.log", 'w') as fd:
        make_process = subprocess.Popen([exp_name, enables],
                                        stdout=fd,
                                        stderr=fd)

    if make_process.wait() != 0:
        elapsed = time.time() - start_time
        printAndFlush(colored("PDG generation failed for %s, took %.4fs" % (bmark, elapsed), 'red'))
        return False
    else:
        elapsed = time.time() - start_time
        printAndFlush(colored("PDG genration succeeded for %s, took %.4fs" % (bmark, elapsed), 'green'))
        return True
    

# ZY - check whether all profilings are there;
# if remake_profile == True, ignore remake them by the Makefile, else abort
def get_exp_result(root_path, bmark, result_path, exp_name="benchmark.collaborative-pipeline.dump"):
    printAndFlush("Generating " + exp_name +  " on %s " % (bmark))

    os.chdir(os.path.join(root_path, bmark, "src"))

    start_time = time.time()
    make_process = subprocess.Popen(["make", exp_name],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.STDOUT)

    if make_process.wait() != 0:
        elapsed = time.time() - start_time
        printAndFlush(colored("Experiment failed for %s, took %.4fs" % (bmark, elapsed), 'red'))
        return None
    else:
        elapsed = time.time() - start_time
        with open(exp_name, 'r') as fd:
            lines = fd.readlines()

        # Parse experiment results
        parsed_result = parseExp(lines, bmark)

        # Create a backup
        shutil.copy(exp_name, os.path.join(result_path, bmark + "." + exp_name))

        printAndFlush(colored(exp_name + " succeeded for %s, took %.4fs" % (bmark, elapsed), 'green'))
        return parsed_result


def get_seq_time(root_path, bmark, times):
    printAndFlush("Try to get sequential execution time (repeated %d times)" % times)
    os.chdir(os.path.join(root_path, bmark, "src"))
    exp_name = "reg_seq"
    seq_time_name = "seq.time"

    time_list = []
    for run_time in range(times):
        make_process = subprocess.Popen(["make", exp_name],
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.STDOUT)

        if make_process.wait() != 0 and os.path.exists(seq_time_name):
            printAndFlush(colored("Sequential time failed for %s" % bmark, 'red'))
            return False
        else:
            with open(seq_time_name, 'r') as fd:
                line = fd.readline()

            try:
                time_list.append(float(line))
                printAndFlush("NO. %d: %.2fs" % (run_time, float(line)))
            except ValueError:
                return False
            os.remove(seq_time_name)
    printAndFlush(colored("Sequential time measurement succeeded for %s!" % bmark, 'green'))
    printAndFlush(time_list)


    return time_list, sum(time_list) / times


def get_para_time(root_path, bmark, times, num_workers=28):
    printAndFlush("Try to get parallel execution time, running times is %d, test workers is %d" % (times, num_workers))
    os.chdir(os.path.join(root_path, bmark, "src"))
    exp_name = "reg_para"
    para_time_name = "parallel.time"

    time_list = []
    for run_time in range(times):
        make_process = subprocess.Popen(["make", exp_name, "REG_NUM_WORKERS=" + str(num_workers)],
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.STDOUT)

        if make_process.wait() != 0 and os.path.exists(para_time_name):
            printAndFlush(colored("Parallel time failed for %s" % bmark, 'red'))
            return False
        else:
            with open(para_time_name, 'r') as fd:
                line = fd.readline()

            try:
                time_list.append(float(line))
                printAndFlush("NO. %d: %.2fs" % (run_time, float(line)))
            except ValueError:
                return False

            os.remove(para_time_name)
    printAndFlush(colored("Parallel time measurement succeeded for %s!" % bmark, 'green'))
    printAndFlush(time_list)

    return time_list, sum(time_list) / times


def get_real_speedup(root_path, bmark, reg_option, times=3, default_num_worker=28):
    printAndFlush("Generating real speedup for %s " % (bmark))
    os.chdir(os.path.join(root_path, bmark, "src"))

    num_workers_plan_list = list(range(1, 29))  # [1,28]

    real_speedup = {}
    # Generate sequential and parallel
    if reg_option == 2:
        exp_name = "benchmark.compare.out"
        no_check_list = ["052.alvinn"]

        start_time = time.time()
        make_process = subprocess.Popen(["make", exp_name],
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.STDOUT)
        if make_process.wait() != 0:
            elapsed = time.time() - start_time
            printAndFlush(colored("Real speedup experiment failed for %s, took %.4fs" % (bmark, elapsed), 'red'))
            return None
        else:
            elapsed = time.time() - start_time

        if os.path.exists(exp_name) and os.stat(exp_name).st_size == 0:
            printAndFlush(colored("Hooyah! Same output from sequential and parallel versions for %s! Took %.4fs" % (bmark, elapsed), 'green'))
        else:
            printAndFlush(colored("Oh snap! Seems like results disagree for %s! Took %.4fs" % (bmark, elapsed), 'red'))
            if bmark in no_check_list:
                printAndFlush(colored("%s is in the no checking list! Continue to get results" % (bmark), 'green'))
            else:
                return None

        seq_time_list, seq_time = get_seq_time(root_path, bmark, times)
        para_time_list, para_time = get_para_time(root_path, bmark, times, num_workers=default_num_worker)

        if seq_time and para_time and seq_time > 0 and para_time > 0:
            speedup = seq_time / para_time
            real_speedup['seq_time'] = round(seq_time, 3)
            real_speedup['seq_time_list'] = seq_time_list
            real_speedup['para_time'] = round(para_time, 3)
            real_speedup['para_time_list_dict'] = {default_num_worker: seq_time_list}
            real_speedup['speedup'] = round(speedup, 2)
        else:
            printAndFlush(colored("Oh snap! Getting execution time failed for %s!" % (bmark), 'green'))
            return None

    # Sequential time only
    elif reg_option == 3:
        seq_time_list, seq_time = get_seq_time(root_path, bmark, times)
        if seq_time and seq_time > 0:
            real_speedup['seq_time'] = round(seq_time, 3)
            real_speedup['seq_time_list'] = seq_time_list
        else:
            printAndFlush(colored("Oh snap! Getting execution time failed for %s!" % (bmark), 'green'))
            return None

    # Parallel time only
    elif reg_option == 4:
        speed_up_dict = {}
        para_time_list_dict = {}
        for num_workers in num_workers_plan_list:
            para_time_list, para_time = get_para_time(root_path, bmark, times, num_workers=num_workers)
            speed_up_dict[num_workers] = round(para_time, 3)
            para_time_list_dict[num_workers] = para_time_list
            printAndFlush("%s %.3f on %d workers" % (bmark, para_time, num_workers))
        # Get the last speedup with 28 workers
        if para_time and para_time > 0:
            real_speedup['para_time'] = round(para_time, 3)
            real_speedup['para_time_dict'] = speed_up_dict
            real_speedup['para_time_list_dict'] = para_time_list_dict
        else:
            printAndFlush(colored("Oh snap! Getting execution time failed for %s!" % (bmark), 'green'))
            return None

    return real_speedup


def get_all_passes(root_path, bmark, passes, result_path, modules=None, extra_flags=None, slamp_parallel_workers=1):
    if modules == None:
        modules = []
    if passes == None:
        passes = []
    status = {}
    if "Inline" in passes:
      status["Inline"] = get_one_prof(root_path, bmark, 'Inline', "benchmark.inlined.o3.out")
    if "Edge" in passes:
        status["Edge"] = get_one_prof(root_path, bmark, 'Edge Profile', "benchmark.edgeProf.out")
    if "Loop" in passes:
        status["Loop"] = get_one_prof(root_path, bmark, 'Loop Profile', "benchmark.loopProf.out")
    if "LAMP" in passes:
        status["LAMP"] = get_one_prof(root_path, bmark, 'LAMP', "benchmark.lamp.out")
    if "SLAMP" in passes:
        status["SLAMP"] = SLAMP.run_SLAMP(root_path, bmark, modules, extra_flags, slamp_parallel_workers)
        SLAMP.parse_SLAMP_output(root_path, bmark, result_path, modules)
    if "Profile-Seq" in passes:
        status["Profile-Seq"] = get_one_prof(root_path, bmark, 'Profile-Seq', "profile-seq.time")
    if "Asan" in passes:
        status["Asan"] = get_one_prof(root_path, bmark, 'Asan', "asan.time")
    if "Msan" in passes:
        status["Msan"] = get_one_prof(root_path, bmark, 'Msan', "msan.time")
    if "Measure" in passes:
        status["Measure"] = get_one_prof(root_path, bmark, 'measure', "benchmark.slamp.measure.txt")
    if "SpecPriv" in passes:
        status["SpecPriv"] = get_one_prof(root_path, bmark, 'SpecPriv Profile', "benchmark.specpriv-profile.out")
    if "HeaderPhi" in passes:
        status["HeaderPhi"] = get_one_prof(root_path, bmark, 'HeaderPhi Profile', "benchmark.headerphi_prof.out")
    if "Experiment" in passes:
        status["Experiment"] = get_exp_result(root_path, bmark, result_path)
    if "Exp-slamp" in passes:
        if 'Edge' in status and status['Edge'] and "SLAMP" in status and status['SLAMP']:
            status["Exp-slamp"] = get_exp_result(root_path, bmark, result_path, "slamp.dump")
        else:
            status["Exp-slamp"] = None
    if "Exp-ignorefn" in passes:
        if 'Edge' in status and status['Edge']:
            status["Exp-ignorefn"] = get_exp_result(root_path, bmark, result_path, "ignorefn.dump")
        else:
            status["Exp-ignorefn"] = None
    if "Exp-3" in passes:
        # status["Experiment-no-spec"] = get_exp_result(root_path, bmark, result_path, "no-spec.dump")

        # if 'Edge' in status and status['Edge'] and 'SpecPriv' in status and status['SpecPriv']:
            # status["Experiment-cheap-spec"] = get_exp_result(root_path, bmark, result_path, "cheap-spec.dump")
        # else:
            # status["Experiment-cheap-spec"] = None

        if 'Edge' in status and status['Edge'] and "LAMP" in status and status['LAMP']:
            status["Experiment-no-specpriv"] = get_exp_result(root_path, bmark, result_path, "no-specpriv.dump")
            status["Experiment-no-specpriv-ignorefn"] = get_exp_result(root_path, bmark, result_path, "no-specpriv-ignorefn.dump")
        else:
            status["Experiment-no-specpriv"] = None

        # if 'Edge' in status and status['Edge'] and 'SpecPriv' in status and status['SpecPriv'] and "LAMP" in status and status['LAMP']:
            # status["Experiment-all-spec"] = get_exp_result(root_path, bmark, result_path, "all-spec.dump")
        # else:
            # status["Experiment-all-spec"] = None
    if "No-Spec" in passes:
        status["Experiment-no-spec"] = get_exp_result(root_path, bmark, result_path, "no-spec.dump")
    if "PDG" in passes:
        status["PDG"] = get_pdg(root_path, bmark, result_path)

    # Generate a json on the fly
    os.chdir(result_path)
    with open("status_" + bmark + ".json", "w") as fd:
        json.dump(status, fd)

    return {bmark: status}


def get_benchmark_list_from_suite(suite, bmark_list):
    # Get suite configuration from json
    if suite == "All":
        suite_list = [k for k, v in bmark_list.items() if v["available"]]
    else:
        suite_list = [k for k, v in bmark_list.items() if suite in v["suites"] and v["available"]]
    return suite_list

#TODO: ask for inputs that were not provided instead of terminating
#allow setting of result path
def parse_args():
    keys = ["root_path", "bmark_list", "core_num", "test_times", "reg_option", "force_die", "passes", "modules", "extra_flags", "suite"]
    nondefault_keys = ["root_path", "bmark_list", "reg_option", 
        "passes", "extra_flags", "suite"]
    default_keys = {"core_num":4, "test_times":3, "force_die":True}

    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--root-path", type=str,
                        help="Root path of CPF benchmark directory")
    parser.add_argument("-b", "--bmark-list", type=str,
                         help="Path to a benchmark json file")
    parser.add_argument("-r", "--reg-option", type=int,
                        required=False, help="Regression option (0-5), will bypass interaction")
    #  parser.add_argument("-f", "--force-die", action='store_true', help="Regression option (0-5), will bypass interaction")
    #  parser.add_argument("-n", "--core-num", type=int,
    #                      default=4, help="Core number")
    #  parser.add_argument("-m", "--memo", type=str,
    #                      default="", help="A short description of the run")
    parser.add_argument("-f", "--force-die", type=bool, action='store_true', help="End the run if any test fails")
    parser.add_argument("-n", "--core-num", type=int, #default=4, 
                        help="Core number")
    parser.add_argument("-t", "--test-times", type=int,
                        #default=3, 
                        help="Test times for sequential and parallel version")
    parser.add_argument("-m", "--modules", type=str, nargs='*')
    parser.add_argument("-q", "--passes", type=str, nargs='*')
    parser.add_argument("-e", "--extra_flags", type=str, nargs='*')

    parser.add_argument("-s", "--suite", type=str, choices=[
        'All', 'reg_fast', 'reg_all', 'Spec', 'SpecFP', 'SpecInt',
        'PolyBench', 'PARSEC', 'MediaBench', 'Toys',
        'MiBench', 'Trimaran', 'Utilities', 'MicroBench', 'Spec2006', 'Spec2017'],
        help="Choose specific test suite")

    parser.add_argument("--slamp-workers", type=int, default=1, help="Number of workers for SLAMP")

    parser.add_argument("-c", "--config_file", type=str,
                        help="config file")

    args = parser.parse_args()

    # By default use command line argument
    config = {}
    config['root_path'] = args.root_path
    config['core_num'] = args.core_num
    config['bmark_list'] = args.bmark_list
    config['test_times'] = args.test_times
    config['reg_option'] = args.reg_option
    config['force_die'] = args.force_die
    config['suite'] = args.suite
    config['passes'] = args.passes 
    config['modules'] = args.modules
    config['extra_flags'] = args.extra_flags
    config['slamp_parallel_workers'] = args.slamp_workers

    # Load from file is given
    if args.config_file:
      config_from_file = get_config_from_file(args.config_file)
      if config_from_file is None:
          print("Loading config file failed")
          sys.exit(-1)
      for key in keys:
          if config[key] == None:
              if key in config_from_file and config_from_file[key] != None:
                config[key] = config_from_file[key]

    # Fill in default values
    for key in default_keys:
      if config[key] == None:
        config[key] = default_keys[key]

    #for key in nondefault_keys:
    #  if config[key] == None:
    #    get_key_from_user()

    # otherwise it's already a list
    if not args.config_file and type(config['bmark_list']) is str:
        with open(config['bmark_list'], 'r') as fd:
            bmark_list = json.load(fd)
        bmark_list = get_benchmark_list_from_suite(config['suite'], bmark_list)
        config['bmark_list'] = bmark_list

    # Get CPF and Regression Git Hash
    if 'LIBERTY_LIBS_DIR' in os.environ and 'LIBERTY_SMTX_DIR' in os.environ:
        config['libs_path'] = os.environ['LIBERTY_LIBS_DIR']
        config['smtx_path'] = os.environ['LIBERTY_SMTX_DIR']
    else:
        print('"LIBERTY_LIBS_DIR" or "LIBERTY_SMTX_DIR" Environment variables are not properly set up')
        print('Have you sourced cpf_environ.rc?')
        return False

    # TODO: get CPF history somehow 
    # try:
    #     repo_cpf = git.Repo(config['obj_path'], search_parent_directories=True)
    # except git.exc.InvalidGitRepositoryError:
    #     print("CPF Framework is not under Git, please check again!")
    #     return False

    # Get 8 byte Git history
    # FIXME: sha_cpf = repo_cpf.head.object.hexsha
    config['sha_cpf'] = "BOGUS_SHA" # FIXME: repo_cpf.git.rev_parse(sha_cpf, short=8)
    config['branch_cpf'] = "BOGUS_BRANCH" #FIXME: repo_cpf.active_branch.name

    # Results directory
    dt = datetime.datetime.now()
    config['result_path'] = os.path.join(config['root_path'], "results", dt.strftime('%Y-%m-%d-%H-%M'))

    if not os.path.exists(config['result_path']):
        os.makedirs(config['result_path'])

    return config


def get_config_from_file(config_file):

    with open(config_file, 'r') as fd:
        config = json.load(fd)

    return config


def get_reg_option_from_user(config):

    # Regression option (removing old artifacts)
    print("Regression Configurations:")
    print("#0: Start from the beginning, redo everything")
    print("#1: Use old profiling if available")
    print("#2: Use old binaries if availble (get sequential + parallel)")
    print("#3: Only get sequential time")
    print("#4: Only get parallel time + #2")
    print(colored("Remaking is irreversible, be cautious!", 'red'))
    while True:
        reg_option = input("Option (0/1/2/3/4): ")
        if reg_option in ['0', '1', '2', '3', '4']:
            reg_option = int(reg_option)
            config['reg_option'] = reg_option
            break
        else:
            print("Invalid input, please try again!")

    return config


# Preview configuration
def preview_config(config):
    print("\n")
    print(colored("Please make sure you've committed all changes for both CPF and Regression, otherwise the Git history hash is meanlingless!", 'red'))
    print(colored("##### Configurations #####", 'green'))
    print("Benchmark root path: %s" %
          (colored(str(config['root_path']), 'yellow')))
    print("CPF lib directory: %s, smtx directory: %s, on branch %s, with Git history: %s" %
          (colored(str(config['libs_path']), 'yellow'),
           colored(str(config['smtx_path']), 'yellow'),
           colored(str(config['branch_cpf']), 'yellow'),
           colored(str(config['sha_cpf']), 'yellow')))
    print("Core number: %s" % colored(str(config['core_num']), 'yellow'))
    print("Test times: %s" % colored(str(config['test_times']), 'yellow'))
    print("Running test on %s benchmarks %s :" % (colored(str(len(config['bmark_list'])), 'yellow'), colored(str(config['bmark_list']), 'yellow')))

    reg_option = config['reg_option']
    prompt = "Regression option not between 0 and 4, please try again!"
    if reg_option == 0:
        prompt = "Will remove everything and start from the beginning"
    elif reg_option == 1:
        prompt = "Will use old profilings when available"
    elif reg_option == 2:
        prompt = "Will use old binaries when available, get sequential and parallel results"
    elif reg_option == 3:
        prompt = "Will get sequential time"
    elif reg_option == 4:
        prompt = "Will use old binaries when available, get parallel results"

    print("Reg option: %s, %s" %
          (colored(str(config['reg_option']), 'yellow'), prompt))

    print("Store results under directory: %s" % colored(config['result_path'], 'yellow'))
    print(colored("#### End of Configurations ####", 'green'))

if __name__ == "__main__":

    config = parse_args()
    if not config:
        print("Bad configuration, please start over, good luck!")
        sys.exit(1)

    ask_memo = False
    if config["reg_option"] is None:
        ask_memo = True
        config = get_reg_option_from_user(config)

    if not config:
        print("Bad configuration, please start over, good luck!")
        sys.exit(1)

    preview_config(config)
    # Ask for memo
    if ask_memo:
        while True:
            confirm = input("Continue with configurations above? (y/n) : ")
            if confirm == 'y':
                config['memo'] = input("A short note of this test: ")
                break
            elif confirm == 'n':
                print("Let's start over, good luck!")
                sys.exit(1)


    result_config_json = os.path.join(config['result_path'], "config.json")
    with open(result_config_json, 'w') as outfile:
        json.dump(config, outfile, indent=4)

    print("\n\n### Experiment Start ###")
    # Preprocesing
    # Create result directory
    #if not os.path.exists(config['result_path']):
    #    os.makedirs(config['result_path'])

    # Create a log with date + memo + configuration
    #log_path = config['result_path'] + ".log"
    #print("Creating log at %s" % log_path)
    #with open(log_path, "w") as fd:
    #    json.dump(config, fd)
    #print("\n")

    # Clean old artifacts
    clean_all_bmarks(config['root_path'], config['bmark_list'], config['reg_option'])

    # Finish till experiment
    status_list = Parallel(n_jobs=config['core_num'])(delayed(get_all_passes)(
        config['root_path'], bmark, config['passes'], config['result_path'], config['modules'], config['extra_flags'], config['slamp_parallel_workers']) for bmark in config['bmark_list'])
    status = dict(ChainMap(*status_list))

    # If any pass failed, die here
    die = False
    if config['force_die']:
        for bmark in config['bmark_list']:
            for p in config['passes']:
                if not status[bmark][p]:
                    die = True
                    print(colored("%s failed on %s" % (bmark, p), 'red'))

    if die:
        sys.exit(1)

    if "RealSpeedup" in config['passes']:
        # Get Speedup in sequential
        for bmark in config['bmark_list']:
            real_speedup = get_real_speedup(config['root_path'], bmark, config['reg_option'], config['test_times'])
            status[bmark]['RealSpeedup'] = real_speedup

            # Dump on the fly
            os.chdir(config['result_path'])
            with open("status.json", "w") as fd:
                json.dump(status, fd)

            if real_speedup:
                if config['reg_option'] == 3:
                    print("For %s, seq time: %.2f" % (bmark, real_speedup['seq_time']))
                elif config['reg_option'] == 4:
                    print("For %s, para time: %.2f" % (bmark, real_speedup['para_time']))
                else:
                    print("For %s, seq time: %.2f, para time: %.2f, speedup: %.2f" %
                          (bmark, real_speedup['seq_time'], real_speedup['para_time'], real_speedup['speedup']))

    os.chdir(config['result_path'])
    with open("status.json", "w") as fd:
        json.dump(status, fd)

    reVis = ReportVisualizer(bmarks=config['bmark_list'], passes=config['passes'], status=status, path=config['result_path'])
    reVis.dumpCSV()
    reVis.dumpDepCoverageTable()

