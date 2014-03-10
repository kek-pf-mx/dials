#!/usr/bin/env python
#
# import_xds.py
#
#  Copyright (C) 2013 Diamond Light Source
#
#  Author: James Parkhurst
#
#  This code is distributed under the BSD license, a copy of which is
#  included in the root directory of this package.
from __future__ import division

class SpotXDSImporter(object):
  ''' Class to import a spot.xds file to a reflection table. '''

  def __init__(self, spot_xds):
    self._spot_xds = spot_xds

  def __call__(self, options):
    ''' Import the spot.xds file. '''
    from iotbx.xds import spot_xds
    from dials.util.command_line import Command
    from dials.array_family import flex
    import dxtbx

    # Read the SPOT.XDS file
    Command.start('Reading SPOT.XDS')
    handle = spot_xds.reader()
    handle.read_file(self._spot_xds)
    centroid = handle.centroid
    intensity = handle.intensity
    try:
      miller_index = handle.miller_index
    except AttributeError:
      miller_index = None
    Command.end('Read {0} spots from SPOT.XDS file.'.format(len(centroid)))

    # Create the reflection list
    Command.start('Creating reflection list')
    table = flex.reflection_table()
    table['id'] = flex.size_t(len(centroid), 0)
    table['panel'] = flex.size_t(len(centroid), 0)
    if miller_index:
      table['miller_index'] = flex.miller_index(miller_index)
    table['xyzobs.px.value'] = flex.vec3_double(centroid)
    table['intensity.raw.value'] = flex.double(intensity)
    Command.end('Created reflection list')

    # Remove invalid reflections
    Command.start('Removing invalid reflections')
    if miller_index and options.remove_invalid:
      flags = flex.bool([h != (0, 0, 0) for h in table['miller_index']])
      table = table.select(flags)
    Command.end('Removed invalid reflections, %d remaining' % len(table))

    # Output the table to pickle file
    if options.output is None: options.output = 'spot_xds.pickle'
    Command.start('Saving reflection table to %s' % options.output)
    table.as_pickle(options.output)
    Command.end('Saved reflection table to %s' % options.output)


class IntegrateHKLImporter(object):
  ''' Class to import an integrate.hkl file to a reflection table. '''

  def __init__(self, integrate_hkl, experiment):
    self._integrate_hkl = integrate_hkl
    self._experiment = experiment

  def __call__(self, options):
    ''' Import the integrate.hkl file. '''

    from iotbx.xds import integrate_hkl
    from dials.array_family import flex
    from dials.util.command_line import Command
    import dxtbx
    from math import pi
    from scitbx import matrix

    # Read the SPOT.XDS file
    Command.start('Reading INTEGRATE.HKL')
    handle = integrate_hkl.reader()
    handle.read_file(self._integrate_hkl)
    hkl    = flex.miller_index(handle.hkl)
    xyzcal = flex.vec3_double(handle.xyzcal)
    xyzobs = flex.vec3_double(handle.xyzobs)
    iobs   = flex.double(handle.iobs)
    sigma  = flex.double(handle.sigma)
    rlp = flex.double(handle.rlp)
    peak = flex.double(handle.peak)
    Command.end('Read %d reflections from INTEGRATE.HKL file.' % len(hkl))

    # Derive the reindex matrix
    rdx = self.derive_reindex_matrix(handle)
    print 'Reindex matrix:\n%d %d %d\n%d %d %d\n%d %d %d' % (rdx.elems)

    # Reindex the reflections
    Command.start('Reindexing reflections')
    hkl = flex.miller_index([rdx * h for h in hkl])
    Command.end('Reindexed %d reflections' % len(hkl))

    # Create the reflection list
    Command.start('Creating reflection table')
    table = flex.reflection_table()
    table['id'] = flex.size_t(len(hkl), 0)
    table['panel'] = flex.size_t(len(hkl), 0)
    table['miller_index'] = hkl
    table['xyzcal.px'] = xyzcal
    table['xyzobs.px.value'] = xyzobs
    table['intensity.cor.value'] = iobs
    table['intensity.cor.variance'] = sigma**2
    table['intensity.raw.value'] = iobs * peak / rlp
    table['intensity.raw.variance'] = sigma**2 * peak / rlp
    table['lp'] = rlp
    Command.end('Created table with {0} reflections'.format(len(table)))

    # Output the table to pickle file
    if options.output is None: options.output = 'integrate_hkl.pickle'
    Command.start('Saving reflection table to %s' % options.output)
    table.as_pickle(options.output)
    Command.end('Saved reflection table to %s' % options.output)

  def derive_reindex_matrix(self, handle):
    '''Derive a reindexing matrix to go from the orientation matrix used
    for XDS integration to the one used for DIALS integration.'''
    from scitbx import matrix

    dA = self._experiment.crystal.get_A()
    dbeam = matrix.col(self._experiment.beam.get_direction())
    daxis = matrix.col(self._experiment.goniometer.get_rotation_axis())
    xbeam = matrix.col(handle.beam_vector)
    xaxis = matrix.col(handle.rotation_axis)

    # want to align XDS -s0 vector...
    from rstbx.cftbx.coordinate_frame_helpers import align_reference_frame
    R = align_reference_frame(- xbeam, dbeam, xaxis, daxis)
    A = matrix.sqr(
      handle.unit_cell_a_axis +
      handle.unit_cell_b_axis +
      handle.unit_cell_c_axis).inverse()
    xA = R * A

    # assert that this should just be a simple integer rotation matrix
    # i.e. reassignment of a, b, c so...

    return matrix.sqr(map(int, map(round, (dA.inverse() * xA).elems)))


