import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys

from parsel import Selector

import utils
from standard_tags import standard_opening_tags, standard_closing_tags

VERBOSE = True


def validate_config_path(full_config_path):
    if not os.path.exists(full_config_path):
        raise ValueError("my_config.cfg doesn't exist. "
                         "Please create one in the same directory as this program, using the instructions in the README.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--input_dir", type=str,
                        default='')
    parser.add_argument("-v", "--verbose", type=int,
                        default=1)
    args = parser.parse_args()
    global VERBOSE
    VERBOSE = bool(int(args.verbose))
    reddit_backup(args.input_dir)


def reddit_backup(existing_bdfr_html_dir):
    if existing_bdfr_html_dir != '' and not os.path.exists(existing_bdfr_html_dir):
        raise FileNotFoundError(existing_bdfr_html_dir)

    root_dir_name = os.path.dirname(os.path.abspath(__file__))
    full_config_path = os.path.join(root_dir_name, "my_config.cfg")
    program_backup_path = os.path.join(root_dir_name, "program_backup_path")
    bdfr_dir = os.path.join(root_dir_name, "bdfr")
    bdfr_html_prog_path = os.path.join(root_dir_name, "bdfr-html")
    generated_bdfr_html_dir = os.path.join(root_dir_name, "html_pages")
    generated_index_file = os.path.join(generated_bdfr_html_dir, "index.html")
    existing_index_file = os.path.join(existing_bdfr_html_dir, "index.html")

    validate_config_path(full_config_path)
    run_bdfr_command(full_config_path, bdfr_dir)
    run_bdfrtohtml_command(bdfr_dir, bdfr_html_prog_path, generated_bdfr_html_dir)
    if existing_bdfr_html_dir == '':
        return

    old_output = perform_offline_backup(existing_bdfr_html_dir, program_backup_path)
    move_generated_html_pages_to_existing_dir(generated_bdfr_html_dir, existing_bdfr_html_dir, generated_index_file,
                                              existing_index_file)
    reorder_index_html(existing_index_file)  # existing_bdfr_html_dir has the unordered, combined output

    print("BDFR HTML merge complete. Running directory comparisons (old vs new)...")
    comparison_logs = utils.compare_directories(old_output, existing_bdfr_html_dir, VERBOSE)
    # existing_bdfr_html_dir has the final output
    comparison_log_dir = os.path.join(program_backup_path, "comparison_logs")
    os.makedirs(comparison_log_dir, exist_ok=True)
    with open(os.path.join(comparison_log_dir, f"{get_timestamp_str()}.txt"), "w") as f:
        f.write(comparison_logs)
    print("Program execution complete. You may un-save from reddit after verifying the new index.html file")


def get_timestamp_str():
    return datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")


def perform_offline_backup(existing_bdfr_html_dir, program_backup_path):
    os.makedirs(program_backup_path, exist_ok=True)
    timestamp_str = get_timestamp_str()
    backup_path = os.path.join(program_backup_path, timestamp_str, os.path.basename(existing_bdfr_html_dir))
    shutil.copytree(existing_bdfr_html_dir, backup_path)
    # keep only the 5 most recent timestamp folders
    timestamp_folders = sorted(
        [f for f in os.listdir(program_backup_path) if os.path.isdir(os.path.join(program_backup_path, f))],
        reverse=True)
    for folder in timestamp_folders[5:]:
        shutil.rmtree(os.path.join(program_backup_path, folder))
    return backup_path


def run_bdfr_command(full_config_path, bdfr_dir, run_bdfr=True):
    if not run_bdfr:
        return
    if os.path.exists(bdfr_dir):
        x = input("BDFR folder exists already. Delete? [y/n] ")
        if x.lower().strip() == "y":
            shutil.rmtree(bdfr_dir)
        else:
            print("Using previous program run's bdfr. Skipping...")
            return
    os.mkdir(bdfr_dir)
    arguments = (
        f"bdfr archive {bdfr_dir} --user me --saved --authenticate -f json --file-scheme '{{POSTID}}_{{TITLE}}' --config {full_config_path}").split(
        " ")
    arguments = [sys.executable, "-m"] + arguments
    print("Running bdfr command...:\n" + " ".join(arguments))
    subprocess.run(arguments, check=True, shell=True)


