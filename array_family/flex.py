#
# flex.py
#
#  Copyright (C) 2013 Diamond Light Source
#
#  Author: James Parkhurst
#
#  This code is distributed under the BSD license, a copy of which is
#  included in the root directory of this package.
from __future__ import absolute_import, division
import boost.python
from dials.model import data
from dials_array_family_flex_ext import *
from cctbx.array_family.flex import *
from cctbx.array_family import flex

import logging
logger = logging.getLogger(__name__)

# Set the 'real' type to either float or double
if get_real_type() == "float":
  real = flex.float
elif get_real_type() == "double":
  real = flex.double
else:
  raise TypeError('unknown "real" type')

def strategy(cls, params=None):
  '''
  Wrap a class that takes params and experiments as a strategy.

  :param cls: The class to wrap
  :param params: The input parameters
  :return: A function to instantiate the strategy

  '''

  class Strategy(cls):
    algorithm = cls
    name = ''

    def __init__(self, *args):
      super(Strategy, self).__init__(params, *args)

  return Strategy

def default_background_algorithm():
  '''
  Get the default background algorithm.

  :return: The default background algorithm

  '''
  from dials.extensions import GLMBackgroundExt
  return strategy(GLMBackgroundExt)

def default_centroid_algorithm():
  '''
  Get the default centroid algorithm.

  :return: The default centroid algorithm

  '''
  from dials.extensions import SimpleCentroidExt
  return strategy(SimpleCentroidExt)

