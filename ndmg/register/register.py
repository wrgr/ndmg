#!/usr/bin/env python

# Copyright 2016 NeuroData (http://neurodata.io)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# register.py
# Created by Greg Kiar on 2016-01-28.
# Email: gkiar@jhu.edu

from subprocess import Popen, PIPE
import os.path as op
import ndmg.utils as ndu
import nibabel as nb
import numpy as np
import nilearn.image as nl


class register(object):

    def __init__(self):
        """
        Enables registration of single images to one another as well as volumes
        within multi-volume image stacks. Has options to compute transforms,
        apply transforms, as well as a built-in method for aligning low
        resolution mri images to a high resolution atlas.
        """
        pass

    def align(self, inp, ref, xfm):
        """
        Aligns two images and stores the transform between them

        **Positional Arguments:**

                inp:
                    - Input impage to be aligned as a nifti image file
                ref:
                    - Image being aligned to as a nifti image file
                xfm:
                    - Returned transform between two images
        """
        cmd = "flirt -in " + inp + " -ref " + ref + " -omat " + xfm +\
              " -cost mutualinfo -bins 256 -dof 12 -searchrx -180 180" +\
              " -searchry -180 180 -searchrz -180 180"
        print "Executing: " + cmd
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        p.communicate()
        pass

    def applyxfm(self, inp, ref, xfm, aligned):
        """
        Aligns two images with a given transform

        **Positional Arguments:**

                inp:
                    - Input impage to be aligned as a nifti image file
                ref:
                    - Image being aligned to as a nifti image file
                xfm:
                    - Transform between two images
                aligned:
                    - Aligned output image as a nifti image file
        """
        cmd = "flirt -in " + inp + " -ref " + ref + " -out " + aligned +\
              " -init " + xfm + " -interp trilinear -applyxfm"

        print "Executing: " + cmd
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        p.communicate()
        pass

    def align_slices(self, mri, corrected_mri, idx, opt):
        """
        Performs eddy-correction (or self-alignment) of a stack of 3D images

        **Positional Arguments:**
                mri:
                    - 4D (DTI) image volume as a nifti file
                corrected_mri:
                    - Corrected and aligned DTI volume in a nifti file
                idx:
                    - Index of the volume to align to in the stack. for DTI,
                      this corresponds to the B0 volume.
                opt: 
                    - 'f': for fMRI
                    - 'd': for DTI
        """
        if (opt == 'f'):
            cmd = "mcflirt -in " + mri + " -out " + corrected_mri +
                " -plots -refvol " + str(idx)
            print "Executing: " + cmd
            p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
            p.communicate()
        else:
            cmd = "eddy_correct " + mri + " " + corrected_mri + " " + str(idx)
            print "Executing: " + cmd
            p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
            p.communicate()
        pass

    def resample(self, base, ingested, template):
        """
        Resamples the image such that images which have already been aligned
        in real coordinates also overlap in the image/voxel space.

        **Positional Arguments**
                base:
                    - Image to be aligned
                ingested:
                    - Name of image after alignment
                template:
                    - Image that is the target of the alignment
        """
        # Loads images
        template_im = nb.load(template)
        base_im = nb.load(base)
        # Aligns images
        target_im = nl.resample_img(base_im,
                                    target_affine=template_im.get_affine(),
                                    target_shape=template_im.get_data().shape,
                                    interpolation="nearest")
        # Saves new image
        nb.save(target_im, ingested)
        pass

    def mri2atlas(self, mri, gtab, mprage, atlas, aligned_mri, outdir):
        """
        Aligns two images and stores the transform between them

        **Positional Arguments:**

                mri:
                    - Input impage to be aligned as a nifti image file
                bvals:
                    - File containing list of bvalues for each scan
                bvecs:
                    - File containing gradient directions for each scan
                mprage:
                    - Intermediate image being aligned to as a nifti image file
                atlas:
                    - Terminal image being aligned to as a nifti image file
                aligned_mri:
                    - Aligned output mri image as a nifti image file
        """
        # Creates names for all intermediate files used
        # GK TODO: come up with smarter way to create these temp file names
        mri_name = op.splitext(op.splitext(op.basename(mri))[0])[0]
        mprage_name = op.splitext(op.splitext(op.basename(mprage))[0])[0]
        atlas_name = op.splitext(op.splitext(op.basename(atlas))[0])[0]

        mri2 = outdir + "/tmp/" + mri_name + "_t2.nii.gz"
        temp_aligned = outdir + "/tmp/" + mri_name + "_ta.nii.gz"
        b0 = outdir + "/tmp/" + mri_name + "_b0.nii.gz"
        xfm1 = outdir + "/tmp/" + mri_name + "_" + mprage_name + "_xfm.mat"
        xfm2 = outdir + "/tmp/" + mprage_name + "_" + atlas_name + "_xfm.mat"
        xfm3 = outdir + "/tmp/" + mri_name + "_" + atlas_name + "_xfm.mat"

        # Align DTI volumes to each other
        self.align_slices(mri, mri2, np.where(gtab.b0s_mask)[0])

        # Loads DTI image in as data and extracts B0 volume
        import ndmg.utils as mgu
        mri_im = nb.load(mri2)
        b0_im = mgu().get_b0(gtab, mri_im.get_data())
        # GK TODO: why doesn't top import work?

        # Wraps B0 volume in new nifti image
        b0_head = mri_im.get_header()
        b0_head.set_data_shape(b0_head.get_data_shape()[0:3])
        b0_out = nb.Nifti1Image(b0_im, affine=mri_im.get_affine(),
                                header=b0_head)
        b0_out.update_header()
        nb.save(b0_out, b0)

        # Algins B0 volume to MPRAGE, and MPRAGE to Atlas
        self.align(b0, mprage, xfm1)
        self.align(mprage, atlas, xfm2)

        # Combines transforms from previous registrations in proper order
        cmd = "convert_xfm -omat " + xfm3 + " -concat " + xfm2 + " " + xfm1
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        p.communicate()

        # Applies combined transform to mri image volume
        self.applyxfm(mri2, atlas, xfm3, temp_aligned)
        self.resample(temp_aligned, aligned_mri, atlas)

        # Clean temp files
        cmd = "rm -f " + mri2 + " " + temp_aligned + " " + b0 + " " +\
              xfm1 + " " + xfm2 + " " + xfm3
        print "Cleaning temporary registration files..."
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        p.communicate()
