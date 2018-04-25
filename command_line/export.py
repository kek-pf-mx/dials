#!/usr/bin/env python
#
# export.py
#
#  Copyright (C) 2013 Diamond Light Source
#
#  Author: James Parkhurst
#
#  This code is distributed under the BSD license, a copy of which is
#  included in the root directory of this package.
#
from __future__ import absolute_import, division, print_function

import logging

from libtbx.phil import parse

logger = logging.getLogger('dials.command_line.export')

help_message = '''

This program is used to export the results of dials processing in various
formats.

The output formats currently supported are:

MTZ format exports the files as an unmerged mtz file, ready for input to
downstream programs such as Pointless and Aimless. The required input is an
experiments.json file and an integrated.pickle file.

NXS format exports the files as an NXmx file. The required input is an
experiments.json file and an integrated.pickle file.

MMCIF format exports the files as an mmcif file. The required input is an
experiments.json file and an integrated.pickle file.

XDS_ASCII format exports intensity data and the experiment metadata in the
same format as used by the output of XDS in the CORRECT step - output can
be scaled with XSCALE.

SADABS format exports intensity data (and geometry by direction cosines)
as an ersatz-SADABS format reverse engineered from the file format used by
EvalCCD for input to SADABS.

MOSFLM format exports the files as an index.mat mosflm-format matrix file and a
mosflm.in file containing basic instructions for input to mosflm. The required
input is an experiments.json file.

XDS format exports an experiments.json file as XDS.INP and XPARM.XDS files. If a
reflection pickle is given it will be exported as a SPOT.XDS file.

Examples::

  # Export to mtz
  dials.export experiments.json integrated.pickle
  dials.export experiments.json integrated.pickle mtz.hklout=integrated.mtz

  # Export to nexus
  dials.export experiments.json integrated.pickle format=nxs
  dials.export experiments.json integrated.pickle format=nxs nxs.hklout=integrated.nxs

  # Export to mmcif
  dials.export experiments.json integrated.pickle format=mmcif
  dials.export experiments.json integrated.pickle format=mmcif mmcif.hklout=integrated.mmcif

  # Export to mosflm
  dials.export experiments.json integrated.pickle format=mosflm

  # Export to xds
  dials.export strong.pickle format=xds
  dials.export indexed.pickle format=xds
  dials.export experiments.json format=xds
  dials.export experiments.json indexed.pickle format=xds

'''

phil_scope = parse('''

  format = *mtz sadabs nxs mmcif mosflm xds best xds_ascii json
    .type = choice
    .help = "The output file format"

  summation = False
    .type = bool
    .help = "Output summation integrated data (default profile fitted)"

  debug = False
    .type = bool
    .help = "Output additional debugging information"

  mtz {

    ignore_panels = False
      .type = bool
      .help = "Ignore multiple panels / detectors in output (deprecated)"

    include_partials = False
      .type = bool
      .help = "Include partial reflections (scaled) in output"

    keep_partials = False
      .type = bool
      .help = "Keep low partiality reflections"

    scale_partials = True
      .type = bool
      .help = "Scale partial reflections to 100% (unreliable if partiality low)"

    apply_scales = False
      .type = bool
      .help = "Apply scale factors in inverse_scale_factor column if present"

    min_isigi = -5
      .type = float
      .help = "Exclude reflections with unfeasible values of I/Sig(I)"

    force_static_model = False
      .type = bool
      .help = "Force program to use static model even if scan varying is present"

    filter_ice_rings = False
      .type = bool
      .help = "Filter reflections at ice ring resolutions"

    ignore_profile_fitting = False
      .type = bool
      .help = "Ignore profile fitted intensities. Sometimes necessary for narrow"
              "wedges or other situations where profile fitting has failed for"
              "all reflections and we only have summation intensities."

    hklout = integrated.mtz
      .type = path
      .help = "The output MTZ file"
  }

  sadabs {

    hklout = integrated.sad
      .type = path
      .help = "The output raw sadabs file"
    run = 1
      .type = int
      .help = "Batch number / run number for output file"
    predict = False
      .type = bool
      .help = "Compute centroids with static model, not observations"

  }

  xds_ascii {

    hklout = DIALS.HKL
      .type = path
      .help = "The output raw hkl file"

  }

  nxs {

    hklout = integrated.nxs
      .type = path
      .help = "The output Nexus file"

  }

  mmcif {

    hklout = integrated.cif
      .type = path
      .help = "The output CIF file"

  }

  mosflm {

    directory = mosflm
      .type = path
      .help = "The output directory for mosflm output"

  }

  xds {

    directory = xds
      .type = path
      .help = "The output directory for xds output"

  }

  best {

    prefix = best
      .type = str
      .help = "The prefix for the output file names for best"
              "(.hkl, .dat and .par files)"

    n_bins = 100
      .type = int(value_min=1)
      .help = "Number of resolution bins for background estimation"

    min_partiality = 0.1
      .type = float(value_min=0, value_max=1)
      .help = "Minimum partiality of reflections to export"

  }

  json {
    filename = rlp.json
      .type = path
    compact = True
      .type = bool
    n_digits = 6
      .type = int(value_min=1)
      .help = "Number of decimal places to be used for representing the"
              "reciprocal lattice points."
  }

  output {

    log = dials.export.log
      .type = path
      .help = "The log filename"

    debug_log = dials.export.debug.log
      .type = path
      .help = "The debug log filename"

  }
''')

