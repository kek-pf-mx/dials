from __future__ import absolute_import, division
import glob
import os
from libtbx import easy_run
from libtbx.test_utils import open_tmp_directory

import libtbx.load_env
have_dials_regression = libtbx.env.has_module("dials_regression")
if have_dials_regression:
  dials_regression = libtbx.env.find_in_repositories(relative_path="dials_regression", test=os.path.isdir)

def exercise():
  data_dir = os.path.join(dials_regression, "centroid_test_data")
  cwd = os.path.abspath(os.curdir)
  tmp_dir = os.path.abspath(open_tmp_directory())
  print tmp_dir
  os.chdir(tmp_dir)

  g = glob.glob(os.path.join(data_dir, "*.cbf"))
  assert len(g) == 9

  cmd = "dials.merge_cbf %s merge_n_images=3" % (" ".join(g))
  print cmd
  result = easy_run.fully_buffered(cmd).raise_if_errors()
  g = glob.glob(os.path.join(tmp_dir, "sum_*.cbf"))
  assert len(g) == 3

def run(args):
  if not have_dials_regression:
    print "Skipping tst_merge_cbf.py: dials_regression not available"
    return

  exercise()

if __name__ == '__main__':
  import sys
  from libtbx.utils import show_times_at_exit
  show_times_at_exit()
  run(sys.argv[1:])
