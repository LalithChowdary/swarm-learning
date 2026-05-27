#######################################################################
## (C)Copyright 2021-25 Hewlett Packard Enterprise Development LP
## Licensed under the Apache License, Version 2.0 (the "License"); you may
## not use this file except in compliance with the License. You may obtain
## a copy of the License at
##
##    http://www.apache.org/licenses/LICENSE-2.0
##
## Unless required by applicable law or agreed to in writing, software
## distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
## WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
## License for the specific language governing permissions and limitations
## under the License.
#######################################################################


##################################################################
# This file is the main entry point for Swarm Learning for
# Scikit-Learn platform. Users can integrate Swarm framework into
# their model code by creating an instance of the SwarmCallback
# class and calling its methods at different phases of training.
#
# Unlike deep learning frameworks, Scikit-Learn has no native
# callback mechanism. Users must write a manual training loop
# using partial_fit() and invoke callback methods explicitly:
#
#   swCb.on_train_begin()
#   for epoch in range(epochs):
#       for X_batch, y_batch in batches:
#           model.partial_fit(X_batch, y_batch)
#           swCb.on_batch_end()
#       swCb.on_epoch_end(epoch)
#   swCb.on_train_end()
##################################################################

from __future__ import print_function

import numpy as np
import sklearn.metrics as skmetrics
from swarmlearning.client.swarm import SwarmCallbackBase, SLPlatforms

# Default Training contract used for learning if not specified by user.
# Any update to default contract needs similar modifications
# in all applicable ML platforms (TF, PYT, etc)
DEFAULT_TRAINING_CONTRACT = 'defaultbb.cqdb.sml.hpe'

# Registry mapping Scikit-Learn model class names to the attribute
# names that hold their trainable weights. Models with list-of-arrays
# parameters (e.g., MLPClassifier stores coefs_ as a list of ndarrays)
# are flagged with 'is_list': True so the serialisation layer can
# flatten and reconstruct them correctly.
_SKLEARN_WEIGHT_REGISTRY = {
    'SGDClassifier':               {'weights': ['coef_', 'intercept_']},
    'SGDRegressor':                {'weights': ['coef_', 'intercept_']},
    'Perceptron':                  {'weights': ['coef_', 'intercept_']},
    'PassiveAggressiveClassifier': {'weights': ['coef_', 'intercept_']},
    'PassiveAggressiveRegressor':  {'weights': ['coef_', 'intercept_']},
    'MLPClassifier':               {'weights': ['coefs_', 'intercepts_'], 'is_list': True},
    'MLPRegressor':                {'weights': ['coefs_', 'intercepts_'], 'is_list': True},
    'MiniBatchKMeans':             {'weights': ['cluster_centers_']},
}