class BaseExporter(object):
  '''
  A base class for export reflections - though do we need a class here
  - could just have entry points registered?
  '''

  def __init__(self, params, experiments, reflections):
    self.params = params
    self.experiments = experiments
    self.reflections = reflections

  def check(self):
    '''Check the input provided was sane.'''
    raise RuntimeError('Overload check()')

  def export(self):
    '''Export the data in the desired format.'''
    raise RuntimeError('Overload export()')

class MTZExporter(object):
  '''
  A class to export reflections in MTZ format

  '''

  def __init__(self, params, experiments, reflections):
    '''
    Initialise the exporter

    :param params: The phil parameters
    :param experiments: The experiment list
    :param reflections: The reflection tables

    '''

    # Check the input
    if len(experiments) == 0:
      raise Sorry('MTZ exporter requires an experiment list')
    if len(reflections) != 1:
      raise Sorry('MTZ exporter requires 1 reflection table')

    # Save the input
    self.params = params
    self.experiments = experiments
    self.reflections = reflections[0]

  def export(self):
    '''
    Export the files

    '''
    from dials.util.export_mtz import export_mtz
    m = export_mtz(
      self.reflections,
      self.experiments,
      self.params.mtz.hklout,
      include_partials=params.mtz.include_partials,
      keep_partials=params.mtz.keep_partials,
      scale_partials=params.mtz.scale_partials,
      min_isigi=params.mtz.min_isigi,
      force_static_model=params.mtz.force_static_model,
      filter_ice_rings=params.mtz.filter_ice_rings,
      ignore_profile_fitting=params.mtz.ignore_profile_fitting,
      apply_scales=params.mtz.apply_scales)
    from cStringIO import StringIO
    summary = StringIO()
    m.show_summary(out=summary)
    logger.info('')
    logger.info(summary.getvalue())

class SadabsExporter(object):
  '''
  A class to export data in HKL format

  '''

  def __init__(self, params, experiments, reflections):
    '''
    Initialise the exporter

    :param params: The phil parameters
    :param experiments: The experiment list
    :param reflections: The reflection tables

    '''

    # Check the input
    if len(experiments) == 0:
      raise Sorry('SADABS exporter requires an experiment list')
    if len(reflections) != 1:
      raise Sorry('SADABS exporter requires 1 reflection table')

    # Save the data
    self.params = params
    self.experiments = experiments
    self.reflections = reflections[0]

  def export(self):
    from dials.util.export_sadabs import export_sadabs
    export_sadabs(
      self.reflections,
      self.experiments,
      self.params.sadabs.hklout,
      run=self.params.sadabs.run,
      summation=self.params.summation,
      include_partials=params.mtz.include_partials,
      keep_partials=params.mtz.keep_partials,
      debug=params.debug,
      predict=params.sadabs.predict)

class XDSASCIIExporter(object):
  '''
  A class to export data in XDS_ASCII format

  '''

  def __init__(self, params, experiments, reflections):
    '''
    Initialise the exporter

    :param params: The phil parameters
    :param experiments: The experiment list
    :param reflections: The reflection tables

    '''

    # Check the input
    if len(experiments) == 0:
      raise Sorry('XDS_ASCII exporter requires an experiment list')
    if len(reflections) != 1:
      raise Sorry('XDS_ASCII exporter requires 1 reflection table')

    # Save the input
    self.params = params
    self.experiments = experiments
    self.reflections = reflections[0]

  def export(self):
    from dials.util.export_xds_ascii import export_xds_ascii
    export_xds_ascii(
      self.reflections,
      self.experiments,
      self.params.xds_ascii.hklout,
      summation=self.params.summation,
      include_partials=params.mtz.include_partials,
      keep_partials=params.mtz.keep_partials)