class reflection_table_aux(boost.python.injector, reflection_table):
  '''
  An injector class to add additional methods to the reflection table.

  '''

  # Set the default algorithms. These are set as class variables so that if they
  # are changed in the class, all new instances of reflection table will have
  # the modified algorithms. If these are modified on the instance level, then
  # only the instance will have the modified algorithms and new instances will
  # have the defaults
  _background_algorithm = default_background_algorithm()
  _centroid_algorithm = default_centroid_algorithm()

  @staticmethod
  def from_predictions(experiment, dmin=None, dmax=None, margin=1, force_static=False, padding=0):
    '''
    Construct a reflection table from predictions.

    :param experiment: The experiment to predict from
    :param dmin: The maximum resolution
    :param dmax: The minimum resolution
    :param margin: The margin to predict around
    :param force_static: Do static prediction with a scan varying model
    :param padding: Padding in degrees
    :return: The reflection table of predictions

    '''
    if experiment.profile is not None:
      return experiment.profile.predict_reflections(
          experiment.imageset,
          experiment.crystal,
          experiment.beam,
          experiment.detector,
          experiment.goniometer,
          experiment.scan,
          dmin=dmin,
          dmax=dmax,
          margin=margin,
          force_static=force_static,
          padding=padding)
    from dials.algorithms.spot_prediction.reflection_predictor \
      import ReflectionPredictor
    predict = ReflectionPredictor(
        experiment, dmin=dmin, dmax=dmax, margin=margin, force_static=force_static, padding=padding)
    return predict()

  @staticmethod
  def from_predictions_multi(experiments, dmin=None, dmax=None, margin=1, force_static=False, padding=0):
    '''
    Construct a reflection table from predictions.

    :param experiments: The experiment list to predict from
    :param dmin: The maximum resolution
    :param dmax: The minimum resolution
    :param margin: The margin to predict around
    :param force_static: Do static prediction with a scan varying model
    :param padding: Padding in degrees
    :return: The reflection table of predictions

    '''
    from scitbx.array_family import flex
    result = reflection_table()
    for i, e in enumerate(experiments):
      rlist = reflection_table.from_predictions(
          e, dmin=dmin, dmax=dmax, margin=margin, force_static=force_static, padding=padding)
      rlist['id'] = flex.int(len(rlist), i)
      result.extend(rlist)
    return result

  @staticmethod
  def from_observations(datablock, params=None):
    '''
    Construct a reflection table from observations.

    :param datablock: The datablock
    :param params: The input parameters
    :return: The reflection table of observations

    '''
    from dials.algorithms.spot_finding.factory \
      import SpotFinderFactory
    from libtbx import Auto

    if params.spotfinder.filter.min_spot_size is Auto:
      detector = datablock.extract_imagesets()[0].get_detector()
      if detector[0].get_type() == 'SENSOR_PAD':
        # smaller default value for pixel array detectors
        params.spotfinder.filter.min_spot_size = 3
      else:
        params.spotfinder.filter.min_spot_size = 6
      logger.info('Setting spotfinder.filter.min_spot_size=%i' % (params.spotfinder.filter.min_spot_size))

    # Get the integrator from the input parameters
    logger.info('Configuring spot finder from input parameters')
    find_spots = SpotFinderFactory.from_parameters(datablock=datablock, params=params)

    # Find the spots
    return find_spots(datablock)

  @staticmethod
  def from_pickle(filename):
    '''
    Read the reflection table from pickle file.

    :param filename: The pickle filename
    :return: The reflection table

    '''
    import cPickle as pickle
    from libtbx import smart_open

    with smart_open.for_reading(filename, 'rb') as infile:
      result = pickle.load(infile)
      assert (isinstance(result, reflection_table))
      return result

  @staticmethod
  def from_h5(filename):
    '''
    Read the reflections table from a HDF5 file.

    :param filename: The hdf5 filename
    :return: The reflection table

    '''
    from dials.util.nexus_old import NexusFile
    handle = NexusFile(filename, 'r')
    self = handle.get_reflections()
    handle.close()
    return self

  @staticmethod
  def empty_standard(nrows):
    '''
    Create an empty table of specified number of rows with most of the standard
    keys

    :param nrows: The number of rows to create
    :return: The reflection table

    '''

    assert nrows > 0
    table = reflection_table(nrows)

    # General properties
    table['flags'] = flex.size_t(nrows, 0)
    table['id'] = flex.int(nrows, 0)
    table['panel'] = flex.size_t(nrows, 0)

    # Predicted properties
    table['miller_index'] = flex.miller_index(nrows)
    table['entering'] = flex.bool(nrows)
    table['s1'] = flex.vec3_double(nrows, (0, 0, 0))
    table['xyzcal.mm'] = flex.vec3_double(nrows, (0, 0, 0))
    table['xyzcal.px'] = flex.vec3_double(nrows, (0, 0, 0))
    #table['ub_matrix'] = flex.mat3_double(nrows, (0, 0, 0, 0, 0, 0, 0, 0, 0))

    # Observed properties
    table['xyzobs.px.value'] = flex.vec3_double(nrows, (0, 0, 0))
    table['xyzobs.px.variance'] = flex.vec3_double(nrows, (0, 0, 0))
    table['xyzobs.mm.value'] = flex.vec3_double(nrows, (0, 0, 0))
    table['xyzobs.mm.variance'] = flex.vec3_double(nrows, (0, 0, 0))
    table['rlp'] = flex.vec3_double(nrows, (0, 0, 0))
    table['intensity.sum.value'] = flex.double(nrows, 0)
    table['intensity.sum.variance'] = flex.double(nrows, 0)
    table['intensity.prf.value'] = flex.double(nrows, 0)
    table['intensity.prf.variance'] = flex.double(nrows, 0)
    table['lp'] = flex.double(nrows, 0)
    table['profile.correlation'] = flex.double(nrows, 0)

    return table

  @staticmethod
  def plot(table, detector, key):
    '''
    Plot a reflection table using matplotlib

    :param table: The reflection table
    :param detector: The detector model
    :param key: The key to plot

    '''
    from matplotlib import pyplot as plt
    from matplotlib.patches import Polygon
    fig = plt.figure()
    ax = fig.add_subplot(111, aspect='equal')
    spots = table[key]
    if 'px' in key:
      spots = [detector[table['panel'][i]].get_pixel_lab_coord(spots[i][0:2]) for i in xrange(len(spots))]
    else:
      assert 'mm' in key
      spots = [detector[table['panel'][i]].get_lab_coord(spots[i][0:2]) for i in xrange(len(spots))]

    min_f = max_f = min_s = max_s = 0

    for i, panel in enumerate(detector):
      fs, ss = panel.get_image_size()
      p0 = panel.get_pixel_lab_coord((0, 0))
      p1 = panel.get_pixel_lab_coord((fs - 1, 0))
      p2 = panel.get_pixel_lab_coord((fs - 1, ss - 1))
      p3 = panel.get_pixel_lab_coord((0, ss - 1))
      p = Polygon((p0[0:2], p1[0:2], p2[0:2], p3[0:2]), closed=True, color='green', fill=False, hatch='/')

      if p.xy[:, 0].min() < min_f: min_f = p.xy[:, 0].min()
      if p.xy[:, 0].max() > max_f: max_f = p.xy[:, 0].max()
      if p.xy[:, 1].min() < min_s: min_s = p.xy[:, 1].min()
      if p.xy[:, 1].max() > max_s: max_s = p.xy[:, 1].max()

      ax.add_patch(p)

    ax.set_xlim((min_f - 10, max_f + 10))
    ax.set_ylim((min_s - 10, max_s + 10))
    plt.scatter([s[0] for s in spots], [s[1] for s in spots], c='blue', linewidth=0)
    plt.show()

  def as_pickle(self, filename):
    '''
    Write the reflection table as a pickle file.

    :param filename: The output filename

    '''
    import cPickle as pickle
    from libtbx import smart_open

    with smart_open.for_writing(filename, 'wb') as outfile:
      pickle.dump(self, outfile, protocol=pickle.HIGHEST_PROTOCOL)

  def as_h5(self, filename):
    '''
    Write the reflection table as a HDF5 file.

    :param filename: The output filename

    '''
    from dials.util.nexus_old import NexusFile
    handle = NexusFile(filename, 'w')
    handle.set_reflections(self)
    handle.close()

  def copy(self):
    '''
    Copy everything.

    :return: A copy of the reflection table

    '''
    from scitbx.array_family import flex
    return self.select(flex.bool(len(self), True))

  def sort(self, name, reverse=False, order=None):
    '''
    Sort the reflection table by a key.

    :param name: The name of the column
    :param reverse: Reverse the sort order
    :param order: For multi element items specify order

    '''
    import __builtin__
    if type(self[name]) in [vec2_double, vec3_double, mat3_double, int6, miller_index]:
      data = self[name]
      if order is None:
        perm = flex.size_t(__builtin__.sorted(range(len(self)), key=lambda x: data[x], reverse=reverse))
      else:
        assert len(order) == len(data[0])

        def compare(x, y):
          a = tuple(x[i] for i in order)
          b = tuple(y[i] for i in order)
          return cmp(a, b)

        perm = flex.size_t(__builtin__.sorted(range(len(self)), key=lambda x: data[x], cmp=compare, reverse=reverse))
    else:
      perm = flex.sort_permutation(self[name], reverse=reverse)
    self.reorder(perm)

  """
  Sorting the reflection table within an already sorted column
  """

  def subsort(self, key0, key1, reverse=False):
    '''
    Sort the reflection based on key1 within a constant key0.

    :param key0: The name of the column values to sort within
    :param key1: The sorting key name within the selected column

    '''
    import copy
    uniq_values = self[key0]
    for ii in set(uniq_values):
      val = (uniq_values == ii).iselection()
      ref_tmp = copy.deepcopy(self[min(val):(max(val) + 1)])
      ref_tmp.sort(key1, reverse)
      self[min(val):(max(val) + 1)] = ref_tmp

  def match(self, other):
    '''
    Match reflections with another set of reflections.

    :param other: The reflection table to match against
    :return: A tuple containing the matches in the reflection table and the
             other reflection table

    '''
    from dials.algorithms.spot_finding.spot_matcher import SpotMatcher
    match = SpotMatcher(max_separation=2)
    oind, sind = match(other, self)
    return sind, oind

  def match_with_reference_without_copying_columns(self, other):
    '''
    Match reflections with another set of reflections.

    :param other: The reflection table to match against
    :return: The matches

    '''
    from collections import defaultdict
    import __builtin__
    logger.info("Matching reference spots with predicted reflections")
    logger.info(' %d observed reflections input' % len(other))
    logger.info(' %d reflections predicted' % len(self))

    # Get the miller index, entering flag and turn number for
    # Both sets of reflections
    i1 = self['id']
    h1 = self['miller_index']
    e1 = self['entering'].as_int()
    x1, y1, z1 = self['xyzcal.px'].parts()
    p1 = self['panel']

    i2 = other['id']
    h2 = other['miller_index']
    e2 = other['entering'].as_int()
    x2, y2, z2 = other['xyzcal.px'].parts()
    p2 = other['panel']

    class Match(object):
      def __init__(self):
        self.a = []
        self.b = []

    # Create the match lookup
    lookup = defaultdict(Match)
    for i in range(len(self)):
      item = h1[i] + (e1[i], i1[i], p1[i])
      lookup[item].a.append(i)

    # Add matches from input reflections
    for i in range(len(other)):
      item = h2[i] + (e2[i], i2[i], p2[i])
      if item in lookup:
        lookup[item].b.append(i)

    # Create the list of matches
    match1 = []
    match2 = []
    for item, value in lookup.iteritems():
      if len(value.b) == 0:
        continue
      elif len(value.a) == 1 and len(value.b) == 1:
        match1.append(value.a[0])
        match2.append(value.b[0])
      else:
        matched = {}
        for i in value.a:
          d = []
          for j in value.b:
            dx = x1[i] - x2[j]
            dy = y1[i] - y2[j]
            dz = z1[i] - z2[j]
            d.append((i, j, dx**2 + dy**2 + dz**2))
          i, j, d = __builtin__.min(d, key=lambda x: x[2])
          if j not in matched:
            matched[j] = (i, d)
          elif d < matched[j][1]:
            matched[j] = (i, d)
        for key1, value1 in matched.iteritems():
          match1.append(value1[0])
          match2.append(key1)

    # Select everything which matches
    sind = flex.size_t(match1)
    oind = flex.size_t(match2)

    # Sort by self index
    sort_index = flex.size_t(__builtin__.sorted(range(len(sind)), key=lambda x: sind[x]))
    sind = sind.select(sort_index)
    oind = oind.select(sort_index)

    s2 = self.select(sind)
    o2 = other.select(oind)
    h1 = s2['miller_index']
    h2 = o2['miller_index']
    e1 = s2['entering']
    e2 = o2['entering']
    assert (h1 == h2).all_eq(True)
    assert (e1 == e2).all_eq(True)
    x1, y1, z1 = s2['xyzcal.px'].parts()
    x2, y2, z2 = o2['xyzcal.px'].parts()
    distance = flex.sqrt((x1 - x2)**2 + (y1 - y2)**2 + (z1 - z2)**2)
    mask = distance < 2
    logger.info(' %d reflections matched' % len(o2))
    logger.info(' %d reflections accepted' % mask.count(True))
    self.set_flags(sind.select(mask), self.flags.reference_spot)
    self.set_flags(sind.select(o2.get_flags(self.flags.strong)), self.flags.strong)
    self.set_flags(sind.select(o2.get_flags(self.flags.indexed)), self.flags.indexed)
    self.set_flags(sind.select(o2.get_flags(self.flags.used_in_refinement)), self.flags.used_in_refinement)
    other_matched_indices = oind.select(mask)
    other_unmatched_mask = flex.bool(len(other), True)
    other_unmatched_mask.set_selected(other_matched_indices, flex.bool(len(other_matched_indices), False))
    other_matched = other.select(other_matched_indices)
    other_unmatched = other.select(other_unmatched_mask)
    mask2 = flex.bool(len(self), False)
    mask2.set_selected(sind.select(mask), True)
    return mask2, other_matched, other_unmatched

  def match_with_reference(self, other):
    '''
    Match reflections with another set of reflections.

    :param other: The reflection table to match against
    :return: The matches

    '''
    from collections import defaultdict
    import __builtin__
    logger.info("Matching reference spots with predicted reflections")
    logger.info(' %d observed reflections input' % len(other))
    logger.info(' %d reflections predicted' % len(self))

    # Get the miller index, entering flag and turn number for
    # Both sets of reflections
    i1 = self['id']
    h1 = self['miller_index']
    e1 = self['entering'].as_int()
    x1, y1, z1 = self['xyzcal.px'].parts()
    p1 = self['panel']

    i2 = other['id']
    h2 = other['miller_index']
    e2 = other['entering'].as_int()
    x2, y2, z2 = other['xyzcal.px'].parts()
    p2 = other['panel']

    class Match(object):
      def __init__(self):
        self.a = []
        self.b = []

    # Create the match lookup
    lookup = defaultdict(Match)
    for i in range(len(self)):
      item = h1[i] + (e1[i], i1[i], p1[i])
      lookup[item].a.append(i)

    # Add matches from input reflections
    for i in range(len(other)):
      item = h2[i] + (e2[i], i2[i], p2[i])
      if item in lookup:
        lookup[item].b.append(i)

    # Create the list of matches
    match1 = []
    match2 = []
    for item, value in lookup.iteritems():
      if len(value.b) == 0:
        continue
      elif len(value.a) == 1 and len(value.b) == 1:
        match1.append(value.a[0])
        match2.append(value.b[0])
      else:
        matched = {}
        for i in value.a:
          d = []
          for j in value.b:
            dx = x1[i] - x2[j]
            dy = y1[i] - y2[j]
            dz = z1[i] - z2[j]
            d.append((i, j, dx**2 + dy**2 + dz**2))
          i, j, d = __builtin__.min(d, key=lambda x: x[2])
          if j not in matched:
            matched[j] = (i, d)
          elif d < matched[j][1]:
            matched[j] = (i, d)
        for key1, value1 in matched.iteritems():
          match1.append(value1[0])
          match2.append(key1)

    # Select everything which matches
    sind = flex.size_t(match1)
    oind = flex.size_t(match2)

    # Sort by self index
    sort_index = flex.size_t(__builtin__.sorted(range(len(sind)), key=lambda x: sind[x]))
    sind = sind.select(sort_index)
    oind = oind.select(sort_index)

    s2 = self.select(sind)
    o2 = other.select(oind)
    h1 = s2['miller_index']
    h2 = o2['miller_index']
    e1 = s2['entering']
    e2 = o2['entering']
    assert (h1 == h2).all_eq(True)
    assert (e1 == e2).all_eq(True)
    x1, y1, z1 = s2['xyzcal.px'].parts()
    x2, y2, z2 = o2['xyzcal.px'].parts()
    distance = flex.sqrt((x1 - x2)**2 + (y1 - y2)**2 + (z1 - z2)**2)
    mask = distance < 2
    logger.info(' %d reflections matched' % len(o2))
    logger.info(' %d reflections accepted' % mask.count(True))
    self.set_flags(sind.select(mask), self.flags.reference_spot)
    self.set_flags(sind.select(o2.get_flags(self.flags.strong)), self.flags.strong)
    self.set_flags(sind.select(o2.get_flags(self.flags.indexed)), self.flags.indexed)
    self.set_flags(sind.select(o2.get_flags(self.flags.used_in_refinement)), self.flags.used_in_refinement)
    other_matched_indices = oind.select(mask)
    other_unmatched_mask = flex.bool(len(other), True)
    other_unmatched_mask.set_selected(other_matched_indices, flex.bool(len(other_matched_indices), False))
    other_matched = other.select(other_matched_indices)
    other_unmatched = other.select(other_unmatched_mask)
    for key, column in self.select(sind.select(mask)).cols():
      other_matched[key] = column
    mask2 = flex.bool(len(self), False)
    mask2.set_selected(sind.select(mask), True)
    return mask2, other_matched, other_unmatched

  #def is_bbox_inside_image_range(self, experiment):
  #''' Check if bbox is within image range. '''
  #from dials.algorithms import filtering
  #assert(len(experiment.detector) == 1)
  #return filtering.is_bbox_outside_image_range(
  #self['bbox'],
  #experiment.detector[0].get_image_size()[::-1],
  #experiment.scan.get_array_range()) != True

  def compute_zeta(self, experiment):
    '''
    Compute zeta for each reflection.

    :param experiment: The experimental models
    :return: Zeta for each reflection

    '''
    from dials.algorithms.profile_model.gaussian_rs import zeta_factor
    m2 = experiment.goniometer.get_rotation_axis()
    s0 = experiment.beam.get_s0()
    self['zeta'] = zeta_factor(m2, s0, self['s1'])
    return self['zeta']

  def compute_zeta_multi(self, experiments):
    '''
    Compute zeta for each reflection.

    :param experiments: The list of experiments
    :return: Zeta for each reflection

    '''
    from dials.algorithms.profile_model.gaussian_rs import zeta_factor
    m2 = flex.vec3_double(len(experiments))
    s0 = flex.vec3_double(len(experiments))
    for i, e in enumerate(experiments):
      m2[i] = e.goniometer.get_rotation_axis()
      s0[i] = e.beam.get_s0()
    self['zeta'] = zeta_factor(m2, s0, self['s1'], self['id'])
    return self['zeta']

  def compute_d_single(self, experiment):
    '''
    Compute the resolution for each reflection.

    :param experiment: The experimental models
    :return: The resolution for each reflection

    '''
    from dials.array_family import flex
    uc = flex.unit_cell(1)
    uc[0] = experiment.crystal.get_unit_cell()
    self['d'] = uc.d(self['miller_index'], flex.size_t(len(self), 0))
    return self['d']

  def compute_d(self, experiments):
    '''
    Compute the resolution for each reflection.

    :param experiments: The experiment list
    :return: The resolution for each reflection

    '''
    from dials.array_family import flex
    uc = flex.unit_cell(len(experiments))
    for i, e in enumerate(experiments):
      uc[i] = e.crystal.get_unit_cell()
    assert self['id'].all_ge(0)
    self['d'] = uc.d(self['miller_index'], flex.size_t(list(self['id'])))
    return self['d']

  def compute_bbox(self, experiments, sigma_b_multiplier=2.0):
    '''
    Compute the bounding boxes.

    :param experiments: The list of experiments
    :param profile_model: The profile models
    :param sigma_b_multiplier: Multiplier to cover extra background
    :return: The bounding box for each reflection

    '''
    self['bbox'] = int6(len(self))
    for expr, indices in self.iterate_experiments_and_indices(experiments):
      self['bbox'].set_selected(indices,
                                expr.profile.compute_bbox(
                                    self.select(indices),
                                    expr.crystal,
                                    expr.beam,
                                    expr.detector,
                                    expr.goniometer,
                                    expr.scan,
                                    sigma_b_multiplier=sigma_b_multiplier))
    return self['bbox']

  def compute_partiality(self, experiments):
    '''
    Compute the reflection partiality.

    :param experiments: The experiment list
    :param profile_model: The profile models
    :return: The partiality for each reflection

    '''
    self['partiality'] = flex.double(len(self))
    for expr, indices in self.iterate_experiments_and_indices(experiments):
      self['partiality'].set_selected(indices,
                                      expr.profile.compute_partiality(
                                          self.select(indices), expr.crystal, expr.beam, expr.detector, expr.goniometer,
                                          expr.scan))
    return self['partiality']

  def compute_mask(self, experiments, image_volume=None, overlaps=None):
    '''
    Apply a mask to the shoeboxes.

    :param experiments: The list of experiments
    :param profile_model: The profile model

    '''
    for expr, indices in self.iterate_experiments_and_indices(experiments):
      result = expr.profile.compute_mask(
          self.select(indices),
          expr.crystal,
          expr.beam,
          expr.detector,
          expr.goniometer,
          expr.scan,
          image_volume=image_volume)
      if result is not None:
        if 'fraction' not in self:
          self['fraction'] = flex.double(len(self))
        self['fraction'].set_selected(indices, result)

  def iterate_experiments_and_indices(self, experiments):
    '''
    A helper function to interate through experiments and indices of reflections
    for each experiment

    '''
    assert (len(experiments) > 0)
    index_list = self.split_indices_by_experiment_id(len(experiments))
    assert (len(experiments) == len(index_list))
    tot = 0
    for l in index_list:
      tot += len(l)
    assert (tot == len(self))
    for experiment, indices in zip(experiments, index_list):
      yield experiment, indices

  def compute_background(self, experiments, image_volume=None):
    '''
    Helper function to compute the background.

    :param experiments: The list of experiments

    '''
    success = self._background_algorithm(experiments).compute_background(self, image_volume)
    self.set_flags(~success, self.flags.failed_during_background_modelling)

  def compute_centroid(self, experiments, image_volume=None):
    '''
    Helper function to compute the centroid.

    :param experiments: The list of experiments

    '''
    self._centroid_algorithm(experiments).compute_centroid(self, image_volume=image_volume)

  def compute_summed_intensity(self, image_volume=None):
    '''
    Compute intensity via summation integration.

    '''
    from dials.algorithms.integration.sum import IntegrationAlgorithm
    algorithm = IntegrationAlgorithm()
    success = algorithm(self, image_volume=image_volume)
    self.set_flags(~success, self.flags.failed_during_summation)

  def compute_fitted_intensity(self, fitter):
    '''
    Helper function to compute the intensity.

    :param experiments: The list of experiments
    :param profile_model: The profile model

    '''
    success = fitter.fit(self)
    self.set_flags(~success, self.flags.failed_during_profile_fitting)

  def compute_corrections(self, experiments):
    '''
    Helper function to correct the intensity.

    :param experiments: The list of experiments
    :return: The LP correction for each reflection

    '''
    from dials.algorithms.integration import Corrections, CorrectionsMulti
    compute = CorrectionsMulti()
    for experiment in experiments:
      compute.append(Corrections(experiment.beam, experiment.goniometer, experiment.detector))
    lp = compute.lp(self['id'], self['s1'])
    self['lp'] = lp
    if experiment.detector[0].get_mu() > 0:
      dqe = compute.dqe(self['id'], self['s1'], self['panel'])
      self['dqe'] = dqe
    return lp

  def integrate(self, experiments, profile_model, reference_selector=None):
    '''
    Helper function to integrate reflections.

    :param experiments: The list of experiments
    :param profile_model: The profile model
    :param reference_selector: The algorithm to choose reference spots

    '''
    self.compute_background(experiments)
    self.compute_centroid(experiments)
    self.compute_summed_intensity()
    if reference_selector is not None:
      reference_selector(self)
    self.compute_fitted_intensity(experiments, profile_model)

  def extract_shoeboxes(self, imageset, mask=None, nthreads=1, verbose=False):
    '''
    Helper function to read a load of shoebox data.

    :param imageset: The imageset
    :param mask: The mask to apply
    :param nthreads: The number of threads to use
    :param verbose: The verbosity
    :return: A tuple containing read time and extract time

    '''
    from dials.model.data import make_image
    from time import time
    assert ("shoebox" in self)
    detector = imageset.get_detector()
    try:
      frame0, frame1 = imageset.get_array_range()
    except Exception:
      frame0, frame1 = (0, len(imageset))
    extractor = ShoeboxExtractor(self, len(detector), frame0, frame1)
    logger.info(" Beginning to read images")
    read_time = 0
    extract_time = 0
    for i in range(len(imageset)):
      if verbose:
        logger.info('  reading image %d' % i)
      st = time()
      image = imageset.get_corrected_data(i)
      mask2 = imageset.get_mask(i)
      if mask is not None:
        assert (len(mask) == len(mask2))
        mask2 = tuple(m1 & m2 for m1, m2 in zip(mask, mask2))
      read_time += time() - st
      st = time()
      extractor.next(make_image(image, mask2))
      extract_time += time() - st
      del image
    assert (extractor.finished())
    logger.info('  successfully read %d images' % (frame1 - frame0))
    logger.info('  read time: %g seconds' % read_time)
    logger.info('  extract time: %g seconds' % extract_time)
    return read_time, extract_time

  def is_overloaded(self, experiments_or_datablock):
    '''
    Check if the shoebox contains overloaded pixels.

    :param experiments: The experiment list
    :return: True/False overloaded for each reflection

    '''
    from dxtbx.model.experiment_list import ExperimentList
    from dials.algorithms.shoebox import OverloadChecker
    assert ('shoebox' in self)
    assert ('id' in self)
    if isinstance(experiments_or_datablock, ExperimentList):
      detectors = [expr.detector for expr in experiments_or_datablock]
    else:
      imagesets = experiments_or_datablock.extract_imagesets()
      detectors = [iset.get_detector() for iset in imagesets]
    checker = OverloadChecker()
    for detector in detectors:
      checker.add(flex.double((p.get_trusted_range()[1] for p in detector)))
    result = checker(self['id'], self['shoebox'])
    self.set_flags(result, self.flags.overloaded)
    return result

  def contains_invalid_pixels(self):
    '''
    Check if the shoebox contains invalid pixels.

    :return: True/False invalid for each reflection

    '''
    from dials.algorithms.shoebox import MaskCode
    assert 'shoebox' in self
    x0, x1, y0, y1, z0, z1 = self['bbox'].parts()
    ntotal = (x1 - x0) * (y1 - y0) * (z1 - z0)
    assert ntotal.all_gt(0)
    sbox = self['shoebox']
    nvalid = sbox.count_mask_values(MaskCode.Valid)
    nbackg = sbox.count_mask_values(MaskCode.Background)
    nforeg = sbox.count_mask_values(MaskCode.Foreground)
    nvalbg = sbox.count_mask_values(MaskCode.Background | MaskCode.Valid)
    nvalfg = sbox.count_mask_values(MaskCode.Foreground | MaskCode.Valid)
    ninvbg = nbackg - nvalbg
    ninvfg = nforeg - nvalfg
    assert ninvbg.all_ge(0)
    assert ninvfg.all_ge(0)
    self.set_flags(ninvbg > 0, self.flags.background_includes_bad_pixels)
    self.set_flags(ninvfg > 0, self.flags.foreground_includes_bad_pixels)
    return (ntotal - nvalid) > 0

  def find_overlaps(self, experiments=None, border=0):
    '''
    Check for overlapping reflections.

    :param experiments: The experiment list
    :param tolerance: A positive integer specifying border around shoebox
    :return: The overlap list

    '''
    from dials.algorithms.shoebox import OverlapFinder
    from itertools import groupby

    # Expand the bbox if necessary
    if border > 0:
      x0, x1, y0, y1, z0, z1 = self['bbox'].parts()
      x0 -= border
      x1 += border
      y0 -= border
      y1 += border
      z0 -= border
      z1 += border
      bbox = int6(x0, x1, y0, y1, z0, z1)
    else:
      bbox = self['bbox']

    # Get the panel and id
    panel = self['panel']
    exp_id = self['id']

    # Group according to imageset
    if experiments is not None:
      groups = groupby(range(len(experiments)), lambda x: experiments[x].imageset)

      # Get the experiment ids we're to treat together
      lookup = {}
      for j, (key, indices) in enumerate(groups):
        for i in indices:
          lookup[i] = j
      group_id = flex.size_t([lookup[i] for i in self['id']])
    elif "imageset_id" in self:
      imageset_id = self['imageset_id']
      assert imageset_id.all_ge(0)
      group_id = flex.size_t(list(imageset_id))
    else:
      raise RuntimeError('Either need to supply experiments or have imageset_id')

    # Create the overlap finder
    find_overlapping = OverlapFinder()

    # Find the overlaps
    overlaps = find_overlapping(group_id, panel, bbox)
    assert (overlaps.num_vertices() == len(self))

    # Return the overlaps
    return overlaps

  def compute_shoebox_overlap_fraction(self, overlaps):
    '''
    Compute the fraction of shoebox overlapping.

    :param overlaps: The list of overlaps
    :return: The fraction of shoebox overlapped with other reflections

    '''
    from dials.array_family import flex
    result = flex.double(len(self))
    bbox = self['bbox']
    for i in range(len(self)):
      b1 = bbox[i]
      xs = b1[1] - b1[0]
      ys = b1[3] - b1[2]
      zs = b1[5] - b1[4]
      assert (xs > 0)
      assert (ys > 0)
      assert (zs > 0)
      mask = flex.bool(flex.grid(zs, ys, xs), False)
      for edge in overlaps.adjacent_vertices(i):
        b2 = bbox[edge]
        x0 = b2[0] - b1[0]
        x1 = b2[1] - b1[0]
        y0 = b2[2] - b1[2]
        y1 = b2[3] - b1[2]
        z0 = b2[4] - b1[4]
        z1 = b2[5] - b1[4]
        if x0 < 0: x0 = 0
        if y0 < 0: y0 = 0
        if z0 < 0: z0 = 0
        if x1 > xs: x1 = xs
        if y1 > ys: y1 = ys
        if z1 > zs: z1 = zs
        assert (x1 > x0)
        assert (y1 > y0)
        assert (z1 > z0)
        m2 = flex.bool(flex.grid(z1 - z0, y1 - y0, x1 - x0), True)
        mask[z0:z1, y0:y1, x0:x1] = m2
      result[i] = (1.0 * mask.count(True)) / mask.size()
    return result

