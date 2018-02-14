from __future__ import absolute_import, division

import iotbx.phil
from dials.util.options import OptionParser
from dials.util.options import flatten_reflections
from dials.util.options import flatten_datablocks
from dials.util.options import flatten_experiments
from dials.array_family import flex

help_message = '''
Augment spot list with additional information - for example number of pixels
in peak region etc.'''

phil_scope = iotbx.phil.parse('''
output {
  reflections = stronger.pickle
    .type = path
}
find_max = False
  .type = bool
''')

def add_max_pixels_to_reflections(reflections):
  '''Iterate through reflections, find max pixel in each shoebox and max
  valid, add columns thereof'''

  from dials.algorithms.shoebox import MaskCode

  good = (MaskCode.Foreground | MaskCode.Valid)

  max_pixel = flex.double(reflections.size(), 0.0)
  max_valid = flex.double(reflections.size(), 0.0)

  shoeboxes = reflections['shoebox']

  for j, s in enumerate(shoeboxes):
    max_pixel[j] = flex.max(s.data)
    valid = (s.mask.as_1d() == good)
    max_valid[j] = flex.max(s.data.as_1d().select(valid))

  reflections['max_pixel'] = max_pixel
  reflections['max_valid'] = max_valid
  return

def add_resolution_to_reflections(reflections, datablock):
  '''Add column d to reflection list'''

  # will assume everything from the first detector at the moment - clearly this
  # could be incorrect, will have to do something a little smarter, later

  from dials.algorithms.indexing.indexer import indexer_base
  imageset = datablock.extract_imagesets()[0]

  if 'imageset_id' not in reflections:
    reflections['imageset_id'] = reflections['id']

  spots_mm = indexer_base.map_spots_pixel_to_mm_rad(
      spots=reflections, detector=imageset.get_detector(), scan=imageset.get_scan())

  indexer_base.map_centroids_to_reciprocal_space(
      spots_mm, detector=imageset.get_detector(), beam=imageset.get_beam(), goniometer=imageset.get_goniometer())

  d_spacings = 1 / spots_mm['rlp'].norms()

  reflections['d'] = d_spacings

def augment_reflections(reflections, params, datablock=None):
  '''Add extra columns of derived data.'''

  from dials.algorithms.shoebox import MaskCode
  good = (MaskCode.Foreground | MaskCode.Valid)

  if params.find_max:
    add_max_pixels_to_reflections(reflections)

  x0, x1, y0, y1, z0, z1 = reflections['bbox'].parts()
  x, y, z = reflections['xyzobs.px.value'].parts()

  dx = x1 - x0
  dy = y1 - y0

  # compute signal pixels in each shoebox as an array
  n_signal = reflections['shoebox'].count_mask_values(good)

  reflections['dx'] = dx
  reflections['dy'] = dy
  reflections['n_signal'] = n_signal

  if datablock:
    add_resolution_to_reflections(reflections, datablock)

  return reflections

def run(args):
  import libtbx.load_env
  from libtbx.utils import Sorry
  from dials.util import log
  usage = "%s [options] [datablock.json] strong.pickle" % \
    libtbx.env.dispatcher_name

  parser = OptionParser(
      usage=usage,
      phil=phil_scope,
      read_reflections=True,
      read_datablocks=True,
      check_format=False,
      epilog=help_message)

  params, options = parser.parse_args(show_diff_phil=True)

  datablocks = flatten_datablocks(params.input.datablock)
  reflections = flatten_reflections(params.input.reflections)

  if len(reflections) != 1:
    raise Sorry("Exactly one reflection file needed")
  if len(datablocks) > 1:
    raise Sorry("0, 1 datablocks required")

  datablock = None
  if len(datablocks) == 1:
    datablock = datablocks[0]

  stronger = augment_reflections(reflections[0], params, datablock=datablock)
  stronger.as_pickle(params.output.reflections)

if __name__ == '__main__':
  import sys
  run(sys.argv[1:])
