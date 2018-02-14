#!/usr/bin/env python
#
# export_mmcif.py
#
#  Copyright (C) 2017 Diamond Light Source
#
#  Author: James Parkhurst
#
#  This code is distributed under the BSD license, a copy of which is
#  included in the root directory of this package.
from __future__ import absolute_import, division
import logging
logger = logging.getLogger(__name__)
from math import pi
from cctbx.sgtbx import bravais_types

RAD2DEG = 180.0 / pi

class MMCIFOutputFile(object):
  '''
  Class to output experiments and reflections as MMCIF file

  '''

  def __init__(self, filename):
    '''
    Init with the filename

    '''
    import iotbx.cif.model
    self._cif = iotbx.cif.model.cif()
    self.filename = filename

  def write(self, experiments, reflections):
    '''
    Write the experiments and reflections to file

    '''
    import iotbx.cif.model

    # Select reflections
    selection = reflections.get_flags(reflections.flags.integrated, all=True)
    reflections = reflections.select(selection)

    # Get the cif block
    cif_block = iotbx.cif.model.block()

    # Hard coding X-ray
    cif_block["_pdbx_diffrn_data_section.id"] = 'dials'
    cif_block["_pdbx_diffrn_data_section.type_scattering"] = "x-ray"
    cif_block["_pdbx_diffrn_data_section.type_merged"] = "false"
    cif_block["_pdbx_diffrn_data_section.type_scaled"] = "false"

    # FIXME Haven't put in any of these bits yet
    #
    #  Facility/beamline proposal tracking details
    #
    # cif_block["_pdbx_diffrn_data_section_experiment.ordinal"] = 1
    # cif_block["_pdbx_diffrn_data_section_experiment.data_section_id"] = "dials"
    # cif_block["_pdbx_diffrn_data_section_experiment.proposal_id"] = "<PROPOSAL ID>

    # Facility/beamline details for this data collection
    #
    # cif_block["_pdbx_diffrn_data_section_site.data_section_id"] = 'dials'
    # cif_block["_pdbx_diffrn_data_section_site.facility"] = "DIAMOND"
    # cif_block["_pdbx_diffrn_data_section_site.beamline"] = "VMX-M"
    # cif_block["_pdbx_diffrn_data_section_site.collection_date"] = scan.epochs()[0]
    # cif_block["_pdbx_diffrn_data_section_site.detector"] = detector[0].name()
    # cif_block["_pdbx_diffrn_data_section_site.detector_type"] = detector[0].type()

    # Write the crystal information
    cif_loop = iotbx.cif.model.loop(
        header=("_pdbx_diffrn_unmerged_cell.ordinal", "_pdbx_diffrn_unmerged_cell.crystal_id",
                "_pdbx_diffrn_unmerged_cell.wavelength", "_pdbx_diffrn_unmerged_cell.cell_length_a",
                "_pdbx_diffrn_unmerged_cell.cell_length_b", "_pdbx_diffrn_unmerged_cell.cell_length_c",
                "_pdbx_diffrn_unmerged_cell.cell_angle_alpha", "_pdbx_diffrn_unmerged_cell.cell_angle_beta",
                "_pdbx_diffrn_unmerged_cell.cell_angle_gamma", "_pdbx_diffrn_unmerged_cell.Bravais_lattice"))
    crystals = experiments.crystals()
    crystal_to_id = {crystal: i + 1 for i, crystal in enumerate(crystals)}
    for i, exp in enumerate(experiments):
      crystal = exp.crystal
      crystal_id = crystal_to_id[crystal]
      wavelength = exp.beam.get_wavelength()
      a, b, c, alpha, beta, gamma = crystal.get_unit_cell().parameters()
      latt_type = str(bravais_types.bravais_lattice(group=crystal.get_space_group()))
      cif_loop.add_row((i + 1, crystal_id, wavelength, a, b, c, alpha, beta, gamma, latt_type))
      cif_block.add_loop(cif_loop)

    # Write the scan information
    cif_loop = iotbx.cif.model.loop(
        header=("_pdbx_diffrn_scan.scan_id", "_pdbx_diffrn_scan.crystal_id", "_pdbx_diffrn_scan.image_id_begin",
                "_pdbx_diffrn_scan.image_id_end", "_pdbx_diffrn_scan.scan_angle_begin",
                "_pdbx_diffrn_scan.scan_angle_end"))
    for i, exp in enumerate(experiments):
      scan = exp.scan
      crystal_id = crystal_to_id[exp.crystal]
      image_range = scan.get_image_range()
      osc_range = scan.get_oscillation_range(deg=True)
      cif_loop.add_row((i + 1, crystal_id, image_range[0], image_range[1], osc_range[0], osc_range[1]))
      cif_block.add_loop(cif_loop)

    # Make a dict of unit_cell parameters
    unit_cell_parameters = {}
    if crystal.num_scan_points > 1:
      for i in range(crystal.num_scan_points):
        a, b, c, alpha, beta, gamma = crystal.get_unit_cell_at_scan_point(i).parameters()
        unit_cell_parameters[i] = (a, b, c, alpha, beta, gamma)
    else:
      unit_cell_parameters[0] = (a, b, c, alpha, beta, gamma)

    ### _pdbx_diffrn_image_proc has been removed from the dictionary extension.
    ### Keeping this section commented out as it may be added back in some
    ### form in future
    #
    # Write the image data
    #scan = experiments[0].scan
    #z0 = scan.get_image_range()[0]
    #
    #cif_loop = iotbx.cif.model.loop(
    #  header=("_pdbx_diffrn_image_proc.image_id",
    #          "_pdbx_diffrn_image_proc.crystal_id",
    #          "_pdbx_diffrn_image_proc.image_number",
    #          "_pdbx_diffrn_image_proc.phi_value",
    #          "_pdbx_diffrn_image_proc.wavelength",
    #          "_pdbx_diffrn_image_proc.cell_length_a",
    #          "_pdbx_diffrn_image_proc.cell_length_b",
    #          "_pdbx_diffrn_image_proc.cell_length_c",
    #          "_pdbx_diffrn_image_proc.cell_angle_alpha",
    #          "_pdbx_diffrn_image_proc.cell_angle_beta",
    #          "_pdbx_diffrn_image_proc.cell_angle_gamma"))
    #for i in range(len(scan)):
    #  z = z0 + i
    #  if crystal.num_scan_points > 1:
    #    a, b, c, alpha, beta, gamma = unit_cell_parameters[i]
    #  else:
    #    a, b, c, alpha, beta, gamma = unit_cell_parameters[0]
    #  # phi is the angle at the image centre
    #  phi = scan.get_angle_from_image_index(z + 0.5, deg=True)
    #  cif_loop.add_row((i+1, 1, z, phi, wavelength,
    #                    a, b, c, alpha, beta, gamma))
    #cif_block.add_loop(cif_loop)

    # Write reflection data
    # FIXME there are three intensity fields. I've put summation in I and Isum
    cif_loop = iotbx.cif.model.loop(
        header=("_pdbx_diffrn_unmerged_refln.reflection_id", "_pdbx_diffrn_unmerged_refln.scan_id",
                "_pdbx_diffrn_unmerged_refln.image_id_begin", "_pdbx_diffrn_unmerged_refln.image_id_end",
                "_pdbx_diffrn_unmerged_refln.index_h", "_pdbx_diffrn_unmerged_refln.index_k",
                "_pdbx_diffrn_unmerged_refln.index_l", "_pdbx_diffrn_unmerged_refln.intensity_meas",
                "_pdbx_diffrn_unmerged_refln.intensity_sigma", "_pdbx_diffrn_unmerged_refln.intensity_sum",
                "_pdbx_diffrn_unmerged_refln.intensity_sum_sigma", "_pdbx_diffrn_unmerged_refln.intensity_profile",
                "_pdbx_diffrn_unmerged_refln.intensity_profile_sigma",
                "_pdbx_diffrn_unmerged_refln.scan_angle_reflection", "_pdbx_diffrn_unmerged_refln.partiality",
                "_pdbx_diffrn_unmerged_refln.scale_value"))
    for i, r in enumerate(reflections):
      refl_id = i + 1
      scan_id = r['id'] + 1
      _, _, _, _, z0, z1 = r['bbox']
      h, k, l = r['miller_index']
      I = r['intensity.sum.value']
      sigI = r['intensity.sum.variance']
      Isum = r['intensity.sum.value']
      sigIsum = r['intensity.sum.variance']
      Iprf = r['intensity.prf.value']
      sigIprf = r['intensity.prf.variance']
      phi = r['xyzcal.mm'][2] * RAD2DEG
      partiality = r['partiality']
      scale = 1.0
      cif_loop.add_row((refl_id, scan_id, z0, z1, h, k, l, I, sigI, Isum, sigIsum, Iprf, sigIprf, phi, partiality,
                        scale))
    cif_block.add_loop(cif_loop)

    # Add the block
    self._cif['dials'] = cif_block

    # Print to file
    print >> open(self.filename, "w"), self._cif

    # Log
    logger.info("Wrote reflections to %s" % self.filename)