class NexusExporter(object):
  '''
  A class to export data in Nexus format

  '''

  def __init__(self, params, experiments, reflections):
    '''
    Initialise the exporter

    :param params: The phil parameters
    :param experiments: The experiment list
    :param reflections: The reflection tables

    '''

    # Check the input
    if len(experiments) == 0:
      raise Sorry('Nexus exporter requires an experiment list')
    if len(reflections) != 1:
      raise Sorry('Nexus exporter requires 1 reflection table')

    # Save the input
    self.params = params
    self.experiments = experiments
    self.reflections = reflections[0]

  def export(self):
    '''
    Export the files

    '''
    from dials.util.nexus import dump
    dump(
      self.experiments,
      self.reflections,
      self.params.nxs.hklout)

class MMCIFExporter(object):
  '''
  A class to export data in CIF format

  '''

  def __init__(self, params, experiments, reflections):
    '''
    Initialise the exporter

    :param params: The phil parameters
    :param experiments: The experiment list
    :param reflections: The reflection tables

    '''

    # Check the input
    if len(experiments) == 0:
      raise Sorry('CIF exporter requires an experiment list')
    if len(reflections) != 1:
      raise Sorry('CIF exporter requires 1 reflection table')

    # Save the input
    self.params = params
    self.experiments = experiments
    self.reflections = reflections[0]

  def export(self):
    '''
    Export the files

    '''
    from dials.util.export_mmcif import MMCIFOutputFile
    outfile = MMCIFOutputFile(self.params.mmcif.hklout)
    outfile.write(self.experiments, self.reflections)


class MosflmExporter(object):
  '''
  A class to export stuff in mosflm format

  '''

  def __init__(self, params, experiments, reflections):
    '''
    Initialise the exporter

    :param params: The phil parameters
    :param experiments: The experiment list
    :param reflections: The reflection tables

    '''

    # Check the input
    if len(experiments) == 0:
      raise Sorry('Mosflm exporter requires an experiment list')
    if len(reflections) != 0:
      raise Sorry('Mosflm exporter does not need a reflection table')

    # Save the stuff
    self.params = params
    self.experiments = experiments

  def export(self):
    '''
    Export the files

    '''
    from dials.util.mosflm import dump
    dump(
      self.experiments,
      self.params.mosflm.directory)


class XDSExporter(object):
  '''
  A class to export stuff in xds format

  '''

  def __init__(self, params, experiments, reflections):
    '''
    Initialise the exporter

    :param params: The phil parameters
    :param experiments: The experiment list
    :param reflections: The reflection tables

    '''

    # Check the input
    if len(reflections) > 1:
      raise Sorry('XDS exporter requires 0 or 1 reflection table')

    # Save the stuff
    self.params = params
    self.experiments = experiments
    if len(reflections) == 0:
      self.reflections = reflections
    else:
      self.reflections = reflections[0]

  def export(self):
    '''
    Export the files

    '''
    from dials.util.xds import dump
    dump(
      self.experiments,
      self.reflections,
      self.params.xds.directory)


class BestExporter(object):
  '''
  A class to export stuff in BEST format

  '''

  def __init__(self, params, experiments, reflections):
    '''
    Initialise the exporter

    :param params: The phil parameters
    :param experiments: The experiment list
    :param reflections: The reflection tables

    '''

    # Check the input
    if len(experiments) == 0:
      raise Sorry('BEST exporter requires an experiment list')
    if len(reflections) == 0:
      raise Sorry('BEST exporter require a reflection table')

    # Save the stuff
    self.params = params
    self.experiments = experiments
    self.reflections = reflections

  def export(self):
    '''
    Export the files

    '''
    from dials.util import best

    experiment = self.experiments[0]
    reflections = self.reflections[0]
    partiality = reflections['partiality']
    sel = partiality >= self.params.best.min_partiality
    logger.info('Selecting %s/%s reflections with partiality >= %s' %(
      sel.count(True), sel.size(), self.params.best.min_partiality))
    if sel.count(True) == 0:
      raise Sorry(
      "No reflections remaining after filtering for minimum partiality (min_partiality=%f)"
       %(self.params.best.min_partiality))
    reflections = reflections.select(sel)

    imageset = experiment.imageset
    prefix = self.params.best.prefix

    best.write_background_file(
      '%s.dat' %prefix, imageset, n_bins=self.params.best.n_bins)
    best.write_integrated_hkl(prefix, reflections)
    best.write_par_file('%s.par' %prefix, experiment)


