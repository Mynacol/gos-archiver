#!/usr/bin/env python3

# This script parses the list of GrapheneOS releases, downloads them and uploads them to Internet Archive.

URI = 'https://grapheneos.org/releases'

import sys
import os
import re
import traceback

import internetarchive as ia

import requests
from bs4 import BeautifulSoup as bs

# Source: http://stackoverflow.com/a/434328/953022
def chunker(seq, size):
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))

# Source: https://stackoverflow.com/a/16696317
def download_file(url):
    local_filename = url.split('/')[-1]
    # NOTE the stream=True parameter below
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=65536): 
                # If you have chunk encoded response uncomment if
                # and set chunk_size parameter to None.
                #if chunk: 
                f.write(chunk)
    return local_filename

class ArchiveUploader:
    def __init__(self, internetarchive = ia):
        self.ia = internetarchive
        self.chunksize = 20

    def find_releases(self):
        everything = {}
        req = requests.get(URI)
        soup = bs(req.text, features="html.parser")
        #changelog = soup.find(id='changelog').article['id']
        latest_stable = soup.css.select_one('#stable-channel')
        latest_beta = soup.css.select_one('#beta-channel')
        for release in [ latest_stable, latest_beta ]:
            for release_device in release.find_all('section'):
                for file in release_device.ul.find_all('a'):
                    release_id = release_device.p.a.string
                    everything.setdefault(release_id, []).append({
                        'device_prettyname': release_device.h3.string.replace(' (extended support)', ''),
                        'device_keyname': release_device['id'].replace('-stable', '').replace('-beta', ''),
                        'filename': file.string,
                        'uri': file['href'],
                    })
        return everything

    def upload_release(self, identifier, metadata, release):
        """Upload all device files for the specified GrapheneOS release"""
        item = self.ia.get_item(identifier)

        if not item.identifier_available():
            # This release was already uploaded
            return 0

        all_files = release
        returncode = 0

        for files in chunker(all_files, self.chunksize):
            local_files = []
            # Download files
            try:
                for file in files:
                    if os.path.exists(file['filename']):
                        print(f"File {file['filename']} already downloaded")
                        local_files.append(file['filename'])
                    else:
                        print(f"Downloading file {file['filename']}")
                        local_files.append(download_file(file['uri']))
            except Exception as e:
                print(f"{identifier}: exception raised while downloading {file}", file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                returncode = 1

            try:
                res = item.upload(local_files, metadata=metadata)
                file_status = zip(local_files, res)
                print_error = False
                for status in file_status:
                    f = status[0]
                    code = status[1].status_code
                    if code != 200:
                        print(f"Upload failed with status code '{code}' for file: {f}", file=sys.stderr)
                        print_error = True

                if print_error:
                    returncode = 1
            except Exception as e:
                print(f"{identifier}: exception raised", file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                returncode = 1

        return returncode


    def main(self):
        """Upload all device files of each release"""
        exitcode = 0
        releases = self.find_releases()
        num_files = sum([len(r) for r in releases])
        print(f"Found {len(releases)} releases with a total of {num_files} files")

        for release_id, release in releases.items():
            try:
                identifier = f"grapheneos_release_{release_id}"
                metadata = {
                    'collection': 'open_source_software',
                    'mediatype': 'software',
                    'publisher': 'GrapheneOS',
                    'creator': 'GrapheneOS',
                    'title': f"GrapheneOS release {release_id}",
                    'description': f"GrapheneOS release {release_id}",
                    'subject': ['GrapheneOS', 'Android'],
                }
                error = self.upload_release(identifier, metadata, release)
                if error:
                    exitcode = 1
            except Exception as e:
                print(f"{identifier}: exception raised", file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                exitcode = 1
        return exitcode


if __name__ == '__main__':
    sys.exit(ArchiveUploader().main())
