from __future__ import absolute_import, division, print_function

from glob import glob
import os
import procrunner

def test(dials_regression, tmpdir):
  tmpdir.chdir()

  images = glob(os.path.join(dials_regression, "centroid_test_data", "centroid*.cbf"))

  result = procrunner.run_process([
      "dials.find_spots",
      "output.datablock=datablock.json",
      "output.reflections=spotfinder.pickle",
      "output.shoeboxes=True",
  ] + images)
  assert result['exitcode'] == 0
  assert result['stderr'] == ''
  assert os.path.exists("datablock.json")
  assert os.path.exists("spotfinder.pickle")

  result = procrunner.run_process([
      "dials.find_hot_pixels",
      "input.datablock=datablock.json",
      "input.reflections=spotfinder.pickle",
      "output.mask=hot_mask.pickle"
  ])
  assert result['exitcode'] == 0
  assert result['stderr'] == ''
  assert os.path.exists("hot_mask.pickle")
  assert "Found 8 hot pixels" in result['stdout']
