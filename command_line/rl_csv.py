# LIBTBX_SET_DISPATCHER_NAME dev.dials.csv
from __future__ import absolute_import, division

import iotbx.phil
from scitbx.array_family import flex
from scitbx import matrix
from dials.util.options import OptionParser
from dials.util.options import flatten_datablocks, flatten_reflections
from dials.algorithms.indexing.indexer \
     import indexer_base, filter_reflections_by_scan_range

import libtbx.load_env

phil_scope = iotbx.phil.parse("""
output {
  csv = rl.csv
    .type = path
    .help = 'Output filename for reciprocal mapped reflections'
  compress = False
    .type = bool
    .help = 'Compress file with gzip as written'
  dp = 0
    .type = int
    .help = 'Decimal places for output, 0 => %f'
}
""")

master_params = phil_scope.fetch().extract()

def run(args):
  import libtbx.load_env
  from dials.util import log
  usage = "%s [options] datablock.json strong.pickle output.csv=rl.csv" % libtbx.env.dispatcher_name

  parser = OptionParser(usage=usage, phil=phil_scope, read_datablocks=True, read_reflections=True, check_format=False)

  params, options = parser.parse_args(show_diff_phil=False)
  datablocks = flatten_datablocks(params.input.datablock)
  reflections = flatten_reflections(params.input.reflections)

  if len(datablocks) == 0 or len(reflections) == 0:
    parser.print_help()
    exit(0)

  imagesets = []

  for db in datablocks:
    imagesets.extend(db.extract_imagesets())

  spots = []

  for reflection in reflections:
    unique_ids = set(reflection['id'])
    for unique_id in sorted(unique_ids):
      spots.append(reflection.select(reflection['id'] == unique_id))

  assert len(imagesets) == len(spots)

  if params.output.compress:
    import gzip
    fout = gzip.GzipFile(params.output.csv, 'w')
  else:
    fout = open(params.output.csv, 'w')

  fout.write('# x,y,z,experiment_id,imageset_id\n')

  dp = params.output.dp

  if dp <= 0:
    fmt = '%f,%f,%f,%d,%d\n'
  else:
    fmt = '%%.%df,%%.%df,%%.%df,%%d,%%d\n' % (dp, dp, dp)

  print 'Using format:', fmt.strip()

  for k, (imageset, refl) in enumerate(zip(imagesets, spots)):
    if 'imageset_id' not in refl:
      refl['imageset_id'] = refl['id']

    reflmm = indexer_base.map_spots_pixel_to_mm_rad(
        spots=refl, detector=imageset.get_detector(), scan=imageset.get_scan())

    indexer_base.map_centroids_to_reciprocal_space(
        reflmm, detector=imageset.get_detector(), beam=imageset.get_beam(), goniometer=imageset.get_goniometer())

    rlp = reflmm['rlp']

    for _rlp in rlp:
      fout.write(fmt % (_rlp[0], _rlp[1], _rlp[2], k, k))

    print 'Appended %d spots to %s' % (len(rlp), params.output.csv)

  fout.close()

if __name__ == '__main__':
  import sys
  run(sys.argv[1:])
