from __future__ import absolute_import, division, print_function

import os
import procrunner

def test(dials_regression, tmpdir):
  tmpdir.chdir()

  input_filename = os.path.join(dials_regression, "centroid_test_data", "datablock.json")
  mask_filename = os.path.join(dials_regression, "centroid_test_data", "lookup_mask.pickle")
  output_filename = "output_datablock.json"

  result = procrunner.run_process([
      'dials.apply_mask',
      'input.datablock=%s' % input_filename,
      'input.mask=%s' % mask_filename,
      'output.datablock=%s' % output_filename,
  ])
  assert result['exitcode'] == 0
  assert result['stderr'] == ''

  from dials.array_family import flex  # import dependency
  from dxtbx.datablock import DataBlockFactory
  datablocks = DataBlockFactory.from_json_file(output_filename)

  assert len(datablocks) == 1
  imagesets = datablocks[0].extract_imagesets()
  assert len(imagesets) == 1
  imageset = imagesets[0]
  assert imageset.external_lookup.mask.filename == mask_filename
