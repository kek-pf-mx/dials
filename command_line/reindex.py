#!/usr/bin/env python
# -*- mode: python; coding: utf-8; indent-tabs-mode: nil; python-indent: 2 -*-
#
# dials.command_line.reindex.py
#
#  Copyright (C) 2014 Diamond Light Source
#
#  Author: Richard Gildea
#
#  This code is distributed under the BSD license, a copy of which is
#  included in the root directory of this package.

from __future__ import absolute_import, division
from __future__ import print_function
# DIALS_ENABLE_COMMAND_LINE_COMPLETION

import copy
from libtbx.phil import command_line
from libtbx import easy_pickle
import iotbx.phil
from cctbx import sgtbx
from dxtbx.model import Crystal
from dxtbx.serialize import dump
# from dials.util.command_line import Importer
from dials.array_family import flex
from dials.util.options import OptionParser
from dials.util.options import flatten_reflections, flatten_experiments

help_message = '''

This program can be used to re-index an experiments.json and/or indexed.pickle
file from one setting to another. The change of basis operator can be
provided in h,k,l, or a,b,c or x,y,z conventions. By default the change of
basis operator will also be applied to the space group in the experiments.json
file, however, optionally, a space group (including setting) to be applied
AFTER applying the change of basis operator can be provided.

Examples::

  dials.reindex experiments.json change_of_basis_op=b+c,a+c,a+b

  dials.reindex indexed.pickle change_of_basis_op=-b,a+b+2*c,-a

  dials.reindex experiments.json index.pickle change_of_basis_op=l,h,k

'''

phil_scope = iotbx.phil.parse("""
change_of_basis_op = a,b,c
  .type = str
hkl_offset = None
  .type = ints(size=3)
space_group = None
  .type = space_group
  .help = "The space group to be applied AFTER applying the change of basis "
           "operator."
reference = None
  .type = path
  .help = "Reference experiment for determination of change of basis operator."
output {
  experiments = reindexed_experiments.json
    .type = str
    .help = "The filename for reindexed experimental models"

  reflections = reindexed_reflections.pickle
    .type = str
    .help = "The filename for reindexed reflections"
}
""", process_includes=True)


def derive_change_of_basis_op(from_hkl, to_hkl):

  # exclude those reflections that we couldn't index
  sel = (to_hkl != (0,0,0)) & (from_hkl != (0,0,0))
  assert sel.count(True) >= 3 # need minimum of 3 equations ?
  to_hkl = to_hkl.select(sel)
  from_hkl = from_hkl.select(sel)

  # for each miller index, solve a system of linear equations to find the
  # change of basis operator
  h, k, l = to_hkl.as_vec3_double().parts()

  r = []
  from scitbx.lstbx import normal_eqns
  for i in range(3):
    eqns = normal_eqns.linear_ls(3)
    for index, hkl in zip((h,k,l)[i], from_hkl):
      eqns.add_equation(right_hand_side=index,
                        design_matrix_row=flex.double(hkl),
                        weight=1)
    eqns.solve()
    r.extend(eqns.solution())

  from scitbx.math import continued_fraction
  from scitbx import matrix
  denom = 12
  r = [int(denom * continued_fraction.from_real(r_, eps=1e-2).as_rational())
       for r_ in r]
  r = matrix.sqr(r).transpose()
  #print (1/denom)*r

  # now convert into a cctbx change_of_basis_op object
  change_of_basis_op = sgtbx.change_of_basis_op(
    sgtbx.rt_mx(sgtbx.rot_mx(r, denominator=denom))).inverse()
  print("discovered change_of_basis_op=%s" %(str(change_of_basis_op)))

  # sanity check that this is the right cb_op
  assert (change_of_basis_op.apply(from_hkl) == to_hkl).count(False) == 0

  return change_of_basis_op


