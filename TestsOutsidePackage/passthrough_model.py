#  ------------------------------------------------------------------------------------------
#  Copyright (c) Microsoft Corporation. All rights reserved.
#  Licensed under the MIT License (MIT). See LICENSE in the repo root for license information.
#  ------------------------------------------------------------------------------------------
import random
from typing import Any, List
import numpy as np
import torch
from torch.nn.parameter import Parameter

from InnerEye.Common.fixed_paths_for_tests import full_ml_test_data_path
from InnerEye.Common.type_annotations import TupleInt3
from InnerEye.ML.config import equally_weighted_classes, SegmentationModelBase
from InnerEye.ML.models.architectures.base_model import BaseSegmentationModel
from InnerEye.ML.utils.model_metadata_util import generate_random_colours_list


RANDOM_COLOUR_GENERATOR = random.Random(0)


class PassThroughModel(SegmentationModelBase):
    """
    Dummy model that returns a fixed segmentation, explained in make_nesting_rectangles.
    """
    def __init__(self, **kwargs: Any) -> None:
        random_seed = 42
        number_of_image_channels = 1
        number_of_classes = 5
        class_names = [f"structure_{i}" for i in range(number_of_classes)]

        super().__init__(
            should_validate=False,
            random_seed=random_seed,
            local_dataset=full_ml_test_data_path(),
            crop_size=(64, 192, 160),
            # This speeds up loading dramatically. Multi-process data loading is tested via BasicModel2Epochs
            num_dataload_workers=0,
            # Disable monitoring so that we can use VS Code remote debugging
            monitoring_interval_seconds=0,
            image_channels=[f"image_{i}" for i in range(number_of_image_channels)],
            ground_truth_ids=class_names,
            ground_truth_ids_display_names=class_names,
            colours=generate_random_colours_list(RANDOM_COLOUR_GENERATOR, number_of_classes),
            fill_holes=[False] * number_of_classes,
            # mask_id="mask",
            dataset_expected_spacing_xyz=(1.269531011581421, 1.269531011581421, 2.5),
            inference_batch_size=1,
            class_weights=equally_weighted_classes(class_names),
            feature_channels=[1]
        )
        self.add_and_validate(kwargs)

    def create_model(self) -> torch.nn.Module:
        return PyTorchPassthroughModel(self.number_of_image_channels, self.number_of_classes,
                                       self.crop_size)


class PyTorchPassthroughModel(BaseSegmentationModel):
    """
    Defines a model that returns a fixed segmentation, explained in make_nesting_rectangles.
    """

    def __init__(self, input_channels: int, number_of_classes: int, crop_size: TupleInt3):
        """
        Creates a new instance of the class.

        :param input_channels: Number of image channels.
        :param number_of_classes: Number of segmentation classes.
        :param crop_size: Crop size.
        """
        super().__init__(input_channels=input_channels, name='PassthroughModel')
        # Create a fake parameter so that we can instantiate an optimizer easily
        self.foo = Parameter(requires_grad=True)
        self.number_of_classes = number_of_classes
        # Cache the fixed segmentation.
        self.cached_patch = self.make_nest(crop_size)

    def forward(self, patches: torch.Tensor) -> torch.Tensor:
        """
        Ignore the actual patches and return a fixed segmentation, explained in make_nesting_rectangles.

        :param patches: Set of patches, of shape (#patches, #image_channels, Z, Y, X). Only the shape
        is used.
        :return: Fixed tensor of shape (#patches, number_of_classes, Z, Y, Z).
        """
        if self.cached_patch.shape[2:] == patches.shape[2:]:
            patch = self.cached_patch
        else:
            patch = self.make_nest((patches.shape[2], patches.shape[3], patches.shape[4]))
        if patches.shape[0] == 1:
            np_predictions = patch
        else:
            np_predictions = np.broadcast_to(patch, (patches.shape[0],) + patch.shape[1:])
        return torch.from_numpy(np_predictions)

    def get_all_child_layers(self) -> List[torch.nn.Module]:
        return list()

    def make_nest(self, output_size: TupleInt3) -> np.ndarray:
        """
        Given a patch shaped (Z, Y, X) return a fixed segmentation shaped to (1, number_of_classes, Z, Y, X).

        :param output_size: Target output size.
        :return: 5d tensor.
        """
        nest = make_nesting_rectangles(self.number_of_classes, output_size[1], output_size[2], 3)
        project_nest = nest.reshape(1, self.number_of_classes, 1, output_size[1], output_size[2])
        return np.broadcast_to(project_nest, (1, self.number_of_classes) + output_size)


def make_distance_range(length: int) -> np.ndarray:
    """
    Create a numpy array of np.float32 of shape (length,) where each item is the distance from the centre.

    If length is odd, then let hl=(length-1)/2, then the result is:
    [hl, hl-1,..., 1, 0, 1, ... hl-1, hl]
    If length is even, then let hl=(length/2)-1, then the result is:
    [hl, hl-1,..., 1, 0, 0, 1, ... hl-1, hl]
    More concretely:
    For length=7, then the result is [3., 2., 1., 0., 1., 2., 3.]
    For length=8, then the result is [3., 2., 1., 0., 0., 1., 2., 3.]

    :param length: Size of array to return.
    :return: Array of distances from the centre.
    """
    return abs(np.arange(1 - length, length + 1, 2, dtype=np.float32)) // 2


