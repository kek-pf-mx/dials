from __future__ import absolute_import, division, print_function
import os
import socket
import time
import timeit
import libtbx.load_env
from libtbx import easy_run

have_dials_regression = libtbx.env.has_module("dials_regression")
if have_dials_regression:
  dials_regression = libtbx.env.find_in_repositories(relative_path="dials_regression", test=os.path.isdir)

def run():
  if not have_dials_regression:
    print("Skipping tst_find_spots_server_client: dials_regression not available.")
    return

  def start_server(server_command):
    result = easy_run.fully_buffered(command=server_command)
    result.show_stdout()
    result.show_stderr()

  import multiprocessing
  s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  s.bind(("", 0))
  port = s.getsockname()[1]
  s.close()
  server_command = "dials.find_spots_server port=%i nproc=3" % port
  print(server_command)

  p = multiprocessing.Process(target=start_server, args=(server_command, ))
  p.daemon = True
  p.start()
  wait_for_server(port) # need to give server chance to start

  try:
    exercise_client(port=port)

  finally:
    client_stop_command = "dials.find_spots_client port=%i stop" % port
    result = easy_run.fully_buffered(command=client_stop_command).raise_if_errors()
    #result.show_stdout()
    p.terminate()

def wait_for_server(port, max_wait=20):
  print("Waiting up to %d seconds for server to start" % max_wait)
  server_ok = False
  start_time = timeit.default_timer()
  max_time = start_time + max_wait
  while (timeit.default_timer() < max_time) and not server_ok:
    try:
      s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      s.connect(('127.0.0.1', port))
      s.close()
      server_ok = True
    except socket.error as e:
      if (e.errno != 111) and (e.errno != 61):
        raise
      # ignore connection failures (111 connection refused on linux; 61 connection refused on mac)
      time.sleep(0.1)
  if not server_ok:
    raise Exception("Server failed to start after %d seconds" % max_wait)
  print("dials.find_spots_server up after %f seconds" % (timeit.default_timer() - start_time))

def exercise_client(port):
  import glob
  data_dir = os.path.join(dials_regression, "centroid_test_data")
  filenames = sorted(glob.glob(os.path.join(data_dir, "*.cbf")))
  assert len(filenames) > 0
  client_command = " ".join(["dials.find_spots_client", "port=%i" % port, "min_spot_size=3", "nproc=1", filenames[0]])

  index_client_command = " ".join([
      client_command,
      "index=True",
      "indexing.method=fft1d",
      "max_refine=10",
  ])
  print(index_client_command)
  result = easy_run.fully_buffered(command=index_client_command).raise_if_errors()
  out = "<document>%s</document>" % "\n".join(result.stdout_lines)
  result.show_stdout()
  #result.show_stderr()

  from xml.dom import minidom
  xmldoc = minidom.parseString(out)
  assert len(xmldoc.getElementsByTagName('image')) == 1
  assert len(xmldoc.getElementsByTagName('spot_count')) == 1
  assert len(xmldoc.getElementsByTagName('spot_count_no_ice')) == 1
  assert len(xmldoc.getElementsByTagName('d_min')) == 1
  assert len(xmldoc.getElementsByTagName('total_intensity')) == 1
  assert len(xmldoc.getElementsByTagName('unit_cell')) == 1
  assert len(xmldoc.getElementsByTagName('n_indexed')) == 1
  assert len(xmldoc.getElementsByTagName('fraction_indexed')) == 1

  unit_cell = [float(f) for f in xmldoc.getElementsByTagName('unit_cell')[0].childNodes[0].data.split()]

  from libtbx.test_utils import approx_equal
  assert approx_equal(unit_cell, [39.90, 42.67, 42.37, 89.89, 90.10, 90.13], eps=1e-1)

  client_command = " ".join([client_command] + filenames[1:])
  result = easy_run.fully_buffered(command=client_command).raise_if_errors()
  out = "<document>%s</document>" % "\n".join(result.stdout_lines)

  from xml.dom import minidom
  xmldoc = minidom.parseString(out)
  images = xmldoc.getElementsByTagName('image')
  assert len(images) == 9
  spot_counts = sorted([int(node.childNodes[0].data) for node in xmldoc.getElementsByTagName('spot_count')])
  assert spot_counts == sorted([203, 196, 205, 209, 195, 205, 203, 207, 189]), spot_counts
  spot_counts_no_ice = sorted(
      [int(node.childNodes[0].data) for node in xmldoc.getElementsByTagName('spot_count_no_ice')])
  assert spot_counts_no_ice \
         == sorted([169, 171, 175, 176, 177, 184, 193, 195, 196]), spot_counts_no_ice
  d_min = sorted([float(node.childNodes[0].data) for node in xmldoc.getElementsByTagName('d_min')])
  assert d_min == sorted([1.45, 1.47, 1.55, 1.55, 1.56, 1.59, 1.61, 1.61, 1.64]), d_min

if __name__ == '__main__':
  from dials.test import cd_auto
  with cd_auto(__file__):
    from libtbx.utils import show_times_at_exit
    show_times_at_exit()
    run()
