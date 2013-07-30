/*
 * pickle.h
 *
 *  Copyright (C) 2013 Diamond Light Source
 *
 *  Author: James Parkhurst
 *
 *  This code is distributed under the BSD license, a copy of which is
 *  included in the root directory of this package.
 */
#ifndef DIALS_MODEL_DATA_BOOST_PYTHON_PICKLE_H
#define DIALS_MODEL_DATA_BOOST_PYTHON_PICKLE_H

#include <boost/python.hpp>
#include <boost/python/def.hpp>
#include <scitbx/vec2.h>
#include <scitbx/vec3.h>
#include <scitbx/array_family/tiny_types.h>
#include <cctbx/miller.h>
#include <scitbx/array_family/boost_python/ref_pickle_double_buffered.h>
#include <dials/error.h>

namespace dials { namespace model { namespace boost_python {
    namespace reflection {

  using namespace boost::python;
  using scitbx::af::flex_grid;

  struct to_string : scitbx::af::boost_python::pickle_double_buffered::to_string
  {
    using scitbx::af::boost_python::pickle_double_buffered::to_string::operator<<;

    to_string() {
      unsigned int version = 1;
      *this << version;
    }

    template <typename ProfileType>
    void profile_to_string(const ProfileType &p) {
      *this << p.accessor().all().size();
      for (std::size_t i = 0; i < p.accessor().all().size(); ++i) {
        *this << p.accessor().all()[i];
      }
      for (std::size_t i = 0; i < p.size(); ++i) {
        *this << p[i];
      }
    }

    to_string& operator<<(const Reflection &val) {
      *this << val.get_miller_index()[0]
            << val.get_miller_index()[1]
            << val.get_miller_index()[2]
            << val.get_status()
            << val.get_entering()
            << val.get_rotation_angle()
            << val.get_beam_vector()[0]
            << val.get_beam_vector()[1]
            << val.get_beam_vector()[2]
            << val.get_image_coord_px()[0]
            << val.get_image_coord_px()[1]
            << val.get_image_coord_mm()[0]
            << val.get_image_coord_mm()[1]
            << val.get_frame_number()
            << val.get_panel_number()
            << val.get_bounding_box()[0]
            << val.get_bounding_box()[1]
            << val.get_bounding_box()[2]
            << val.get_bounding_box()[3]
            << val.get_bounding_box()[4]
            << val.get_bounding_box()[5]
            << val.get_centroid_position()[0]
            << val.get_centroid_position()[1]
            << val.get_centroid_position()[2]
            << val.get_centroid_variance()[0]
            << val.get_centroid_variance()[1]
            << val.get_centroid_variance()[2]
            << val.get_centroid_sq_width()[0]
            << val.get_centroid_sq_width()[1]
            << val.get_centroid_sq_width()[2]
            << val.get_intensity()
            << val.get_intensity_variance()
            << val.get_corrected_intensity()
            << val.get_corrected_intensity_variance();

      profile_to_string(val.get_shoebox());
      profile_to_string(val.get_shoebox_mask());
      profile_to_string(val.get_shoebox_background());
      profile_to_string(val.get_transformed_shoebox());

      return *this;
    }
  };

  struct from_string : scitbx::af::boost_python::pickle_double_buffered::from_string
  {
    using scitbx::af::boost_python::pickle_double_buffered::from_string::operator>>;

    from_string(const char* str_ptr)
    : scitbx::af::boost_python::pickle_double_buffered::from_string(str_ptr) {
      *this >> version;
      DIALS_ASSERT(version == 1);
    }

    template <typename ProfileType>
    ProfileType profile_from_string() {
      typename ProfileType::index_type shape;
      typename ProfileType::size_type n_dim;
      *this >> n_dim;
      shape.resize(n_dim);
      for (std::size_t i = 0; i < n_dim; ++i) {
        *this >> shape[i];
      }
      ProfileType p = ProfileType(flex_grid<>(shape));
      for (std::size_t i = 0; i < p.size(); ++i) {
        *this >> p[i];
      }
      return p;
    }

    from_string& operator>>(Reflection& val) {
      *this >> val.miller_index_[0]
            >> val.miller_index_[1]
            >> val.miller_index_[2]
            >> val.status_
            >> val.entering_
            >> val.rotation_angle_
            >> val.beam_vector_[0]
            >> val.beam_vector_[1]
            >> val.beam_vector_[2]
            >> val.image_coord_px_[0]
            >> val.image_coord_px_[1]
            >> val.image_coord_mm_[0]
            >> val.image_coord_mm_[1]
            >> val.frame_number_
            >> val.panel_number_
            >> val.bounding_box_[0]
            >> val.bounding_box_[1]
            >> val.bounding_box_[2]
            >> val.bounding_box_[3]
            >> val.bounding_box_[4]
            >> val.bounding_box_[5]
            >> val.centroid_position_[0]
            >> val.centroid_position_[1]
            >> val.centroid_position_[2]
            >> val.centroid_variance_[0]
            >> val.centroid_variance_[1]
            >> val.centroid_variance_[2]
            >> val.centroid_sq_width_[0]
            >> val.centroid_sq_width_[1]
            >> val.centroid_sq_width_[2]
            >> val.intensity_
            >> val.intensity_variance_
            >> val.corrected_intensity_
            >> val.corrected_intensity_variance_;

      val.shoebox_ = profile_from_string<flex_double>();
      val.shoebox_mask_ = profile_from_string<flex_int>();
      val.shoebox_background_ = profile_from_string<flex_double>();
      val.transformed_shoebox_ = profile_from_string<flex_double>();
      return *this;
    }

    unsigned int version;
  };

  struct ReflectionPickleSuite : boost::python::pickle_suite {

    static
    boost::python::tuple getstate(const Reflection &r) {
      to_string buf;
      buf << r;
      return boost::python::make_tuple(buf.buffer);
    }

    static
    void setstate(Reflection &r, boost::python::tuple state) {
      DIALS_ASSERT(boost::python::len(state) == 1);
      PyObject* py_str = boost::python::object(state[0]).ptr();
      from_string buf(PyString_AsString(py_str));
      buf >> r;
    }
  };

}}}} // namespace dials::model::boost_python::reflection

#endif /* DIALS_MODEL_DATA_BOOST_PYTHON_PICKLE_H */
