import os
import filecmp
import difflib

UTILS_VERBOSE = True

def compare_directories(dir1, dir2, verbose):
    global UTILS_VERBOSE
    UTILS_VERBOSE = verbose
    comparison_logs = ""
    dir_comparison = filecmp.dircmp(dir1, dir2)

    for file_name in dir_comparison.common_files:
        file1 = os.path.join(dir1, file_name)
        file2 = os.path.join(dir2, file_name)
        comparison_logs += compare_files(file1, file2)

    for subdir in dir_comparison.common_dirs:
        comparison_logs += compare_directories(os.path.join(dir1, subdir), os.path.join(dir2, subdir), verbose)

    for file_name in dir_comparison.left_only:
        comparison_logs += print_and_return(f"File {file_name} only in {dir1}")

    for file_name in dir_comparison.right_only:
        comparison_logs += print_and_return(f"File {file_name} only in {dir2}")

    return comparison_logs


def compare_files(file1, file2):
    comparison_logs = ""
    with open(file1, 'r', encoding="utf8") as f1, open(file2, 'r', encoding="utf8") as f2:
        file1_lines = f1.readlines()
        file2_lines = f2.readlines()

    diff = list(difflib.unified_diff(file1_lines, file2_lines, fromfile=file1, tofile=file2, lineterm=''))

    if len(diff) > 40:
        comparison_logs += print_and_return(f"Too many differences in {file1} vs {file2}. Please check manually.")
    else:
        for line in diff:
            comparison_logs += print_and_return(line)

    return comparison_logs


def print_and_return(str):
    if UTILS_VERBOSE:
        print(str)
    return str + "\n"