def run_bdfrtohtml_command(bdfr_dir, bdfr_html_prog_path, generated_bdfr_html_dir):
    env = os.environ.copy()
    env["PYTHONPATH"] = bdfr_html_prog_path
    arguments = f"bdfrtohtml --input_folder {bdfr_dir} --output_folder {generated_bdfr_html_dir}".split(" ")
    arguments = [sys.executable, "-m"] + arguments
    subprocess.run(arguments, check=True, shell=True, env=env)


def move_generated_html_pages_to_existing_dir(generated_bdfr_html_dir, existing_bdfr_html_dir, generated_index_file,
                                              existing_index_file):
    """
    1. Transfer posts referenced in newly generated index.html to the already existing one to modify it in place by calling the transfer_section_content function
    2. Delete newly generated style.css since we do not want a new CSS file every time, we can reuse and modify one CSS all the time
    3. Move all other files from newly generated bdfr html dir to the input dir of this program by using shutil's copytree and rmtree
    """
    transfer_section_content(generated_index_file, existing_index_file)
    os.remove(generated_index_file)  # existing_bdfr_html_dir now has correct unordered html
    os.remove(os.path.join(generated_bdfr_html_dir, "style.css"))  # to preserve our original styles css
    shutil.copytree(generated_bdfr_html_dir, existing_bdfr_html_dir, dirs_exist_ok=True)
    shutil.rmtree(generated_bdfr_html_dir)


def transfer_section_content(source_file, destination_file):
    """
    Extract section content from newly generated index.html and insert it into destination html
    Text between section tags are what contain the references to the individual HTML files created for each post
    """
    with open(source_file, 'r', encoding="utf8") as f:
        source_html = f.read()
    # Extract content within <section> tags for index html generated in this run
    section_re_pattern = r'<section class="one-column">(.*)</section>'
    source_list = re.findall(section_re_pattern, source_html, re.DOTALL)
    section_contents = source_list[0]
    with open(destination_file, 'r', encoding="utf8") as f:
        destination_html = f.read()
    # Extract content within <section> tags for index html generated in previous run
    existing_section_contents = re.findall(section_re_pattern, destination_html, re.DOTALL)[0]
    # Insert content within <section> tags into destination HTML
    combined_section = existing_section_contents + "\n" + section_contents
    full_dest_html = standard_opening_tags + combined_section + standard_closing_tags
    # Write modified destination HTML file
    with open(destination_file, 'w', encoding="utf8") as f:
        f.write(full_dest_html)


def reorder_index_html(existing_index_file):
    """
    Group posts in index.html by subreddit, since upto now we just appended the current run's posts to the previous run's
    Will work even if the previous run's index.html was not generated by this program, i.e. even if the posts were ungrouped by subreddit to begin with
    """
    f = open(existing_index_file, 'r', encoding="utf8")
    unordered_html = f.read()
    f.close()

    sel = Selector(unordered_html)
    list_div_str = sel.xpath("//section/div").getall()

    divs_dict = {}
    # will be used to store div tags for each subreddit as key to later retrieve in order by iterating over the keys.
    # The order of the keys/subreddits do not matter, but the order of posts within each subreddit does
    href_re = re.compile('a href="https://reddit.com/r/(.*?)"')

    for div in list_div_str:
        mo = href_re.search(div)
        subreddit_name = mo.group(1)
        if subreddit_name not in divs_dict:
            divs_dict[subreddit_name] = [div]
        else:
            divs_dict[subreddit_name].append(div)

    ordered_divs_list = []
    for subreddit_name in sorted(divs_dict.keys(), key=str.lower):
        is_first_subreddit_post = True
        for div in list(set(divs_dict[subreddit_name])):  # to make the program an idempotent operation
            if is_first_subreddit_post:
                initial_str = f"<p></p><p></p><p><h3>Subreddit Below = r/{subreddit_name}</h3></p><p></p><p></p><p></p>"
            else:
                initial_str = ""
            ordered_divs_list.append(initial_str + div)
            is_first_subreddit_post = False

    if VERBOSE:
        print("Sanity check:")
        print("Length of unordered divs", len(list_div_str))
        print("Length of ordered divs", len(ordered_divs_list))

    final_html_str = standard_opening_tags
    for div in ordered_divs_list:
        final_html_str += div + "\n"
    final_html_str += standard_closing_tags

    os.remove(existing_index_file)
    f = open(existing_index_file, 'w', encoding="utf8")
    f.write(final_html_str)
    f.close()


if __name__ == "__main__":
    main()