def run(args):
  import libtbx.load_env
  from libtbx.utils import Sorry
  usage = "%s [options] experiments.json indexed.pickle" %libtbx.env.dispatcher_name

  parser = OptionParser(
    usage=usage,
    phil=phil_scope,
    read_reflections=True,
    read_experiments=True,
    check_format=False,
    epilog=help_message)

  params, options = parser.parse_args(show_diff_phil=True)

  reflections = flatten_reflections(params.input.reflections)
  experiments = flatten_experiments(params.input.experiments)
  if len(experiments) == 0 and len(reflections) == 0:
    parser.print_help()
    return
  if params.change_of_basis_op is None:
    raise Sorry("Please provide a change_of_basis_op.")

  reference_crystal = None
  if params.reference is not None:
    from dxtbx.serialize import load
    reference_experiments = load.experiment_list(
      params.reference, check_format=False)
    assert len(reference_experiments.crystals()) == 1
    reference_crystal = reference_experiments.crystals()[0]

  if len(experiments) and params.change_of_basis_op is libtbx.Auto:
    if reference_crystal is not None:
      if len(experiments.crystals()) > 1:
        raise Sorry("Only one crystal can be processed at a time")
      from dials.algorithms.indexing.compare_orientation_matrices \
           import difference_rotation_matrix_axis_angle

      cryst = experiments.crystals()[0]
      R, axis, angle, change_of_basis_op = difference_rotation_matrix_axis_angle(
        cryst, reference_crystal)
      print("Change of basis op: %s" %change_of_basis_op)
      print("Rotation matrix to transform input crystal to reference::")
      print(R.mathematica_form(format="%.3f", one_row_per_line=True))
      print("Rotation of %.3f degrees" %angle, "about axis (%.3f, %.3f, %.3f)" %axis)

    elif len(reflections):
      assert len(reflections) == 1

      # always re-map reflections to reciprocal space
      from dials.algorithms.indexing import indexer
      refl_copy = flex.reflection_table()
      for i, imageset in enumerate(experiments.imagesets()):
        if 'imageset_id' in reflections[0]:
          sel = (reflections[0]['imageset_id'] == i)
        else:
          sel = (reflections[0]['id'] == i)
        refl = indexer.indexer_base.map_spots_pixel_to_mm_rad(
          reflections[0].select(sel),
          imageset.get_detector(), imageset.get_scan())

        indexer.indexer_base.map_centroids_to_reciprocal_space(
          refl, imageset.get_detector(), imageset.get_beam(),
          imageset.get_goniometer())
        refl_copy.extend(refl)

      # index the reflection list using the input experiments list
      refl_copy['id'] = flex.int(len(refl_copy), -1)
      from dials.algorithms.indexing import index_reflections
      index_reflections(refl_copy, experiments, tolerance=0.2)
      hkl_expt = refl_copy['miller_index']
      hkl_input = reflections[0]['miller_index']

      change_of_basis_op = derive_change_of_basis_op(hkl_input, hkl_expt)

      # reset experiments list since we don't want to reindex this
      experiments = []

  else:
    change_of_basis_op = sgtbx.change_of_basis_op(params.change_of_basis_op)

  if len(experiments):
    for crystal in experiments.crystals():
      cryst_orig = copy.deepcopy(crystal)
      cryst_reindexed = cryst_orig.change_basis(change_of_basis_op)
      if params.space_group is not None:
        a, b, c = cryst_reindexed.get_real_space_vectors()
        cryst_reindexed = Crystal(
          a, b, c, space_group=params.space_group.group())
      crystal.update(cryst_reindexed)

      print("Old crystal:")
      print(cryst_orig)
      print()
      print("New crystal:")
      print(cryst_reindexed)
      print()

    print("Saving reindexed experimental models to %s" %params.output.experiments)
    dump.experiment_list(experiments, params.output.experiments)

  if len(reflections):
    assert(len(reflections) == 1)
    reflections = reflections[0]

    miller_indices = reflections['miller_index']

    if params.hkl_offset is not None:
      h,k,l = miller_indices.as_vec3_double().parts()
      h += params.hkl_offset[0]
      k += params.hkl_offset[1]
      l += params.hkl_offset[2]
      miller_indices = flex.miller_index(h.iround(), k.iround(), l.iround())
    non_integral_indices = change_of_basis_op.apply_results_in_non_integral_indices(miller_indices)
    if non_integral_indices.size() > 0:
      print("Removing %i/%i reflections (change of basis results in non-integral indices)" %(
      non_integral_indices.size(), miller_indices.size()))
    sel = flex.bool(miller_indices.size(), True)
    sel.set_selected(non_integral_indices, False)
    miller_indices_reindexed = change_of_basis_op.apply(
      miller_indices.select(sel))
    reflections['miller_index'].set_selected(sel, miller_indices_reindexed)
    reflections['miller_index'].set_selected(~sel, (0,0,0))

    print("Saving reindexed reflections to %s" %params.output.reflections)
    easy_pickle.dump(params.output.reflections, reflections)


if __name__ == '__main__':
  import sys
  run(sys.argv[1:])