class XDSFileImporter(object):
  ''' Import a data block from xds. '''

  def __init__(self, args):
    ''' Initialise with the options'''
    self.args = args

  def __call__(self, options):
    from dials.model.experiment.experiment_list import ExperimentListFactory
    from dials.model.experiment.experiment_list import ExperimentListDumper
    import os
    # Get the XDS.INP file
    xds_inp = os.path.join(self.args[0], 'XDS.INP')
    if options.xds_file is None:
      xds_file = XDSFileImporter.find_best_xds_file(self.args[0])
    else:
      xds_file = os.path.join(self.args[0], options.xds_file)

    # Check a file is given
    if xds_file is None:
      raise RuntimeError('No XDS file found')

    # Load the experiment list
    unhandled = []
    experiments = ExperimentListFactory.from_xds(xds_inp, xds_file)

    # Print out any unhandled files
    if len(unhandled) > 0:
      print '-' * 80
      print 'The following command line arguments were not handled:'
      for filename in unhandled:
        print '  %s' % filename

    # Print some general info
    print '-' * 80
    print 'Read %d experiments' % len(experiments)

    # Loop through the data blocks
    for i, exp in enumerate(experiments):

      # Print some experiment info
      print "-" * 80
      print "Experiment %d" % i
      print "  format: %s" % str(exp.imageset.reader().get_format_class())
      print "  type: %s" % type(exp.imageset)
      print "  num images: %d" % len(exp.imageset)

      # Print some model info
      if options.verbose > 1:
        print ""
        if exp.beam:       print exp.beam
        else:              print "no beam!"
        if exp.detector:   print exp.detector
        else:              print "no detector!"
        if exp.goniometer: print exp.goniometer
        else:              print "no goniometer!"
        if exp.scan:       print exp.scan
        else:              print "no scan!"
        if exp.crystal:    print exp.crystal
        else:              print "no crystal!"

    # Write the experiment list to a JSON or pickle file
    if options.output is None:
      options.output = 'experiments.json'
    print "-" * 80
    print 'Writing experiments to %s' % options.output
    dump = ExperimentListDumper(experiments)
    dump.as_file(options.output)

    # Optionally save as a data block
    if options.xds_datablock:
      print "-" * 80
      print "Writing data block to %s" % options.xds_datablock
      dump = DataBlockDumper(experiments.to_datablocks())
      dump.as_file(options.xds_datablock)

  @staticmethod
  def find_best_xds_file(xds_dir):
    ''' Find the best available file.'''
    from os.path import exists, join

    # The possible files to check
    paths = [join(xds_dir, 'XDS_ASCII.HKL'),
             join(xds_dir, 'INTEGRATE.HKL'),
             join(xds_dir, 'GXPARM.XDS'),
             join(xds_dir, 'XPARM.XDS')]

    # Return the first path that exists
    for p in paths:
      if exists(p):
        return p

    # If no path exists, return None
    return None


def select_importer(args):
  from os.path import split
  from dials.model.experiment.experiment_list import ExperimentListFactory
  import libtbx.load_env
  path, filename = split(args[0])
  if filename == 'SPOT.XDS':
    return SpotXDSImporter(args[0])
  elif filename == 'INTEGRATE.HKL':
    assert(len(args) == 2)
    experiments = ExperimentListFactory.from_json_file(args[1])
    assert(len(experiments) == 1)
    return IntegrateHKLImporter(args[0], experiments[0])
  else:
    raise RuntimeError('expected (SPOT.XDS|INTEGRATE.HKL), got %s' % filename)


if __name__ == '__main__':

  from optparse import OptionParser

  # The option parser
  usage = "usage: %prog [options] (SPOT.XDS|INTEGRATE.HKL)"
  parser = OptionParser(usage)

  # The thing to import
  parser.add_option(
    "-i", "--input",
    dest = "input",
    type = "choice", choices=["experiment", "reflections"],
    default = "experiment",
    help = "The input method")

  # Write the datablock to JSON or Pickle
  parser.add_option(
    "-o", "--output",
    dest = "output",
    type = "string", default = None,
    help = "The output file")

  # Specify the file to use
  parser.add_option(
    '--xds-file',
    dest = 'xds_file',
    type = 'string', default = None,
    help = 'Explicitly specify file to use (fname=xds_dir/xds_file)')

  # Add an option to output a datablock with xds as well.
  parser.add_option(
    '--xds-datablock',
    dest = 'xds_datablock',
    type = 'string', default = None,
    help = 'Output filename of data block with xds')

  # Remove invalid reflections
  parser.add_option(
    "-r", "--remove-invalid",
    dest = "remove_invalid",
    action = "store_true", default = False,
    help = "Remove non-index reflections (if miller indices are present)")

  # Print verbose output
  parser.add_option(
    "-v", "--verbose",
    dest = "verbose",
    action = "count", default = 0,
    help = "Set the verbosity level (-vv gives a verbosity level of 2)")

  # Parse the command line arguments
  (options, args) = parser.parse_args()

  # Check number of arguments
  if len(args) == 0:
    parser.print_help()
    exit(0)

  # Select the importer class
  if options.input == 'experiment':
    importer = XDSFileImporter(args)
    pass
  else:
    importer = select_importer(args)

  # Import the XDS data
  importer(options)
