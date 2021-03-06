#!/usr/bin/env python
# coding=utf-8

"""
Syncs files between an Android device and your computer.

Like rsync, expects source and destination to be of the form THING:PATH,
or just PATH  for the local filesystem. The difference is that adbsync
expects an Android device identifier instead of a hostnam for "THING".
Leave in the coon, but leave out "THING" if you want the defaut device.
(And actually, right now only the default device works.)
"""

import argparse
import datetime
import errno
import os
import re
import subprocess
import sys
import time

from pprint import pprint

__copyright__ = "Copyright 2012 Laurence Gonsalves"
__author__    = "Laurence Gonsalves"
__license__   = "GPLv2"
__email__     = "laurence@xenomachina.com"

def mkdir_p(path):
  try:
    os.makedirs(path)
  except OSError as exc:
    if exc.errno != errno.EEXIST:
      raise

def touch(fname, dt=None):
  if dt is not None:
    dt = time.mktime(dt.timetuple())
    dt = (time.time(), dt)
  with file(fname, 'a'):
    os.utime(fname, dt)

LS_LINE_REGEX = re.compile(r'(..........)\s+(\w+)\s+(\w+)\s+(\d+)?\s+(\d\d\d\d-\d\d-\d\d \d\d:\d\d)\s+(.+)$')

class FileInfo(object):
  def __init__(self, perms, user, group, size, timestamp, name):
    self.perms = perms
    assert perms[1] == 'r'
    self.user = user
    self.group = group
    self.size = None if size is None else int(size)
    self.timestamp = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M')
    self.name = name

  def __repr__(self):
    return 'FileInfo(' + ', '.join(map(repr, (self.perms,
                     self.user,
                     self.group,
                     self.size,
                     self.timestamp,
                     self.name))) + ')'

def ListAndroidDir(dir, device=None):
  adb_prefix = ['adb'] + (['-s', device] if device else [])
  for line in subprocess.check_output(adb_prefix + ['shell', 'ls', '-la', dir]).split('\r\n'):
    if line:
      m = LS_LINE_REGEX.match(line)
      if m:
          yield FileInfo(*m.groups())
      else:
          print ("No match on line %r" % line)

def main():
  parser = argparse.ArgumentParser(description='Android file sync tool.')
  parser.add_argument('-n', '--dry-run',
      action='store_true',
      help="perform a trial run with no changes made")
  parser.add_argument('SRC',
      help="location to sync from")
  parser.add_argument('DEST',
      help="location to sync to")
  args = parser.parse_args()
  src = args.SRC
  dest = args.DEST
  dry_run = args.dry_run

  # For now, source must be Android, dest must not.
  assert ':' in src
  src_device, src = src.rsplit(":", 1)
  assert ':' not in dest

  # For now, source must be a directory, as must dest.
  assert src.endswith('/')
  assert dest.endswith('/')

  if not dry_run:
    mkdir_p(dest)
  file_count = 0
  copied_count = 0
  adb_prefix = ['adb'] + (['-s', src_device] if src_device else [])

  def copy_file(file, dest_file):
    print file.name + '...'
    pull_cmd = adb_prefix + ['pull', os.path.join(src, file.name), dest_file]
    if not dry_run:
      subprocess.check_call(pull_cmd)
      if not file.perms.startswith("d"):
          touch(dest_file, file.timestamp)
    return 1

  def handle_file(file):
    if file.perms.startswith("d"):
      copied_count = 0
      file_count = 0
      for subfile in ListAndroidDir(os.path.join(src, file.name), src_device):
        subfile.name = os.path.join(file.name, subfile.name)
        sfc, scc = handle_file(subfile)
        file_count += sfc
        copied_count += scc
      return file_count, copied_count
    out_fnam = os.path.join(dest, file.name)
    try:
      stat = os.stat(out_fnam)
    except OSError as exc:
      if exc.errno != errno.ENOENT:
        raise
      stat = None
    if stat is not None:
      if ((int(stat.st_mtime) != int(time.mktime(file.timestamp.timetuple())))
        or (stat.st_size != file.size)):
          stat = None
    if stat is None:
      return 1, copy_file(file, out_fnam)
    else:
      return 1, 0

  for file in ListAndroidDir(src, src_device):
    fc, cc = handle_file(file)
    file_count += fc
    copied_count += cc

  print "Copied %d files. %d files now up to date." % (copied_count, file_count)


if __name__ == '__main__':
  main()
