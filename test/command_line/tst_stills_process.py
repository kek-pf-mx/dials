from __future__ import absolute_import, division
from dials.array_family import flex # import dependency

class Test(object):
  def __init__(self):
    from os.path import join
    import libtbx.load_env
    try:
      dials_regression = libtbx.env.dist_path('dials_regression')
    except KeyError:
      print 'SKIP: dials_regression not configured'
      exit(0)

    self.lcls_path = join(dials_regression, "image_examples/LCLS_cspad_nexus")
    self.sacla_path = join(dials_regression, "image_examples/SACLA_MPCCD_Cheetah")

  def run(self):
    self.test_cspad_cbf_in_memory()
    self.test_sacla_h5()
    try:
      import mpi4py # Check if mpi4py exists
    except ImportError:
      pass
    else:
      self.test_sacla_h5(use_mpi=True)

  def test_cspad_cbf_in_memory(self):
    from os.path import join, exists
    import os, dxtbx
    from uuid import uuid4
    from dials.command_line.stills_process import phil_scope, Processor
    from libtbx.phil import parse
    from dxtbx.imageset import ImageSet, ImageSetData, MemReader, MemMasker
    from dxtbx.datablock import DataBlockFactory
    from dxtbx.format.FormatCBFCspad import FormatCBFCspadInMemory
    import cPickle as pickle

    dirname = 'tmp_%s' % uuid4().hex
    os.mkdir(dirname)
    os.chdir(dirname)

    assert exists(join(self.lcls_path, 'idx-20130301060858801.cbf'))

    f = open("process_lcls.phil", 'w')
    f.write("""
      dispatch.squash_errors = False
      spotfinder {
        filter.min_spot_size=2
        threshold.dispersion.gain=25
        threshold.dispersion.global_threshold=100
      }
      indexing {
        known_symmetry {
          space_group = P6122
          unit_cell = 92.9 92.9 130.4 90 90 120
        }
        refinement_protocol.d_min_start=1.7
        stills.refine_candidates_with_known_symmetry=True
      }
      """)
    f.close()
    params = phil_scope.fetch(parse(file_name="process_lcls.phil")).extract()
    params.output.datablock_filename = None
    processor = Processor(params)
    mem_img = dxtbx.load(join(self.lcls_path, 'idx-20130301060858801.cbf'))
    raw_data = mem_img.get_raw_data() # cache the raw data to prevent swig errors
    mem_img = FormatCBFCspadInMemory(mem_img._cbf_handle)
    mem_img._raw_data = raw_data
    mem_img._cbf_handle = None # drop the file handle to prevent swig errors
    imgset = ImageSet(ImageSetData(MemReader([mem_img]), MemMasker([mem_img])))
    imgset.set_beam(mem_img.get_beam())
    imgset.set_detector(mem_img.get_detector())
    datablock = DataBlockFactory.from_imageset(imgset)[0]
    processor.process_datablock("20130301060858801", datablock) # index/integrate the image
    result = "idx-20130301060858801_integrated.pickle"
    #n_refls = range(140,152) # large ranges to handle platform-specific differences
    # 09/20/17 Changes to still indexer: refine candidate basis vectors in target symmetry if supplied
    #n_refls = range(128,140) # large ranges to handle platform-specific differences
    # 09/27/17 Bugfix for refine_candidates_with_known_symmetry
    n_refls = range(140, 152) # large ranges to handle platform-specific differences
    table = pickle.load(open(result, 'rb'))
    assert len(table) in n_refls, len(table)
    assert 'id' in table
    assert (table['id'] == 0).count(False) == 0

    print 'OK'

  def test_sacla_h5(self, in_memory=False, use_mpi=False):
    from os.path import join, exists
    from libtbx import easy_run
    import os
    from uuid import uuid4

    dirname = 'tmp_%s' % uuid4().hex
    os.mkdir(dirname)
    os.chdir(dirname)

    assert exists(join(self.sacla_path, 'run266702-0-subset.h5'))

    geometry_path = join(self.sacla_path, 'refined_experiments_level1.json')
    assert exists(geometry_path)

    f = open("process_sacla.phil", 'w')
    f.write("""
      dispatch.squash_errors = True
      input.reference_geometry=%s
      indexing {
        known_symmetry {
          space_group = P43212
          unit_cell = 78.9 78.9 38.1 90 90 90
        }
        refinement_protocol.d_min_start = 2.2
        stills.refine_candidates_with_known_symmetry=True
      }
      spotfinder {
        filter.min_spot_size = 2
        threshold {
          dispersion {
            gain = 5.46 # from dials.estimate_gain run266702-0-subset.h5 max_images=4
            global_threshold = 50
          }
        }
      }
      refinement {
        parameterisation {
          detector.fix_list = Dist,Tau1
        }
      }
      """ % geometry_path)
    f.close()

    # Call dials.stills_process
    if use_mpi:
      command = ['mpirun', '-n', '4', 'dials.stills_process']
    else:
      command = ['dials.stills_process']
    command += [join(self.sacla_path, 'run266702-0-subset.h5'), 'process_sacla.phil']
    result = easy_run.fully_buffered(command).raise_if_errors()
    result.show_stdout()

    import cPickle as pickle
    # Frame 1 no longer indexing after cctbx r25607 which made wavelengths be on a per-image basis
    #for result, n_refls in zip(["idx-run266702-0-subset_00000_integrated.pickle",
    #                            "idx-run266702-0-subset_00001_integrated.pickle"],
    #                            [range(109,114), range(80,85)]): # large ranges to handle platform-specific differences
    #for result, n_refls in zip(["idx-run266702-0-subset_00000_integrated.pickle"],
    #                            [range(109,114)]): # large ranges to handle platform-specific differences
    # dxtbx r25668 and 25669 flip X axis in the SACLA format class and changed indexing results.
    #for result, n_refls in zip(["idx-run266702-0-subset_00001_integrated.pickle"],
    #                            [range(90,96)]): # large ranges to handle platform-specific differences
    # 02/12/17 Handle change to stills_process refining after indexing plus new spotfinding params
    #for result, n_refls in zip(["idx-run266702-0-subset_00000_integrated.pickle",
    #                            "idx-run266702-0-subset_00001_integrated.pickle",
    #                            "idx-run266702-0-subset_00003_integrated.pickle"],
    #                            [range(75,90),range(220,230),range(285,295)]): # large ranges to handle platform-specific differences
    # 02/14/17 Further changes to stills_process: resetting rejected reflections before re-refinement
    #for result, n_refls in zip(["idx-run266702-0-subset_00000_integrated.pickle",
    #                            "idx-run266702-0-subset_00001_integrated.pickle",
    #                            "idx-run266702-0-subset_00003_integrated.pickle"],
    #                            [range(80,95),range(225,235),range(235,245)]): # large ranges to handle platform-specific differences
    # 02/21/17 Changes to stills_process: refine during indexing instead of after. Also used refined metrology from Rahel
    #for result, n_refls in zip(["idx-run266702-0-subset_00001_integrated.pickle",
    #                            "idx-run266702-0-subset_00003_integrated.pickle"],
    #                            [range(600,610),range(505,520)]): # large ranges to handle platform-specific differences
    # 04/25/17 Changes after reverting sign_error_27Feb2014_through_15Feb2017 in xfel/mono_simulation/max_like.py
    #for result, n_refls in zip(["idx-run266702-0-subset_00001_integrated.pickle",
    #                            "idx-run266702-0-subset_00003_integrated.pickle"],
    #                            [range(565,580),range(495,510)]): # large ranges to handle platform-specific differences
    # 09/20/17 Changes to still indexer: refine candidate basis vectors in target symmetry if supplied
    #for result, n_refls in zip(["idx-run266702-0-subset_00001_integrated.pickle",
    #                            "idx-run266702-0-subset_00003_integrated.pickle"],
    #                            [range(100,115),range(155,165)]): # large ranges to handle platform-specific differences
    # 09/27/17 Bugfix for refine_candidates_with_known_symmetry
    for result, n_refls in zip([
        "idx-run266702-0-subset_00000_integrated.pickle", "idx-run266702-0-subset_00001_integrated.pickle",
        "idx-run266702-0-subset_00003_integrated.pickle"
    ], [range(212, 225), range(565, 580), range(475, 500)]): # large ranges to handle platform-specific differences
      table = pickle.load(open(result, 'rb'))
      assert len(table) in n_refls, (result, len(table))
      assert 'id' in table
      assert (table['id'] == 0).count(False) == 0
    print 'OK'

if __name__ == '__main__':
  from dials.test import cd_auto
  with cd_auto(__file__):
    test = Test()
    test.run()