class reflection_table_selector(object):
  '''
  A class to select columns from reflection table.

  This is mainly useful for specifying selections from phil parameters

  '''

  def __init__(self, column, op, value):
    '''
    Initialise the selector

    :param col: The column name
    :param op: The operator
    :param value: The value

    '''
    import operator

    # Set the column and value
    self.column = column
    self.value = value

    # Set the operator
    if isinstance(op, str):
      if op == '<':
        self.op = operator.lt
      elif op == '<=':
        self.op = operator.le
      elif op == '==':
        self.op = operator.eq
      elif op == '!=':
        self.op = operator.ne
      elif op == '>=':
        self.op = operator.ge
      elif op == '>':
        self.op = operator.gt
      elif op == '&':
        self.op = operator.and_
      else:
        raise RuntimeError('Unknown operator')
    else:
      self.op = op

  @property
  def op_string(self):
    '''
    Return the operator as a string

    '''
    import operator
    if self.op == operator.lt:
      string = '<'
    elif self.op == operator.le:
      string = '<='
    elif self.op == operator.eq:
      string = '=='
    elif self.op == operator.ne:
      string = '!='
    elif self.op == operator.ge:
      string = '>='
    elif self.op == operator.gt:
      string = '>'
    elif self.op == operator.and_:
      string = '&'
    else:
      raise RuntimeError('Unknown operator')
    return string

  def __call__(self, reflections):
    '''
    Select the reflections

    :param reflections: The reflections

    :return: The selection as a mask

    '''
    import __builtin__
    if self.column == 'intensity.sum.i_over_sigma':
      I = reflections['intensity.sum.value']
      V = reflections['intensity.sum.variance']
      mask1 = V > 0
      I = I.select(mask1)
      V = V.select(mask1)
      data = I / flex.sqrt(V)
    elif self.column == 'intensity.prf.i_over_sigma':
      I = reflections['intensity.prf.value']
      V = reflections['intensity.prf.variance']
      mask1 = V > 0
      I = I.select(mask1)
      V = V.select(mask1)
      data = I / flex.sqrt(V)
    else:
      mask1 = None
      data = reflections[self.column]
    if isinstance(data, double):
      value = __builtin__.float(self.value)
    elif isinstance(data, int):
      value = __builtin__.int(self.value)
    elif isinstance(data, size_t):
      value = __builtin__.int(self.value)
    elif isinstance(data, std_string):
      value = self.value
    elif isinstance(data, vec3_double):
      raise RuntimeError("Comparison not implemented")
    elif isinstance(data, vec2_double):
      raise RuntimeError("Comparison not implemented")
    elif isinstance(data, mat3_double):
      raise RuntimeError("Comparison not implemented")
    elif isinstance(data, int6):
      raise RuntimeError("Comparison not implemented")
    elif isinstance(data, shoebox):
      raise RuntimeError("Comparison not implemented")
    else:
      raise RuntimeError('Unknown column type')
    mask2 = self.op(data, self.value)
    if mask1 is not None:
      mask1.set_selected(size_t(range(len(mask1))).select(mask1), mask2)
    else:
      mask1 = mask2
    return mask1