class JsonExporter(object):
  '''
  A class to export reflections in json format

  '''

  def __init__(self, params, reflections, datablocks=None, experiments=None):
    '''
    Initialise the exporter

    :param params: The phil parameters
    :param experiments: The experiment list
    :param reflections: The reflection tables

    '''

    # Check the input
    if datablocks is None and experiments is None:
      raise Sorry('json exporter requires a datablock or an experiment list')
    if len(reflections) == 0:
      raise Sorry('json exporter require a reflection table')

    # Save the stuff
    self.params = params
    self.datablocks = datablocks
    self.experiments = experiments
    self.reflections = reflections

  def export(self):
    '''
    Export the files

    '''
    from dials.util import export_json
    from scitbx.array_family import flex

    if self.experiments is not None and len(self.experiments) > 0:
      imagesets = [expt.imageset for expt in self.experiments]
    else:
      imagesets = []
      for datablock in self.datablocks:
        imagesets.extend(datablock.extract_imagesets())

    reflections = None
    assert len(self.reflections) == len(imagesets), (len(self.reflections), len(imagesets))
    for i, (refl, imgset) in enumerate(zip(self.reflections, imagesets)):
      refl['imageset_id'] = flex.size_t(refl.size(), i)
      if reflections is None:
        reflections = refl
      else:
        reflections.extend(refl)

    settings = self.params
    settings.__inject__('beam_centre', None)
    settings.__inject__('reverse_phi', None)

    exporter = export_json.ReciprocalLatticeJson(settings=self.params)
    exporter.load_models(imagesets, reflections)
    exporter.as_json(
      filename=params.json.filename, compact=params.json.compact,
      n_digits=params.json.n_digits, datablocks=datablocks)


if __name__ == '__main__':
  import libtbx.load_env
  from dials.util.options import OptionParser
  from dials.util.options import flatten_datablocks
  from dials.util.options import flatten_experiments
  from dials.util.options import flatten_reflections
  from dials.util.version import dials_version
  from dials.util import log
  from libtbx.utils import Sorry
  import os

  usage = '%s experiments.json reflections.pickle [options]' % (
              libtbx.env.dispatcher_name)

  # Create the option parser
  if 'DIALS_EXPORT_DO_NOT_CHECK_FORMAT' in os.environ:
    parser = OptionParser(
      usage=usage,
      read_experiments=True,
      read_reflections=True,
      read_datablocks=True,
      check_format=False,
      phil=phil_scope,
      epilog=help_message)
  else:
    parser = OptionParser(
      usage=usage,
      read_experiments=True,
      read_reflections=True,
      read_datablocks=True,
      phil=phil_scope,
      epilog=help_message)

  # Get the parameters
  params, options = parser.parse_args(show_diff_phil=False)

  # Configure the logging
  log.config(
    info=params.output.log,
    debug=params.output.debug_log)

  # Print the version number
  logger.info(dials_version())

  # Log the diff phil
  diff_phil = parser.diff_phil.as_str()
  if diff_phil is not '':
    logger.info('The following parameters have been modified:\n')
    logger.info(diff_phil)

  # Get the experiments and reflections
  datablocks = flatten_datablocks(params.input.datablock)

  experiments = flatten_experiments(params.input.experiments)
  reflections = flatten_reflections(params.input.reflections)
  if len(reflections) == 0 and len(experiments) == 0 and len(datablocks) == 0:
    parser.print_help()
    exit(0)

  # Choose the exporter
  if params.format == 'mtz':
    exporter = MTZExporter(params, experiments, reflections)
  elif params.format == 'sadabs':
    exporter = SadabsExporter(params, experiments, reflections)
  elif params.format == 'xds_ascii':
    exporter = XDSASCIIExporter(params, experiments, reflections)
  elif params.format == 'nxs':
    exporter = NexusExporter(params, experiments, reflections)
  elif params.format == 'mmcif':
    exporter = MMCIFExporter(params, experiments, reflections)
  elif params.format == 'mosflm':
    exporter = MosflmExporter(params, experiments, reflections)
  elif params.format == 'xds':
    exporter = XDSExporter(params, experiments, reflections)
  elif params.format == 'best':
    exporter = BestExporter(params, experiments, reflections)
  elif params.format == 'json':
    exporter = JsonExporter(
      params, reflections, datablocks=datablocks, experiments=experiments)
  else:
    raise Sorry('Unknown format: %s' % params.format)

  # Export the data
  exporter.export()