class SwarmCallback(SwarmCallbackBase):
    '''
    This is the customized callback class sub-classed from
    SwarmCallbackBase class that implements different swarm
    functionalities for Scikit-Learn models.

    Scikit-Learn models do NOT have a native callback mechanism.
    Users must write a manual training loop using partial_fit()
    and call on_train_begin / on_batch_end / on_epoch_end /
    on_train_end explicitly (Approach 1 - Direct Callback).

    Key design decisions:
      - Lazy weight init: Scikit-Learn model attributes (coef_,
        intercept_, etc.) do not exist until the first partial_fit()
        call. We handle this by accepting 'initData' and running
        a dummy partial_fit() during construction.
      - Weight injection: There is no official load_state_dict()
        equivalent, so we use setattr() to overwrite model
        attributes directly.
    '''

    # Scikit-Learn context - mirrors the pattern used by
    # _KerasContext and pyTorchContext in tf.py / pyt.py
    class _SklearnContext:
        def __init__(self, model):
            self.model = model


    def __init__(self, syncFrequency, minPeers,
                 trainingContract=DEFAULT_TRAINING_CONTRACT, **kwargs):
        '''
        This function initializes the various Swarm network parameters, which
        are described below -
        :param syncFrequency: Batches of local training to be performed between
                              2 swarm sync rounds. If adaptive sync enabled, this
                              is the frequency to be used at the start.
        :param minPeers: Min peers required during each sync round for Swarm to
                          proceed further.
        :param trainingContract: Training contract associated with this learning.
                                 Default value is 'defaultbb.cqdb.sml.hpe'.
        :param useAdaptiveSync: Modulate the next interval length post each sync
                                  round based on perf on validation data.
        :param adsValData: Validation dataset - (X,Y) tuple used for adaptive sync
        :param adsValBatch_size: Validation data batch size (not used for sklearn,
                                 kept for interface consistency)
        :param checkinModelOnTrainEnd: Indicates which model to check-in once
                                           local model training ends at a node.
                                           Allowed values: ['inactive', 'snapshot',
                                           'active']
        :param mergeMethod: Indicates the type of merge technique used for swarm merge.
        :param nodeWeightage: A number between 1-100 to indicate the relative
                               importance of this node compared to others
        :param model: Scikit-Learn model instance (must support partial_fit)
        :param initData: Tuple (X_sample, y_sample) used to run a dummy
                         partial_fit() to lazily allocate model weights before
                         the first swarm sync.
        :param classes: Array of all possible class labels. Required for
                        classifiers so partial_fit() knows the full label set
                        on the very first call.
        :param weight_attrs: Optional list of attribute name strings for custom
                             models not in _SKLEARN_WEIGHT_REGISTRY.
        :param lossFunction: Name of an sklearn.metrics function to compute loss
                             (e.g., 'log_loss', 'hinge_loss').
        :param metricFunction: Name of an sklearn.metrics function to compute
                               metrics (e.g., 'accuracy_score', 'roc_auc_score').
        :param metricFunctionArgs: Dict of extra keyword arguments passed to
                                   the metricFunction.
        :param logger: Basic Python logger.
        :param totalEpochs: Total epochs used in local training.
        '''
        SwarmCallbackBase.__init__(self, syncFrequency, minPeers,
                                   trainingContract, kwargs)
        self._verifyAndSetPlatformContext(kwargs)
        self._swarmInitialize()

        # Optional loss and metric functions for validation / UI display
        self.lossFunction = kwargs.get('lossFunction', None)
        self.metricFunction = kwargs.get('metricFunction', None)
        self.metricFunctionArgs = kwargs.get('metricFunctionArgs', {})

        if self.valData is None:
            self.logger.info("=============================================================")
            self.logger.info("WARNING: adsValData is not available to compute Loss and metrics")
            self.logger.info("=============================================================")


    # ------------------------------------------------------------------ #
    #  Lifecycle hooks - called explicitly by the user in their loop      #
    # ------------------------------------------------------------------ #

    def on_train_begin(self):
        '''
        Scikit-Learn specific on_train_begin implementation.
        Triggers the initial swarm sync so all peers start from the
        same merged weights.
        '''
        self._swarmOnTrainBegin()


    def on_batch_end(self, batch=None):
        '''
        Scikit-Learn specific on_batch_end implementation.
        Should be called after each model.partial_fit() call.
        '''
        self._swarmOnBatchEnd()


    def on_epoch_end(self, epoch=None):
        '''
        Scikit-Learn specific on_epoch_end implementation.
        Should be called at the end of each epoch.
        '''
        self._swarmOnEpochEnd()


    def on_train_end(self):
        '''
        Scikit-Learn specific on_train_end implementation.
        Triggers final merge and model check-in to Swarm network.
        '''
        self._swarmOnTrainEnd()


    # ------------------------------------------------------------------ #
    #  Abstract method implementations                                    #
    # ------------------------------------------------------------------ #

    def _verifyAndSetPlatformContext(self, params):
        '''
        Scikit-Learn specific implementation of abstract method
        _verifyAndSetPlatformContext in SwarmCallbackBase class.

        Responsibilities:
          1. Set mlPlatform to SKLEARN.
          2. Validate that a model was provided.
          3. Lazily initialise model weights via a dummy partial_fit()
             if the model has not been fitted yet (coef_ etc. missing).
          4. Look up or accept a weight attribute configuration.
          5. Wrap the model in a _SklearnContext.
        '''
        # --- Platform ---
        ml_platform = params.get('ml_platform', SLPlatforms.SKLEARN.name)
        if ml_platform != SLPlatforms.SKLEARN.name:
            self._logAndRaiseError("Invalid ml platform type: %s" % ml_platform)
        self.mlPlatform = SLPlatforms[ml_platform]

        # --- Model ---
        self.model = params.get('model', None)
        if self.model is None:
            self._logAndRaiseError("Scikit-Learn model is None")

        # --- Lazy weight initialization ---
        # Check if the model already has fitted weight attributes
        has_weights = any(
            hasattr(self.model, attr)
            for attr in ['coef_', 'coefs_', 'cluster_centers_']
        )
        if not has_weights:
            initData = params.get('initData', None)
            classes = params.get('classes', None)
            if initData is None:
                self._logAndRaiseError(
                    "Model weights are not initialized. "
                    "Provide 'initData=(X_sample, y_sample)' so a dummy "
                    "partial_fit() can allocate them before the first sync."
                )
            X_init, y_init = initData
            self.logger.info("Running dummy partial_fit() to allocate model weights ...")
            if classes is not None:
                self.model.partial_fit(X_init, y_init, classes=classes)
            else:
                self.model.partial_fit(X_init, y_init)
            self.logger.info("Dummy partial_fit() completed. Weights allocated.")

        # --- Weight config lookup ---
        model_name = type(self.model).__name__
        self._weightConfig = _SKLEARN_WEIGHT_REGISTRY.get(model_name, None)
        if self._weightConfig is None:
            # Allow user-supplied custom attribute list
            custom_attrs = params.get('weight_attrs', None)
            if custom_attrs:
                self._weightConfig = {'weights': custom_attrs}
            else:
                self._logAndRaiseError(
                    "Model '%s' not found in weight registry and no "
                    "'weight_attrs' provided." % model_name
                )

        # --- Context ---
        self.mlCtx = SwarmCallback._SklearnContext(self.model)
        self.logger.debug("Initialized Scikit-Learn context for Swarm")

        # hfMode is not applicable for Scikit-Learn
        self.hfMode = None


    def _getValidationDataForAdaptiveSync(self, valData, valBatchSize):
        '''
        Scikit-Learn specific implementation of abstract method
        _getValidationDataForAdaptiveSync in SwarmCallbackBase class.

        For Scikit-Learn we only support (X, Y) tuple validation data.
        '''
        valGen = valSteps = valX = valY = valSampleWeight = None
        if valData is not None and isinstance(valData, tuple) and len(valData) == 2:
            valX, valY = valData
        return valGen, valSteps, valX, valY, valSampleWeight


    def _saveModelWeightsToDict(self):
        '''
        Scikit-Learn specific implementation of abstract method
        _saveModelWeightsToDict in SwarmCallbackBase class.

        Extracts model weight attributes into a flat dictionary.
        For models with list-of-arrays parameters (e.g., MLP), each
        array in the list is stored under a separate key with an
        index suffix (e.g., coefs__0, coefs__1).
        '''
        paramsDict = {}
        self.weightNames = []
        model = self.mlCtx.model
        is_list = self._weightConfig.get('is_list', False)

        for attr in self._weightConfig['weights']:
            val = getattr(model, attr)
            if is_list and isinstance(val, list):
                # Flatten list-of-arrays into individual keyed entries
                for i, arr in enumerate(val):
                    key = "%s_%d" % (attr, i)
                    paramsDict[key] = np.array(arr, dtype=np.float64)
                    self.weightNames.append(key)
            else:
                paramsDict[attr] = np.array(val, dtype=np.float64)
                self.weightNames.append(attr)
        return paramsDict


    def _loadModelWeightsFromDict(self, paramsDict):
        '''
        Scikit-Learn specific implementation of abstract method
        _loadModelWeightsFromDict in SwarmCallbackBase class.

        Injects merged weights back into the model by overwriting
        the appropriate attributes using setattr().
        '''
        model = self.mlCtx.model
        is_list = self._weightConfig.get('is_list', False)

        if is_list:
            for attr in self._weightConfig['weights']:
                # Reconstruct the list of arrays from the flat keys
                keys = sorted(
                    [k for k in self.weightNames if k.startswith(attr + '_')],
                    key=lambda x: int(x.rsplit('_', 1)[-1])
                )
                reconstructed = [paramsDict[k] for k in keys]
                setattr(model, attr, reconstructed)
        else:
            for attr in self._weightConfig['weights']:
                setattr(model, attr, paramsDict[attr])


    def _calculateLocalLossAndMetrics(self):
        '''
        Scikit-Learn specific implementation of abstract method
        _calculateLocalLossAndMetrics in SwarmCallbackBase class.

        TODO: Implement loss and metrics computation using
        sklearn.metrics functions. Not needed for on_train_begin().
        '''
        valLoss = 0
        totalMetrics = 0
        return valLoss, totalMetrics
