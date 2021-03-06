""" Test to check that the defined architecture works and that we can quantize
regression datasets and convert them into classification problems, we use a
very simple dataset such as Boston Housing UCI """

from protodata.datasets.scikit_dataset import BostonSettings
from protodata.datasets import Datasets
from protodata.utils import get_data_location
from protodata.data_ops import TrainMode, DataMode
from protodata.quantize import Quantize

from widedeep.model.model_base import LinearModel, MLP
from widedeep.model.joint_model import JointClassifier
from widedeep.ops.losses import Optimizers, CrossEntropy
import widedeep.utils as utils
import widedeep.ops.metrics as metrics

import tensorflow as tf

logger = utils.get_logger('data')


flags = tf.app.flags
FLAGS = flags.FLAGS


flags.DEFINE_string(
    "data_location",
    get_data_location(Datasets.BOSTON),
    "Where data is stored"
)

flags.DEFINE_integer(
    "batch_size",
    32,
    "Batch size to use."
)

flags.DEFINE_string(
    "network",
    utils.NetworkModels.MLP,
    "Network to use for MLP, if used"
)

flags.DEFINE_integer(
    "summaries",
    50,
    "Steps between summaries."
)

flags.DEFINE_integer(
    "checkpoints",
    100,
    "Steps between model checkpoints."
)

flags.DEFINE_integer(
    "steps",
    5000,
    "Steps to train."
)

flags.DEFINE_float(
    "gpu_frac",
    0.70,
    "Percentage of GPU memory to use."
)

# High levels of gpu_frac can lead to Error:
# failed to create cublas handle: CUBLAS_STATUS_NOT_INITIALIZED
flags.DEFINE_string(
    "mode",
    TrainMode.DEEP,
    "Architecture to use"
)

flags.DEFINE_bool(
    "training",
    False,
    "Execution mode"
)

# Regularization
flags.DEFINE_float(
    "l1_regularization",
    None,
    "L1 regularization for the loss. Set to None to disable"
)

flags.DEFINE_float(
    "l2_regularization",
    None,
    "L2 regularization for the loss. Set to None to disable"
)

# Gradient
flags.DEFINE_float(
    "gradient_clip",
    None,
    "If not None, value to use for clipping the gradient"
)

# Linear parameters
flags.DEFINE_float(
    "linear_initial_lr",
    0.01,
    "Initial learning rate for the linear model."
)

flags.DEFINE_integer(
    "linear_decay_steps",
    None,
    "Steps at which learning rate decreases for the linear model."
)

flags.DEFINE_float(
    "linear_decay_rate",
    None,
    "Decrease rate of the learning rate for the linear model."
)

# MLP parameters
flags.DEFINE_float(
    "mlp_initial_lr",
    0.01,
    "Initial learning rate for the MLP model."
)

flags.DEFINE_integer(
    "mlp_decay_steps",
    10000,
    "Steps at which learning rate decreases for the MLP model."
)

flags.DEFINE_float(
    "mlp_decay_rate",
    0.5,
    "Decrease rate of the learning rate for the MLP model."
)

flags.DEFINE_string(
    "mlp_network",
    utils.NetworkModels.MLP,
    "Network to use for the MLP"
)

if __name__ == '__main__':

    # Select Airbnb dataset
    dataset = BostonSettings(
        dataset_location=FLAGS.data_location,
        quantizer=Quantize(edges=[20, 40, 60],
                           batch_size=FLAGS.batch_size)
    )

    # Define columns
    wide = dataset.get_wide_columns()
    logger.info('Using columns {}'.format(wide))

    # Create linear model
    linear_model = LinearModel('linear',
                               columns_list=wide,
                               optimizer=Optimizers.SGD,
                               initial_lr=FLAGS.linear_initial_lr,
                               decay_steps=FLAGS.linear_decay_steps,
                               decay_rate=FLAGS.linear_decay_rate)

    # Create deep model
    mlp_model = MLP('mlp',
                    columns_list=wide,
                    layers=utils.get_network_definition(FLAGS.mlp_network),
                    optimizer=Optimizers.SGD,
                    initial_lr=FLAGS.mlp_initial_lr,
                    decay_steps=FLAGS.mlp_decay_steps,
                    decay_rate=FLAGS.mlp_decay_rate)

    # Set models according to settings
    if FLAGS.mode == TrainMode.WIDE:
        models = [linear_model]
    elif FLAGS.mode == TrainMode.DEEP:
        models = [mlp_model]
    elif FLAGS.mode == TrainMode.WIDE_AND_DEEP:
        models = [linear_model, mlp_model]
    else:
        raise ValueError('Unsupported option in Boston training %s' 
                         % FLAGS.mode)

    # Create model
    joint = JointClassifier(utils.get_default_output(),
                            outputs=dataset.get_num_classes(),
                            models=models,
                            l1_reg=FLAGS.l1_regularization,
                            l2_reg=FLAGS.l2_regularization,
                            loss_fn=CrossEntropy(),
                            clip_gradient=FLAGS.gradient_clip)

    # Define metrics
    model_metrics = [
        metrics.Accuracy(),
        metrics.AccuracyRandom(dataset.get_num_classes()),
        metrics.AccuracyMode(dataset.get_num_classes())
    ]

    if FLAGS.training:
        # Start training
        joint.train(dataset,
                    batch_size=FLAGS.batch_size,
                    track_models=FLAGS.checkpoints,
                    track_summaries=FLAGS.summaries,
                    steps=FLAGS.steps,
                    gpu_frac=FLAGS.gpu_frac,
                    metrics=model_metrics)
    else:
        # Evaluate on test
        results = joint.evaluate(dataset,
                                 batch_size=FLAGS.batch_size,
                                 data_mode=DataMode.TEST,
                                 track_summaries=FLAGS.summaries,
                                 gpu_frac=FLAGS.gpu_frac,
                                 metrics=model_metrics)
        logger.info(results)