def make_stroke_rectangle(dim0: int, dim1: int, half_side: int, thickness: int) -> np.ndarray:
    """
    Create a stroked rectangle within a rectangle.

    Create a numpy array of np.float32 of shape (dim0, dim1), that is 0. except for an unfilled
    rectangle of 1.'s centred about the centre of the array.

    For example, with dim0=5, dim1=8, half_side=2, thickness=1, this will produce this array:
    array([[0., 0., 0., 0., 0., 0., 0., 0.],
           [0., 0., 1., 1., 1., 1., 0., 0.],
           [0., 0., 1., 0., 0., 1., 0., 0.],
           [0., 0., 1., 1., 1., 1., 0., 0.],
           [0., 0., 0., 0., 0., 0., 0., 0.]], dtype=float32)

    :param dim0: Target array dim0.
    :param dim1: Target array dim1.
    :param half_side: Inner rectangle approximate half side length.
    :param thickness: Stroke thickness.
    :return: np.ndarray mostly 0s apart from the stroked path of a rectangle.
    """
    x1 = make_distance_range(dim0)
    x2 = make_distance_range(dim1)
    X1, X2 = np.meshgrid(x1, x2, sparse=False, indexing='ij')
    bool_array = (((half_side - thickness <= X1) & (X1 < half_side) & (X2 < half_side))
                  | ((X1 < half_side) & (half_side - thickness <= X2) & (X2 < half_side))) * 1
    return bool_array.astype(np.float32)


def make_fill_rectangle(dim0: int, dim1: int, half_side: int) -> np.ndarray:
    """
    Create a filled rectangle within a rectangle.

    Create a numpy array of np.float32 of shape (dim0, dim1) that is 0. except for a filled
    foreground rectangle of 1.'s centred about the centre of the array.
    If dim0 is odd then the length in axis 0 will be 2*half_side - 1, otherwise it will be
        length 2*half_side.
    Similarly for dim1.

    For example, with dim0=5, dim1=8, half_side=2, this will produce this array:
    array([[0., 0., 0., 0., 0., 0., 0., 0.],
           [0., 0., 1., 1., 1., 1., 0., 0.],
           [0., 0., 1., 1., 1., 1., 0., 0.],
           [0., 0., 1., 1., 1., 1., 0., 0.],
           [0., 0., 0., 0., 0., 0., 0., 0.]], dtype=float32)

    :param dim0: Target array dim0.
    :param dim1: Target array dim1.
    :param half_side: Inner rectangle approximate half side length.
    :return: np.ndarray mostly 0s apart from the filled path of a rectangle.
    """
    x1 = make_distance_range(dim0)
    x2 = make_distance_range(dim1)
    X1, X2 = np.meshgrid(x1, x2, sparse=False, indexing='ij')
    bool_array = ((X1 < half_side) & (X2 < half_side))
    return bool_array.astype(np.float32)


def make_nesting_rectangles(dim0: int, dim1: int, dim2: int, thickness: int) -> np.ndarray:
    """
    Create an np.ndarray of np.float32 of shape (dim0, dim1, dim2) of nesting rectangles.

    The first slice is intended to be a background so is an inverted filled rectangle.
    The remaining slices are consecutively larger stroked rectangles, none overlapping.

    For example, with dim0=3, dim1=5, dim2=8, half_side=2, thickness=1 this will produce an
    array of shape (3, 5, 8) where:
    slice 0 =
    array([[1., 1., 1., 1., 1., 1., 1., 1.],
           [1., 1., 0., 0., 0., 0., 1., 1.],
           [1., 1., 0., 0., 0., 0., 1., 1.],
           [1., 1., 0., 0., 0., 0., 1., 1.],
           [1., 1., 1., 1., 1., 1., 1., 1.]], dtype=float32)
    slice 1 =
    array([[0., 0., 0., 0., 0., 0., 0., 0.],
           [0., 0., 0., 0., 0., 0., 0., 0.],
           [0., 0., 0., 1., 1., 0., 0., 0.],
           [0., 0., 0., 0., 0., 0., 0., 0.],
           [0., 0., 0., 0., 0., 0., 0., 0.]], dtype=float32)
    slice 2 =
    array([[0., 0., 0., 0., 0., 0., 0., 0.],
           [0., 0., 1., 1., 1., 1., 0., 0.],
           [0., 0., 1., 0., 0., 1., 0., 0.],
           [0., 0., 1., 1., 1., 1., 0., 0.],
           [0., 0., 0., 0., 0., 0., 0., 0.]], dtype=float32)

    :param dim0: Target array dim0.
    :param dim1: Target array dim1.
    :param dim2: Target array dim2.
    :param thickness: Stroke thickness.
    :return: np.ndarray of background then a set of rectangles.
    """
    nesting = np.empty((dim0, dim1, dim2), dtype=np.float32)
    nesting[0] = 1. - make_fill_rectangle(dim1, dim2, (dim0 - 1) * thickness)
    for feature in range(1, dim0):
        nesting[feature] = make_stroke_rectangle(dim1, dim2, feature * thickness, thickness)
    return nesting
